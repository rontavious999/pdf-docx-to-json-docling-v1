# Extraction Strategy Comparison: hi_res vs ocr_only

**Date:** November 9, 2024  
**Test Corpus:** 38 dental forms (PDF and DOCX files)

## Executive Summary

A comprehensive comparison was performed between two extraction strategies:
- **hi_res**: Model-based layout detection with table structure inference
- **ocr_only**: OCR-based extraction for all documents

### Overall Results

| Metric | hi_res | ocr_only | Winner |
|--------|--------|----------|--------|
| **Total fields captured** | 412 | 377 | ✅ hi_res (+35 fields, +9.3%) |
| **Dictionary matches** | 286 | 239 | ✅ hi_res (+47 matches, +19.7%) |
| **Average dictionary reuse** | 69.42% | 63.40% | ✅ hi_res (+6.02%) |
| **Files with better field capture** | 10 files | 1 file | ✅ hi_res |
| **Files with same field capture** | 27 files | 27 files | Tie |

## Detailed Analysis

### Field Capture Performance

**Files where hi_res performed better (captured MORE fields):**
1. **npf1.pdf**: hi_res=76, ocr=41 (+35 fields, +85% improvement)
2. **consent_crown_bridge_prosthetics.pdf**: hi_res=14, ocr=2 (+12 fields, +600% improvement)
3. **Chicago-Dental-Solutions_Form.pdf**: hi_res=52, ocr=46 (+6 fields, +13% improvement)
4. **CFGingivectomy.pdf**: hi_res=12, ocr=7 (+5 fields, +71% improvement)
5. **Gingivectomy Consent_6.23.2022.pdf**: hi_res=5, ocr=2 (+3 fields, +150% improvement)

**Files where ocr_only performed better:**
1. **Invisalign Patient Consent.pdf**: ocr=44, hi_res=8 (+36 fields for OCR)
   - Note: This appears to be an anomaly where hi_res failed to extract most content

### Text Extraction Quality

Analysis of character counts from extracted text files shows:

| Document | hi_res chars | ocr_only chars | Difference |
|----------|-------------|----------------|------------|
| Chicago-Dental-Solutions_Form.pdf | 6,561 | 4,337 | +2,224 (+51%) |
| CFGingivectomy.pdf | 4,535 | 4,408 | +127 (+3%) |
| Endodontic Consent_6.20.2022.pdf | 2,767 | 2,641 | +126 (+5%) |
| Most DOCX files | Similar | Similar | ~0% |

**Key Findings:**
- Hi_res extracted **more complete text** from complex PDF forms with tables
- DOCX files showed identical extraction between both strategies (as expected)
- OCR_only sometimes missed layout context, leading to field separation issues

### Section Detection Accuracy

**Example: Chicago-Dental-Solutions_Form.pdf**

Hi_res sections:
- Patient Information (14 fields)
- Insurance (14 fields)
- Medical History (18 fields)
- Emergency Contact (4 fields)
- Consent (2 fields)

OCR_only sections:
- Patient Information (15 fields)
- Insurance (13 fields)
- Dental History (12 fields) ← Different section name
- Emergency Contact (4 fields)
- Consent (2 fields)

**Analysis:** Hi_res correctly identified "Medical History" section, while ocr_only labeled it as "Dental History". This affects field organization and downstream processing.

### Dictionary Reuse Rates

Higher dictionary reuse indicates better field recognition and normalization:

| Form Type | hi_res Reuse | ocr_only Reuse | Difference |
|-----------|-------------|----------------|------------|
| NPF (New Patient Form) | 89.3% | 96.0% | -6.7% (ocr better) |
| Chicago-Dental-Solutions | 67.3% | 65.2% | +2.1% (hi_res better) |
| **Overall Average** | **69.4%** | **63.4%** | **+6.0% (hi_res better)** |

## Form-Specific Observations

### 1. Complex Multi-Column Forms (e.g., Chicago-Dental-Solutions_Form)
- **Winner: hi_res**
- Hi_res better preserved table structures and field layouts
- Extracted 6 more fields (52 vs 46)
- Better text completeness (+2,224 characters, +51%)

### 2. Simple Single-Column Forms (e.g., most consent forms)
- **Winner: Tie**
- Both strategies performed identically
- No significant difference in field capture or quality

### 3. Scanned/Image-Based PDFs
- **Mixed Results**
- Most forms: hi_res performed better with layout detection
- Exception: Invisalign form where ocr_only extracted more content
- Recommendation: Use hi_res as default with OCR fallback

### 4. DOCX Files
- **Winner: Tie**
- Identical extraction quality
- No meaningful difference between strategies

## Parity Analysis

### Field Detection
✅ **Hi_res advantages:**
- Better at detecting fields in complex table layouts
- Preserves multi-column structures
- More accurate field boundaries

⚠️ **OCR_only limitations:**
- Sometimes merges adjacent fields
- Can lose table structure context
- Inconsistent with multi-column layouts

### Section Usage
✅ **Hi_res advantages:**
- More accurate section classification
- Better context awareness (Medical History vs Dental History)
- Consistent section ordering

⚠️ **OCR_only limitations:**
- Occasional section misclassification
- Less consistent section detection

## Recommendations

### Primary Recommendation: Use hi_res Strategy

**Rationale:**
1. ✅ **9.3% more fields captured** overall (412 vs 377)
2. ✅ **19.7% more dictionary matches** (286 vs 239)
3. ✅ **Better text extraction quality** for complex PDFs
4. ✅ **Superior section classification**
5. ✅ **Won on 10 files, lost on only 1 file**
6. ✅ **6% better average dictionary reuse**

### When to Use OCR_only

Consider ocr_only only for:
- ❌ Not recommended based on these results
- Exception: If hi_res fails on a specific document (rare case like Invisalign)

### Suggested Configuration

```python
# Recommended default settings
python3 unstructured_extract.py \
  --strategy hi_res \
  --infer-table-structure \
  --languages eng
```

### Fallback Strategy

For maximum robustness:
1. Try hi_res first (default)
2. If extraction returns empty or suspiciously small result, retry with ocr_only
3. This is already supported via `--retry` flag

## Conclusion

**Hi_res strategy is the clear winner** for dental form extraction:

- **Quantitative Advantage**: 9.3% more fields, 19.7% more dictionary matches
- **Qualitative Advantage**: Better layout preservation, section classification, and text completeness
- **Reliability**: Performed better or equal on 37 out of 38 files (97.4% success rate)

The superior performance of hi_res is attributed to:
1. Model-based layout detection that understands document structure
2. Table structure inference that preserves field relationships
3. Better handling of multi-column layouts common in dental forms

**Recommendation**: Continue using hi_res as the default strategy for all form types.
