# Archivev11 Visual Comparison - What's Missing vs What's There

**Side-by-side comparison of TXT input vs JSON output**

---

## npf1.txt - Dental History Section

### What's in the TXT File (lines 74-91):

```text
74. Dental History Cont. - Please mark (x) any of the following conditions that apply to you
75. Appearance                            Function                                    Habits                                   Previous Comfort Options
76. [ ] Discolored teeth                 [ ] Grinding/Clenching                       [ ] Thumb sucking                       [ ] Nitrous Oxide
77. [ ] Worn teeth                        [ ] Headaches                               [ ] Nail-biting                         [ ] Oral Sedation (Pill)
78. [ ] Misshaped teeth                  [ ] Jaw Joint (TMJ) pain                     [ ] Cheek/Lip biting                    [ ] IV Sedation
79. [ ] Crooked teeth                     [ ] Jaw Joint (TMJ) clicking/popping        [ ] Chewing on ice/foreign objects
80. [ ] Spaces                           [ ] Bad Bite
81. [ ]                                   [ ]                                        Sleep Pattern or Conditions
82. [ ] Overbite                            Speech Impediment                         [ ] Sleep Apnea
83.    Flat teeth                         [ ] Mouth Breathing                         [ ] Snoring
84. Pain/Discomfort                       [ ] Sore Muscles (neck, shoulders)          [ ] Daytime Drowsiness
85. [ ] Sensitivity (hot, cold, sweet)    [ ] Difficulty Opening or Closing           [ ] Bed wetting (for children)
86. [ ] Pressure                            Difficulty Chewing on either side
87. [ ] Broken teeth/fillings            Periodontal (Gum) Health                     Social
88. [ ]                                   [ ] Bleeding, Swollen, Irritated gums      Tobacco
89. [ ] Worn Dry Mouth teeth              [ ] Bad breath                              How much          How long
90.                                       [ ] Loose tipped, shifting teeth            Alcohol Frequency
91.                                       [ ] Previous perio/gum disease              Drugs Frequency
```

**Total: 34 checkbox items across 4 main categories + additional subcategories**

---

### What's in the JSON Output (CURRENT):

#### Main Field: "Dental History Cont. - Please mark (x) any of the following conditions that apply to you"
**Type:** dropdown (multi-select)  
**Options: 29**

✅ **Captured (29 items):**
1. Discolored teeth
2. Grinding/Clenching
3. Thumb sucking
4. Nitrous Oxide
5. Worn teeth
6. Headaches
7. Nail-biting
8. Oral Sedation (Pill)
9. Misshaped teeth
10. Jaw Joint (TMJ) pain
11. Cheek/Lip biting
12. IV Sedation
13. Crooked teeth
14. Jaw Joint (TMJ) clicking
15. Chewing on ice
16. Spaces
17. Bad Bite
18. Overbite
19. Sleep Apnea
20. Mouth Breathing
21. Snoring
22. Sore Muscles (neck, shoulders)
23. Daytime Drowsiness
24. Sensitivity (hot, cold, sweet)
25. Difficulty Opening or Closing
26. Bed wetting (for children)
27. Bleeding, Swollen, Irritated gums
28. Worn Dry Mouth teeth
29. Bad breath

❌ **Missing (5 items):**
- **Speech Impediment** (line 82, column 2) - Text only, no checkbox
- **Flat teeth** (line 83, column 1) - Text only, no checkbox
- **Pressure** (line 86, column 1) - Has checkbox but text extraction stopped early
- **Difficulty Chewing on either side** (line 86, column 2) - Text only, no checkbox
- **Broken teeth/fillings** (line 87, column 1) - Has checkbox but followed by category header

---

#### Malformed Field 1: "Loose tipped, shifting teeth Alcohol Frequency" ❌
**Type:** dropdown  
**Options: 1**
- Loose tipped, shifting teeth Alcohol Frequency

**Problem:** Should be just "Loose tipped, shifting teeth"  
**Cause:** "Alcohol Frequency" is a label in the Social column (line 90), not part of the checkbox item  

---

#### Malformed Field 2: "Previous perio/gum disease Drugs Frequency" ❌
**Type:** dropdown  
**Options: 1**
- Previous perio

