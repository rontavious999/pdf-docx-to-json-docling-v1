# Quick Summary: Archivev12 Missing Fields Analysis

## Problem
Multiple fields on same line are NOT being split and parsed correctly.

## Missing Fields (npf1.txt & npf.txt)
1. **Sex/Gender** - Line: `Sex Mor F   Soc. Sec. #   Please Circle One: Single...`
2. **Marital Status** - Same line as above
3. **Work Phone** - Line: `Work Phone (   )         Occupation`
4. **Occupation** - Same line as above

## Why It Fails
Current `split_multi_question_line()` requires:
- ✅ Checkboxes `[ ]`
- ✅ Colons after labels `Label:`
- ✅ Pattern: `] ... Label: [`

Real forms have:
- ❌ No checkboxes (e.g., "Sex M or F")
- ❌ No colons (e.g., "Marital Status [ ]")
- ❌ Just spacing (e.g., "Work Phone   Occupation")

## Validation
Tested current function on problematic lines → ALL FAILED (0/4 split correctly)

## Proposed Fixes (All Generic, No Hardcoding)

### 1. Enhanced Multi-Field Splitting (HIGH PRIORITY)
Add patterns for:
- Checkboxes without colons: `Label [ ] options ... Label [ ] options`
- Known labels with spacing: `Work Phone   Occupation`
- Mixed patterns: `Sex M or F   SSN   Marital: [ ] Single...`

### 2. Special Field Recognition (HIGH PRIORITY)
Add detection for common fields:
- Sex/Gender patterns
- Marital Status patterns  
- Phone field patterns

### 3. Label Dictionary (MEDIUM PRIORITY)
Detect known labels: sex, gender, marital_status, work_phone, occupation, email, etc.

### 4. Context-Aware Parsing (MEDIUM PRIORITY)
Recognize options without checkboxes after "circle one:", "choose:", etc.

## Expected Results After Fixes
✅ Sex/Gender captured from all forms
✅ Marital Status captured with options
✅ Work Phone, Occupation as separate fields
✅ No regressions on existing forms (like Chicago)

## Implementation Files
- `llm_text_to_modento.py` - Main parsing logic
- Functions to modify: `split_multi_question_line()`, `preprocess_lines()`
- Add new helper functions for enhanced detection

See `ARCHIVEV12_ANALYSIS.md` for full details.
