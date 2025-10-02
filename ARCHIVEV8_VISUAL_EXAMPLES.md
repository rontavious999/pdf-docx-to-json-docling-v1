# Archivev8 Visual Examples

This document provides side-by-side comparisons of TXT input and JSON output to illustrate the issues found.

---

## Issue 1: Orphaned Checkbox Labels ❌

### Input (TXT)
```
Do you have, or have you had, any of the following? 
   [ ] AIDS/HIV Positive      [ ] Chest Pains                   [ ] Frequent Headaches       [ ] Hypoglycemia             [ ] Rheurnatism 
   [ ] Alzheimer's Disease    [ ] Cold Sores/Fever Blisters     [ ] Genital Herpes           [ ] rregular Heartbeat       [ ] Scarlet Fever 
   [ ] Anaphylaxis            [ ] Congenital Heart Disorder     [ ] Glaucoma                 [ ] Kidney Problems          [ ] Shingles 
   [ ]                       [ ]                               [ ]                           [ ]                          [ ] Sickle Cell Disease 
      Anemia                    Convulsions                       Hay Fever                    Leukemia                   [ ] Sinus Trouble
   [ ] Angina                [ ] Cortisone Medicine            [ ] Heart Attack/Failure      [ ] Liver Disease            [ ] Spina Bifida 
```

Notice line 4 has checkboxes `[ ]` but almost no labels.  
Line 5 has the labels `Anemia`, `Convulsions`, `Hay Fever`, `Leukemia` but no checkboxes.

### Current Output (JSON)
```json
{
  "key": "do_you_have_or_have_you_had_any_of_the_following",
  "title": "Do you have, or have you had, any of the following?",
  "type": "dropdown",
  "control": {
    "options": [
      {"name": "AIDS/HIV Positive", "value": "aidshiv_positive"},
      {"name": "Chest Pains", "value": "chest_pains"},
      {"name": "Frequent Headaches", "value": "frequent_headaches"},
      {"name": "Hypoglycemia", "value": "hypoglycemia"},
      {"name": "Rheurnatism", "value": "rheurnatism"},
      {"name": "Alzheimer's Disease", "value": "alzheimers_disease"},
      ...
      {"name": "Sickle Cell Disease", "value": "sickle_cell_disease"},
      {"name": "Sinus Trouble", "value": "sinus_trouble"},
      {"name": "Angina", "value": "angina"},
      ...
      ❌ MISSING: Anemia
      ❌ MISSING: Convulsions
      ❌ MISSING: Hay Fever
      ❌ MISSING: Leukemia
    ],
    "multi": true
  }
}
```

### Expected Output (JSON)
```json
{
  "control": {
    "options": [
      ...
      {"name": "Anaphylaxis", "value": "anaphylaxis"},
      ✅ {"name": "Anemia", "value": "anemia"},
      ✅ {"name": "Convulsions", "value": "convulsions"},
      ✅ {"name": "Hay Fever", "value": "hay_fever"},
      ✅ {"name": "Leukemia", "value": "leukemia"},
      {"name": "Sickle Cell Disease", "value": "sickle_cell_disease"},
      ...
    ],
    "multi": true
  }
}
```

---

## Issue 2: Header Information as Fields ❌

### Input (TXT)
```
                                                                                                          Tel: 626.577.2017 
                                                                                                          Fax: 626.577.2003 

                 Prestige Dental                                                                   1060 E. Pasadena, Green St., CA Suite 91106 203 
                Family, Cosmetic and Implant Dentistry                                           frontdesk@prestige-dental.net 

                                Patient Information Form 

Today's Date 
```

Lines 4-5 are business header information, not form fields.

### Current Output (JSON)
```json
[
  ❌ {
    "key": "prestige_dental_1060_e_pasadena_green_st_ca_suite_91106_203",
    "type": "input",
    "title": "Prestige Dental 1060 E. Pasadena, Green St., CA Suite 91106 203",
    "section": "General"
  },
  ❌ {
    "key": "family_cosmetic_and_implant_dentistry_frontdeskprestige-dentalne",
    "type": "input",
    "title": "Family, Cosmetic and Implant Dentistry frontdesk@prestige-dental.net",
    "section": "General"
  },
  {
    "key": "todays_date",
    "type": "date",
    "title": "Today's Date",
    "section": "General"
  },
  ...
]
```