**Problem:** Should be "Previous perio/gum disease"  
**Cause:** "Drugs Frequency" is a label in the Social column (line 91), not part of the checkbox item  

---

### Visual Breakdown by Line

| Line | Column 1 | Column 2 | Column 3 | Column 4 | Captured? |
|------|----------|----------|----------|----------|-----------|
| 76 | ✅ Discolored teeth | ✅ Grinding/Clenching | ✅ Thumb sucking | ✅ Nitrous Oxide | 4/4 ✅ |
| 77 | ✅ Worn teeth | ✅ Headaches | ✅ Nail-biting | ✅ Oral Sedation | 4/4 ✅ |
| 78 | ✅ Misshaped teeth | ✅ TMJ pain | ✅ Cheek/Lip biting | ✅ IV Sedation | 4/4 ✅ |
| 79 | ✅ Crooked teeth | ✅ TMJ clicking | ✅ Chewing on ice | (empty) | 3/3 ✅ |
| 80 | ✅ Spaces | ✅ Bad Bite | (empty) | (empty) | 2/2 ✅ |
| 81 | (blank checkbox) | (blank checkbox) | (header) | (empty) | N/A |
| 82 | ✅ Overbite | ❌ Speech Impediment | ✅ Sleep Apnea | (empty) | 2/3 ⚠️ |
| 83 | ❌ Flat teeth | ✅ Mouth Breathing | ✅ Snoring | (empty) | 2/3 ⚠️ |
| 84 | (header) | ✅ Sore Muscles | ✅ Daytime Drowsiness | (empty) | 2/2 ✅ |
| 85 | ✅ Sensitivity | ✅ Difficulty Opening | ✅ Bed wetting | (empty) | 3/3 ✅ |
| 86 | ❌ Pressure | ❌ Difficulty Chewing | (empty) | (empty) | 0/2 ❌ |
| 87 | ❌ Broken teeth | (header) | (header) | (empty) | 0/1 ❌ |
| 88 | (blank checkbox) | ✅ Bleeding gums | (label) | (empty) | 1/1 ✅ |
| 89 | ✅ Worn Dry Mouth | ✅ Bad breath | (label) | (empty) | 2/2 ✅ |
| 90 | (empty) | ⚠️ Loose tipped* | (label) | (empty) | 1/1 ⚠️ |
| 91 | (empty) | ⚠️ Previous perio* | (label) | (empty) | 1/1 ⚠️ |

*Captured but with malformed title (includes adjacent column label)

---

## npf1.txt - Medical History Section ✅

### What's in the TXT File (lines 93-108):

```text
93. Medical History - Please mark (x) to your response to indicate if you have or have had any of the following
94. Cancer                           Endocrinology                   Musculoskeletal                Respiratory                 Medical Allergies
95. Type                              [ ] Diabetes                   [ ] Arthritis                   [ ] Asthma                  [ ] Antibiotics
96. [ ] Chemotherapy                 [ ] Hepatitis A/B/C            [ ] Artificial Joints           [ ] Emphysema              (Penicillin...)
97. [ ] Radiation Therapy            [ ] Jaundice                   [ ] Jaw Joint Pain              [ ] Respiratory Problems [ ] Opioids
...
```

**Total: 50 checkbox items across 5 categories**

---

### What's in the JSON Output (CURRENT):

#### Field: "Medical History - Please mark (x) to your response to indicate if you have or have had any of the following"
**Type:** dropdown (multi-select)  
**Options: 50** ✅

**Status:** ✅ **PERFECT** - All 50 items captured correctly!

**Why it works:**
- Every line has checkboxes in consistent column positions
- No text-only entries mixed in
- Category headers on separate line (line 94)
- Parser successfully detected as multi-column grid

---

## Chicago-Dental-Solutions_Form.txt - Medical History ✅

### What's in the TXT File (lines 84-100):

```text
84. Do you have, or have you had, any of the following?
85. [ ] AIDS/HIV Positive      [ ] Chest Pains                   [ ] Frequent Headaches       ...
86. [ ] Alzheimer's Disease    [ ] Cold Sores/Fever Blisters     [ ] Genital Herpes           ...
...
```

