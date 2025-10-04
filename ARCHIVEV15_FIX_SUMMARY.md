# Archivev15 Fix Summary: Inline Checkbox Options

## Problem Statement

The PDF to JSON conversion script was failing to capture important opt-in preference fields that appeared as inline checkboxes after field labels in the Chicago Dental Solutions form.

### Examples of Missing Fields

```
Cell Phone:                         [ ] Yes, send me Text Message alerts
E-mail Address:                                                  [ ] Yes, send me alerts via Email
```

**Before Fix:**
- Only "Cell Phone" input field was captured
- Only "E-mail Address" input field was captured
- The checkbox options were completely missing from the JSON

**After Fix:**
- "Cell Phone" input field
- "Yes, send me Text Message alerts" radio field (opt-in)
- "E-mail Address" input field  
- "Yes, send me alerts via Email" radio field (opt-in)

## Root Causes

### 1. Incorrect Line Splitting

The `try_split_known_labels()` function was finding the word "Email" in the checkbox text and treating it as a separate field, splitting the line incorrectly:

```
Original: "E-mail Address:  [ ] Yes, send me alerts via Email"
Split to: ["E-mail Address:  [ ] Yes, send me alerts via", "Email"]
```

### 2. Missing Pattern Detection

There was no logic to detect the specific pattern of a field label followed by wide spacing and an inline checkbox option.

### 3. Template Matching Conflicts

The template matching system was changing keys of the new opt-in fields, causing them to be removed as duplicates during post-processing.

## Solution

### 1. Created Detection Function

Added `detect_field_with_inline_checkbox()` function to identify the pattern:

```python
def detect_field_with_inline_checkbox(line: str) -> Optional[Tuple[str, str]]:
    """
    Pattern: "Field Label:    <spaces>    [ ] Option text"
    Returns: (field_label, checkbox_option) if detected, None otherwise
    """
    pattern = r'^(.+?):\s{5,}' + CHECKBOX_ANY + r'\s+(.+)$'
    match = re.match(pattern, line.strip())
    
    if match:
        field_label = match.group(1).strip()
        checkbox_text = match.group(2).strip()
        
        if len(field_label) <= 50 and len(checkbox_text) >= 5:
            return (field_label, checkbox_text)
    
    return None
```

### 2. Integrated Detection Early

Added detection BEFORE `try_split_known_labels()` in the parsing loop (around line 2894):

```python
# Archivev15 Fix 1: Check for field label with inline checkbox option
field_checkbox_split = detect_field_with_inline_checkbox(raw)
if field_checkbox_split:
    field_label, checkbox_option = field_checkbox_split
    
    # Create the main field (e.g., "Cell Phone")
    field_key = slugify(field_title)
    questions.append(Question(field_key, field_title, cur_section, "input", ...))
    
    # Create the checkbox field with opt_in_ prefix
    checkbox_key = f"opt_in_{slugify(checkbox_title)}"
    questions.append(Question(checkbox_key, checkbox_title, cur_section, "radio", ...))
    
    i += 1
    continue
```

### 3. Modified Preprocessing

Updated `enhanced_split_multi_field_line()` to detect and preserve these lines:

```python
def enhanced_split_multi_field_line(line: str) -> List[str]:
    # Archivev15 Fix 1: Check if this is a field with inline checkbox option
    # These should NOT be split, so return early
    if detect_field_with_inline_checkbox(line):
        return [line]
    
    # Continue with other splitting strategies...
```

### 4. Protected Opt-In Fields from Template Matching

Modified `apply_templates_and_count()` to skip fields with `opt_in_` prefix:

```python
is_conditional_field = (
    bool(q.get("conditional_on")) or
    "_explanation" in q.get("key", "") or
    q.get("key", "").startswith("opt_in_") or  # Skip opt-in preference fields
    ...
)
```

## Results

### Chicago Dental Solutions Form

**Before:** 60 items
**After:** 61 items (+1 net after deduplication)

**New Fields Added:**
1. `opt_in_yes_send_me_text_message_alerts` - "Yes, send me Text Message alerts" (radio)
2. `opt_in_yes_send_me_alerts_via_email` - "Yes, send me alerts via Email" (radio)

### Other Forms

- npf.txt: 50 items (no change - pattern not present)
- npf1.txt: 59 items (no change - pattern not present)

## Code Changes

### Files Modified

- `llm_text_to_modento.py`: 
  - Added `detect_field_with_inline_checkbox()` function (line ~1022)
  - Integrated detection in main parsing loop (line ~2894)
  - Modified `enhanced_split_multi_field_line()` (line ~748)
  - Updated `apply_templates_and_count()` (line ~4135)

### Key Design Decisions

1. **Used `opt_in_` prefix for checkbox keys** - Prevents conflicts with main field keys and makes it clear these are preference/opt-in fields

2. **Detected pattern using RAW line** - The detection must happen on the raw line before `collapse_spaced_caps()` removes the wide spacing

3. **Integrated early in pipeline** - Detection must happen before `try_split_known_labels()` which would incorrectly split these lines

4. **Protected from template matching** - Template matching would change the keys and cause deduplication conflicts

## Testing

All forms tested successfully with no regressions:
- ✅ Chicago form gains 1 net field (2 new fields, 1 deduped)
- ✅ NPF forms unchanged (pattern not present)
- ✅ All expected fields present in output JSON
- ✅ No regressions in existing field capture

## Future Considerations

This fix handles the specific pattern of:
- Field label ending with colon
- Wide spacing (5+ spaces)
- Single inline checkbox with option text

If other patterns emerge (e.g., multiple inline checkboxes after a field), additional logic may be needed.
