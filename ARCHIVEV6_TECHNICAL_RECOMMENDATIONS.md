# Technical Recommendations for Archivev6 Issues

## Overview
Based on analysis of Archivev6.zip, these are the recommended fixes for `llm_text_to_modento.py` to improve Modento-compliant JSON generation. All fixes use general patterns and will work across all forms.

---

## Fix 1: Clean Checkbox Markers from Field Titles

### Location
Function: `parse_to_questions()` - approximately line 1000-1100 where dropdown fields are created

### Current Problem
When inline checkboxes are found, the entire line including "[ ]" markers becomes the field title:
```
Title: "[ ] I live/work in area [ ] Google [ ] Yelp [ ] Social Media"
```

### Recommended Solution
Extract the question/prompt text that appears BEFORE the first checkbox marker.

### Implementation Pattern
```python
def extract_title_from_inline_checkboxes(line: str) -> str:
    """
    Extract the question/prompt text before the first checkbox marker.
    
    Example:
        "How did you hear? [ ] Google [ ] Friend" -> "How did you hear?"
        "Gender: [ ] Male [ ] Female" -> "Gender:"
    """
    # Pattern to match text before first checkbox
    match = re.match(r'^(.*?)(?:\[\s*\]|\[x\]|☐|☑|□|■)', line)
    if match:
        title = match.group(1).strip()
        # Clean up trailing colons, question marks, etc
        title = title.rstrip(':? ').strip()
        if title:
            return title
    # Fallback: return cleaned line
    return re.sub(CHECKBOX_ANY, '', line).strip()
```

### Integration Point
In `parse_to_questions()`, when creating dropdown fields from inline options:
```python
# Current code around line 1050-1100
if opts_inline:
    # BEFORE creating the Question:
    title = extract_title_from_inline_checkboxes(line)  # NEW
    questions.append(Question(
        key=slugify(title),  # Use cleaned title
        title=title,         # Use cleaned title
        section=cur_section,
        qtype="dropdown",
        control={"options": [make_option(n, v) for n, v in opts_inline], "multi": True}
    ))
```

---

## Fix 2: Create Follow-up Fields for Y/N with "If yes, please explain"

### Location
Function: `parse_to_questions()` - in the compound Y/N section (around line 950-1000)

### Current Problem
Y/N questions with "if yes, please explain" only create the radio button, not the follow-up text field.

### Recommended Solution
Enhanced pattern detection and automatic follow-up field creation.

### Implementation Pattern
```python
# In parse_to_questions(), enhance the compound Y/N section

# After creating the Y/N radio field:
for m in COMPOUND_YN_RE.finditer(line):
    ptxt = clean_token(m.group("prompt"))
    # ... create radio field ...
    
    # NEW: Check for follow-up indicators
    if re.search(r'\b(if\s+yes|please\s+explain|if\s+so|explain\s+below)\b', line, re.I):
        # Create follow-up text input
        follow_up_key = slugify(ptxt + "_details")
        follow_up_title = f"{ptxt} - Please explain"
        questions.append(Question(
            key=follow_up_key,
            title=follow_up_title,
            section=cur_section,
            qtype="input",
            control={"input_type": "text"}
        ))
    
    # Also check next line for follow-up indicators
    if i + 1 < len(lines):
        next_line = lines[i + 1].strip()
        if re.search(r'^(if\s+yes|please\s+explain|explain|comment)', next_line, re.I):
            # Create follow-up field if not already created
            follow_up_key = slugify(ptxt + "_details")
            if not any(q.key == follow_up_key for q in questions):
                questions.append(Question(
                    key=follow_up_key,
                    title=f"{ptxt} - Details",
                    section=cur_section,
                    qtype="input",
                    control={"input_type": "text"}
                ))
```

---

## Fix 3: Improve Grid Column Text Extraction

### Location
Function: `options_from_inline_line()` - around line 399-450

### Current Problem
Text from different columns/regions gets concatenated into malformed labels:
- "Artificial Angina (chest Heart pain) Valve" - should be separate items
- "Heart Conditions Gastrointestinal" - categories mixed with options

### Recommended Solution
Better whitespace-based column splitting and artifact filtering.

### Implementation Pattern
```python
def options_from_inline_line(ln: str) -> List[Tuple[str, Optional[bool]]]:
    """
    Enhanced to handle grid/multi-column layouts with better text extraction.
    """
    s_norm = normalize_glyphs_line(ln)
    
    # ... existing code ...
    
    if len(checkbox_positions) >= 3:  # Grid detection
        options = []
        for i, start_pos in enumerate(checkbox_positions):
            if i + 1 < len(checkbox_positions):
                end_pos = checkbox_positions[i + 1]
            else:
                end_pos = len(s_norm)
            
            segment = s_norm[start_pos:end_pos]
            label = re.sub(CHECKBOX_ANY, '', segment).strip()
            
            # NEW: Better cleaning
            # 1. Collapse multiple spaces
            label = re.sub(r'\s{3,}', ' ', label)
            
            # 2. Remove trailing checkbox artifacts
            label = label.strip('[]')
            
            # 3. Split on excessive spacing (likely column boundary)
            # If label has 5+ consecutive spaces, take only first part
            parts = re.split(r'\s{5,}', label)
            if len(parts) > 1:
                # Take the first non-empty part
                label = next((p.strip() for p in parts if p.strip()), label)
            
            # 4. Remove common artifacts
            # Filter out category headers that got included
            if re.match(r'^(Type|Cardiovascular|Gastrointestinal|Neurological|Viral|Women)$', label, re.I):
                continue
            
            label = clean_token(label)
            
            if label and len(label) > 1 and label.lower() not in YESNO_SET:
                options.append((label, None))
        
        if len(options) >= 2:  # Changed from >= 3 to be more permissive
            return options
    
    return items
```

