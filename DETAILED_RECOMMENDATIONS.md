# Recommended Fixes for PDF-to-JSON Conversion (Modento Compliant)

## Overview
After analyzing the Archivev5.zip archive containing PDFs, TXT outputs, and JSON outputs, I've identified several systematic issues that affect the quality of the Modento-compliant JSON forms generated. All recommendations below are **general fixes** that will work across all forms, not hard-coded solutions for specific forms.

---

## Priority 1: Critical Issues

### 1. Grid/Multi-Column Medical Conditions Parser

**Issue**: Medical conditions laid out in grid format (multiple checkboxes per line with spacing) are being treated as single concatenated options instead of being split into individual options.

**Example Problem**:
```
Input (txt): [ ] AIDS/HIV Positive    [ ] Chest Pains    [ ] Headaches    [ ] Hypoglycemia
Current Output: One option with value "aidshiv_positive_chest_pains_headaches_hypoglycemia"
Expected: Four separate options: "AIDS/HIV Positive", "Chest Pains", "Headaches", "Hypoglycemia"
```

**Recommended Fix**:
- In `options_from_inline_line()` function: Enhance checkbox detection to split by column positions
- When multiple checkboxes are found on one line with significant spacing (e.g., 3+ spaces between items), treat each as a separate option
- Use regex pattern: `\[\s*\]\s*([^[]{1,40}?)(?=\s{3,}\[\s*\]|\s*$)` to capture individual checkbox items with their labels
- Implementation location: Around line 400-450 in `llm_text_to_modento.py`

**Code Pattern**:
```python
def options_from_inline_line_enhanced(line: str) -> List[Tuple[str, Optional[bool]]]:
    """Split inline checkboxes even when in grid/column format"""
    # Detect multiple checkboxes with spacing
    # Split by checkbox positions
    # Return individual options
```

---

### 2. Orphaned Checkbox Association

**Issue**: When checkboxes appear on one line and their labels appear on the next line (due to PDF layout), they aren't being properly associated.

**Example Problem**:
```
Input (txt):
[ ]                 [ ]                 [ ]
   Anemia              Diabetes            Cancer

Current: Malformed or skipped entries
Expected: Three separate options for Anemia, Diabetes, Cancer
```

**Recommended Fix**:
- In `parse_to_questions()`: Add look-ahead logic when processing lines with only checkboxes and minimal text
- When a line has multiple checkboxes but very short/no labels, peek at next line
- If next line has multiple words/phrases with similar spacing, associate them with checkboxes
- Implementation: In the main parsing loop, around line 600-700

**Code Pattern**:
```python
# After detecting a line with orphaned checkboxes
if multiple_checkboxes_minimal_text(line):
    next_line = lines[i+1] if i+1 < len(lines) else ""
    if looks_like_orphaned_labels(next_line):
        # Associate labels from next line with checkboxes from current line
        # based on column positions
```

---

### 3. Enhanced Junk Text Filtering

**Issue**: Business addresses, location names, and footer text are being parsed as form fields.

**Example Problem**:
```
Input (txt): "3138 N Lincoln Ave Chicago, IL    5109B S Pulaski Rd.    845 N Michigan Ave"
Current: Creates an input field
Expected: Filtered out as junk/footer text
```

**Recommended Fix**:
- Enhance `scrub_headers_footers()` function to detect multi-location lines
- Add pattern detection for multiple addresses/locations on same line
- Look for patterns: multiple street addresses, multiple city-state pairs, multiple zip codes
- Implementation: Lines 250-300 in `llm_text_to_modento.py`

**Code Pattern**:
```python
# In scrub_headers_footers or as separate filter
MULTI_LOCATION_RE = re.compile(
    r'.*\b(Ave|St|Rd|Blvd).*\b(Ave|St|Rd|Blvd).*',  # Multiple street suffixes
    re.I
)
# Also detect lines with multiple city/state patterns
CITY_STATE_RE = re.compile(r',\s*[A-Z]{2}\s+\d{5}')
if len(CITY_STATE_RE.findall(line)) >= 2:
    # Skip as multi-location footer
```

---

### 4. Consistent "If yes, please explain" Follow-up Fields

**Issue**: Questions with "If yes, please explain" don't consistently create follow-up input fields.

**Example Problem**:
```
Input: "Are you under a physician's care now? [ ] Yes [ ] No    If yes, please explain:"
Current: Only creates the Yes/No radio field
Expected: Creates radio field + conditional follow-up text input field
```

**Recommended Fix**:
- Enhance the compound Y/N detection in `extract_compound_yn_prompts()`
- After creating a Y/N field, check if line or next line contains IF_GUIDANCE_RE pattern
- If found, automatically create a follow-up input field
- Make it conditional with "if" logic tied to the Y/N answer
- Implementation: Around lines 700-800 in parsing logic

