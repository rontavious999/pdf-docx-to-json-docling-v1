"""
text_to_modento package — v2.20

TXT (Unstructured) -> Modento-compliant JSON

Modularized structure for better maintainability.

Package Structure:
------------------
text_to_modento/
├── __init__.py              - Package initialization
├── main.py                  - Entry point (delegates to core)
├── core.py                  - Main parsing logic (original monolithic script)
└── modules/
    ├── __init__.py          - Modules package
    ├── constants.py         - Constants, regex patterns, configuration ✓
    ├── debug_logger.py      - Debug logging utilities ✓
    ├── text_preprocessing.py - Text cleanup and normalization (planned)
    ├── question_parser.py    - Field extraction and parsing (planned)
    ├── grid_parser.py        - Multi-column grid handling (planned)
    ├── template_catalog.py   - Template matching (planned)
    └── postprocessing.py     - Merging and consolidation (planned)

The modularization is being done incrementally while maintaining full
backward compatibility. The original CLI interface via text_to_modento.py
remains unchanged.
"""

__version__ = "2.21"

# Re-export main function and utility functions for programmatic access
from .core import (
    main, detect_multi_field_line, detect_inline_checkbox_with_text, 
    extract_compound_yn_prompts, slugify, PARENT_RE
)
from .modules.constants import (
    DATE_LABEL_RE, STATE_LABEL_RE, CHECKBOX_ANY
)
from .modules.text_preprocessing import (
    normalize_glyphs_line, normalize_section_name, coalesce_soft_wraps
)
from .modules.template_catalog import (
    _norm_text
)

__all__ = [
    'main', '__version__',
    'detect_multi_field_line', 'detect_inline_checkbox_with_text', 'extract_compound_yn_prompts',
    'slugify', '_norm_text', 'PARENT_RE',
    'DATE_LABEL_RE', 'STATE_LABEL_RE', 'CHECKBOX_ANY',
    'normalize_glyphs_line', 'normalize_section_name', 'coalesce_soft_wraps'
]