---

## Fix 4: Enhance Orphaned Checkbox Detection Integration

### Location
Function: `parse_to_questions()` - main parsing loop, around line 750-800

### Current Problem
The `extract_orphaned_checkboxes_and_labels()` function exists but isn't being called consistently.

### Recommended Solution
Add explicit calls to check for orphaned checkboxes during option harvesting.

### Implementation Pattern
```python
# In parse_to_questions(), in the option harvesting section (around line 750)

# After checking for inline options:
opts_inline = options_from_inline_line(line)
opts_block: List[Tuple[str, Optional[bool]]] = []

# NEW: Check for orphaned checkboxes before processing
if not opts_inline and i + 1 < len(lines):
    orphaned_opts = extract_orphaned_checkboxes_and_labels(line, lines[i+1])
    if orphaned_opts:
        # Found orphaned checkboxes - use them
        title = line.strip()
        # Remove checkboxes from title
        title = re.sub(CHECKBOX_ANY, '', title).strip()
        if not title:
            # Look back for a title
            if i > 0:
                prev_line = lines[i-1].strip()
                if prev_line and not re.search(CHECKBOX_ANY, prev_line):
                    title = prev_line
        
        if title:
            # Create dropdown with orphaned options
            questions.append(Question(
                key=slugify(title),
                title=title,
                section=cur_section,
                qtype="dropdown",
                control={"options": [make_option(n, v) for n, v in orphaned_opts], "multi": True}
            ))
            i += 2  # Skip current and next line
            continue
```

---

## Fix 5: Additional Title Cleaning for Edge Cases

### Location
Multiple locations where titles are set

### Current Problem
Some field titles still have artifacts like double checkboxes or trailing checkbox markers.

### Recommended Solution
Universal title cleaning function.

### Implementation Pattern
```python
def clean_field_title(title: str) -> str:
    """
    Clean field title by removing checkbox markers and artifacts.
    Apply this to all field titles before creating Questions.
    """
    # Remove checkbox markers
    cleaned = re.sub(CHECKBOX_ANY, '', title)
    
    # Remove multiple spaces
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
    # Trim whitespace
    cleaned = cleaned.strip()
    
    # Remove trailing colons if followed by nothing
    cleaned = re.sub(r':\s*$', '', cleaned)
    
    return cleaned
```

Apply this function when creating ANY Question object:
```python
questions.append(Question(
    key=slugify(title),
    title=clean_field_title(title),  # Apply cleaning
    section=cur_section,
    ...
))
```

---

## Testing Checklist

After implementing these fixes, validate against all three forms:

### Chicago-Dental-Solutions_Form
- [ ] "How did you hear about us?" title has no "[ ]" markers
- [ ] "Women are you:" title is clean
- [ ] "Are you allergic to any of the following?" title is clean
- [ ] Y/N questions create follow-up fields for:
  - [ ] "Are you under a physician's care now?"
  - [ ] "Have you ever been hospitalized?"
  - [ ] "Have you ever had a serious head/neck injury?"
  - [ ] "Are you taking any medications?"
- [ ] Medical conditions include: Anemia, Convulsions, Hay Fever, Leukemia

### npf
- [ ] No field titles contain "[ ]" markers
- [ ] Grid checkboxes properly split (not concatenated)
- [ ] No category headers mixed with options
- [ ] "Who can we thank for your visit?" is separate from "Other" checkbox

### npf1
- [ ] All fields have clean titles
- [ ] No data loss from parsing issues

---

## Implementation Priority

1. **Fix 1** (Title Cleaning) - Highest visual impact
2. **Fix 2** (Follow-up Fields) - Improves data completeness
3. **Fix 4** (Orphaned Checkboxes) - Prevents data loss
4. **Fix 3** (Grid Extraction) - More complex, requires careful testing
5. **Fix 5** (Universal Cleaning) - Polish pass

---

## Code Modification Summary

### Files to Modify
- `llm_text_to_modento.py` (primary file)

### Functions to Enhance
1. `parse_to_questions()` - main parsing loop
2. `options_from_inline_line()` - grid checkbox parsing
3. `extract_orphaned_checkboxes_and_labels()` - triggering logic

### New Helper Functions to Add
1. `extract_title_from_inline_checkboxes()` - extract clean titles
2. `clean_field_title()` - universal title cleaner

### Estimated Lines of Code
- New functions: ~50 lines
- Modifications to existing: ~100 lines
- Total impact: ~150 lines

---

## Risk Assessment

### Low Risk
- Fix 1, 2, 5 - Simple string manipulation, easy to test

### Medium Risk
- Fix 4 - Existing function, just need better integration

### Higher Risk
- Fix 3 - Complex grid parsing, needs extensive testing

### Mitigation
- Test incrementally with all three sample forms
- Keep backup of original JSON outputs for comparison
- Implement fixes one at a time with validation between each

