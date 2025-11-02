"""
Modularized components of the text_to_modento pipeline.
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

# Export ML field detector (Category 2 Fix 2.1)
from .ml_field_detector import (
    MLFieldDetector,
    FieldPrediction,
    initialize_ml_detector
)

# Export performance enhancements (Performance Recommendations 1-3)
from .performance_enhancements import (
    detect_inline_checkbox_options,
    infer_radio_vs_checkbox,
    enhance_field_type_detection,
    is_procedural_consent_text,
    consolidate_procedural_consent_blocks,
    track_unmatched_field_for_expansion,
    suggest_dictionary_additions
)

__all__ = [
    'preprocess_text_with_ocr_correction',
    'preprocess_field_label',
    'restore_ligatures',
    'normalize_whitespace',
    'apply_char_confusion_corrections',
    'correct_field_label',
    'MLFieldDetector',
    'FieldPrediction',
    'initialize_ml_detector',
    'detect_inline_checkbox_options',
    'infer_radio_vs_checkbox',
    'enhance_field_type_detection',
    'is_procedural_consent_text',
    'consolidate_procedural_consent_blocks',
    'track_unmatched_field_for_expansion',
    'suggest_dictionary_additions'
]
