# Analysis of Archivev10.zip - Missing Fields Investigation

**Date:** October 2, 2025  
**Repository:** pdf-to-json-llm  
**Issue:** Fields visible in PDF/txt not captured in JSON output

---

## Executive Summary

After analyzing the Archivev10.zip archive containing 3 dental forms (PDFs, txt files, and JSON outputs), I identified **critical issues** affecting field capture accuracy, particularly in multi-column checkbox grids.

### Key Findings:

| Form | Total Fields | Medical Conditions in txt | Medical Conditions in JSON | Missing | Dental Conditions in txt | Dental Conditions in JSON | Missing |
|------|--------------|---------------------------|---------------------------|---------|--------------------------|---------------------------|---------|
| **npf1.txt** | 50 | 50 checkboxes | 45 items (8 dropdowns) | 5 (10%) | 34 checkboxes | 3 items (1 dropdown) | 31 (91%) |
| **Chicago** | 39 | ~73 checkboxes | 73 items (1 dropdown) | 0 (0%) | ~30 checkboxes | Minimal capture | ~27 (90%) |
| **npf.txt** | 34 | No medical section | N/A | N/A | Minimal dental | Minimal capture | N/A |

**Critical Issue:** Multi-column checkbox grids in Dental History and Medical History sections are being severely under-captured, with **80-90% of checkbox items missing** from the JSON output.

---

## Detailed Analysis

### Problem 1: Multi-Column Grid Parsing Failure 🔴 CRITICAL

**What's happening:**

The parser treats multi-column checkbox grids as single-column lists, resulting in:
- Concatenated field titles from multiple columns
- Missing individual checkbox items
- Malformed dropdown fields

**Example from npf1.txt (line 97):**

```
Text file shows:
  [ ] Radiation Therapy    [ ] Jaundice    [ ] Jaw Joint Pain    [ ] Respiratory Problems [ ] Opioids
```

**What SHOULD be created:** 5 separate checkbox fields or 1 multi-select dropdown with 5 options

**What IS being created:** 1 dropdown field with title "Radiation Therapy Jaundice Jaw Joint Pain Respiratory Problems Opioids" and 5 options

**Impact:** 
- ❌ Field title is malformed (concatenated condition names)
- ❌ Not Modento-compliant
- ✓ Options are captured correctly (but title is wrong)

---

### Problem 2: Dental History Grid Nearly Completely Lost 🔴 CRITICAL

**Example from npf1.txt (lines 75-91):**

The txt file contains a 4-column grid with category headers:
```
Appearance         Function                      Habits                        Previous Comfort Options
[ ] Discolored     [ ] Grinding/Clenching        [ ] Thumb sucking            [ ] Nitrous Oxide
[ ] Worn teeth     [ ] Headaches                 [ ] Nail-biting              [ ] Oral Sedation
...
```

**What SHOULD be captured:** 34 individual checkbox items across 4 categories

**What IS being captured:** Only 1 dropdown with 3 items from line 79:
- "Crooked teeth Jaw Joint (TMJ) clicking/popping Chewing on ice/foreign objects"

**Missing:** 31 out of 34 items (91% loss!)

**Why:** The parser is:
1. Skipping category headers (lines 75, 84, 87, etc.)
2. Not recognizing the multi-column layout
3. Only capturing one line (79) and creating a malformed dropdown from it

---

### Problem 3: Category Headers Confusion 🟡 MEDIUM

**What's happening:**

Lines that are category headers (without checkboxes) are being:
- Treated as field titles (e.g., "Cardiovascular")
- Included in concatenated field titles
- Causing confusion about where fields start/end

**Example from npf1.txt (line 94):**
```
Cancer    Endocrinology    Musculoskeletal    Respiratory    Medical Allergies
```

These are category headers for the columns below them, NOT checkbox items. But the parser treats them as potential field names.

**Example from npf1.txt (line 99):**
```
Cardiovascular [ ]    [ ] Liver Disease    ...    [ ] Sleep Apnea
```

"Cardiovascular" is treated as a field title, creating a dropdown with only 1 option ("Sleep Apnea").

