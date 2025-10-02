# Archivev7 Visual Examples - Before & After

This document shows concrete examples of issues found in Archivev7 analysis with exact TXT input and current JSON output, plus expected JSON output.

---

## Example 1: Grid/Table Layout - Medical Conditions (npf1)

### TXT Input (lines 94-100)

```
Medical History - Please mark (x) to your response to indicate if you have or have had any of the following
Cancer                           Endocrinology                   Musculoskeletal                Respiratory                 Medical Allergies
Type                              [ ] Diabetes                   [ ] Arthritis                   [ ] Asthma                  [ ] Antibiotics
[ ] Chemotherapy                 [ ] Hepatitis A/B/C            [ ] Artificial Joints           [ ] Emphysema              (Penicillin/Amoxicillin /Clindamycin)
[ ] Radiation Therapy            [ ] Jaundice                   [ ] Jaw Joint Pain              [ ] Respiratory Problems [ ] Opioids
                                 [ ] Kidney Disease             [ ] Rheumatoid Arthritis        [ ] Sinus Problems                     Oxycodone, Tylenol 3)
Cardiovascular [ ]               [ ] Liver Disease                                              [ ] Sleep Apnea            (Percocet, [ ]
[ ] Artificial Angina (chest Heart pain) Valve [ ] Thyroid Disease Neurological [ ] Anxiety     [ ] Tuberculosis            [ ] Latex Local Anesthetics
```

### Current JSON Output (❌ WRONG)

```json
{
  "key": "artificial_angina_chest_heart_pain_valve_thyroid_disease_neur",
  "title": "Artificial Angina (chest Heart pain) Valve Thyroid Disease Neurological Anxiety Tuberculosis Latex Local Anesthetics",
  "section": "Medical History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {
        "name": "Artificial Valve",
        "value": "artificial_valve"
      },
      {
        "name": "Thyroid Disease",
        "value": "thyroid_disease"
      },
      {
        "name": "Anxiety",
        "value": "anxiety"
      },
      {
        "name": "Tuberculosis",
        "value": "tuberculosis"
      },
      {
        "name": "Latex Local Anesthetics",
        "value": "latex_local_anesthetics"
      }
    ],
    "multi": true
  }
}
```

**Problems:**
- Title is a nonsensical concatenation
- Options are partially correct but context is lost
- Missing many conditions from the grid
- Creates 6 separate malformed dropdowns instead of 1 organized one

### Expected JSON Output (✅ CORRECT)

**Option A: Single Consolidated Dropdown**
```json
{
  "key": "medical_conditions",
  "title": "Do you have or have you had any of the following medical conditions?",
  "section": "Medical History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Chemotherapy", "value": "chemotherapy"},
      {"name": "Radiation Therapy", "value": "radiation_therapy"},
      {"name": "Diabetes", "value": "diabetes"},
      {"name": "Hepatitis A/B/C", "value": "hepatitis_abc"},
      {"name": "Jaundice", "value": "jaundice"},
      {"name": "Kidney Disease", "value": "kidney_disease"},
      {"name": "Liver Disease", "value": "liver_disease"},
      {"name": "Thyroid Disease", "value": "thyroid_disease"},
      {"name": "Arthritis", "value": "arthritis"},
      {"name": "Artificial Joints", "value": "artificial_joints"},
      {"name": "Jaw Joint Pain", "value": "jaw_joint_pain"},
      {"name": "Rheumatoid Arthritis", "value": "rheumatoid_arthritis"},
      {"name": "Asthma", "value": "asthma"},
      {"name": "Emphysema", "value": "emphysema"},
      {"name": "Respiratory Problems", "value": "respiratory_problems"},
      {"name": "Sinus Problems", "value": "sinus_problems"},
      {"name": "Sleep Apnea", "value": "sleep_apnea"},
      {"name": "Tuberculosis", "value": "tuberculosis"},
      {"name": "Artificial Valve", "value": "artificial_valve"},
      {"name": "Anxiety", "value": "anxiety"}
    ],
    "multi": true
  }
}
```

**Option B: Organized by Category** (Better for UX)
```json
{
  "key": "cancer_conditions",
  "title": "Cancer - Please mark any that apply",
  "section": "Medical History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Chemotherapy", "value": "chemotherapy"},
      {"name": "Radiation Therapy", "value": "radiation_therapy"}
    ],
    "multi": true
  }
},
{
  "key": "endocrinology_conditions",
  "title": "Endocrinology - Please mark any that apply",
  "section": "Medical History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Diabetes", "value": "diabetes"},
      {"name": "Hepatitis A/B/C", "value": "hepatitis_abc"},
      {"name": "Jaundice", "value": "jaundice"},
      {"name": "Kidney Disease", "value": "kidney_disease"},
      {"name": "Liver Disease", "value": "liver_disease"},
      {"name": "Thyroid Disease", "value": "thyroid_disease"}
    ],
    "multi": true
  }
},
{
  "key": "musculoskeletal_conditions",
  "title": "Musculoskeletal - Please mark any that apply",
  "section": "Medical History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Arthritis", "value": "arthritis"},
      {"name": "Artificial Joints", "value": "artificial_joints"},
      {"name": "Jaw Joint Pain", "value": "jaw_joint_pain"},
      {"name": "Rheumatoid Arthritis", "value": "rheumatoid_arthritis"}
    ],
    "multi": true
  }
},
{
  "key": "respiratory_conditions",
  "title": "Respiratory - Please mark any that apply",
  "section": "Medical History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Asthma", "value": "asthma"},
      {"name": "Emphysema", "value": "emphysema"},
      {"name": "Respiratory Problems", "value": "respiratory_problems"},
      {"name": "Sinus Problems", "value": "sinus_problems"},
      {"name": "Sleep Apnea", "value": "sleep_apnea"},
      {"name": "Tuberculosis", "value": "tuberculosis"}
    ],
    "multi": true
  }
}
```