### Expected Output (JSON)
```json
[
  ✅ (Lines 4-5 should be filtered out)
  {
    "key": "todays_date",
    "type": "date",
    "title": "Today's Date",
    "section": "General"
  },
  ...
]
```

---

## Issue 3: Follow-up Fields Removed ⚠️

### Input (TXT)
```
              Are you under a physician's care now? [ ] Yes [ ] No           If yes, please explain: 
    Have you ever been hospitalized/ had major surgery? [ ] Yes [ ] No       If yes, please explain: 
          Have you ever had a serious head/ neck injury? [ ] Yes [ ] No      If yes, please explain: 
           Are you taking any medications, pills or drugs? [ ] Yes [ ] No    If yes, please explain:
```

4 questions with "If yes, please explain" prompts.

### Current Output (JSON)
```json
[
  {
    "key": "are_you_under_a_physicians_care_now",
    "title": "Are you under a physician's care now?",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Yes", "value": "yes"},
        {"name": "No", "value": "no"}
      ]
    }
  },
  ✅ {
    "key": "are_you_under_a_physicians_care_now_explanation",
    "title": "Please explain",
    "type": "input",
    "control": {"input_type": "text"},
    "conditional_on": [["are_you_under_a_physicians_care_now", "yes"]]
  },
  {
    "key": "have_you_ever_been_hospitalized_had_major_surgery",
    "title": "Have you ever been hospitalized/ had major surgery?",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Yes", "value": "yes"},
        {"name": "No", "value": "no"}
      ]
    }
  },
  ❌ (Missing explanation field - removed during template matching)
  {
    "key": "have_you_ever_had_a_serious_head_neck_injury",
    "title": "Have you ever had a serious head/ neck injury?",
    "type": "radio"
  },
  ❌ (Missing explanation field)
  {
    "key": "are_you_taking_any_medications_pills_or_drugs",
    "title": "Are you taking any medications, pills or drugs?",
    "type": "radio"
  },
  ❌ (Missing explanation field)
]
```

**Note:** The parser initially creates all 4 explanation fields (verified with `--debug`), but 3 are removed during the template matching phase.

### Expected Output (JSON)
```json
[
  {
    "key": "are_you_under_a_physicians_care_now",
    "title": "Are you under a physician's care now?",
    "type": "radio"
  },
  ✅ {
    "key": "are_you_under_a_physicians_care_now_explanation",
    "title": "Please explain",
    "type": "input",
    "conditional_on": [["are_you_under_a_physicians_care_now", "yes"]]
  },
  {
    "key": "have_you_ever_been_hospitalized_had_major_surgery",
    "title": "Have you ever been hospitalized/ had major surgery?",
    "type": "radio"
  },
  ✅ {
    "key": "have_you_ever_been_hospitalized_had_major_surgery_explanation",
    "title": "Please explain",
    "type": "input",
    "conditional_on": [["have_you_ever_been_hospitalized_had_major_surgery", "yes"]]
  },
  {
    "key": "have_you_ever_had_a_serious_head_neck_injury",
    "title": "Have you ever had a serious head/ neck injury?",
    "type": "radio"
  },
  ✅ {
    "key": "have_you_ever_had_a_serious_head_neck_injury_explanation",
    "title": "Please explain",
    "type": "input",
    "conditional_on": [["have_you_ever_had_a_serious_head_neck_injury", "yes"]]
  },
  {
    "key": "are_you_taking_any_medications_pills_or_drugs",
    "title": "Are you taking any medications, pills or drugs?",
    "type": "radio"
  },
  ✅ {
    "key": "are_you_taking_any_medications_pills_or_drugs_explanation",
    "title": "Please explain",
    "type": "input",
    "conditional_on": [["are_you_taking_any_medications_pills_or_drugs", "yes"]]
  }
]
```

---

## Issue 4: Malformed Medical Text ⚠️

### Input (TXT)
```
   [ ] Blood Blood Transfusion Disease [ ] Epilepsy/ Excessive Seizers Bleeding [ ] Herpes   [ ] Psychiatric Care         [ ] [ ] Tonsillitis 
```

