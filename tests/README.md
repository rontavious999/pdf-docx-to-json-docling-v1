# Test Suite for PDF-to-JSON Docling Pipeline

This directory contains unit tests for the critical parsing functions in the pipeline.

## Running Tests

### Run all tests:
```bash
pytest tests/
```

### Run with verbose output:
```bash
pytest tests/ -v
```

### Run a specific test file:
```bash
pytest tests/test_text_preprocessing.py -v
```

### Run a specific test class or function:
```bash
pytest tests/test_question_parser.py::TestCleanOptionText -v
pytest tests/test_question_parser.py::TestCleanOptionText::test_removes_duplicate_words -v
```

### Run with coverage report:
```bash
pip install pytest-cov
pytest tests/ --cov=text_to_modento --cov-report=term-missing
```

## Test Structure

### `test_text_preprocessing.py`
Tests for text preprocessing functions:
- `coalesce_soft_wraps()` - Line joining logic
- `normalize_glyphs_line()` - Character normalization

### `test_question_parser.py`
Tests for question parsing functions:
- `clean_option_text()` - Option text cleaning
- `split_multi_question_line()` - Multi-question line splitting
- `extract_compound_yn_prompts()` - Yes/No question extraction
- Field pattern matching (dates, states, checkboxes)

### `test_template_matching.py`
Tests for template catalog and field matching:
- Template loading
- Exact key/title matching
- Alias resolution
- Fuzzy matching
- Field and section normalization

### `test_edge_cases.py`
Tests for edge case handling:
- Multi-field label splitting
- Grid column headers
- Inline checkbox detection
- Various challenging form layouts

### `test_multi_model_extract.py` ✨ **NEW - Multi-Model Extraction**
Tests for multi-model extraction system:
- **Quality metrics**: Text quality scoring and confidence calculation
- **Document type detection**: Scanned vs. digital PDF detection
- **Model recommendation**: Heuristics-based model selection
- **Extraction results**: Result handling and error management
- **Model availability**: Graceful fallback when models unavailable
- **Comparison mode**: Side-by-side model comparison

### `test_integration.py` ✨ **NEW - Patch 3**
End-to-end integration tests for the full pipeline:
- **PDF extraction**: Tests PDF → text extraction with auto-OCR
- **DOCX extraction**: Tests DOCX → text extraction
- **JSON conversion**: Tests text → JSON conversion with template matching
- **Full pipeline**: Tests complete PDF/DOCX → text → JSON workflow
- **Parallel processing**: Tests Patch 1 (unique file naming in parallel mode)
- **Error handling**: Tests graceful handling of unsupported file types

Test fixtures are located in `tests/fixtures/` directory.

## Test Data

Tests use representative form snippets, not hardcoded form-specific data. This ensures tests are general-purpose and will work with various dental intake forms.

## Adding New Tests

When adding new parsing logic or fixing bugs:

1. Create a test that demonstrates the issue
2. Verify the test fails without your fix
3. Implement the fix
4. Verify the test passes
5. Ensure existing tests still pass (no regressions)

Example test structure:
```python
def test_new_feature(self):
    """Clear description of what is being tested."""
    input_data = "sample input"
    expected_output = "expected result"
    
    result = function_to_test(input_data)
    
    assert result == expected_output, "Helpful error message"
```

## Continuous Integration

These tests should be run automatically on every commit to catch regressions early. Set up CI/CD (GitHub Actions, Jenkins, etc.) to run:

```bash
pytest tests/ --cov=text_to_modento --cov-report=xml
```

## Test Coverage Goals

- **Critical functions**: 100% coverage (line coalescing, option cleaning, template matching)
- **Parsing logic**: >80% coverage
- **Overall codebase**: >70% coverage

Check current coverage:
```bash
pytest tests/ --cov=text_to_modento --cov-report=term-missing
```

## Known Limitations

~~These tests focus on unit testing individual functions. Integration testing (full form processing) is done manually using sample forms in the `documents/` directory.~~

✅ **UPDATE (Patch 3)**: Integration tests have been added! See `test_integration.py` for end-to-end testing of the full pipeline with sample forms in `tests/fixtures/`.

## Test Coverage

The test suite now includes:
- **75 unit tests** covering individual parsing functions
- **21 multi-model extraction tests** covering quality metrics and model selection
- **7 integration tests** covering end-to-end workflows
- **Total: 121 tests** ensuring code quality and catching regressions

Test coverage:
- Text preprocessing and normalization
- Question parsing and field extraction
- Template matching and fuzzy search
- Edge cases (multi-field labels, grids, inline checkboxes)
- Multi-model extraction (quality scoring, document detection, model selection)
- Integration testing (PDF/DOCX → text → JSON pipeline)

Integration tests verify:
- Complete PDF → text → JSON pipeline
- Complete DOCX → text → JSON pipeline
- Multi-model extraction with quality metrics
- OCR fallback for scanned documents
- Parallel file naming (Patch 1)
- Error handling for edge cases