---

### Problem 4: Incomplete Checkbox Detection Within Lines 🟡 MEDIUM

**What's happening:**

When parsing lines with multiple checkboxes, the parser often captures only:
- The first few items
- The last few items
- Or creates malformed combinations

**Example from npf1.txt (line 95):**
```
Type    [ ] Diabetes    [ ] Arthritis    [ ] Asthma    [ ] Antibiotics
```

This creates a dropdown titled "Type" with 4 options, which is actually correct! But it's inconsistent - other similar lines are parsed differently.

---

### Problem 5: Text Artifacts and Concatenation 🟡 MEDIUM

**What's happening:**

When checkbox items span columns or have nearby text, they get concatenated:

**Examples:**
- "Emphysema (Penicillin/Amoxicillin /Clindamycin)" 
  - "Emphysema" is column 4, the parenthetical is from column 5 (Medical Allergies)
- "HIV Positive Other"
  - "HIV Positive" is one item, "Other" is a label from the next column
- "Seizures Women Additional Comments"
  - "Seizures" is the actual item, "Women" and "Additional Comments" are from other columns

---

## Why This Is Happening

### Root Cause Analysis:

The current parsing logic in `llm_text_to_modento.py` has these fundamental issues:

1. **No Multi-Column Grid Detection** 
   - The code assumes checkboxes are arranged vertically (one per line or sequential)
   - Multi-column layouts (3-5 columns of checkboxes) are not recognized
   - Lines with multiple checkboxes are treated as "compound" fields or option lists

2. **Grid Header Logic Is Incomplete**
   - `looks_like_grid_header()` exists but only looks for pipe-separated columns or 3+ whitespace-separated parts
   - It doesn't handle the common case of category headers without pipes
   - Medical/Dental history grids don't match its pattern

3. **Checkbox Extraction Is Sequential**
   - `INLINE_CHOICE_RE` and related logic extracts checkboxes left-to-right
   - It doesn't understand that checkboxes in different columns are independent items
   - Proximity-based grouping causes items from different columns to merge

4. **Category Header Detection Is Insufficient**
   - `is_category_header()` was added in Fix 3 but isn't being applied consistently
   - Lines like "Appearance", "Function", "Pain/Discomfort" aren't recognized as headers
   - These headers don't have a consistent pattern (no colons, not all caps, etc.)

---

## What Should Happen (Expected Behavior)

### For Medical History Grid (npf1.txt lines 93-108):

**Input:** 
```
Medical History - Please mark (x) to your response...

Cancer              Endocrinology       Musculoskeletal     Respiratory         Medical Allergies
Type                [ ] Diabetes        [ ] Arthritis       [ ] Asthma          [ ] Antibiotics
[ ] Chemotherapy    [ ] Hepatitis A/B/C [ ] Artificial      [ ] Emphysema       (Penicillin...)
...
```

**Expected Output:**
```json
{
  "key": "medical_conditions",
  "title": "Do you have or have you had any of the following?",
  "section": "Medical History",
  "type": "checkboxes",  // or multi-select dropdown
  "control": {
    "options": [
      {"name": "Diabetes", "value": "diabetes"},
      {"name": "Arthritis", "value": "arthritis"},
      {"name": "Asthma", "value": "asthma"},
      {"name": "Antibiotics Allergy", "value": "antibiotics_allergy"},
      {"name": "Chemotherapy", "value": "chemotherapy"},
      {"name": "Hepatitis A/B/C", "value": "hepatitis_abc"},
      ... // all 50 conditions as separate options
    ]
  }
}
```

**OR** (alternative acceptable output):
- 5 separate multi-select dropdowns, one per category (Cancer, Endocrinology, etc.)
- Each with the appropriate subset of conditions

### For Dental History Grid (npf1.txt lines 74-91):

**Expected Output:**
```json
{
  "key": "dental_conditions",
  "title": "Please mark any of the following conditions that apply to you",
  "section": "Dental History", 
  "type": "checkboxes",
  "control": {
    "options": [
      {"name": "Discolored teeth", "value": "discolored_teeth"},
      {"name": "Grinding/Clenching", "value": "grinding_clenching"},
      {"name": "Thumb sucking", "value": "thumb_sucking"},
      {"name": "Nitrous Oxide (previous use)", "value": "nitrous_oxide"},
      ... // all 34 items as separate options
    ]
  }
}
```

