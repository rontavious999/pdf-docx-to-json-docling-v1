# Visual Examples of Current Parser Failures

## Example 1: Sex/Gender + Marital Status (npf1.txt, line 7)

### What's in the TXT file:
```
Sex Mor F   Soc. Sec. #                                            Please Circle One: Single Married Separated Widow
```

### What SHOULD be in JSON:
```json
[
  {
    "key": "sex",
    "title": "Sex",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Male", "value": "male"},
        {"name": "Female", "value": "female"}
      ]
    }
  },
  {
    "key": "ssn",
    "title": "Social Security Number",
    "type": "input",
    "control": {"input_type": "text"}
  },
  {
    "key": "marital_status",
    "title": "Marital Status",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Single", "value": "single"},
        {"name": "Married", "value": "married"},
        {"name": "Separated", "value": "separated"},
        {"name": "Widowed", "value": "widowed"}
      ]
    }
  }
]
```

### What's ACTUALLY in JSON:
```json
[]
```
❌ **NOTHING - All three fields completely missing!**

---

## Example 2: Sex + Marital Status with checkboxes (npf.txt, line 31)

### What's in the TXT file:
```
Sex [ ] Male [ ] Female    Marital Status [ ] Married [ ] Single [ ] Divorced [ ] Separated [ ] Widowed
```

### What SHOULD be in JSON:
```json
[
  {
    "key": "sex",
    "title": "Sex",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Male", "value": "male"},
        {"name": "Female", "value": "female"}
      ]
    }
  },
  {
    "key": "marital_status",
    "title": "Marital Status",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Married", "value": "married"},
        {"name": "Single", "value": "single"},
        {"name": "Divorced", "value": "divorced"},
        {"name": "Separated", "value": "separated"},
        {"name": "Widowed", "value": "widowed"}
      ]
    }
  }
]
```

### What's ACTUALLY in JSON:
```json
[]
```
❌ **MISSING - Line not split, treated as single confusing field**

---

## Example 3: Work Phone + Occupation (npf1.txt, line 14)

### What's in the TXT file:
```
Work Phone (      )                         Occupation
```

### What SHOULD be in JSON:
```json
[
  {
    "key": "work_phone",
    "title": "Work Phone",
    "type": "input",
    "control": {"input_type": "phone"}
  },
  {
    "key": "occupation",
    "title": "Occupation",
    "type": "input",
    "control": {"input_type": "text"}
  }
]
```

### What's ACTUALLY in JSON:
```json
[]
```
❌ **BOTH FIELDS MISSING**

---

## Example 4: WORKING CASE - Chicago Form (line 16)

### What's in the TXT file:
```
       Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single [ ] Other:
```

### What's in JSON:
```json
[
  {
    "key": "sex",
    "title": "Gender",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Male", "value": "male"},
        {"name": "Female", "value": "female"},
        {"name": "Other", "value": "other"},
        {"name": "Prefer not to self identify", "value": "not_say"}
      ]
    }
  },
  {
    "key": "marital_status",
    "title": "Marital Status",
    "type": "radio",
    "control": {
      "options": [
        {"name": "Single", "value": "single"},
        {"name": "Married", "value": "married"},
        {"name": "Widowed", "value": "widowed"},
        {"name": "Divorced", "value": "divorced"},
        {"name": "Prefer not to say", "value": "not say"}
      ]
    }
  }
]
```
✅ **WORKS PERFECTLY!**

### Why Chicago works:
1. ✅ Has colons: `Gender:` and `Marital Status:`
2. ✅ Has checkboxes: `[ ]`
3. ✅ Matches pattern: `Label: [ ] ... Label: [ ]`

---

## The Pattern

| Form | Format | Colons? | Checkboxes? | Works? |
|------|--------|---------|-------------|--------|
| Chicago | `Gender: [ ] Male [ ] Female` | ✅ Yes | ✅ Yes | ✅ **YES** |
| npf.txt | `Sex [ ] Male [ ] Female` | ❌ No | ✅ Yes | ❌ **NO** |
| npf1.txt | `Sex M or F` | ❌ No | ❌ No | ❌ **NO** |

**Conclusion**: Current parser only works when fields have BOTH colons AND checkboxes.

---

## Root Cause in Code

The function `split_multi_question_line()` uses this regex pattern:

```python
split_pattern = r'\]\s+([^\[]{0,50}?)\s{4,}([A-Z][A-Za-z\s]+?):\s*\['
#                  ^                                              ^^
#                  |                                              ||
#                  Requires closing bracket ]                    ||
#                                                                 ||
#                                          Requires colon --------+|
#                                          Requires opening bracket [
```

This pattern literally requires: `] ... Label: [`

It **cannot** handle:
- `Label [ ]` (no colon)
- `Label _____` (no checkboxes)
- `Sex M or F` (no checkboxes at all)

---

## Testing Results

I tested the current function with the problematic lines:

| Test | Input | Expected Segments | Actual Segments | Result |
|------|-------|-------------------|-----------------|--------|
| 1 | `Sex Mor F   Soc. Sec. #   Please Circle One: ...` | 3 | 1 | ❌ FAIL |
| 2 | `Sex [ ] Male [ ] Female    Marital Status [ ] ...` | 2 | 1 | ❌ FAIL |
| 3 | `Work Phone (   )   Occupation` | 2 | 1 | ❌ FAIL |
| 4 | `Email   Home Phone (   )   Cell Phone (   )` | 3 | 1 | ❌ FAIL |

**Success Rate: 0/4 (0%)**

---

## What Needs to Change

The parser needs to recognize these additional patterns:

1. **No colon**: `Label [ ] options` → Split based on spacing + checkboxes
2. **No checkboxes**: `Label _____` → Split based on known field labels + spacing
3. **Mixed formats**: `Sex M or F   SSN   Marital: [ ] Single` → Multiple strategies

See `ARCHIVEV12_ANALYSIS.md` for detailed implementation proposals.
