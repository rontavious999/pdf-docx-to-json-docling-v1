# Archivev8 Quick Reference Guide

## 4 Issues Found - Quick Summary

| # | Issue | Severity | Function | Lines | Fix Complexity |
|---|-------|----------|----------|-------|----------------|
| 1 | Orphaned checkbox labels not captured | CRITICAL | `parse_to_questions()` | ~1400-1600 | Medium |
| 2 | Header/business info parsed as fields | CRITICAL | `scrub_headers_footers()` | ~225-280 | Low |
| 3 | "If yes" follow-up fields removed | MEDIUM | `apply_templates_and_count()` | ~2239-2256 | Low |
| 4 | Malformed medical condition text | MEDIUM | `make_option()` | Various | Low |

---

## Issue 1: Orphaned Checkbox Labels ❌

**What's wrong:**
```
Line 88: [ ]           [ ]           [ ]           [ ]           [ ] Sickle Cell Disease
Line 89:    Anemia       Convulsions   Hay Fever     Leukemia   [ ] Sinus Trouble
```
→ Anemia, Convulsions, Hay Fever, Leukemia are **missing** from JSON

**Where:** Chicago-Dental-Solutions_Form.txt, lines 88-89

**Fix:** Detect orphaned checkboxes, look ahead to next line for labels, associate by column position

---

## Issue 2: Header Text as Fields ❌

**What's wrong:**
```
Prestige Dental                                    1060 E. Pasadena, Green St., CA Suite 91106 203
```
→ Creates field: `prestige_dental_1060_e_pasadena_green_st_ca_suite_91106_203`

**Where:** npf.txt, lines 6-7

**Fix:** Filter lines combining business name + address + contact info patterns

---

## Issue 3: Follow-up Fields Removed ⚠️

**What's wrong:**
```
Are you under a physician's care now? [ ] Yes [ ] No    If yes, please explain:
Have you ever been hospitalized? [ ] Yes [ ] No         If yes, please explain:
...
```
→ Parser creates 4 explanation fields, but final JSON only has 1

**Where:** Chicago-Dental-Solutions_Form.txt, lines 69-72

**Fix:** Exempt conditional/explanation fields from template matching/merging

---

## Issue 4: Malformed Text ⚠️

**What's wrong:**
```
[ ] Blood Blood Transfusion Disease
[ ] Epilepsy/ Excessive Seizers Bleeding
```
→ Creates options with repeated/malformed text

**Where:** Chicago-Dental-Solutions_Form.txt, line 96

**Fix:** Clean repeated words, intelligently split slash-separated conditions

---

## What's Working ✅

- ✅ Multi-question line splitting (Gender + Marital Status on one line)
- ✅ Medical conditions grid parsing (most conditions)
- ✅ Footer text filtering (multi-location addresses)

---

## Testing Checklist

After fixes, verify:

- [ ] Anemia, Convulsions, Hay Fever, Leukemia in medical conditions dropdown
- [ ] No "Prestige Dental" header fields in npf.json
- [ ] 4 explanation fields in Chicago form JSON (not just 1)
- [ ] No "Blood Blood" or similar repeated words in options
- [ ] Multi-question splitting still works
- [ ] Footer filtering still works

---

## Files Modified

1. `llm_text_to_modento.py` - All fixes in this file:
   - Issue #1: Lines ~1400-1600 in `parse_to_questions()`
   - Issue #2: Lines ~225-280 in `scrub_headers_footers()`
   - Issue #3: Lines ~2239-2256 in `apply_templates_and_count()`
   - Issue #4: Various locations in option creation

---

## Priority Order

1. **FIRST:** Fix Issue #2 (header filtering) - easiest, high impact
2. **SECOND:** Fix Issue #3 (preserve follow-ups) - easy, medium impact  
3. **THIRD:** Fix Issue #4 (clean text) - easy, medium impact
4. **FOURTH:** Fix Issue #1 (orphaned labels) - medium complexity, high impact

---

## Key Principles

- ✅ Use **general patterns**, not hard-coded fixes
- ✅ Maintain **backward compatibility**
- ✅ Test each fix **independently**
- ✅ No regressions to **working features**