**OR** (alternative acceptable output):
- 4 separate multi-select dropdowns: "Appearance", "Function", "Habits", "Previous Comfort Options"
- Each with the appropriate subset of conditions

---

## Proposed Fixes (Generic, Reusable Solutions)

### Fix 1: Enhanced Multi-Column Checkbox Grid Detection 🔴 HIGH PRIORITY

**Location:** `llm_text_to_modento.py`, around line 1700-1800 (in `parse_to_questions()`)

**What to do:**

1. **Detect multi-column checkbox patterns**
   - Look for lines with 3+ checkboxes separated by significant whitespace (8+ spaces)
   - Identify if consecutive lines follow the same column pattern
   - Calculate approximate column positions based on checkbox locations

2. **Create column-aware checkbox extraction**
   ```python
   def detect_checkbox_columns(line: str) -> List[Tuple[int, str]]:
       """
       Returns list of (position, text_after_checkbox) for each checkbox in line.
       Position is the character index where the checkbox appears.
       """
       # Find all checkbox positions
       # Group text after each checkbox up to the next checkbox or EOL
       # Return structured data
   ```

3. **Aggregate multi-line grids into single multi-select field**
   ```python
   def parse_checkbox_grid(lines: List[str], start_idx: int) -> Tuple[Question, int]:
       """
       Detects and parses a multi-line, multi-column checkbox grid.
       Returns a single multi-select dropdown/checkbox field with all options.
       """
       # Detect grid boundaries
       # Extract all checkbox items across all rows and columns
       # Skip category headers (lines without checkboxes)
       # Create single consolidated field
       # Return Question and last_line_index
   ```

**Expected outcome:**
- Medical History grid → 1 field with 50 options (instead of 8 fields with malformed titles)
- Dental History grid → 1 field with 34 options (instead of 1 field with 3 options)

---

### Fix 2: Improved Category Header Detection 🟡 MEDIUM PRIORITY

**Location:** `llm_text_to_modento.py`, `is_category_header()` function

**What to do:**

Enhance the existing `is_category_header()` function to recognize:

1. **Short lines without checkboxes that precede lines with checkboxes**
   ```python
   def is_category_header(line: str, next_lines: List[str]) -> bool:
       """
       Enhanced to check multiple next lines and column alignment.
       """
       cleaned = collapse_spaced_caps(line.strip())
       
       # Must be short (1-4 words)
       if len(cleaned.split()) > 4:
           return False
       
       # Must NOT have checkboxes
       if re.search(CHECKBOX_ANY, cleaned):
           return False
       
       # Check if next 2-3 lines have checkboxes
       has_checkboxes_below = False
       for next_line in next_lines[:3]:
           if re.search(CHECKBOX_ANY, next_line):
               has_checkboxes_below = True
               break
       
       return has_checkboxes_below
   ```

2. **Column-aligned category headers**
   - If a line has 3-5 words/phrases aligned with checkbox columns below, treat as header
   - Example: "Appearance    Function    Habits    Previous Comfort Options"

**Expected outcome:**
- Category headers like "Cancer", "Cardiovascular", "Pain/Discomfort" are recognized and skipped
- Not treated as field titles or included in concatenated titles

---

### Fix 3: Whitespace-Based Column Detection 🟡 MEDIUM PRIORITY

**Location:** New helper function in `llm_text_to_modento.py`

**What to do:**

Create a function that analyzes whitespace patterns to detect column boundaries:

```python
def detect_column_boundaries(lines: List[str], start_idx: int, max_lines: int = 15) -> Optional[List[int]]:
    """
    Analyzes multiple lines to detect consistent column positions.
    Returns list of character positions where columns start, or None if no pattern found.
    
    Example:
      Input lines with checkboxes at positions [5, 35, 65, 95]
      Returns: [5, 35, 65, 95]
    """
    # Collect checkbox positions across multiple lines
    # Find consistent positions (±3 chars tolerance)
    # Return column boundaries if 3+ consistent columns found
```

