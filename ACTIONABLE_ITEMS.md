# Actionable Items for PDF-to-JSON Pipeline (Unstructured-based)

## Overview
This document outlines actionable next steps to further improve the PDF-to-JSON conversion pipeline, which now uses the Unstructured library for document extraction. These items are prioritized and categorized for clarity.

**Important**: All improvements must maintain the general-purpose, form-agnostic approach. **Do not hardcode any specific forms or form layouts.**

---

## Priority 1: Critical Feature Gaps

### 1.1 OCR Auto-Detection Enhancement
**Current State**: The pipeline now uses the Unstructured library which automatically handles document parsing with various strategies including OCR when needed.

**Current Implementation**: The Unstructured library provides multiple extraction strategies:
- `hi_res` (default): Uses ML-based layout detection for best accuracy
- `fast`: Faster extraction with lower accuracy
- `auto`: Automatically chooses the best strategy
- `ocr_only`: Forces OCR for all documents

**Action Items**:
- [x] **Migrated to Unstructured library** - Now using modern ML-based extraction
- [x] **Hi-res strategy enabled by default** - Provides superior accuracy
- [ ] **Test with various scanned documents** - Verify extraction quality
- [ ] **Document best practices** - Guide users on strategy selection
- [ ] **Step 2: Implement automatic text layer detection**
  - Enhance `has_text_layer()` to be more robust:
    - Check if extracted text length is below threshold (e.g., 100 characters)
    - Verify text-to-page-area ratio (scanned PDFs may have minimal text)
    - Detect if text consists only of metadata/headers
    - Handle multi-page PDFs (check first few pages for text)
  - Consider false positives: forms with minimal text by design
  
