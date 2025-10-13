#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
question_parser.py

Question parsing utility functions extracted from core.py.
Patch 7: Phase 1 Modularization - Independent Utilities

This module contains utility functions for text cleaning, normalization,
field classification, and option generation.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

# Import from sibling modules
from .text_preprocessing import collapse_spaced_caps

# ---------- Constants

CHECKBOX_ANY = r"(?:\[\s*\]|\[x\]|☐|☑|□|■|❒|◻|✓|✔|✗|✘)"

PHONE_RE = re.compile(r"\b(phone|cell|mobile|telephone)\b", re.I)
EMAIL_RE = re.compile(r"\bemail\b", re.I)
ZIP_RE = re.compile(r"\b(zip|postal)\b", re.I)
SSN_RE = re.compile(r"\b(ssn|social security|soc(?:ial)?\s*sec(?:urity)?|ss#)\b", re.I)
DATE_LABEL_RE = re.compile(r"\b(date|dob|birth)\b", re.I)
INITIALS_RE = re.compile(r"\binitials?\b", re.I)

SPELL_FIX = {
    "rregular": "Irregular",
    "hyploglycemia": "Hypoglycemia",
    "diabates": "Diabetes",
    "osteoperosis": "Osteoporosis",
    "artritis": "Arthritis",
    "rheurnatism": "Rheumatism",
    "e": "Email",
}

# ---------- Utility Functions


def clean_field_title(title: str) -> str:
    """
    Clean field title by removing checkbox markers and artifacts (Fix 5).
    Apply this to all field titles before creating Questions.
    """
    # Remove checkbox markers
    cleaned = re.sub(CHECKBOX_ANY, '', title)
    
    # Archivev18 Fix 1: Remove date template artifacts (e.g., ": / /" or "/ /")
    # These appear in forms as placeholder formatting (e.g., "Birth Date#: / /")
    cleaned = re.sub(r':\s*/\s*/\s*$', '', cleaned)  # Remove ": / /" at end
    cleaned = re.sub(r'/\s*/\s*$', '', cleaned)      # Remove "/ /" at end
    
    # Archivev20 Fix 7: OCR error correction
    # Common OCR misreads from Docling output
    ocr_corrections = {
        r'\bN\s+o\s+D\s+ental\b': 'No Dental',
        r'\bPrim\s+ary\b': 'Primary',
        r'\bsom\s+eone\b': 'someone',
        r'\bH\s+older\b': 'Holder',
        # Add more patterns as needed, but keep generic
    }
    for pattern, replacement in ocr_corrections.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.I)
    
    # Remove multiple spaces
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
    # Trim whitespace
    cleaned = cleaned.strip()
    
    # Remove trailing colons if followed by nothing
    cleaned = re.sub(r':\s*$', '', cleaned)
    
    # Archivev18 Fix 1b: Also remove trailing '#' followed by colon (e.g., "Birth Date#:" -> "Birth Date#")
    # But preserve the # if it's part of the field name
    cleaned = re.sub(r'#:\s*$', '#', cleaned)
    
    return cleaned


def clean_token(s: str) -> str:
    s = collapse_spaced_caps(s).strip(" -–—:\t")
    return SPELL_FIX.get(s, s)


def normalize_opt_name(s: str) -> str:
    s = clean_token(s).lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def classify_input_type(label: str) -> Optional[str]:
    l = label.lower()
    if EMAIL_RE.search(l):   return "email"
    if PHONE_RE.search(l):   return "phone"
    if SSN_RE.search(l):     return "ssn"
    if ZIP_RE.search(l):     return "zip"
    if INITIALS_RE.search(l):return "initials"
    return "text"


def classify_date_input(label: str) -> str:
    l = label.lower()
    return "past" if ("birth" in l or "dob" in l) else "any"


def slugify(s: str, maxlen: int = 64) -> str:
    s = collapse_spaced_caps(s.strip()).lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "q"
    if re.match(r"^\d", s):
        s = "q_" + s
    return (s[:maxlen] or "q")


def clean_option_text(text: str) -> str:
    """
    Clean malformed option text.
    
    Fixes:
    1. Repeated words: "Blood Blood Transfusion" -> "Blood Transfusion"
    2. Slash-separated malformed: "Epilepsy/ Excessive Seizers Bleeding" -> "Epilepsy"
    3. OCR typos: "rregular Heartbeat" -> "Irregular Heartbeat" (Archivev16 Fix)
    
    Args:
        text: Raw option text
    
    Returns:
        Cleaned option text
    """
    if not text:
        return text
    
    # Fix 1: Remove consecutive duplicate words
    words = text.split()
    cleaned_words = []
    prev_word_lower = None
    
    for word in words:
        word_normalized = word.lower().strip('.,;:')
        
        # Skip if this word is same as previous (case-insensitive)
        if word_normalized != prev_word_lower:
            cleaned_words.append(word)
        
        prev_word_lower = word_normalized
    
    text = ' '.join(cleaned_words)
    
    # Fix 2: Handle malformed slash-separated conditions
    # Pattern: "ConditionA/ random text that doesn't make sense"
    # But preserve valid compound phrases like "I live/work in area", "AIDS/HIV", "Family/Friend"
    if '/' in text:
        parts = [p.strip() for p in text.split('/')]
        
        # Check if we have a clean first part and a messy second part
        if len(parts) >= 2:
            first_part = parts[0]
            second_part = parts[1]
            
            # Common valid compound patterns to preserve
            # Pattern 1: "word1/word2" where both are short (likely acronym or compound like "AIDS/HIV")
            # Pattern 2: "I live/work" - starts with pronoun/common phrase
            valid_compound_starts = {'i', 'you', 'we', 'they', 'he', 'she'}
            valid_continuation_words = {'work', 'or', 'and', 'in', 'of', 'to'}
            
            is_valid_compound = False
            if len(parts) == 2:  # Only check for simple two-part compounds
                first_word = first_part.split()[0].lower() if first_part.split() else ''
                second_word = second_part.split()[0].lower() if second_part.split() else ''
                
                # Short compound (likely valid): "AIDS/HIV", "M/F"
                if len(first_part) <= 10 and len(second_part) <= 10 and len(second_part.split()) <= 2:
                    is_valid_compound = True
                # Phrase continuation: "I live/work"
                elif first_word in valid_compound_starts or second_word in valid_continuation_words:
                    is_valid_compound = True
            
            # Heuristics for "messy" second part (only if not a valid compound):
            # - More than 2 words (likely run-on text)
            # - Contains multiple spaces (formatting artifact)
            # - Contains unusual capitalization patterns
            if not is_valid_compound:
                is_messy_second = (
                    len(second_part.split()) > 2 or
                    '  ' in second_part
                )
                
                # If first part looks complete and second is messy, use just first
                if len(first_part) >= 3 and first_part[0].isupper() and is_messy_second:
                    text = first_part
    
    # Fix 3: Clean extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Fix 4: Correct common OCR typos (Archivev16, Archivev17)
    # Common patterns where OCR misreads "I" as "r" or "u" as "rn"
    OCR_CORRECTIONS = {
        r'\brregular\b': 'Irregular',
        r'\brrregular\b': 'Irregular',
        r'\brheurnatism\b': 'Rheumatism',
    }
    
    for pattern, replacement in OCR_CORRECTIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text.strip()


def make_option(name: str, bool_value: Optional[bool]) -> Dict:
    if bool_value is True:  return {"name": "Yes", "value": True}
    if bool_value is False: return {"name": "No",  "value": False}
    # Archivev8 Fix 4: Apply text cleaning
    name = clean_option_text(name)
    return {"name": name, "value": slugify(name, 80)}