This would allow the parser to understand that a checkbox at position 5 is in column 1, position 35 is in column 2, etc.

**Expected outcome:**
- Better handling of forms with varying column widths
- More accurate extraction of text associated with each checkbox

---

### Fix 4: Grid Section Consolidation Post-Processor 🟡 MEDIUM PRIORITY

**Location:** New post-processing function in `llm_text_to_modento.py`

**What to do:**

Add a post-processing step that runs after initial parsing:

```python
def postprocess_consolidate_checkbox_grids(payload: List[dict], dbg: Optional[DebugLogger] = None) -> List[dict]:
    """
    Finds malformed multi-column checkbox fields and consolidates them.
    
    Detects:
    - Multiple dropdown fields with concatenated titles (e.g., "Radiation Therapy Jaundice...")
    - Fields where title contains 3+ capitalized medical/dental terms
    - Fields in Medical/Dental History with suspiciously short option counts (< 5)
    
    Actions:
    - Consolidates into single multi-select field
    - Uses generic title like "Medical Conditions" or "Dental Conditions"
    - Combines all options
    """
    # Identify malformed fields using is_malformed_condition_field()
    # Group consecutive malformed fields
    # Consolidate into single field
    # Remove consolidated fields from payload
    # Add new consolidated field
```

**Expected outcome:**
- Even if parsing creates malformed fields, they get fixed in post-processing
- More robust handling of edge cases

---

### Fix 5: Better Grid Boundary Detection 🟢 LOW PRIORITY

**Location:** Enhancement to existing `detect_table_layout()` function

**What to do:**

The existing `detect_table_layout()` function (added in Fix 4 from Archivev9) should be enhanced to detect:

1. **Header-less grids** - Checkbox grids without clear header rows
2. **Category-based grids** - Grids where each row starts with a category label
3. **Inconsistent column counts** - Grids where different rows have different numbers of columns

**Expected outcome:**
- Existing table detection logic catches more edge cases
- Better integration with new column detection logic

---

## Implementation Strategy

### Recommended Order:

1. **Fix 1 (Multi-Column Grid Detection)** - Implements core functionality
2. **Fix 2 (Category Header Detection)** - Refines what gets parsed
3. **Fix 4 (Grid Consolidation Post-Processor)** - Safety net for edge cases
4. **Fix 3 (Column Boundary Detection)** - Optimization for better accuracy
5. **Fix 5 (Grid Boundary Enhancement)** - Polish and edge case handling

### Why This Order:

- **Fix 1** addresses the root cause and has the highest impact
- **Fix 2** prevents bad data from entering the pipeline
- **Fix 4** acts as a safety net even if parsing isn't perfect
- **Fixes 3 & 5** are optimizations that can be added incrementally

### Testing After Each Fix:

```bash
# Run on all 3 forms
python3 llm_text_to_modento.py --in /tmp/archivev10/output --out /tmp/test_fix1 --debug

# Compare field counts
python3 -c "
import json
for form in ['npf1', 'Chicago-Dental-Solutions_Form', 'npf']:
    with open(f'/tmp/test_fix1/{form}.modento.json') as f:
        data = json.load(f)
    print(f'{form}: {len(data)} fields')
    
    # Count medical history checkboxes
    for item in data:
        if item.get('section') == 'Medical History' and item.get('type') in ['dropdown', 'checkboxes']:
            opts = item.get('control', {}).get('options', [])
            print(f'  Medical: {item.get(\"title\", \"\")[:40]} - {len(opts)} options')
"
```

---

## Success Criteria

### After Fix 1 Implementation:

| Metric | Before | Target After Fix 1 | Stretch Goal |
|--------|--------|-------------------|--------------|
| npf1 Medical History items captured | 45/50 (90%) | 50/50 (100%) | ✓ |
| npf1 Dental History items captured | 3/34 (9%) | 34/34 (100%) | ✓ |
| Malformed field titles | 6-8 per form | 0 | ✓ |
| Medical/Dental fields per form | 8-20 | 1-5 | ✓ |