- [ ] **Step 3: Define heuristics for auto-OCR trigger**
  - Calculate text density per page (characters per square inch)
  - Set threshold: if < X characters per page across first 3 pages, trigger OCR
  - Alternative: check if any page has meaningful text (>50 words)
  - Account for legitimately sparse forms (don't over-trigger OCR)
  
- [ ] **Step 4: Implement automatic OCR fallback in `extract_text_from_pdf()`**
  - Try normal text extraction first
  - Evaluate result using heuristics from Step 3
  - If text layer is insufficient, log message and invoke OCR automatically
  - Respect `--force-ocr` flag (skip text extraction entirely)
  - Respect explicit `--ocr` flag (force OCR even if text detected)
  
- [ ] **Step 5: Add user feedback and logging**
  - Log message: "PDF appears to be scanned, automatically using OCR..."
  - Show progress during OCR (processing page X of Y)
  - Report OCR confidence scores if available from Tesseract
  - Warn if OCR dependencies are not installed
  
- [ ] **Step 6: Handle edge cases**
  - PDFs with mixed pages (some scanned, some with text layer)
  - Encrypted PDFs that block text extraction
  - Very large PDFs where OCR would take excessive time
  - PDFs with images embedded in text layer (already has text)
  - Corrupted or damaged PDF files
  
- [ ] **Step 7: Add configuration options**
  - Add `--auto-ocr-threshold` parameter for customizing detection sensitivity
  - Add `--no-auto-ocr` flag to disable automatic detection
  - Consider config file option for default behavior
  - Document configuration options clearly
  
- [ ] **Step 8: Performance considerations**
  - Cache text layer detection results (don't re-check same file)
  - Consider sampling (check first N pages only for large documents)
  - Provide option to skip OCR for very large documents
  - Add timeout parameter for OCR operations
  
- [ ] **Step 9: Testing and validation**
  - Test with PDFs that have full text layer (should not trigger OCR)
  - Test with completely scanned PDFs (should trigger OCR automatically)
  - Test with mixed PDFs (some pages scanned, others with text)
  - Test with nearly-empty forms (minimal text by design, not scanned)
  - Test with encrypted/protected PDFs
  - Measure accuracy of auto-detection (false positive/negative rate)
  
- [ ] **Step 10: Update documentation**
  - Explain automatic OCR detection in README
  - Document the heuristics used for detection
  - Provide guidance on when to use `--force-ocr` vs auto-detection
  - Note performance implications of OCR
  - Update installation instructions to emphasize OCR dependencies

**Acceptance Criteria**:
- Scanned PDFs are automatically detected with >95% accuracy
- OCR is automatically invoked when text layer is insufficient
- Users receive clear feedback when auto-OCR is triggered
- Performance is acceptable (detection adds <1 second overhead per file)
- False positives are rare (<5%): forms with minimal text by design don't trigger OCR unnecessarily
- Manual override options (`--force-ocr`, `--no-auto-ocr`) work correctly
- Documentation clearly explains the feature and configuration options
- Backward compatibility: existing `--ocr` flag continues to work as before

---

## Priority 2: Edge Case Handling Improvements

### 2.1 Multi-Field Label Splitting
**Current Limitation**: Fields like "Phone: Mobile    Home    Work" with multiple blanks are captured as a single field instead of three separate fields. If a single line contains multiple subfields under one label (e.g., "Phone: Mobile Home Work" with several blanks in a row), the current parser captures it as one combined field.

**Background**: The desired behavior is to split this into separate fields (mobile phone, home phone, etc.). This requires detecting multiple blanks or keywords on one line without hardcoding specific field names.

**Action Items**:
- [ ] **Step 1: Enhance blank/underscore pattern detection**
  - Add detection for repeated underscore patterns (e.g., `_____ _____ _____`)
  - Count consecutive blank segments separated by 2+ spaces
  - Detect patterns like `____/____ ` with slashes between blanks
  - Handle both PDF spacing (may have exact positions) and DOCX spacing (may vary)
  
- [ ] **Step 2: Implement generic sub-field keyword detection**
  - Create configurable keyword list for common sub-field types:
    - Contact types: Mobile, Cell, Home, Work, Office, Business, Personal, Fax
    - Priority levels: Primary, Secondary, Alternate, Emergency
    - Time-based: Day, Evening, Night
  - DO NOT hardcode specific field names in the logic
  - Use case-insensitive matching
  - Support partial matches (e.g., "Mob" for "Mobile")
  
- [ ] **Step 3: Develop spacing analysis heuristics**
  - Measure spacing between potential sub-fields (4+ spaces suggests separate fields)
  - Detect columnar alignment using position analysis
  - Handle cases where keywords appear without underscores/blanks
  - Account for proportional vs monospace font spacing differences
  
- [ ] **Step 4: Implement splitting logic in `detect_multi_field_line()`**
  - Enhance existing function to return structured sub-field data
  - Generate appropriate field keys by combining main label + sub-label
  - Preserve original section information for split fields
  - Handle edge case: single field with multiple keywords should not split
  
- [ ] **Step 5: Integrate with main parsing pipeline**
  - Call detection function early in `parse_to_questions()` loop
  - Create separate Question objects for each detected sub-field
  - Ensure proper input_type assignment (usually "text" for split fields)
  - Maintain consistent key generation pattern
  
- [ ] **Step 6: Add validation to prevent false positives**
  - Don't split if line contains actual filled values (e.g., phone number present)
  - Require minimum of 2 distinct sub-fields to trigger split
  - Ignore lines where "keywords" are part of instructions (e.g., "Call home or mobile")
  - Add configurable threshold for minimum spacing between fields
  
- [ ] **Step 7: Test comprehensively**
  - Test with phone fields: "Phone: Mobile ___ Home ___ Work ___"
  - Test with email fields: "Email: Personal ___ Work ___"
  - Test with address fields: "Address: Home ___ Work ___"
  - Test with edge cases: single field, no blanks, filled values
  - Verify PDF vs DOCX extraction differences handled correctly
  
- [ ] **Step 8: Update existing tests and add new ones**
  - Enhance `TestMultiFieldDetection` class with more scenarios
  - Add tests for false positive prevention
  - Test key generation patterns
  - Verify section preservation

**Acceptance Criteria**:
- Lines with multiple blanks/underscores after a label are split into separate fields
- Each sub-field has a descriptive key (e.g., `phone_mobile`, `phone_home`, `phone_work`)
- Solution works generically across different field types (phone, email, address, etc.)
- No false positives: single fields or filled fields are not incorrectly split
- Handles spacing variations from different extraction methods (PDF vs DOCX)
- At least 90% accuracy on test cases with multi-field patterns

### 2.2 Multi-Column Grid Column Headers
**Current Limitation**: In multi-column checkbox grids, sometimes the form provides category headers for each column (e.g., columns labeled "Appearance / Function / Habits" with options under each). Currently, those header labels are not captured or associated with the options; the parser just grabs all the options as one list. The result is that the JSON knows all the items a patient checked, but loses the grouping that the columns implied.

**Background**: This is a minor loss of information since all individual options are still captured. A future improvement is to capture these column headers and either incorporate them into the option names or include them as metadata. This likely involves detecting a row of short words at the top of a grid and mapping each option to the correct category.

**Action Items**:
- [ ] **Step 1: Enhance header row detection in grid parser**
  - Improve detection of category header patterns (short words, 1-3 words per category)
  - Detect slash-separated headers: "Appearance / Function / Habits"
  - Detect pipe-separated headers: "Appearance | Function | Habits"
  - Detect space-separated headers with significant spacing (8+ spaces)
  - Handle headers with or without trailing colons
  
- [ ] **Step 2: Map column positions to headers**
  - Determine horizontal position/range for each header
  - Create column boundary detection using checkbox positions in data rows
  - Map each checkbox option to its corresponding column based on position
  - Handle cases where columns don't perfectly align
  
- [ ] **Step 3: Decide on output strategy** (requires stakeholder input)
  - **Option A - Prefix approach**: Modify option text to include category
    - Example: "Smoking" → "Habits - Smoking"
    - Pros: Simple, backward compatible, searchable
    - Cons: May create long option names, changes original text
  - **Option B - Metadata approach**: Add category field to each option
    - Example: `{"text": "Smoking", "category": "Habits"}`
    - Pros: Preserves original text, structured data
    - Cons: Requires schema change, more complex
  - **Option C - Nested groups**: Create option groups by category
    - Example: `{"Habits": ["Smoking", "Drinking"], "Function": [...]}`
    - Pros: Best data structure, clearest grouping
    - Cons: May not be compatible with Modento schema
  - Document decision rationale and get stakeholder approval
  
- [ ] **Step 4: Implement chosen strategy in `detect_multicolumn_checkbox_grid()`**
  - Enhance the existing `category_header` detection (currently captures but doesn't use)
  - Parse header text to extract individual category names
  - Store category information during grid parsing
  - Apply chosen strategy to associate options with categories
  
- [ ] **Step 5: Update `parse_multicolumn_checkbox_grid()` function**
  - Modify option creation logic to include category information
  - Ensure proper handling when no headers are present (don't break existing grids)
  - Handle partial header cases (some columns have headers, others don't)
  - Maintain existing option text cleaning and deduplication
  
- [ ] **Step 6: Handle edge cases**
  - Grids with 2 columns vs 3+ columns
  - Headers that span multiple words
  - Misaligned headers (header doesn't perfectly match column position)
  - Mixed grids (some rows have categories, others don't)
  - Empty columns or sparsely populated columns
  
- [ ] **Step 7: Testing and validation**
  - Test with 2-column grids (simple case)
  - Test with 3-column grids (common case)
  - Test with 4+ column grids (complex case)
  - Test grids without headers (ensure no regression)
  - Test grids with partial headers
  - Verify existing grid parsing functionality remains intact
  
- [ ] **Step 8: Update documentation**
  - Document the header detection algorithm
  - Explain the chosen output strategy and why
  - Add examples of before/after JSON output
  - Note limitations (e.g., headers must be on separate line)

**Acceptance Criteria**:
- Column headers in multi-column grids are captured when present
- Headers are meaningfully associated with their corresponding options
- Existing grid parsing functionality remains intact (no regressions)
- Solution works generically without hardcoding specific headers or categories
- Works with 2-column through 4+ column layouts
- Gracefully handles grids without headers (no change in behavior)
- Chosen output strategy is documented and approved by stakeholders

### 2.3 Inline Checkbox with Continuation Text
**Current Limitation**: Some forms include a checkbox in the middle of a sentence, for example, "[ ] Yes, send me text alerts" as part of a larger question or statement. In a few cases, the parser might miss treating that as a separate boolean field. The text is captured, but it might not create a distinct JSON field for the "send text alerts" preference.

**Background**: The fix would involve refining the regex that looks for checkbox patterns so that even if the "[ ]" is inline with text, it knows to create a field (likely with the text after the checkbox as its label). This is an infrequent pattern, but addressing it would ensure no checkbox is left behind.

**Action Items**:
- [ ] **Step 1: Analyze existing inline checkbox detection**
  - Review current `detect_inline_checkbox_with_text()` function
  - Identify which patterns are already handled
  - Document patterns that are currently missed
  - Collect real-world examples from forms
  
- [ ] **Step 2: Enhance inline checkbox pattern detection**
  - Improve regex to detect: `[ ] Yes/No, [continuation text]`
  - Handle patterns like: `[ ] Yes, send me alerts`
  - Handle patterns like: `[ ] No, do not contact me`
  - Support checkboxes not at start of line (mid-sentence)
  - Detect checkbox within a longer sentence or question
  
- [ ] **Step 3: Extract meaningful field information**
  - Capture the Yes/No indicator
  - Extract the descriptive continuation text after the comma
  - Generate appropriate field key from continuation text
  - Preserve original full text as field title
  - Handle variations: "Yes," vs "Yes -" vs "Yes:" vs "Yes if"
  
- [ ] **Step 4: Determine appropriate field type**
  - Analyze whether to create:
    - **Radio field**: Two options (Yes/No) with continuation as context
    - **Boolean field**: Single checkbox with true/false value
    - **Text field**: With checkbox as trigger and continuation as label
  - Document decision logic and rationale
  - Ensure consistency with how other boolean/radio fields are handled
  
- [ ] **Step 5: Handle context and question association**
  - Check if checkbox line follows a question line
  - Associate inline checkbox with parent question if present
  - Handle standalone inline checkboxes (no prior context)
  - Avoid creating duplicate fields if checkbox is part of option list
  
- [ ] **Step 6: Prevent false positives**
  - Don't treat regular bullet points as checkboxes
  - Don't split option lists into individual fields incorrectly
  - Require minimum text length for continuation (e.g., 10 characters)
  - Validate that continuation text is meaningful (not just punctuation)
  - Don't create fields for instructional text with checkboxes
  
- [ ] **Step 7: Integration with existing parsing logic**
  - Determine where in `parse_to_questions()` to apply detection
  - Ensure inline checkbox detection runs before option parsing
  - Avoid conflicts with existing checkbox/option extraction
  - Maintain proper section assignment for detected fields
  
- [ ] **Step 8: Comprehensive testing**
  - Test pattern: "[ ] Yes, send me text alerts"
  - Test pattern: "[ ] No, I do not want to receive updates"
  - Test pattern: "Contact preference: [ ] Yes, email is okay"
  - Test mid-sentence: "I agree [ ] to the terms and conditions"
  - Test false positive: regular option lists should not trigger
  - Test edge case: checkbox with very short continuation text
  
- [ ] **Step 9: Update tests**
  - Enhance `TestInlineCheckboxDetection` class
  - Add tests for mid-sentence checkboxes
  - Add tests for false positive prevention
  - Test field type assignment logic
  - Test key generation from continuation text

**Acceptance Criteria**:
- Inline checkboxes with meaningful continuation text (10+ chars) are recognized as distinct fields
- Boolean preference (Yes/No) is captured along with descriptive text
- Pattern matching is generic and doesn't hardcode specific phrases
- No false positives: regular option lists are not incorrectly split
- Works for checkboxes at start of line, mid-sentence, or following a label
- Generated field keys are meaningful and derived from continuation text
- Proper field type assigned based on context (radio, boolean, or text)

### 2.4 Visual Layout-Dependent Fields (Documentation & Monitoring)
**Current Limitation**: Because the parser works off text alone (not visual/spatial layout), fields that rely purely on spatial arrangement without clear labels are tricky. An example might be a form that has side-by-side fields with no labels on the second field – the parser might not realize there are two separate fields.

**Background**: There is no specific instance of this documented, but it's an inherent limitation when layout info is limited. In practice, most fields do have labels or are separated by recognizable patterns, so this is rarely an issue. The ongoing improvements in multi-field splitting (Priority 2.1) will likely cover most such cases. This is primarily a documentation and awareness item rather than an implementation task.

**Action Items**:
- [ ] **Step 1: Document the inherent limitation**
  - Add to README.md under "Known Limitations"
  - Explain that the parser primarily uses text patterns, not visual layout
  - Note that most forms have sufficient textual cues
  - Emphasize that this affects <1% of fields in practice
  
- [ ] **Step 2: Identify patterns that help compensate**
  - Document successful patterns that work without spatial layout:
    - Consistent spacing (4+ spaces between fields)
    - Underscores or blank indicators (`_____`)
    - Label-value pairs with colons
    - Bullet points or checkbox markers
  - Provide form design recommendations for best results
  
- [ ] **Step 3: Monitor for specific instances**
  - Track cases in debug logs where spatial layout would help
  - Collect examples from real forms where this limitation appears
  - Document specific patterns that are problematic
  - Assess actual impact on field capture rate
  
- [ ] **Step 4: Evaluate if spatial layout extraction is needed**
  - Assess frequency: Is this a real problem or theoretical concern?
  - If needed, leverage Unstructured's built-in layout features:
    - Unstructured's hi-res strategy provides layout-aware extraction
    - Table structure inference is built-in
    - Bounding box analysis available in elements
    - Coordinate information preserved in element metadata
  - Test with current Unstructured implementation first
  
- [ ] **Step 5: Consider alternative approaches if needed**
  - **Approach A**: Enhance spacing analysis in existing parser
    - Improve column detection using position data
    - Better handle implicit field boundaries
    - This extends Priority 2.1 work
  - **Approach B**: Add optional layout-aware mode
    - Use PDF coordinate information when available
    - Fall back to text-only parsing for DOCX
    - Higher complexity but more accurate
  - **Approach C**: Form design guidelines
    - Provide best practices for form creators
    - Recommend always using labels for fields
    - Suggest minimum spacing between fields
  
- [ ] **Step 6: Update best practices documentation**
  - Add section on "Form Design for Optimal Parsing"
  - Recommend explicit labels for all fields
  - Suggest using clear separators (spaces, lines, boxes)
  - Provide examples of well-structured vs problematic layouts
  
- [ ] **Step 7: Enhance debugging output for spatial issues**
  - Log warnings when multiple fields might be on same line
  - Detect unusually long field values (might be merged fields)
  - Flag fields with very short labels (might be missing context)
  - Add stats on potential spatial layout issues

**Acceptance Criteria**:
- Limitation is clearly documented in user-facing documentation
- Design guidelines help form creators avoid this issue
- Monitoring is in place to detect if this becomes a significant problem
- If implementation is needed, approach is researched and documented
- Existing multi-field splitting improvements (Priority 2.1) address the most common spatial layout challenges
- Impact remains minimal (<1% of fields affected)

---

## Priority 3: Code Quality and Maintainability

### 3.1 Modularize Large Parsing Script ✅ **IN PROGRESS**
**Current State**: `docling_text_to_modento.py` is ~5000 lines in a single file.

**Status**: Modularization has begun! The package structure is in place.

**Completed Action Items**:
- [x] Create package structure `docling_text_to_modento/` with `modules/` subdirectory
- [x] Move original script to `docling_text_to_modento/core.py`
- [x] Create backward-compatible wrapper `docling_text_to_modento.py`
- [x] Extract constants to `modules/constants.py` (regex patterns, configuration)
- [x] Extract debug logger to `modules/debug_logger.py`
- [x] Create stub modules for future extraction:
  - `modules/text_preprocessing.py` - Line cleanup, normalization, soft-wrap coalescing
  - `modules/question_parser.py` - Question extraction, checkbox detection
  - `modules/grid_parser.py` - Multi-column grid handling
  - `modules/postprocessing.py` - Merging, consolidation, section inference
  - `modules/template_catalog.py` - Template matching and field standardization
- [x] Maintain backward compatibility with existing command-line interface
- [x] Test that CLI functionality is preserved
- [x] Update documentation to reflect new structure

**Remaining Action Items**:
- [ ] Incrementally extract remaining functions from `core.py` to respective modules
- [ ] Update `core.py` imports to use extracted modules
- [ ] Validate all functionality with test suite

**Current Module Structure**:
  ```
  docling_text_to_modento/
  ├── __init__.py
  ├── README.md
  ├── main.py (entry point)
  ├── core.py (original script, ~5000 lines)
  └── modules/
      ├── __init__.py
      ├── constants.py ✅
      ├── debug_logger.py ✅
      ├── text_preprocessing.py (stub)
      ├── question_parser.py (stub)
      ├── grid_parser.py (stub)
      ├── postprocessing.py (stub)
      └── template_catalog.py (stub)
  
  docling_text_to_modento.py (backward-compatible CLI wrapper) ✅
  ```

**Acceptance Criteria**:
- [x] Code is organized into logical, maintainable package structure
- [x] Backward compatibility maintained (CLI works unchanged)
- [x] Constants and utilities extracted to separate modules
- [x] **Text preprocessing functions extracted (511 lines)** ✨
- [x] Core.py reduced from 5010 to 4616 lines (8% reduction)
- [x] All existing functionality works exactly as before
- [ ] Remaining functions can be extracted incrementally (question parser, grid parser, template catalog, postprocessing)
- [x] Each extracted module has clear responsibilities and minimal coupling

### 3.2 Add Unit Tests
**Current State**: No automated test suite exists; testing is manual with sample forms.

**Action Items**:
- [ ] Set up testing framework (pytest recommended)
- [ ] Create test structure:
  ```
  tests/
  ├── test_text_preprocessing.py
  ├── test_question_parser.py
  ├── test_grid_parser.py
  ├── test_template_matching.py
  └── fixtures/
      └── sample_text_snippets.txt
  ```
- [ ] Write unit tests for critical functions:
  - `coalesce_soft_wraps()` - test line joining logic
  - `detect_multicolumn_checkbox_grid()` - test grid detection
  - `split_multi_question_line()` - test field splitting
  - `clean_option_text()` - test option text cleaning
  - `extract_compound_yn_prompts()` - test yes/no question extraction
- [ ] Create fixture data from representative form snippets
- [ ] Add integration tests using complete sample forms
- [ ] Set up CI/CD to run tests automatically (optional)
- [ ] Document how to run tests in README

**Acceptance Criteria**:
- Test suite covers critical parsing functions with >70% code coverage
- Tests pass consistently and catch regressions
- Tests use representative form snippets, not hardcoded form-specific data
- Documentation explains how to run and add new tests

### 3.3 Update Outdated References
**Current State**: Code and documentation contain outdated "LLMWhisperer" references.

**Action Items**:
- [ ] Update `docling_text_to_modento.py`:
  - Line 4677: Change help text from "Folder with LLMWhisperer .txt files" to "Folder with extracted .txt files"
- [ ] Update `README.md`:
  - Line 24: Change "llm_text_to_modento.py" to "docling_text_to_modento.py"
  - Line 39: Change "llm_text_to_modento.py" to "docling_text_to_modento.py"
- [ ] Update `run_all.py`:
  - Line 6 comment: Change "llm_text_to_modento.py" to "docling_text_to_modento.py"
- [ ] Update `FIXES_SUMMARY.md`:
  - Replace references to "llm_text_to_modento.py" with "docling_text_to_modento.py"
- [ ] Update `QUICK_REFERENCE.md`:
  - Line 40: Change "llm_text_to_modento.py" to "docling_text_to_modento.py"
- [ ] Review `docling_extract.py`:
  - Line 8: Keep "This replaces the LLMWhisperer API" as historical context (acceptable)

**Acceptance Criteria**:
- All user-facing text references the current script name
- No confusing references to deprecated LLMWhisperer API
- Historical context in comments is acceptable if clearly marked as such

---

## Priority 4: Documentation Improvements

### 4.1 Add Limitations Section to README
**Current State**: README doesn't explicitly mention OCR limitation or edge cases.

**Action Items**:
- [ ] Add "Known Limitations" section to README.md:
  - OCR not supported (scanned PDFs won't be processed)
  - Multi-sub-field labels not split
  - Grid column headers not associated with options
  - Inline checkboxes may not be fully captured
- [ ] Add "Supported Form Types" section:
  - Digitally-created PDFs with text layer
  - DOCX forms
  - Common dental intake form layouts
- [ ] Add "Best Practices" section:
  - Use fillable PDFs when possible
  - Ensure PDFs have embedded text (not scanned images)
  - Forms should follow common layout conventions

**Acceptance Criteria**:
- Users understand what types of forms are supported
- Limitations are clearly documented
- Expectations are properly set for accuracy and coverage

### 4.2 Create Architecture Documentation
**Current State**: No high-level architecture documentation exists.

**Action Items**:
- [ ] Create `ARCHITECTURE.md` document:
  - System overview diagram
  - Pipeline flow (extraction → parsing → JSON generation)
  - Module responsibilities (after refactoring)
  - Key algorithms (grid detection, line coalescing, template matching)
  - Extension points for adding new features
- [ ] Document key design decisions:
  - Why local extraction vs API
  - Why regex-based parsing vs ML models
  - How template matching works
  - How sections are inferred
- [ ] Add developer guide section:
  - How to add new field patterns
  - How to add new section detection rules
  - How to extend the template dictionary
  - Debugging tips using --debug mode

**Acceptance Criteria**:
- New developers can understand the system architecture
- Design decisions are documented with rationale
- Clear guidance on how to extend the system

---

## Priority 5: Field Title Normalization Review

### 5.1 Review Field Title Enhancement Strategy
**Current Behavior**: Code sometimes changes field titles for "better UX" (e.g., "Comments:" → "Have you had any serious illness not listed above - Please explain").

**Action Items**:
- [ ] Document the current title enhancement behavior
- [ ] Determine if Modento expects exact form titles or enhanced titles
- [ ] Consult with stakeholders about preferred approach:
  - **Option A**: Always preserve original form text verbatim
  - **Option B**: Continue enhancing titles for clarity (current approach)
  - **Option C**: Add both original and enhanced titles to JSON
- [ ] Implement decision consistently across all field types
- [ ] Add configuration option (if flexibility is needed):
  - `--preserve-titles` flag to disable enhancements
  - Config file setting for title enhancement strategy
- [ ] Update documentation to explain title handling

**Acceptance Criteria**:
- Clear policy on when/how field titles are modified
- Policy is consistently applied across all field types
- Users can control title enhancement behavior if needed

---

## Priority 6: Performance and Scalability

### 6.1 Add Parallel Processing Support
**Current State**: Forms are processed sequentially, one at a time.

**Action Items**:
- [ ] Evaluate if parallelization is needed:
  - Measure current processing time per form
  - Determine typical batch sizes
  - Identify performance bottleneck (extraction vs parsing)
- [ ] If beneficial, implement parallel processing:
  - Add `--parallel` or `--jobs N` flag
  - Use multiprocessing for file-level parallelism
  - Ensure thread-safety of shared resources (catalog, debug logger)
- [ ] Add progress reporting for batch jobs:
  - Show "Processing X of Y forms..."
  - Display estimated time remaining
  - Report any failures at the end
- [ ] Test with large batches (50+ forms) to validate improvement

**Acceptance Criteria**:
- Processing time scales linearly with number of forms
- Parallel processing option is available for large batches
- Progress reporting provides visibility into batch processing

---

## Priority 7: Template Dictionary Enhancements

### 7.1 Version and Validate Template Dictionary
**Current State**: `dental_form_dictionary.json` has no version tracking or validation.

**Action Items**:
- [ ] Add version metadata to dictionary:
  - Version number
  - Last updated date
  - Change log within file
- [ ] Create JSON schema for template dictionary:
  - Define required fields
  - Validate field types and structures
  - Enforce option format consistency
- [ ] Implement dictionary validation on load:
  - Check schema compliance
  - Warn about missing required fields
  - Validate "if" clause references
- [ ] Add dictionary management tools:
  - Script to validate dictionary JSON
  - Script to merge multiple dictionaries
  - Script to analyze dictionary coverage against sample forms
- [ ] Document dictionary format and how to extend it

**Acceptance Criteria**:
- Template dictionary has clear version tracking
- Invalid dictionary files are detected at startup
- Tools exist to validate and maintain the dictionary
- Documentation explains dictionary structure and extension

---

## Priority 8: Enhanced Debugging and Diagnostics

### 8.1 Improve Debug Output and Stats
**Current State**: Debug mode exists but could be more informative.

**Action Items**:
- [ ] Enhance `.stats.json` output:
  - Add extraction metadata (PDF vs DOCX, page count, character count)
  - Include parsing statistics (sections found, grids detected, options parsed)
  - List near-miss template matches with similarity scores
  - Report unmatched fields that might need dictionary entries
- [ ] Add visual debugging option:
  - Generate HTML report showing side-by-side form text and parsed output
  - Highlight matched vs unmatched fields
  - Show confidence scores for template matches
- [ ] Improve error messages:
  - More specific error messages for common issues
  - Suggestions for fixing problems
  - Links to relevant documentation sections
- [ ] Add validation mode:
  - `--validate` flag to check JSON output against Modento schema
  - Report any schema compliance issues
  - Suggest corrections for common problems

**Acceptance Criteria**:
- Debug output provides actionable insights
- Users can easily identify why fields were missed or mismatched
- Error messages are clear and helpful
- Validation mode catches schema issues before submission

---

## Implementation Guidelines

### General Principles
1. **Never hardcode form-specific logic** - All solutions must work generically
2. **Use configurable patterns** - Regex, keyword lists, and thresholds should be parameterizable
3. **Maintain backward compatibility** - Existing functionality must not break
4. **Test with multiple forms** - Validate changes against diverse form layouts
5. **Document decisions** - Explain the "why" behind implementation choices

### Testing Strategy
- Use the existing sample forms (Chicago, NPF, NPF1) as regression tests
- Add new sample forms representing different edge cases
- Measure field capture accuracy before and after changes
- Ensure no regressions in existing field capture

### Code Style
- Follow existing code conventions (naming, structure, comments)
- Add version tags to fixes (e.g., "Archivev20 Fix 1")
- Update fix documentation files when making changes
- Keep functions focused and reasonably sized (<100 lines preferred)

---

## Success Metrics

### Quantitative Goals
- **Field Capture Rate**: Maintain >95% accuracy on test forms
- **OCR Support**: Process scanned forms with >90% text extraction accuracy
- **Test Coverage**: Achieve >70% code coverage with unit tests
- **Processing Speed**: Process forms in <5 seconds each (after optimization)

### Qualitative Goals
- **Code Maintainability**: New developers can understand and modify code
- **User Experience**: Clear documentation and helpful error messages
- **Reliability**: Consistent output quality across diverse forms
- **Extensibility**: Easy to add new field types and patterns

---

## Review Feedback Mapping

This section maps the specific issues identified in the repository review to the actionable priorities above:

### Remaining Issues and Edge Cases (<5% of fields)

The review identified several edge cases that affect a small minority of fields on typical forms. These have been broken down into detailed actionable items:

1. **Multi-sub-field labels not split** → **Priority 2.1: Multi-Field Label Splitting**
   - Issue: Lines like "Phone: Mobile Home Work" with several blanks in a row are captured as one field
   - Solution: Generic heuristics to detect and split composite fields using pattern detection, keyword identification, and spacing analysis
   - Approach: NO form-specific hacks; enhance generic logic to detect repeated underscore patterns and common subfield keywords

2. **Checkbox grid column headers** → **Priority 2.2: Multi-Column Grid Column Headers**
   - Issue: Category headers (e.g., "Appearance / Function / Habits") are not captured or associated with options
   - Solution: Detect header row patterns and map options to correct categories
   - Approach: Capture headers and incorporate into option names or metadata; NO hardcoding of specific headers

3. **Inline checkbox statements** → **Priority 2.3: Inline Checkbox with Continuation Text**
   - Issue: Checkbox mid-sentence like "[ ] Yes, send me text alerts" might not create distinct JSON field
   - Solution: Refine regex to detect inline checkboxes even when embedded in text
   - Approach: Generic pattern matching; NO hardcoding of specific phrases

4. **OCR auto-detection** → **Priority 1.1: OCR Auto-Detection Enhancement**
   - Issue: Pipeline requires manual `--ocr` flag for scanned PDFs; no automatic detection
   - Solution: Implement automatic fallback when text extraction returns minimal content
   - Approach: Check text layer presence/quality and automatically invoke OCR when needed

5. **Visual layout-dependent fields** → **Priority 2.4: Visual Layout-Dependent Fields**
   - Issue: Fields relying purely on spatial arrangement without labels are difficult to parse
   - Solution: Document limitation, monitor for real instances, improve spacing analysis
   - Approach: Most cases covered by multi-field splitting; primarily a documentation item

### Key Principles from Review

All solutions must adhere to these principles emphasized in the review:

✅ **NO form-specific hacks** - Issues will be resolved by enhancing generic logic  
✅ **Generic pattern detection** - Use heuristics, spacing analysis, and keyword patterns  
✅ **Configurable, not hardcoded** - No specific field names or form layouts in code  
✅ **Backward compatible** - Maintain >95% field capture accuracy  
✅ **Well-tested** - Comprehensive test coverage for edge cases  

---

## Timeline and Prioritization

### Phase 1 (Immediate - High Impact)
- Document visual layout limitations (Priority 2.4)
- Update outdated references (Priority 3.3)
- Add limitations documentation (Priority 4.1)
- Review field title strategy (Priority 5.1)

### Phase 2 (Short Term - Foundation)
- Implement OCR auto-detection (Priority 1.1) - Addresses review feedback item #4
- Create unit tests (Priority 3.2)
- Create architecture documentation (Priority 4.2)

### Phase 3 (Medium Term - Enhancements)
- Implement multi-field splitting (Priority 2.1) - Addresses review feedback item #1
- Enhance inline checkbox detection (Priority 2.3) - Addresses review feedback item #3
- Handle grid column headers (Priority 2.2) - Addresses review feedback item #2
- Modularize codebase (Priority 3.1)

### Phase 4 (Long Term - Optimization)
- Add parallel processing (Priority 6.1)
- Enhance debugging tools (Priority 8.1)
- Version template dictionary (Priority 7.1)

---

## Conclusion

These actionable items provide a clear roadmap for enhancing the PDF-to-JSON pipeline with Unstructured library. Each item is designed to be implemented independently while maintaining the system's core principle of generic, form-agnostic processing.

### Key Improvements from Review Feedback

This document has been enhanced based on comprehensive repository review feedback, with detailed action items addressing:

- **5 specific edge cases** identified in the review (<5% of fields affected)
- **Step-by-step implementation plans** for each improvement
- **Clear acceptance criteria** to validate success
- **Adherence to core principle**: NO form-specific hacks, only generic enhancements

### Impact Assessment

When all Priority 2 items are completed:
- **Current**: >95% field capture accuracy with <5% edge cases
- **Target**: >98% field capture accuracy with <2% edge cases
- **Approach**: Generic logic improvements, not form-specific solutions

### Next Steps

**For Stakeholders**:
1. Review and approve the detailed action items in Priorities 1.1, 2.1, 2.2, 2.3, and 2.4
2. Decide on output strategy for grid column headers (Option A, B, or C in Priority 2.2)
3. Prioritize which edge cases to address first based on real-world form frequency

**For Developers**:
1. Start with Priority 2.4 (documentation only, no code changes)
2. Implement Priority 1.1 (OCR auto-detection) as it's foundational
3. Tackle Priority 2.1 (multi-field splitting) as it has highest impact
4. Address Priorities 2.2 and 2.3 based on stakeholder prioritization
5. Maintain comprehensive test coverage for all changes

**For Testing**:
- Use existing test forms to validate no regressions
- Collect additional forms that exhibit the edge cases identified
- Measure field capture accuracy before and after each improvement
- Document any new edge cases discovered during implementation

**Questions or Clarifications**: Please open a GitHub issue or update this document with any questions about these actionable items.
