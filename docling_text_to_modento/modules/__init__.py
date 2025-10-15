"""
Modularized components of the docling_text_to_modento pipeline.
"""

# Export OCR correction functions (Category 2 Fix 2.2)
from .ocr_correction import (
    preprocess_text_with_ocr_correction,
    preprocess_field_label,
    restore_ligatures,
    normalize_whitespace,
    apply_char_confusion_corrections,
    correct_field_label
)

__all__ = [
    'preprocess_text_with_ocr_correction',
    'preprocess_field_label',
    'restore_ligatures',
    'normalize_whitespace',
    'apply_char_confusion_corrections',
    'correct_field_label'
]
