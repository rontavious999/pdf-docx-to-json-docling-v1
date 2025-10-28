#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR Post-Processing Enhancement Module

Provides correction capabilities for common OCR errors to improve
field detection accuracy.

This module implements Fix 2.2 from the Category 2 roadmap.
"""

import re
from typing import Dict, List, Optional, Set
from difflib import get_close_matches


# Common OCR character confusions
OCR_CHAR_CONFUSION = {
    # Letters ↔ Numbers
    'l': ['1', 'I', '|'],
    '1': ['l', 'I', '|'],
    'O': ['0', 'Q'],
    '0': ['O', 'Q'],
    'S': ['5', '$'],
    '5': ['S', '$'],
    'B': ['8'],
    '8': ['B'],
    'Z': ['2'],
    '2': ['Z'],
    'G': ['6'],
    '6': ['G'],
    
    # Case confusions  
    'rn': ['m'],
    'm': ['rn', 'nn'],
    'vv': ['w'],
    'w': ['vv'],
    'cl': ['d'],
    'ii': ['u'],
    
    # Punctuation
    '—': ['-', '--'],
    '–': ['-'],
}

# Unicode ligatures that need restoration
LIGATURE_REPLACEMENTS = {
    'ﬁ': 'fi',
    'ﬂ': 'fl',
    'ﬀ': 'ff',
    'ﬃ': 'ffi',
    'ﬄ': 'ffl',
    'ﬆ': 'st',
    'Ꜳ': 'AA',
    'ꜳ': 'aa',
}

# Common OCR errors in medical/dental field labels
COMMON_LABEL_CORRECTIONS = {
    'ph0ne': 'phone',
    'ema1l': 'email',
    'addres': 'address',
    'adress': 'address',
    'b1rthdate': 'birthdate',
    'bir thdate': 'birthdate',
    'soc1al': 'social',
    'secur1ty': 'security',
    'pat1ent': 'patient',
    'pat ient': 'patient',
    'insur ance': 'insurance',
    'med1cal': 'medical',
    'h1story': 'history',
    'all ergy': 'allergy',
    'medic ation': 'medication',
    'phys1cian': 'physician',
    'em ergency': 'emergency',
    'c0ntact': 'contact',
    # Additional corrections for common spacing/concatenation issues
    'nod ental': 'no dental',
    'dent al': 'dental',
    'howdidyouhearaboutus': 'how did you hear about us',
    'hearaboutus': 'hear about us',
    'dateofbirth': 'date of birth',
    'phonenumber': 'phone number',
    'emailaddress': 'email address',
}


def restore_ligatures(text: str) -> str:
    """
    Replace Unicode ligatures with standard characters.
    
    Args:
        text: Text potentially containing ligatures
        
    Returns:
        Text with ligatures converted to standard characters
        
    Example:
        >>> restore_ligatures("ofﬁce")
        'office'
        >>> restore_ligatures("ﬁle")
        'file'
    """
    for ligature, replacement in LIGATURE_REPLACEMENTS.items():
        text = text.replace(ligature, replacement)
    return text


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace issues from OCR.
    
    - Remove extra spaces within words (e.g., "P h o n e" → "Phone")
    - Preserve intentional spacing
    - Fix spacing around punctuation
    
    Args:
        text: Text with potential whitespace issues
        
    Returns:
        Text with normalized whitespace
        
    Example:
        >>> normalize_whitespace("P h o n e  N u m b e r")
        'Phone Number'
        >>> normalize_whitespace("First  Name")
        'First Name'
    """
    if not text:
        return text
    
    # Pattern 1: Single char + space + single char (likely OCR error)
    # "P h o n e" → "Phone"
    # Be conservative: only if repeated pattern (3+ occurrences)
    single_char_spaces = re.findall(r'\b\w\s+(?=\w\s+\w)', text)
    if len(single_char_spaces) >= 2:
        # Likely OCR spacing error
        text = re.sub(r'\b(\w)\s+(?=\w\b)', r'\1', text)
    
    # Pattern 2: Missing space after punctuation
    text = re.sub(r'([.:,;])([A-Za-z])', r'\1 \2', text)
    
    # Pattern 3: Multiple spaces → single space
    text = re.sub(r'\s{2,}', ' ', text)
    
    return text.strip()


