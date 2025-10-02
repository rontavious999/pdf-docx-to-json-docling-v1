# Test Cases for Archivev10 Fixes

This document specifies test cases to validate the proposed fixes for multi-column checkbox grid parsing.

---

## Test Case 1: npf1.txt Medical History Section

**File:** npf1.txt, lines 93-108  
**Issue:** 5 missing items, 6 malformed field titles  
**Priority:** HIGH

### Current Behavior (Baseline):

**Fields created:** 8 dropdown fields

1. "Type" - 4 options ✓ (correct)
2. "Do you have or have you had..." - 23 options ✓ (correct but some malformed option names)
3. "Radiation Therapy Jaundice..." - 5 options ❌ (malformed title)
4. "Cardiovascular" - 1 option ❌ (wrong title, wrong count)
5. "Pacemaker Hematologic..." - 3 options ❌ (malformed title)
6. "Rheumatic Fever Blood..." - 4 options ❌ (malformed title)
7. "Scarlet Fever Bruise..." - 3 options ❌ (malformed title)
8. "Stroke Excessive Bleeding" - 2 options ❌ (malformed title)

**Total items:** 45 (missing: High/Low Blood Pressure, Gastrointestinal Disease, Liver Disease, Fainting, Mitral Valve Prolapse)

### Expected Behavior After Fix 1:

**Fields created:** 1-2 multi-select fields

**Option 1 (Recommended):**
```json
{
  "key": "medical_conditions",
  "title": "Medical History - Do you have or have you had any of the following?",
  "section": "Medical History",
  "type": "checkboxes",
  "control": {
    "options": [
      {"name": "Diabetes", "value": "diabetes"},
      {"name": "Arthritis", "value": "arthritis"},
      {"name": "Asthma", "value": "asthma"},
      {"name": "Antibiotics Allergy", "value": "antibiotics_allergy"},
      {"name": "Chemotherapy", "value": "chemotherapy"},
      ... // all 50 items as clean separate options
    ]
  }
}
```

**Option 2 (Acceptable):**
- Multiple fields, one per category (Cancer, Endocrinology, etc.)
- Each with clean title and appropriate subset of conditions

**Success Criteria:**
- ✅ All 50 checkbox items captured
- ✅ No malformed field titles (no concatenated condition names)
- ✅ Clean option names (no text from adjacent columns)
- ✅ Proper section assignment (Medical History)
- ✅ No duplicate items

**Test Command:**
```bash
python3 llm_text_to_modento.py --in /tmp/archivev10/output --out /tmp/test_fix1 --debug
python3 -c "
import json
with open('/tmp/test_fix1/npf1.modento.json') as f:
    data = json.load(f)
medical = [i for i in data if i.get('section') == 'Medical History' and i.get('type') in ['dropdown', 'checkboxes']]
total_options = sum(len(i.get('control', {}).get('options', [])) for i in medical)
print(f'Medical History fields: {len(medical)}')
print(f'Total options: {total_options}')
for field in medical:
    title = field.get('title', '')
    if len(title) > 50:
        print(f'⚠️  Long title detected: {title[:60]}...')
"
```

---

## Test Case 2: npf1.txt Dental History Section

**File:** npf1.txt, lines 74-91  
**Issue:** 31 missing items (91% loss!)  
**Priority:** CRITICAL

### Current Behavior (Baseline):

**Fields created:** 1 dropdown field

1. "Crooked teeth Jaw Joint (TMJ) clicking/popping..." - 3 options ❌

**Total items:** 3 (missing 31 items including ALL items from Appearance, most from Function, most from Habits, ALL from Previous Comfort Options, ALL from Pain/Discomfort, ALL from Periodontal Health)

### Expected Behavior After Fix 1:

**Fields created:** 1-2 multi-select fields

