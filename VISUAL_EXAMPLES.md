# Visual Examples of Identified Issues

This document provides clear visual examples of each issue found in the PDF-to-JSON conversion.

---

## Issue 1: Grid/Multi-Column Checkboxes 🔴

### Current TXT Input:
```
[ ] AIDS/HIV Positive      [ ] Chest Pains        [ ] Frequent Headaches
[ ] Alzheimer's Disease    [ ] Cold Sores         [ ] Genital Herpes
```

### Current JSON Output (WRONG):
```json
[
  {
    "key": "aidshiv_positive_chest_pains_frequent_headaches",
    "options": [
      {"name": "AIDS/HIV Positive [ ] Chest Pains [ ] Frequent Headaches"}
    ]
  },
  {
    "key": "alzheimers_disease_cold_sores_genital_herpes",
    "options": [
      {"name": "Alzheimer's Disease [ ] Cold Sores [ ] Genital Herpes"}
    ]
  }
]
```

### Expected JSON Output (CORRECT):
```json
{
  "key": "medical_conditions",
  "title": "Do you have any of the following?",
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "AIDS/HIV Positive", "value": "aids_hiv_positive"},
      {"name": "Chest Pains", "value": "chest_pains"},
      {"name": "Frequent Headaches", "value": "frequent_headaches"},
      {"name": "Alzheimer's Disease", "value": "alzheimers_disease"},
      {"name": "Cold Sores", "value": "cold_sores"},
      {"name": "Genital Herpes", "value": "genital_herpes"}
    ],
    "multi": true
  }
}
```

**Impact**: Critical - Users can't select individual conditions properly

---

## Issue 2: Orphaned Checkboxes 🔴

### Current TXT Input:
```
[ ]                    [ ]                    [ ]
Anemia                 Convulsions            Hay Fever
```

### Current JSON Output (WRONG):
```json
{
  "key": "q",
  "title": "[ ] [ ] [ ]",
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "[ ] [ ] [ ]"}
    ]
  }
}
```

### Expected JSON Output (CORRECT):
```json
{
  "key": "medical_conditions",
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Anemia", "value": "anemia"},
      {"name": "Convulsions", "value": "convulsions"},
      {"name": "Hay Fever", "value": "hay_fever"}
    ],
    "multi": true
  }
}
```

**Impact**: Critical - Loses condition information entirely

---

## Issue 3: Business Address Junk 🔴

### Current TXT Input:
```
3138 N Lincoln Ave Chicago, IL    5109B S Pulaski Rd.    845 N Michigan Ave Suite 945W
60657                              Chicago, IL 60632      Chicago, IL 60611
```

### Current JSON Output (WRONG):
```json
[
  {
    "key": "q_3138_n_lincoln_ave_chicago_il_5109b_s_pulaski_rd",
    "title": "3138 N Lincoln Ave Chicago, IL 5109B S Pulaski Rd. 845 N Michigan Ave Suite 945W",
    "type": "input"
  },
  {
    "key": "q_60657_chicago_il_60632_chicago_il_60611",
    "title": "60657 Chicago, IL 60632 Chicago, IL 60611",
    "type": "input"
  }
]
```

### Expected JSON Output (CORRECT):
```json
// These lines should be filtered out - no JSON output
```

**Impact**: Critical - Creates meaningless form fields

---

## Issue 4: Missing Follow-up Fields 🔴

### Current TXT Input:
```
Are you under a physician's care now? [ ] Yes [ ] No    If yes, please explain:
```