**Total: 73 checkbox items across multiple lines (5 per line)**

---

### What's in the JSON Output (CURRENT):

#### Field: "Do you have, or have you had, any of the following?"
**Type:** dropdown (multi-select)  
**Options: 73** ✅

**Status:** ✅ **PERFECT** - All 73 items captured correctly!

**Why it works:**
- Consistent pattern: exactly 5 checkboxes per line
- Every checkbox starts a line item
- Regular spacing between columns
- No text-only entries
- No inline category headers

---

## Summary Table

| Form | Section | Total Items | Captured | Missing | Malformed | Status |
|------|---------|-------------|----------|---------|-----------|--------|
| npf1 | Medical History | 50 | 50 | 0 | 0 | ✅ Perfect |
| npf1 | Dental History | 34 | 29 | 5 | 2 | ⚠️ Partial |
| Chicago | Medical History | 73 | 73 | 0 | 0 | ✅ Perfect |
| npf | (Simple form) | N/A | N/A | 0 | 0 | ✅ Perfect |

---

## Why npf1 Dental History Is Different

### Characteristics of Working Sections (Medical History, Chicago):
1. ✅ Every line has checkboxes at consistent positions
2. ✅ No text-only entries (every item has a checkbox)
3. ✅ Category headers on separate lines, not inline
4. ✅ No labels mixed into data rows

### Characteristics of Problematic Section (npf1 Dental History):
1. ❌ Some lines have text without checkboxes
2. ❌ Column count varies (2-4 items per line)
3. ❌ Category headers inline with data ("Pain/Discomfort", "Social")
4. ❌ Labels from adjacent columns bleed into text extraction
5. ❌ Some checkboxes on lines without item text (blank checkboxes)

---

## What Fixes Will Do

### After Fix 1 (Column Boundary Detection):

**Malformed Field 1:** ~~"Loose tipped, shifting teeth Alcohol Frequency"~~ → **"Loose tipped, shifting teeth"** ✅  
**Malformed Field 2:** ~~"Previous perio/gum disease Drugs Frequency"~~ → **"Previous perio/gum disease"** ✅

### After Fix 2 (Text-Only Item Detection):

**Missing Items:** 29/34 → **34/34** ✅
- ✅ Speech Impediment (detected at column 2 position)
- ✅ Flat teeth (detected at column 1 position)
- ✅ Pressure (re-extracted with proper boundary)
- ✅ Difficulty Chewing on either side (detected at column 2 position)
- ✅ Broken teeth/fillings (re-extracted with proper boundary)

---

## Expected Final State

### npf1 Dental History - After All Fixes:

#### Field: "Dental History Cont. - Please mark (x) any of the following conditions that apply to you"
**Type:** dropdown (multi-select)  
**Options: 34** ✅ (up from 29)

**All items:**
1. Discolored teeth
2. Grinding/Clenching
3. Thumb sucking
4. Nitrous Oxide
5. Worn teeth
6. Headaches
7. Nail-biting
8. Oral Sedation (Pill)
9. Misshaped teeth
10. Jaw Joint (TMJ) pain
11. Cheek/Lip biting
12. IV Sedation
13. Crooked teeth
14. Jaw Joint (TMJ) clicking
15. Chewing on ice
16. Spaces
17. Bad Bite
18. Overbite
19. **Speech Impediment** ✨ NEW
20. Sleep Apnea
21. **Flat teeth** ✨ NEW
22. Mouth Breathing
23. Snoring
24. Sore Muscles (neck, shoulders)
25. Daytime Drowsiness
26. Sensitivity (hot, cold, sweet)
27. Difficulty Opening or Closing
28. **Pressure** ✨ NEW
29. **Difficulty Chewing on either side** ✨ NEW
30. Bed wetting (for children)
31. **Broken teeth/fillings** ✨ NEW
32. Bleeding, Swollen, Irritated gums
33. Worn Dry Mouth teeth
34. Bad breath
35. Loose tipped, shifting teeth (clean title) ✅
36. Previous perio/gum disease (clean title) ✅

**Total: 36 options** (34 main grid items + 2 additional fields with clean titles)

---

**End of Visual Comparison**