**Option 1 (Recommended):**
```json
{
  "key": "dental_conditions",
  "title": "Dental History - Please mark any of the following conditions",
  "section": "Dental History",
  "type": "checkboxes",
  "control": {
    "options": [
      {"name": "Discolored teeth", "value": "discolored_teeth"},
      {"name": "Worn teeth", "value": "worn_teeth"},
      {"name": "Grinding/Clenching", "value": "grinding_clenching"},
      {"name": "Thumb sucking", "value": "thumb_sucking"},
      {"name": "Nitrous Oxide (previous use)", "value": "nitrous_oxide"},
      ... // all 34 items as clean separate options
    ]
  }
}
```

**Option 2 (Acceptable):**
- 4 fields: "Appearance", "Function", "Habits", "Previous Comfort Options"
- Each with appropriate subset of conditions

**Success Criteria:**
- ✅ All 34 checkbox items captured
- ✅ No malformed field titles
- ✅ Categories represented (Appearance, Function, Habits, etc.)
- ✅ Clean option names
- ✅ Proper section assignment (Dental History)

**Test Command:**
```bash
python3 llm_text_to_modento.py --in /tmp/archivev10/output --out /tmp/test_fix1 --debug
python3 -c "
import json
with open('/tmp/test_fix1/npf1.modento.json') as f:
    data = json.load(f)
dental = [i for i in data if i.get('section') == 'Dental History' and i.get('type') in ['dropdown', 'checkboxes']]
total_options = sum(len(i.get('control', {}).get('options', [])) for i in dental)
print(f'Dental History fields: {len(dental)}')
print(f'Total options: {total_options}')
for field in dental:
    opts = field.get('control', {}).get('options', [])
    print(f'  {field.get(\"title\", \"\")[:40]} - {len(opts)} options')
"
```

---

## Test Case 3: Chicago Form Medical History (Regression Test)

**File:** Chicago-Dental-Solutions_Form.txt  
**Issue:** Currently works well (73/73 items captured)  
**Priority:** HIGH (ensure no regression)

### Current Behavior (Should Remain Unchanged):

**Fields created:** 1 dropdown field

1. "Do you have, or have you had, any of the following?" - 73 options ✓

**Total items:** 73 (all captured correctly)

### Expected Behavior After Fix 1:

**MUST remain the same or better!**

**Success Criteria:**
- ✅ Still captures all 73 medical conditions
- ✅ Field title remains clean and descriptive
- ✅ No duplicates introduced
- ✅ No items lost
- ✅ Section assignment correct

**Test Command:**
```bash
python3 llm_text_to_modento.py --in /tmp/archivev10/output --out /tmp/test_fix1 --debug
python3 -c "
import json
with open('/tmp/test_fix1/Chicago-Dental-Solutions_Form.modento.json') as f:
    data = json.load(f)
medical = [i for i in data if i.get('section') == 'Medical History' and 'following' in i.get('title', '').lower()]
if medical:
    opts = medical[0].get('control', {}).get('options', [])
    print(f'Chicago Medical History: {len(opts)} options')
    if len(opts) != 73:
        print(f'⚠️  Expected 73 options, got {len(opts)}')
    else:
        print('✓ No regression - still 73 options')
"
```

---

## Test Case 4: npf.txt (No Medical History)

**File:** npf.txt  
**Issue:** None - form has no medical/dental history section  
**Priority:** LOW (ensure no false positives)

### Current Behavior:

**Fields created:** 34 total fields, none in Medical/Dental History sections

### Expected Behavior After Fix 1:

**MUST remain the same!**

**Success Criteria:**
- ✅ No medical history fields created
- ✅ No dental history fields created
- ✅ All 34 fields remain intact
- ✅ No false positives from grid detection

**Test Command:**
```bash
python3 llm_text_to_modento.py --in /tmp/archivev10/output --out /tmp/test_fix1 --debug
python3 -c "
import json
with open('/tmp/test_fix1/npf.modento.json') as f:
    data = json.load(f)
medical = [i for i in data if i.get('section') == 'Medical History']
dental = [i for i in data if i.get('section') == 'Dental History']
print(f'Total fields: {len(data)}')
print(f'Medical History fields: {len(medical)}')
print(f'Dental History fields: {len(dental)}')
if len(medical) > 0 or len(dental) > 0:
    print('⚠️  False positive - detected medical/dental fields where none exist')
"
```

