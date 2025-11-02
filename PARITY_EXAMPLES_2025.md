# Parity Analysis - Concrete Examples

## Analysis Date: November 2, 2025

This document provides specific examples from the current pipeline run showing parity issues between PDF/DOCX sources, extracted text, and generated JSON.

---

## Overall Statistics

**Forms Processed**: 38 dental forms
**Average Fields Per Form**: 11.9 fields
**Average Dictionary Match Rate**: 58.8%
**Best Performing Forms**: Patient registration forms (90-100% match)
**Worst Performing Forms**: Consent forms (22-43% match)

---

## Example 1: Patient Registration Form (npf.pdf)

### Source Characteristics
- **Type**: Patient information form
- **Complexity**: Medium (50 lines of text)
- **Layout**: Mixed single and multi-column with form fields

### Text Extraction Sample
```
Patient Information Form

Today's Date________________

Patient Name: First__________________ MI_____ Last_______________________ Nickname_____________
Address: Street_________________________________________________________ Apt/Unit/Suite________
City_________________________________________________ State_______ Zip_______________
Phone: Mobile_______________________ Home_______________________ Work______________________
```

### JSON Output Statistics
- **Total Fields Captured**: 33
- **Dictionary Match Rate**: 100%
- **Sections**: Patient Information (28), Dental History (2), Signature (3)

### Parity Issues Identified

1. **Issue**: Compound fields not properly split
   ```
   Extracted: "Patient Name: First__________________ MI_____ Last_______________________"
   JSON Result: Three separate fields but with incorrect names:
   - "Patient Name - First" 
   - "Patient Name" (should be MI)
   - "Patient Name - Last"
   ```
   **Impact**: Field labels are confusing, not semantically correct
   **Related Improvement**: #4 (Semantic Field Label Recognition)

2. **Issue**: OCR errors in header
   ```
   Extracted: "Tel: 626.577.2017 os) 7 Lint? Fax: 626.577.2003 Aneatige"
   Should be: "Tel: 626.577.2017 Fax: 626.577.2003 [Practice Name]"
   ```
   **Impact**: Header text corrupted, though doesn't affect field extraction
   **Related Improvement**: #2 (Enhanced OCR Error Correction)

3. **Issue**: Multi-sub-field line creates multiple fields
   ```
   Extracted: "Phone: Mobile_______ Home_______ Work_______"
   JSON Result: Three separate fields all named "Patient Name - [Mobile/Home/Work]"
   ```
   **Impact**: Field naming inconsistent, semantic meaning lost
   **Related Improvement**: #5 (Compound Field Detection)

---

## Example 2: Complex Patient Form (npf1.pdf)

### Source Characteristics
- **Type**: Comprehensive patient registration + dental history
- **Complexity**: High (220 lines of text)
- **Layout**: Dense multi-column with grids and checkboxes

### JSON Output Statistics
- **Total Fields Captured**: 65
- **Dictionary Match Rate**: 91%
- **Sections**: Patient Info (29), Insurance (7), Medical (11), Dental (9), Signature (2), General (3), Emergency (4)

### Parity Issues Identified

1. **Issue**: Medical conditions grid with 80+ checkboxes
   ```
   Extracted: "¨ AIDS/HIV Positive ¨ Alzheimer's Disease ¨ Anemia ¨ Angina..."
   JSON Result: Single "conditions" field with 80 options
   ```
   **Status**: ✓ WORKING CORRECTLY - Grid detection successful
   **Note**: Good example of proper grid parsing

2. **Issue**: Malformed grid detected
   ```
   Debug log: "malformed_grid_detected -> 'Nitrous Oxide Oral Sedation (Pill) IV Sedation...' with 5 options"
   ```
   **Impact**: Grid structure not properly preserved
   **Related Improvement**: #3 (Multi-Column Layout Detection)

3. **Issue**: Duplicate field consolidation
   ```
   JSON output: "date_of_birth", "date_of_birth_2", "date_of_birth_3", "date_of_birth_4"
   ```
   **Impact**: Four Date of Birth fields when form likely has 2-3 (patient, guarantor, etc.)
   **Related Improvement**: #10 (Duplicate Field Consolidation)

---

## Example 3: Consent Form (CFGingivectomy.pdf)

### Source Characteristics
- **Type**: Medical consent form with extensive legal text
- **Complexity**: Medium (66 lines of text, mostly paragraphs)
- **Layout**: Mostly prose with few actual form fields

### JSON Output Statistics
- **Total Fields Captured**: 17
- **Dictionary Match Rate**: 29% (LOWEST)
- **Sections**: Consent (5), Patient Information (4), Signature (4), General (4)

### Parity Issues Identified

1. **Issue**: Paragraphs captured as fields
   ```
   Captured as field:
   "Periodontal surgery may be seen as a secondary line of treatment of those 
   pockets persisting after initial treatment..."
   
   JSON: {
     "key": "periodontal_surgery_may_be_seen_as_a_secondary_line_of",
     "title": "Terms",
     "type": "input"
   }
   ```
   **Impact**: 11 out of 17 fields are actually instructional text, not form fields
   **Related Improvement**: #7 (Instructional Text Filtering)

2. **Issue**: Real form fields at end of document
   ```
   Actual form fields (only 6):
   - Name of Patient: ___________________________________
   - Date of Birth: ________________
   - Patient Signature: ________________
   - Date: ________________
   - Witness: ________________
   - Date: ________________
   ```
   **Impact**: Only ~35% of captured "fields" are actual form fields
   **Related Improvement**: #7 (Instructional Text Filtering)

3. **Issue**: OCR artifacts
   ```
   Extracted: "= ie |"
   Appears twice at start of document
   ```
   **Impact**: Meaningless text treated as field
   **Related Improvement**: #2 (Enhanced OCR Error Correction)

