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
pytest tests/ --cov=docling_text_to_modento --cov-report=term-missing
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
pytest tests/ --cov=docling_text_to_modento --cov-report=xml
```

## Test Coverage Goals

- **Critical functions**: 100% coverage (line coalescing, option cleaning, template matching)
- **Parsing logic**: >80% coverage
- **Overall codebase**: >70% coverage

Check current coverage:
```bash
pytest tests/ --cov=docling_text_to_modento --cov-report=term-missing
```

## Known Limitations

These tests focus on unit testing individual functions. Integration testing (full form processing) is done manually using sample forms in the `documents/` directory.

Consider adding integration tests in the future:
```python
def test_full_form_processing():
    """Test complete pipeline on sample form."""
    # Process a known sample form
    # Verify expected field count and key fields
```