### Quality Checks:

- ✅ No field titles with concatenated condition names
- ✅ All visible checkboxes in PDF/txt are captured in JSON
- ✅ Category headers are not treated as field names
- ✅ Each checkbox item appears exactly once in the JSON
- ✅ Fields have clean, descriptive titles (not malformed concatenations)
- ✅ Fields are assigned to the correct section (Medical History vs Dental History)

---

## Code Locations Reference

**Main parsing function:**
- `parse_to_questions()` - lines 1624-2197

**Existing related functions:**
- `looks_like_grid_header()` - line 1088
- `detect_table_layout()` - line 1110 
- `parse_table_to_questions()` - line 1175
- `is_category_header()` - line 1013
- `is_malformed_condition_field()` - line 2417
- `postprocess_consolidate_medical_conditions()` - line 2441

**Where to add new functions:**
- New grid detection: After line 1260 (before grid parsing logic)
- Column detection helper: Around line 1100 (with other grid helpers)
- Grid consolidation post-processor: Around line 2500 (with other post-processors)
- Call new post-processor: In `process_one()` around line 2610

---

## Examples of Forms Working Correctly

**Chicago-Dental-Solutions_Form.txt** has a medical history section that was captured well:
- 73 medical conditions → 1 dropdown field with 73 options
- Field title: "Do you have, or have you had, any of the following?"
- Clean, properly formatted option names

**Why it worked:**
- Checkboxes are arranged in a more vertical layout (fewer columns)
- Less column-to-column spacing, so parser recognizes them as sequential items
- Category headers are less prominent

This shows the current code CAN handle checkbox lists well when they're formatted more linearly.

---

## Additional Notes

### Forms Without Issues:

**npf.txt** - No medical history section at all
- Only has patient info, insurance, and dental benefit terms
- All fields captured correctly
- No fixes needed for this form

### Modento Compliance:

All proposed fixes maintain Modento compliance:
- Field structure remains consistent
- Section assignments are correct
- No hard-coded form-specific logic
- All fixes are generic and reusable across forms

### Backward Compatibility:

Proposed fixes should NOT break existing working behavior:
- Forms with single-column checkboxes continue to work
- Forms with vertical layouts continue to work
- Only multi-column grids get special handling
- Existing post-processors remain in place

---

## Questions for User

Before implementing, please confirm:

1. **Field Structure Preference:**
   - Should multi-column grids become 1 large multi-select field? OR
   - Should they become multiple fields (one per category)? OR
   - Either is acceptable?

2. **Category Headers:**
   - Should category headers (Cancer, Endocrinology, etc.) be preserved as labels/hints? OR
   - Should they be omitted entirely?

3. **Priority:**
   - Should we focus on Medical History grids first? OR
   - Both Medical and Dental History equally? OR
   - Dental History is more important?

4. **Backward Compatibility:**
   - Are there any existing forms (not in Archivev10) we should test against? OR
   - Can we assume Archivev9 and Archivev10 are representative?

---

## Conclusion

The root cause of missing fields in Archivev10 is **multi-column checkbox grid parsing failure**. The current parser assumes vertical/sequential checkbox layouts and doesn't understand that checkboxes arranged horizontally across multiple columns represent independent items.

**Key Impact:**
- 80-90% of Dental History checkboxes are missing
- 10% of Medical History checkboxes are missing
- Field titles are malformed (concatenated condition names)
- Not Modento-compliant

**Solution:**
- Implement multi-column grid detection
- Enhance category header recognition
- Add grid consolidation post-processor
- All fixes are generic and reusable (no form-specific hard-coding)

**Estimated Effort:**
- Fix 1: 4-6 hours (core functionality)
- Fix 2: 1-2 hours (enhancement)
- Fix 3: 2-3 hours (optimization)
- Fix 4: 2-3 hours (safety net)
- Testing: 2-3 hours per fix
- **Total: ~15-20 hours**

All proposed fixes follow the established code patterns and will work across all forms, not just Archivev10.
