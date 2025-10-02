# Archivev6 Issues - Visual Examples

This document provides clear before/after examples of each issue found in the Archivev6 analysis.

---

## Issue 1: Checkbox Markers in Field Titles

### Example 1: "How did you hear about us?"

**TXT Input:**
```
How did you hear about us?
[ ] I live/work in area [ ] Google [ ] Yelp [ ] Social Media
```

**Current JSON Output (WRONG):**
```json
{
  "key": "i_livework_in_area_google_yelp_social_media",
  "title": "[ ] I live/work in area [ ] Google [ ] Yelp [ ] Social Media",
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "I live/work in area", "value": "i_livework_in_area"},
      {"name": "Google", "value": "google"},
      {"name": "Yelp", "value": "yelp"},
      {"name": "Social Media", "value": "social_media"}
    ]
  }
}
```

**Expected JSON Output (CORRECT):**
```json
{
  "key": "how_did_you_hear_about_us",
  "title": "How did you hear about us?",
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "I live/work in area", "value": "i_livework_in_area"},
      {"name": "Google", "value": "google"},
      {"name": "Yelp", "value": "yelp"},
      {"name": "Social Media", "value": "social_media"}
    ]
  }
}
```

**What Changed:**
- ✅ Title changed from `"[ ] I live/work..."` to `"How did you hear about us?"`
- ✅ Key changed to match clean title
- ✅ Options remain the same (already correct)

---

### Example 2: Women's Health Question

**TXT Input:**
```
Women are you : [ ] Pregnant [ ] Trying to get pregnant [ ] Nursing [ ] Taking oral contraceptives
```

**Current JSON Output (WRONG):**
```json
{
  "key": "women_are_you_pregnant_trying_to_get_pregnant_nursing_taking_ora",
  "title": "Women are you : [ ] Pregnant [ ] Trying to get pregnant [ ] Nursing [ ] Taking oral contraceptives",
  "type": "dropdown"
}
```

**Expected JSON Output (CORRECT):**
```json
{
  "key": "women_are_you",
  "title": "Women are you:",
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Pregnant", "value": "pregnant"},
      {"name": "Trying to get pregnant", "value": "trying_to_get_pregnant"},
      {"name": "Nursing", "value": "nursing"},
      {"name": "Taking oral contraceptives", "value": "taking_oral_contraceptives"}
    ]
  }
}
```

**What Changed:**
- ✅ Title changed from `"Women are you : [ ] Pregnant..."` to `"Women are you:"`
- ✅ Removed checkbox markers from title
- ✅ Options remain properly extracted

---

## Issue 2: Missing Follow-up Fields

### Example: Physician Care Question

**TXT Input:**
```
Are you under a physician's care now? [ ] Yes [ ] No           If yes, please explain:
```

**Current JSON Output (INCOMPLETE):**
```json
{
  "key": "are_you_under_a_physicians_care_now",
  "title": "Are you under a physician's care now?",
  "type": "radio",
  "control": {
    "options": [
      {"name": "Yes", "value": true},
      {"name": "No", "value": false}
    ]
  }
}
```

**Expected JSON Output (COMPLETE):**
```json
[
  {
    "key": "are_you_under_a_physicians_care_now",
    "title": "Are you under a physician's care now?",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Yes", "value": true},
        {"name": "No", "value": false}
      ]
    }
  },
  {
    "key": "are_you_under_a_physicians_care_now_details",
    "title": "Are you under a physician's care now? - Please explain",
    "type": "input",
    "control": {
      "input_type": "text"
    }
  }
]
```

**What Changed:**
- ✅ Added SECOND field for explanation
- ✅ Follow-up field is text input type
- ✅ Original Y/N field unchanged

**This pattern should apply to ALL 4 questions:**
1. Are you under a physician's care now?
2. Have you ever been hospitalized/had major surgery?
3. Have you ever had a serious head/neck injury?
4. Are you taking any medications, pills or drugs?

---

## Issue 3: Text Concatenation in Grid Layouts

### Example: npf Form - Malformed Medical Conditions