Notice:
- "Blood Blood Transfusion Disease" (repeated word)
- "Epilepsy/ Excessive Seizers Bleeding" (run-on text after slash)
- Extra checkboxes before Tonsillitis

### Current Output (JSON)
```json
{
  "control": {
    "options": [
      ...
      ❌ {
        "name": "Blood Blood Transfusion Disease",
        "value": "blood_blood_transfusion_disease"
      },
      ❌ {
        "name": "Epilepsy/ Excessive Seizers Bleeding",
        "value": "epilepsy_excessive_seizers_bleeding"
      },
      ...
    ]
  }
}
```

### Expected Output (JSON)
```json
{
  "control": {
    "options": [
      ...
      ✅ {
        "name": "Blood Transfusion Disease",
        "value": "blood_transfusion_disease"
      },
      ✅ {
        "name": "Epilepsy",
        "value": "epilepsy"
      },
      ...
    ]
  }
}
```

---

## Working Features ✅

### Multi-Question Line Splitting ✅

**Input (TXT):**
```
Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single [ ] Other:
```

**Output (JSON):**
```json
[
  ✅ {
    "key": "sex",
    "type": "radio",
    "title": "Gender",
    "control": {
      "options": [
        {"name": "Male", "value": "male"},
        {"name": "Female", "value": "female"}
      ]
    }
  },
  ✅ {
    "key": "marital_status",
    "type": "radio",
    "title": "Marital Status",
    "control": {
      "options": [
        {"name": "Single", "value": "single"},
        {"name": "Married", "value": "married"}
      ]
    }
  }
]
```

Correctly splits into 2 separate questions!

---

### Footer Text Filtering ✅

**Input (TXT):**
```
  LINCOLN DENTAL CARE                     MIDWAY SQUARE DENTAL CENTER                   CHICAGO DENTAL DESIGN 
3138 N Lincoln Ave Chicago, IL                   5109B S Pulaski Rd.                   845 N Michigan Ave Suite 945W 
         60657                                    Chicago, IL 60632                         Chicago, IL 60611 
```

**Output (JSON):**
```json
✅ (Not present in JSON - correctly filtered out!)
```

The footer text with multiple locations is correctly recognized and filtered.

---

### Medical Conditions Grid Parsing ✅

**Input (TXT):**
```
   [ ] AIDS/HIV Positive      [ ] Chest Pains                   [ ] Frequent Headaches       [ ] Hypoglycemia             [ ] Rheurnatism 
   [ ] Alzheimer's Disease    [ ] Cold Sores/Fever Blisters     [ ] Genital Herpes           [ ] rregular Heartbeat       [ ] Scarlet Fever 
```

**Output (JSON):**
```json
{
  "control": {
    "options": [
      ✅ {"name": "AIDS/HIV Positive", "value": "aidshiv_positive"},
      ✅ {"name": "Chest Pains", "value": "chest_pains"},
      ✅ {"name": "Frequent Headaches", "value": "frequent_headaches"},
      ✅ {"name": "Hypoglycemia", "value": "hypoglycemia"},
      ✅ {"name": "Rheurnatism", "value": "rheurnatism"},
      ✅ {"name": "Alzheimer's Disease", "value": "alzheimers_disease"},
      ✅ {"name": "Cold Sores/Fever Blisters", "value": "cold_soresfever_blisters"},
      ✅ {"name": "Genital Herpes", "value": "genital_herpes"},
      ✅ {"name": "rregular Heartbeat", "value": "rregular_heartbeat"},
      ✅ {"name": "Scarlet Fever", "value": "scarlet_fever"}
    ],
    "multi": true
  }
}
```

Each checkbox + label combination is correctly parsed as a separate option!

---

## Summary

**4 Issues to Fix:**
1. ❌ Orphaned checkbox labels
2. ❌ Header information as fields
3. ⚠️ Follow-up fields removed
4. ⚠️ Malformed medical text

**3 Features Working Well:**
1. ✅ Multi-question line splitting
2. ✅ Medical conditions grid parsing
3. ✅ Footer text filtering

All recommended fixes are **general pattern-based** and will work across all forms.