---

## Test Case 5: Archivev9 Forms (Regression Test)

**Files:** Forms from Archivev9.zip (if available)  
**Priority:** MEDIUM (ensure no regression on previous fixes)

### Expected Behavior After Fix 1:

**Previous fixes must still work!**

**Success Criteria:**
- ✅ Fix 1 (enhanced condition consolidation) still works
- ✅ Fix 2 (multi-line section headers) still works
- ✅ Fix 3 (category header detection) still works
- ✅ Fix 6 (duplicate consolidation) still works
- ✅ Fix 8 (section inference) still works

**Test Command:**
```bash
# If Archivev9 forms are available
python3 llm_text_to_modento.py --in /path/to/archivev9/output --out /tmp/test_archivev9 --debug

# Compare field counts with baseline
# Verify no regressions in:
# - Field counts per section
# - Duplicate removal
# - Section assignments
```

---

## Test Case 6: Edge Cases

### 6a. Single-Column Checkbox List

**Input:**
```
[ ] Item 1
[ ] Item 2
[ ] Item 3
```

**Expected:** Should still work (existing behavior preserved)

### 6b. Two-Column Checkbox Grid

**Input:**
```
[ ] Item 1        [ ] Item 4
[ ] Item 2        [ ] Item 5
[ ] Item 3        [ ] Item 6
```

**Expected:** Detect as 2-column grid, create 1 field with 6 options

### 6c. Irregular Column Spacing

**Input:**
```
[ ] Item 1    [ ] Item 2          [ ] Item 3
[ ] Item 4         [ ] Item 5     [ ] Item 6
```

**Expected:** Detect columns even with irregular spacing, create 1 field with 6 options

### 6d. Mixed Checkbox and Text

**Input:**
```
Category Header
[ ] Item 1        [ ] Item 2        [ ] Item 3
Some explanatory text
[ ] Item 4        [ ] Item 5        [ ] Item 6
```

**Expected:** Skip category header and text, capture all 6 checkbox items

### 6e. Empty Checkboxes

**Input:**
```
[ ]               [ ] Item 2        [ ] Item 3
```

**Expected:** Skip empty checkbox, capture Item 2 and Item 3

---

## Automated Test Script