---

## Example 2: Multiple Questions on Same Line (Chicago-Dental-Solutions)

### TXT Input (line 16)

```
Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single [ ] Other:
```

### Current JSON Output (❌ WRONG)

**No fields created - completely missing from JSON!**

### Expected JSON Output (✅ CORRECT)

```json
{
  "key": "gender",
  "title": "Gender",
  "section": "Patient Information",
  "optional": false,
  "type": "radio",
  "control": {
    "options": [
      {
        "name": "Male",
        "value": "male"
      },
      {
        "name": "Female",
        "value": "female"
      }
    ]
  }
},
{
  "key": "marital_status",
  "title": "Marital Status",
  "section": "Patient Information",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {
        "name": "Married",
        "value": "married"
      },
      {
        "name": "Single",
        "value": "single"
      },
      {
        "name": "Other",
        "value": "other"
      }
    ],
    "multi": false
  }
}
```

---

## Example 3: "If Yes" Follow-up Missing (Chicago-Dental-Solutions)

### TXT Input (lines 69-72)

```
Are you under a physician's care now? [ ] Yes [ ] No           If yes, please explain:
Have you ever been hospitalized/ had major surgery? [ ] Yes [ ] No       If yes, please explain:
Have you ever had a serious head/ neck injury? [ ] Yes [ ] No      If yes, please explain:
Are you taking any medications, pills or drugs? [ ] Yes [ ] No    If yes, please explain:
```

### Current JSON Output (❌ PARTIAL)

**These questions are completely missing from the JSON output!**

Only 1 unrelated conditional field exists in the entire form.

### Expected JSON Output (✅ CORRECT)

```json
{
  "key": "physician_care_now",
  "title": "Are you under a physician's care now?",
  "section": "Medical History",
  "optional": false,
  "type": "radio",
  "control": {
    "options": [
      {
        "name": "Yes",
        "value": "yes"
      },
      {
        "name": "No",
        "value": "no"
      }
    ]
  }
},
{
  "if": [
    {
      "key": "physician_care_now",
      "value": "yes"
    }
  ],
  "key": "physician_care_now_explanation",
  "title": "Please explain",
  "section": "Medical History",
  "optional": false,
  "type": "input",
  "control": {
    "input_type": "text",
    "hint": "Please provide details"
  }
},
{
  "key": "hospitalized_major_surgery",
  "title": "Have you ever been hospitalized or had major surgery?",
  "section": "Medical History",
  "optional": false,
  "type": "radio",
  "control": {
    "options": [
      {
        "name": "Yes",
        "value": "yes"
      },
      {
        "name": "No",
        "value": "no"
      }
    ]
  }
},
{
  "if": [
    {
      "key": "hospitalized_major_surgery",
      "value": "yes"
    }
  ],
  "key": "hospitalized_major_surgery_explanation",
  "title": "Please explain",
  "section": "Medical History",
  "optional": false,
  "type": "input",
  "control": {
    "input_type": "text",
    "hint": "Please provide details"
  }
},
{
  "key": "head_neck_injury",
  "title": "Have you ever had a serious head/neck injury?",
  "section": "Medical History",
  "optional": false,
  "type": "radio",
  "control": {
    "options": [
      {
        "name": "Yes",
        "value": "yes"
      },
      {
        "name": "No",
        "value": "no"
      }
    ]
  }
},
{
  "if": [
    {
      "key": "head_neck_injury",
      "value": "yes"
    }
  ],
  "key": "head_neck_injury_explanation",
  "title": "Please explain",
  "section": "Medical History",
  "optional": false,
  "type": "input",
  "control": {
    "input_type": "text",
    "hint": "Please provide details"
  }
},
{
  "key": "medications",
  "title": "Are you taking any medications, pills or drugs?",
  "section": "Medical History",
  "optional": false,
  "type": "radio",
  "control": {
    "options": [
      {
        "name": "Yes",
        "value": "yes"
      },
      {
        "name": "No",
        "value": "no"
      }
    ]
  }
},
{
  "if": [
    {
      "key": "medications",
      "value": "yes"
    }
  ],
  "key": "medications_explanation",
  "title": "Please list all medications",
  "section": "Medical History",
  "optional": false,
  "type": "input",
  "control": {
    "input_type": "text",
    "hint": "Include dosage and frequency"
  }
}
```

