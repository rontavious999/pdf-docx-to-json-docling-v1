# text_to_modento Package

This directory contains the modularized version of the `text_to_modento.py` script.

## Structure

```
text_to_modento/
├── __init__.py              # Package initialization
├── README.md                # This file
├── main.py                  # Entry point (delegates to core)
├── core.py                  # Main parsing logic (original ~5000 line script)
└── modules/
    ├── __init__.py          # Modules package
    ├── constants.py         # Constants, regex patterns, configuration [✓ Complete]
    ├── debug_logger.py      # Debug logging utilities [✓ Complete]
    ├── text_preprocessing.py # Text cleanup and normalization [Planned]
    ├── question_parser.py    # Field extraction and parsing [Planned]
    ├── grid_parser.py        # Multi-column grid handling [Planned]
    ├── template_catalog.py   # Template matching [Planned]
    └── postprocessing.py     # Merging and consolidation [Planned]
```

## Usage

### Command Line (Backward Compatible)

The original CLI interface is preserved via the wrapper script in the parent directory:

```bash
python text_to_modento.py --in output --out JSONs --debug
```

### Programmatic Usage

```python
from text_to_modento import main

# Run the processing pipeline
main()

# Or import from core for advanced usage
from text_to_modento.core import process_one, TemplateCatalog
```

## Modularization Status

### ✅ Completed
- **Package Structure**: Created `text_to_modento/` package with `modules/` subdirectory
- **Backward Compatibility**: Original CLI wrapper maintained at `text_to_modento.py`
- **Constants Module**: All regex patterns and configuration extracted to `modules/constants.py`
- **Debug Logger Module**: Debug logging utilities extracted to `modules/debug_logger.py`

### 📋 Planned
The following modules are planned for incremental extraction from `core.py`:

1. **text_preprocessing.py**: Line cleanup, header/footer scrubbing, soft-wrap coalescing
2. **question_parser.py**: Main parsing logic, field extraction, checkbox detection
3. **grid_parser.py**: Multi-column grid detection and parsing
4. **template_catalog.py**: Template matching against dental form dictionary
5. **postprocessing.py**: Field merging, consolidation, section inference

## Design Principles

1. **Backward Compatibility**: The original `text_to_modento.py` CLI interface must work exactly as before
2. **Incremental Refactoring**: Modules are extracted incrementally while maintaining full functionality
3. **Minimal Changes**: Code is organized, not rewritten
4. **Clear Separation**: Each module has clear responsibilities and minimal coupling

## Testing

The existing test suite in `tests/` continues to work without modification:

```bash
python -m pytest tests/ -v
```

Or run individual test files:

```python
python tests/test_text_preprocessing.py
python tests/test_question_parser.py
python tests/test_template_matching.py
```

## Future Enhancements

Once modularization is complete:
- Unit tests can be added for individual modules
- Functions can be more easily tested in isolation
- Code navigation and maintenance will be significantly easier
- Module-level documentation can provide clear interfaces