**TXT Input:**
```
[ ] Artificial Angina (chest Heart pain) Valve [ ] Thyroid Disease Neurological [ ] Anxiety
```

**Current JSON Output (WRONG):**
```json
{
  "title": "[ ] Artificial Angina (chest Heart pain) Valve [ ] Thyroid Disease Neurological [ ] Anxiety [ ] Tuberculosis [ ] Latex Local Anesthetics",
  "control": {
    "options": [
      {"name": "Artificial Angina (chest Heart pain) Valve"},
      {"name": "Thyroid Disease Neurological"},
      {"name": "Anxiety"},
      {"name": "Tuberculosis"},
      {"name": "Latex Local Anesthetics"}
    ]
  }
}
```

**Expected JSON Output (CORRECT):**
```json
{
  "title": "Medical Conditions",
  "control": {
    "options": [
      {"name": "Artificial Heart Valve"},
      {"name": "Angina (chest pain)"},
      {"name": "Thyroid Disease"},
      {"name": "Anxiety"},
      {"name": "Tuberculosis"},
      {"name": "Latex allergy"},
      {"name": "Local Anesthetics allergy"}
    ]
  }
}
```

**What Changed:**
- ✅ Separated merged concepts (e.g., "Artificial" + "Valve" was merging with "Angina")
- ✅ Removed category headers that got mixed in (e.g., "Neurological")
- ✅ Clean, readable option labels

---

## Issue 4: Orphaned Checkbox Data Loss

### Example: Medical Conditions with Missing Items

**TXT Input:**
```
[ ]                       [ ]                               [ ]                           [ ]                          [ ] Sickle Cell Disease 
   Anemia                    Convulsions                       Hay Fever                    Leukemia                   [ ] Sinus Trouble
```

**Current JSON Output (INCOMPLETE):**
```json
{
  "title": "Do you have, or have you had, any of the following?",
  "control": {
    "options": [
      {"name": "AIDS/HIV Positive"},
      {"name": "Chest Pains"},
      ...
      {"name": "Sickle Cell Disease"},
      {"name": "Sinus Trouble"},
      ...
    ]
  }
}
```

**Missing Items:** Anemia, Convulsions, Hay Fever, Leukemia

**Expected JSON Output (COMPLETE):**
```json
{
  "title": "Do you have, or have you had, any of the following?",
  "control": {
    "options": [
      {"name": "AIDS/HIV Positive"},
      {"name": "Chest Pains"},
      ...
      {"name": "Anemia"},          ← ADDED
      {"name": "Convulsions"},     ← ADDED
      {"name": "Hay Fever"},       ← ADDED
      {"name": "Leukemia"},        ← ADDED
      {"name": "Sickle Cell Disease"},
      {"name": "Sinus Trouble"},
      ...
    ]
  }
}
```

**What Changed:**
- ✅ Detected orphaned checkboxes on line 1
- ✅ Associated with labels on line 2
- ✅ Added 4 missing medical conditions

---

## Issue 5: Title Cleaning Edge Cases

### Example: Minor Artifacts

**Current Issues:**
- Double spaces: `"Title    with    spaces"`
- Trailing checkbox: `"Question text [ ]"`
- Extra colons: `"Label : :"`

**After Fix:**
- `"Title with spaces"`
- `"Question text"`
- `"Label"`

---

## Summary Table

| Issue | Severity | Forms Affected | Fix Complexity | Visual Impact |
|-------|----------|----------------|----------------|---------------|
| 1. Checkbox markers in titles | HIGH | All 3 | LOW-MEDIUM | Very visible |
| 2. Missing follow-up fields | HIGH | Chicago | LOW | Functionality gap |
| 3. Text concatenation | HIGH | npf | HIGH | Data quality |
| 4. Orphaned checkboxes | MEDIUM | Chicago | LOW-MEDIUM | Data loss |
| 5. Title cleaning | LOW | All 3 | LOW | Polish |

---

## Key Takeaway

All issues are **fixable with general pattern matching**. No form-specific hard-coding needed.

The recommended fixes in `ARCHIVEV6_TECHNICAL_RECOMMENDATIONS.md` provide the exact code patterns to implement these changes.