```bash
#!/bin/bash
# test_archivev10_fixes.sh

echo "Running Archivev10 Fix Tests..."

# Run parser on all forms
python3 llm_text_to_modento.py --in /tmp/archivev10/output --out /tmp/test_results --debug

# Test Case 1: npf1 Medical History
echo -e "\n=== Test Case 1: npf1 Medical History ==="
python3 << 'EOF'
import json
with open('/tmp/test_results/npf1.modento.json') as f:
    data = json.load(f)
medical = [i for i in data if i.get('section') == 'Medical History' and i.get('type') in ['dropdown', 'checkboxes']]
total_options = sum(len(i.get('control', {}).get('options', [])) for i in medical)
malformed = sum(1 for i in medical if len(i.get('title', '').split()) > 8)

print(f"Fields: {len(medical)}")
print(f"Total options: {total_options}")
print(f"Malformed titles: {malformed}")

if total_options >= 50 and malformed == 0:
    print("✅ PASS")
else:
    print("❌ FAIL")
EOF

# Test Case 2: npf1 Dental History
echo -e "\n=== Test Case 2: npf1 Dental History ==="
python3 << 'EOF'
import json
with open('/tmp/test_results/npf1.modento.json') as f:
    data = json.load(f)
dental = [i for i in data if i.get('section') == 'Dental History' and i.get('type') in ['dropdown', 'checkboxes']]
total_options = sum(len(i.get('control', {}).get('options', [])) for i in dental)

print(f"Fields: {len(dental)}")
print(f"Total options: {total_options}")

if total_options >= 34:
    print("✅ PASS")
else:
    print("❌ FAIL")
EOF

# Test Case 3: Chicago Regression
echo -e "\n=== Test Case 3: Chicago Regression ==="
python3 << 'EOF'
import json
with open('/tmp/test_results/Chicago-Dental-Solutions_Form.modento.json') as f:
    data = json.load(f)
medical = [i for i in data if i.get('section') == 'Medical History' and 'following' in i.get('title', '').lower()]
if medical:
    opts = medical[0].get('control', {}).get('options', [])
    print(f"Options: {len(opts)}")
    if len(opts) == 73:
        print("✅ PASS - No regression")
    else:
        print(f"❌ FAIL - Expected 73, got {len(opts)}")
EOF

# Test Case 4: npf No False Positives
echo -e "\n=== Test Case 4: npf No False Positives ==="
python3 << 'EOF'
import json
with open('/tmp/test_results/npf.modento.json') as f:
    data = json.load(f)
medical = [i for i in data if i.get('section') == 'Medical History']
dental = [i for i in data if i.get('section') == 'Dental History']

print(f"Medical fields: {len(medical)}")
print(f"Dental fields: {len(dental)}")

if len(medical) == 0 and len(dental) <= 1:
    print("✅ PASS - No false positives")
else:
    print("❌ FAIL - Detected medical/dental fields where none exist")
EOF

echo -e "\n=== Test Summary ==="
echo "Review results above. All tests should show ✅ PASS"
```

---

## Performance Test

```bash
# Measure parsing time before and after fix
time python3 llm_text_to_modento.py --in /tmp/archivev10/output --out /tmp/baseline

# After implementing fix
time python3 llm_text_to_modento.py --in /tmp/archivev10/output --out /tmp/test_fix1

# Performance should not degrade significantly (< 20% slowdown acceptable)
```

---

## Manual Verification Checklist

After running automated tests, manually verify:

- [ ] Open npf1.modento.json and check Medical History section
- [ ] Verify all 50 conditions are present as separate options
- [ ] Check no field titles contain concatenated condition names
- [ ] Open npf1.modento.json and check Dental History section
- [ ] Verify all 34 conditions are present
- [ ] Check categories are represented (Appearance, Function, etc.)
- [ ] Open Chicago form JSON and verify 73 medical conditions still present
- [ ] Open npf.modento.json and verify no medical/dental history fields
- [ ] Compare field counts across all forms (should be consistent)
- [ ] Check debug output for any warning messages

---

## Acceptance Criteria Summary

### Fix 1 is considered successful if:

1. **npf1 Medical History:**
   - ✅ 50/50 conditions captured (vs 45/50 baseline)
   - ✅ 0 malformed field titles (vs 6 baseline)
   - ✅ Clean option names (no concatenation)

2. **npf1 Dental History:**
   - ✅ 34/34 conditions captured (vs 3/34 baseline)
   - ✅ 0 malformed field titles (vs 1 baseline)
   - ✅ All categories represented

3. **Chicago Form:**
   - ✅ No regression (still 73/73 conditions)
   - ✅ No new malformed fields

4. **npf Form:**
   - ✅ No false positives
   - ✅ No new fields created

5. **Performance:**
   - ✅ Parsing time increase < 20%
   - ✅ No crashes or errors

6. **Code Quality:**
   - ✅ Generic solution (no hard-coding)
   - ✅ Debug logging added
   - ✅ Follows existing code patterns

---

## Post-Implementation Testing

After all 5 fixes are implemented:

1. Run full test suite on Archivev10 forms
2. Run regression tests on Archivev9 forms
3. Test on 5-10 additional dental forms (if available)
4. Performance benchmarking
5. User acceptance testing (review JSON outputs with stakeholders)

**Target:** 100% field capture rate with 0 malformed titles across all test forms.