**Code Pattern**:
```python
# After creating Y/N radio field
if IF_GUIDANCE_RE.search(line) or (i+1 < len(lines) and IF_GUIDANCE_RE.search(lines[i+1])):
    follow_up_key = base_key + "_explain"
    follow_up = Question(
        follow_up_key,
        "Please explain",
        cur_section,
        "input",
        control={"input_type": "text"}
    )
    # Add conditional logic to show only if answer is Yes
    questions.append(follow_up)
```

---

## Priority 2: Important Improvements

### 5. Better Soft-Wrap Line Coalescing

**Issue**: Multi-line questions aren't always properly joined together.

**Example**:
```
Input (txt):
Have you ever taken Fosamax, Boniva, Actonel/  [ ] Yes [ ] No
other medications containing bisphosphonates?
```

**Recommended Fix**:
- Enhance `coalesce_soft_wraps()` function
- Detect when a line ends with "/" or mid-word continuation
- Look for lines that end with incomplete phrases (no punctuation) followed by lowercase start
- Better detection of wrapped medical questions
- Implementation: Lines 300-350

---

### 6. Communication Preference Field Separation

**Issue**: Opt-in checkboxes (e.g., "[ ] Yes, send me Text Message alerts") get merged with preceding fields.

**Example Problem**:
```
Input: "Cell Phone: ___________    [ ] Yes, send me Text Message alerts"
Current: Merged into one field
Expected: Separate phone field + separate opt-in checkbox
```

**Recommended Fix**:
- In parsing logic, detect standalone checkbox patterns with "Yes/No" + action verb
- Look for patterns: `[ ] Yes, send me|allow|consent|agree to ...`
- Split these into separate checkbox/radio fields
- Implementation: Around line 650-750

**Code Pattern**:
```python
CONSENT_CHECKBOX_RE = re.compile(
    r'\[\s*\]\s*(?:Yes|No)?,?\s+(send me|allow|consent|agree|authorize)',
    re.I
)
# If found, split into separate field
```

---

### 7. Enhanced Medical History Section Detection

**Issue**: Medical conditions aren't always consolidated into a single dropdown.

**Recommended Fix**:
- Strengthen the medical history block detection
- When entering "Medical History" or "Dental History" section
- AND detecting a question like "Do you have any of the following?"
- Activate a special "condition collection mode"
- Collect ALL subsequent checkboxes into one dropdown until section change
- Implementation: Lines 900-1000 in parse_to_questions

---

### 8. Better Terms Field Detection

**Issue**: Long informational paragraphs should become "terms" fields requiring agreement.

**Recommended Fix**:
- Enhance paragraph detection logic
- Look for multi-sentence blocks (3+ sentences)
- Check for consent language: "I understand", "I agree", "I authorize"
- Convert to "terms" type with agreement checkbox
- Implementation: Around lines 800-850

**Code Pattern**:
```python
def is_terms_paragraph(text: str) -> bool:
    sentences = text.count('.') + text.count('!')
    consent_words = ['understand', 'agree', 'authorize', 'consent', 'acknowledge']
    has_consent = any(word in text.lower() for word in consent_words)
    return sentences >= 3 and has_consent and len(text) > 150
```

---

## Priority 3: Polish & Consistency

### 9. Improved Section Header Detection

**Issue**: Section boundaries aren't always correctly identified.

**Recommended Fix**:
- Enhance `is_heading()` function
- Better detection of ALL-CAPS headers
- Recognize common section names: "PATIENT INFORMATION", "INSURANCE", "MEDICAL HISTORY"
- Use section context to influence field types
- Implementation: Around line 200

---

### 10. Better Junk Token Filtering

**Issue**: Tokens like "<<<", ">>>", "OC123", "Rev 02/20" should be filtered.

**Recommended Fix**:
- Already partially implemented in `scrub_headers_footers()`
- Enhance with more patterns:
  - Version numbers: "v1.0", "ver 2.3"
  - Reference codes: "OC\d+", "REF\d+"
  - Continuation markers: "continued on", "see back", "over →"
- Implementation: Lines 250-300

---

## Summary of Key Code Areas to Modify

1. **options_from_inline_line()** - Lines ~400-450: Grid/column checkbox splitting
2. **parse_to_questions()** - Lines ~600-1000: Orphaned checkbox handling, follow-up field creation
3. **scrub_headers_footers()** - Lines ~250-300: Enhanced junk filtering
4. **coalesce_soft_wraps()** - Lines ~300-350: Better line joining
5. **is_heading()** - Line ~200: Section detection
6. **New helper functions**: `is_terms_paragraph()`, `CONSENT_CHECKBOX_RE` pattern

## Testing Approach

All fixes should be tested against:
1. The three forms in Archivev5.zip
2. Any other test forms in the repository
3. Ensure no regressions - existing working fields should remain working

## Implementation Notes

- All fixes use **general pattern matching** and heuristics
- No hard-coding of specific form fields
- Changes should be **backwards compatible** with existing forms
- Focus on improving **parsing accuracy** while maintaining **generalizability**