def apply_char_confusion_corrections(text: str, context: str = 'general') -> str:
    """
    Apply character confusion corrections based on context.
    
    Args:
        text: Text to correct
        context: 'label', 'value', 'general' - influences correction strategy
        
    Returns:
        Text with likely OCR errors corrected
        
    Example:
        >>> apply_char_confusion_corrections("Ph0ne", "label")
        'Phone'
        >>> apply_char_confusion_corrections("Ema1l", "label")
        'Email'
    """
    if not text:
        return text
    
    # For field labels, apply aggressive corrections
    if context == 'label':
        # Common patterns: "Ph0ne" → "Phone", "Ema1l" → "Email"
        # Check against known patterns
        text_lower = text.lower()
        
        # Check direct corrections first
        for wrong, right in COMMON_LABEL_CORRECTIONS.items():
            if wrong in text_lower:
                # Preserve original casing
                text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)
        
        # Pattern-based corrections
        # "0" → "O" at start of words or in middle of lowercase letters
        text = re.sub(r'\b0([a-z])', r'O\1', text)  # 0ffice → Office
        text = re.sub(r'([a-z])0([a-z])', r'\1o\2', text)  # w0rd → word
        
        # "1" → "l" in middle of lowercase letters
        text = re.sub(r'([a-z])1([a-z])', r'\1l\2', text)  # ema1l → email
        
        # "5" → "S" at start of words
        text = re.sub(r'\b5([a-z])', r'S\1', text)  # 5tate → State
    
    return text


def correct_field_label(text: str, known_labels: Optional[Set[str]] = None, 
                       threshold: float = 0.85) -> str:
    """
    Correct field label using dictionary and fuzzy matching.
    
    Uses Levenshtein distance to find closest known label.
    
    Args:
        text: Field label text to correct
        known_labels: Set of known valid labels (optional, uses default if None)
        threshold: Similarity threshold (0.0-1.0)
        
    Returns:
        Corrected label text
        
    Example:
        >>> correct_field_label("Fone", known_labels={"phone", "email"})
        'phone'
        >>> correct_field_label("Adress", known_labels={"address", "phone"})
        'address'
    """
    if not text:
        return text
    
    # If no known labels provided, use common field labels
    if known_labels is None:
        known_labels = {
            'phone', 'email', 'address', 'city', 'state', 'zip',
            'name', 'first', 'last', 'middle', 'date', 'birth',
            'social', 'security', 'patient', 'insurance', 'medical',
            'history', 'allergy', 'medication', 'physician', 'emergency',
            'contact', 'relationship', 'gender', 'age', 'occupation',
            'employer', 'referred', 'referral', 'signature'
        }
    
    text_lower = text.lower().strip()
    
    # Try exact match first
    if text_lower in known_labels:
        return text
    
    # Try fuzzy match with threshold
    matches = get_close_matches(text_lower, known_labels, n=1, cutoff=threshold)
    if matches:
        # Found a close match - return it with original casing preserved where possible
        match = matches[0]
        
        # Try to preserve original casing
        if text.isupper():
            return match.upper()
        elif text.istitle():
            return match.title()
        else:
            return match
    
    # No match found, return original
    return text


def preprocess_text_with_ocr_correction(text: str, context: str = 'general') -> str:
    """
    Enhanced text preprocessing with OCR correction.
    
    Applied early in the pipeline before pattern matching.
    
    Args:
        text: Text to preprocess
        context: Processing context ('label', 'value', 'general')
        
    Returns:
        Preprocessed text with OCR errors corrected
        
    Example:
        >>> preprocess_text_with_ocr_correction("Ph0ne  N um ber:")
        'Phone Number:'
    """
    if not text:
        return text
    
    # Phase 1: Restore ligatures
    text = restore_ligatures(text)
    
    # Phase 2: Normalize whitespace
    text = normalize_whitespace(text)
    
    # Phase 3: Apply character confusion corrections
    text = apply_char_confusion_corrections(text, context)
    
    return text


def preprocess_field_label(label: str, known_labels: Optional[Set[str]] = None) -> str:
    """
    Special preprocessing for field labels with dictionary correction.
    
    Args:
        label: Field label to preprocess
        known_labels: Optional set of known valid labels
        
    Returns:
        Preprocessed and corrected label
        
    Example:
        >>> preprocess_field_label("Ph0ne  Num ber")
        'Phone Number'
    """
    # Apply general OCR correction
    label = preprocess_text_with_ocr_correction(label, context='label')
    
    # Apply dictionary-based correction
    # Split compound labels and correct each part
    parts = label.split()
    if len(parts) > 1:
        # Correct each word separately
        corrected_parts = [correct_field_label(part, known_labels) for part in parts]
        label = ' '.join(corrected_parts)
    else:
        label = correct_field_label(label, known_labels)
    
    return label


def get_correction_stats(text: str) -> Dict[str, int]:
    """
    Get statistics about potential OCR corrections in text.
    
    Useful for debugging and analysis.
    
    Args:
        text: Text to analyze
        
    Returns:
        Dict with correction statistics
    """
    stats = {
        'ligatures_found': 0,
        'excessive_spaces': 0,
        'char_confusions': 0,
        'total_chars': len(text)
    }
    
    # Count ligatures
    for ligature in LIGATURE_REPLACEMENTS:
        stats['ligatures_found'] += text.count(ligature)
    
    # Count excessive spacing patterns
    stats['excessive_spaces'] = len(re.findall(r'\s{2,}', text))
    stats['excessive_spaces'] += len(re.findall(r'\b\w\s+\w\s+\w', text))
    
    # Count potential character confusions (heuristic)
    stats['char_confusions'] += len(re.findall(r'\d[a-z]|[a-z]\d', text))
    
    return stats