### Current JSON Output (WRONG):
```json
{
  "key": "are_you_under_physician_care",
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

### Expected JSON Output (CORRECT):
```json
[
  {
    "key": "are_you_under_physician_care",
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
    "key": "are_you_under_physician_care_explanation",
    "title": "If yes, please explain",
    "type": "input",
    "control": {
      "input_type": "text"
    }
  }
]
```

**Impact**: Critical - Users can't provide required explanations

---

## Issue 5: Multi-line Question Wrapping 🟡

### Current TXT Input:
```
Have you ever taken Fosamax, Boniva, Actonel/  [ ] Yes [ ] No
other medications containing bisphosphonates?
```

### Current JSON Output (WRONG):
```json
[
  {
    "key": "have_you_ever_taken_fosamax_boniva_actonel",
    "title": "Have you ever taken Fosamax, Boniva, Actonel/",
    "type": "radio"
  },
  {
    "key": "other_medications_containing_bisphosphonates",
    "title": "other medications containing bisphosphonates?",
    "type": "input"
  }
]
```

### Expected JSON Output (CORRECT):
```json
{
  "key": "have_you_ever_taken_fosamax_boniva_actonel_other_medications",
  "title": "Have you ever taken Fosamax, Boniva, Actonel/other medications containing bisphosphonates?",
  "type": "radio",
  "control": {
    "options": [
      {"name": "Yes", "value": true},
      {"name": "No", "value": false}
    ]
  }
}
```

**Impact**: Important - Splits single question into multiple fields

---

## Issue 6: Consent Checkbox Merging 🟡

### Current TXT Input:
```
Cell Phone: _______________    [ ] Yes, send me Text Message alerts
```

### Current JSON Output (WRONG):
```json
{
  "key": "cell_phone",
  "title": "Cell Phone: [ ] Yes, send me Text Message alerts",
  "type": "input",
  "control": {
    "input_type": "phone"
  }
}
```

### Expected JSON Output (CORRECT):
```json
[
  {
    "key": "cell_phone",
    "title": "Cell Phone",
    "type": "input",
    "control": {
      "input_type": "phone"
    }
  },
  {
    "key": "consent_text_alerts",
    "title": "Yes, send me Text Message alerts",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Yes", "value": true},
        {"name": "No", "value": false}
      ]
    }
  }
]
```

**Impact**: Important - Loses opt-in information

---

## Issue 7: Multiple Condition Dropdowns 🟡

### Current JSON Output (WRONG):
```json
[
  {
    "key": "do_you_have_any_of_the_following",
    "options": [...]
  },
  {
    "key": "asthma_emphysema_hemophilia",
    "options": [...]
  },
  {
    "key": "breathing_problem_excessive_thirst",
    "options": [...]
  }
]
```

### Expected JSON Output (CORRECT):
```json
{
  "key": "medical_conditions",
  "title": "Do you have any of the following?",
  "type": "dropdown",
  "control": {
    "options": [
      // ALL conditions in ONE dropdown
      {"name": "Asthma", "value": "asthma"},
      {"name": "Emphysema", "value": "emphysema"},
      {"name": "Hemophilia", "value": "hemophilia"},
      {"name": "Breathing Problem", "value": "breathing_problem"},
      {"name": "Excessive Thirst", "value": "excessive_thirst"}
    ],
    "multi": true
  }
}
```

**Impact**: Important - Inconsistent form structure

---

## Issue 8: Long Paragraphs Not Terms 🟡

### Current TXT Input:
```
To the best of my knowledge, the questions on this form have been accurately 
answered. I understand that providing incorrect information can be dangerous 
to my health. It is my responsibility to inform the dental official of any 
changes in medical status.
```

### Current JSON Output (WRONG):
```json
{
  "key": "to_the_best_of_my_knowledge",
  "title": "To the best of my knowledge, the questions on this form...",
  "type": "input"
}
```

### Expected JSON Output (CORRECT):
```json
{
  "key": "patient_acknowledgment",
  "title": "Terms",
  "type": "terms",
  "control": {
    "agree_text": "I have read and agree to the terms.",
    "html_text": "To the best of my knowledge, the questions on this form have been accurately answered. I understand that providing incorrect information can be dangerous to my health. It is my responsibility to inform the dental official of any changes in medical status."
  }
}
```

**Impact**: Important - Loses legal consent structure

---

## Summary of Impact

| Issue | Priority | Impact | Forms Affected |
|-------|----------|--------|----------------|
| Grid checkboxes | 🔴 Critical | Data loss | All 3 |
| Orphaned checkboxes | 🔴 Critical | Data loss | All 3 |
| Junk text | 🔴 Critical | Invalid fields | All 3 |
| Follow-up fields | 🔴 Critical | Missing data | All 3 |
| Line wrapping | 🟡 Important | Field splitting | 2 of 3 |
| Consent merging | 🟡 Important | Data structure | 2 of 3 |
| Multiple dropdowns | 🟡 Important | Inconsistency | All 3 |
| Terms detection | 🟡 Important | Legal issues | 2 of 3 |

All issues are fixable with general pattern matching - no form-specific hard-coding needed.