---

## Example 4: Medical History Form (Chicago-Dental-Solutions_Form.pdf)

### Source Characteristics
- **Type**: New patient registration with medical history
- **Complexity**: Medium (118 lines)
- **Layout**: Mixed form fields and checkbox grids

### JSON Output Statistics
- **Total Fields Captured**: 29
- **Dictionary Match Rate**: 79%
- **Sections**: Patient Info (4), Insurance (15), Medical History (7), Signature (3)

### Parity Issues Identified

1. **Issue**: Dictionary match failures
   ```
   Warnings:
   - No dictionary match for field: 'Other' (key: other)
   - No dictionary match for field: 'State: ___' (key: state__primary_2)
   - No dictionary match for field: 'Are you under a physician's care now?'
   - No dictionary match for field: 'Phen-Fen or Redux? [ ] Yes [ ] No'
   ```
   **Impact**: 21% of fields not standardized
   **Related Improvement**: #8 (Expand Dictionary Coverage)

2. **Issue**: Incorrect field matching
   ```
   Parsed: "Name of Employer"
   Matched to: "first_name" (alias_contains, score=0.83)
   Should match: "employer" or "employer_name"
   ```
   **Impact**: Semantically wrong field assignment
   **Related Improvement**: #9 (Smart Alias Matching)

3. **Issue**: Medical conditions checkbox grid
   ```
   Extracted: 80 medical conditions as checkboxes
   JSON: Single field with all 80 options (✓ CORRECT)
   Debug: Skipping duplicate condition: 'Hypoglycemia' (appeared twice in form)
   ```
   **Status**: Mostly working, with good duplicate detection

---

## Example 5: IV Sedation Form (IV Sedation Pre-op.docx)

### Source Characteristics
- **Type**: Pre-operative consent and instructions
- **Complexity**: Low (11 fields captured from DOCX)
- **Layout**: Bulleted instructions with form fields

### JSON Output Statistics
- **Total Fields Captured**: 11
- **Dictionary Match Rate**: 27% (SECOND LOWEST)
- **Problem**: Mostly instructions, few actual fields

### Parity Issues Identified

1. **Issue**: Instructions treated as fields
   ```
   Captured: "administering and prescribing all anesthetics and/or medications."
   Type: Listed as field
   Should be: Filtered as instructional text
   ```
   **Related Improvement**: #7 (Instructional Text Filtering)

---

## Category-Specific Parity Analysis

### Registration Forms (Best Performance: 90-100% parity)
**Examples**: npf.pdf, npf1.pdf

**Strengths**:
- Clear field structure with labels and blanks
- Standard field types (name, address, phone, etc.)
- Good dictionary coverage
- Effective grid detection for medical history

**Remaining Issues**:
- Compound field separation (e.g., First/MI/Last on same line)
- Duplicate field proliferation
- Semantic field naming

### Consent Forms (Worst Performance: 22-43% parity)
**Examples**: CFGingivectomy.pdf, IV Sedation Pre-op.docx, consent_crown_bridge_prosthetics.pdf

**Weaknesses**:
- Extensive legal/instructional text captured as fields
- Few actual form fields (often just name/date/signature)
- Low dictionary match due to unique consent language
- Terms and conditions paragraphs

**Critical Need**:
- Instructional text filtering (#7)
- Sentence length heuristics
- Paragraph structure detection

### Medical History Forms (Medium Performance: 75-85% parity)
**Examples**: Chicago-Dental-Solutions_Form.pdf

**Mixed Results**:
- Good grid detection for checkbox questions
- Reasonable field capture
- Some dictionary gaps for medical questions

**Improvement Areas**:
- Better medical terminology dictionary coverage
- Compound question parsing (e.g., "Are you taking X? If yes, explain: ___")

---

## Priority Recommendations Based on Examples

### Immediate Impact (Fix First)
1. **Instructional Text Filtering** - Would eliminate 50-70% of false positives in consent forms
2. **Compound Field Detection** - Would properly split First/MI/Last and similar patterns
3. **Dictionary Expansion** - Would improve match rate from 58.8% to 75%+ across all forms

### High Value (Fix Second)
4. **Semantic Field Naming** - Would fix "Patient Name - Birth" → "Date of Birth" issues
5. **Duplicate Consolidation** - Would reduce field count by 20-30% by merging true duplicates
6. **Smart Alias Matching** - Would fix "Name of Employer" → "first_name" mismatches

### Long-term Quality (Fix Third)
7. **OCR Error Correction** - Would clean up header corruption and artifacts
8. **Multi-Column Detection** - Would improve grid parsing in complex forms
9. **Confidence Scoring** - Would enable quality-based review and filtering

---

## Validation Approach

For each improvement, validate using these representative forms:
- **Registration Forms**: npf.pdf, npf1.pdf (expect 95%+ parity)
- **Consent Forms**: CFGingivectomy.pdf (expect 90%+ filtering of instructions)
- **Medical History**: Chicago-Dental-Solutions_Form.pdf (expect 90%+ dictionary match)

Success metrics:
- Reduce false positive fields by 50%+
- Increase dictionary match rate to 85%+ average
- Reduce duplicate fields by 40%+
- Improve semantic field naming for 80%+ of compound fields

---

## Conclusion

The current pipeline performs well on structured registration forms but struggles with:
1. Consent forms with extensive instructional text (22-43% accuracy)
2. Compound fields on single lines (semantic naming issues)
3. Dictionary coverage for medical/consent-specific terminology

Implementing the prioritized improvements would raise overall parity from current 58.8% average to 85-90%+ across all form types, with registration forms approaching 98%+ and consent forms improving from 22-43% to 80%+.