---

## Example 4: Grid Checkboxes in Table Format (npf1, lines 76-78)

### TXT Input

```
Appearance                            Function                                    Habits                                   Previous Comfort Options
[ ] Discolored teeth                 [ ] Grinding/Clenching                       [ ] Thumb sucking                       [ ] Nitrous Oxide
[ ] Worn teeth                        [ ] Headaches                               [ ] Nail-biting                         [ ] Oral Sedation (Pill)
[ ] Misshaped teeth                  [ ] Jaw Joint (TMJ) pain                     [ ] Cheek/Lip biting                    [ ] IV Sedation
[ ] Crooked teeth                     [ ] Jaw Joint (TMJ) clicking/popping        [ ] Chewing on ice/foreign objects
[ ] Spaces                           [ ] Bad Bite
```

### Current JSON Output (❌ WRONG)

Creates multiple malformed dropdowns with confused titles and options.

### Expected JSON Output (✅ CORRECT)

```json
{
  "key": "dental_appearance_concerns",
  "title": "Appearance - Please mark any that apply",
  "section": "Dental History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Discolored teeth", "value": "discolored_teeth"},
      {"name": "Worn teeth", "value": "worn_teeth"},
      {"name": "Misshaped teeth", "value": "misshaped_teeth"},
      {"name": "Crooked teeth", "value": "crooked_teeth"},
      {"name": "Spaces", "value": "spaces"}
    ],
    "multi": true
  }
},
{
  "key": "dental_function_issues",
  "title": "Function - Please mark any that apply",
  "section": "Dental History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Grinding/Clenching", "value": "grinding_clenching"},
      {"name": "Headaches", "value": "headaches"},
      {"name": "Jaw Joint (TMJ) pain", "value": "tmj_pain"},
      {"name": "Jaw Joint (TMJ) clicking/popping", "value": "tmj_clicking"},
      {"name": "Bad Bite", "value": "bad_bite"}
    ],
    "multi": true
  }
},
{
  "key": "dental_habits",
  "title": "Habits - Please mark any that apply",
  "section": "Dental History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Thumb sucking", "value": "thumb_sucking"},
      {"name": "Nail-biting", "value": "nail_biting"},
      {"name": "Cheek/Lip biting", "value": "cheek_lip_biting"},
      {"name": "Chewing on ice/foreign objects", "value": "chewing_ice"}
    ],
    "multi": true
  }
},
{
  "key": "previous_comfort_options",
  "title": "Previous Comfort Options - Please mark any that apply",
  "section": "Dental History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "Nitrous Oxide", "value": "nitrous_oxide"},
      {"name": "Oral Sedation (Pill)", "value": "oral_sedation"},
      {"name": "IV Sedation", "value": "iv_sedation"}
    ],
    "multi": true
  }
}
```

---

## Example 5: Simple Inline Grid (Working Correctly ✅)

### TXT Input (Chicago-Dental-Solutions, line 26)

```
[ ] I live/work in area [ ] Google        [ ] Yelp     [ ] Social Media
```

### Current JSON Output (✅ CORRECT)

```json
{
  "key": "how_did_you_hear_about_us",
  "title": "How did you hear about us?",
  "section": "Dental History",
  "optional": false,
  "type": "dropdown",
  "control": {
    "options": [
      {
        "name": "I live/work in area",
        "value": "i_livework_in_area"
      },
      {
        "name": "Google",
        "value": "google"
      },
      {
        "name": "Yelp",
        "value": "yelp"
      },
      {
        "name": "Social Media",
        "value": "social_media"
      }
    ],
    "multi": true
  }
}
```

**This works because:** It's a single-line, single-question format with inline checkboxes. The current parser handles this well.

---

## Example 6: Multi-Location Junk (Working Correctly ✅)

### TXT Input (Chicago-Dental-Solutions, lines 57-59)

```
LINCOLN DENTAL CARE                     MIDWAY SQUARE DENTAL CENTER                   CHICAGO DENTAL DESIGN
3138 N Lincoln Ave Chicago, IL                   5109B S Pulaski Rd.                   845 N Michigan Ave Suite 945W
     60657                                    Chicago, IL 60632                         Chicago, IL 60611
```

### Current JSON Output (✅ CORRECT)

**Not present in JSON** - correctly filtered as junk text!

The junk filtering is working as intended for multi-location footer lines.

---

## Summary of Examples

| Example | Issue Type | Status | Priority |
|---------|-----------|--------|----------|
| 1 | Grid/Table Medical Conditions | ❌ Critical | P1 |
| 2 | Multiple Questions on One Line | ❌ High | P1 |
| 3 | "If Yes" Follow-ups Missing | ❌ Medium | P2 |
| 4 | Grid/Table Dental History | ❌ Critical | P1 |
| 5 | Simple Inline Grid | ✅ Working | - |
| 6 | Multi-Location Junk | ✅ Working | - |

**Key Insight:** The parser handles single-line, single-question grids well, but fails on:
1. Multi-question single lines
2. Multi-row table/grid structures
3. Some "if yes" patterns (inconsistent)
