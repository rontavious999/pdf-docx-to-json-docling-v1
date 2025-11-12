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
DATE_LABEL_RE = re.compile(r"\b(date|dob|birth|signed|today'?s?\s+date|"
                     r"signature\s+date|consent\s+date|treatment\s+date|"
                     r"visit\s+date|appointment\s+date|procedure\s+date)\b", re.I)
INITIALS_RE = re.compile(r"\binitials?\b", re.I)
NAME_RE = re.compile(r"\b(first\s*name|last\s*name|full\s*name|patient\s*name|insured'?s?\s*name|"
                     r"parent\s*name|responsible\s*party\s*name|emergency\s*contact\s*name|"
                     r"guardian\s*name|subscriber\s*name|member\s*name|policy\s*holder\s*name|"
                     r"patient'?s?\s*name|parent'?s?\s*name|guardian'?s?\s*name|"
                     r"name\s+\(print\)|name\s+\(please\s+print\)|printed\s+name|"
                     r"legal\s+name|authorized\s+representative|representative\s+name|"
                     r"^name$|^name\s*of\s*(patient|insured|parent|guardian|subscriber|representative))\b", re.I)
NUMBER_RE = re.compile(r"\b(age|years?|months?|days?|count|quantity|number|amount|total|"
                       r"how\s+many|num\s+of|no\.\s+of|#\s+of)\b", re.I)

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


def is_consent_or_terms_text(text: str) -> bool:
    """
    Improvement 2: Detect if text is likely a consent/terms statement.
    
    Returns True if the text appears to be legal/consent language rather than
    a form field to be filled out.
    """
    text_lower = text.lower()
    
    # Consent/terms indicators
    consent_phrases = [
        r'\bi\s+(?:hereby\s+)?(?:certify|acknowledge|consent|agree|understand|authorize)',
        r'\bpatient\s+(?:acknowledges?|consents?|agrees?)',
        r'\bby\s+signing',
        r'\bi\s+have\s+(?:read|been\s+informed)',
        r'\bto\s+the\s+best\s+of\s+my\s+knowledge',
        r'\bi\s+give\s+(?:my\s+)?consent',
        r'\bpossible\s+(?:risks?|complications?)',
        r'\bnecessitating\s+(?:additional|several)',
        r'\bmay\s+(?:include|result\s+in)',
    ]
    
    # Check for multiple consent indicators (stronger signal)
    match_count = sum(1 for pattern in consent_phrases if re.search(pattern, text_lower))
    if match_count >= 2:
        return True
    
    # Single strong indicator - check strongest patterns first
    # First 3 patterns are very strong indicators even in short text
    for pattern in consent_phrases[:3]:
        if re.search(pattern, text_lower):
            # If text is long OR starts with these strong patterns, it's consent
            if len(text) > 30 or re.match(pattern, text_lower):
                return True
    
    # Other patterns need longer text to be confident
    if len(text) > 80:
        for pattern in consent_phrases[3:]:
            if re.search(pattern, text_lower):
                return True
    
    return False


def should_be_terms_field(title: str, text_length: int = 0) -> bool:
    """
    Improvement 2: Determine if a field should be classified as 'terms' type.
    
    Args:
        title: The field title/label
        text_length: Length of the associated text content
    
    Returns:
        True if this should be a terms field
    """
    if is_consent_or_terms_text(title):
        return True
    
    # Very long text is likely terms/consent
    if text_length > 200:
        return True
    
    # Explicit terms indicators in title
    terms_keywords = ['terms', 'consent', 'agreement', 'acknowledgment', 'disclosure']
    title_lower = title.lower()
    if any(keyword in title_lower for keyword in terms_keywords):
        return True
    
    return False


def is_signature_field(text: str) -> bool:
    """
    Improvement 5: Enhanced signature field detection.
    
    Detects various signature field patterns including:
    - "Signature of Patient/Guardian/Parent"
    - "Patient Signature"
    - "Signature: ___________"
    - "Signed by"
    
    Returns:
        True if this appears to be a signature field
    """
    text_lower = text.lower()
    
    # Primary signature patterns
    signature_patterns = [
        r'\bsignature\b',
        r'\bsigned\s+by\b',
        r'\bsign\s+here\b',
        r'\bpatient.{0,20}signature\b',
        r'\bguardian.{0,20}signature\b',
        r'\bparent.{0,20}signature\b',
    ]
    
    for pattern in signature_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False


def infer_field_type_from_context(title: str, has_options: bool = False, 
                                   option_count: int = 0) -> Optional[str]:
    """
    Improvement 9: Infer field type from context when not explicitly specified.
    
    Args:
        title: The field title/label
        has_options: Whether the field has checkbox/radio options
        option_count: Number of options if any
    
    Returns:
        Inferred field type ('radio', 'dropdown', 'date', 'input', 'terms') or None
    """
    title_lower = title.lower()
    
    # Signature fields
    if is_signature_field(title):
        return 'signature'
    
    # Terms/consent fields
    if should_be_terms_field(title):
        return 'terms'
    
    # Date fields (unless they have options)
    if not has_options and DATE_LABEL_RE.search(title):
        return 'date'
    
    # Radio fields (small number of options)
    if has_options and option_count <= 6:
        return 'radio'
    
    # Dropdown fields (many options or specific keywords)
    if has_options and option_count > 6:
        return 'dropdown'
    
    # Yes/No questions are radio (check before multi-selection keywords)
    # Also check for common question patterns that imply Yes/No
    yes_no_patterns = [
        r'\b(yes\s*(?:or|/)\s*no|y\s*(?:or|/)\s*n)\b',
        r'\b(are\s+you|do\s+you|have\s+you|did\s+you|is\s+the|will\s+you)',  # Question patterns
    ]
    for pattern in yes_no_patterns:
        if re.search(pattern, title_lower):
            # If it's a question without explicit options, likely radio
            if not has_options or option_count <= 2:
                return 'radio'
    
    # Multi-selection indicators suggest dropdown
    dropdown_keywords = ['select all', 'check all', 'choose all', 'multiple', 'which of the following']
    if any(keyword in title_lower for keyword in dropdown_keywords):
        return 'dropdown'
    
    # Default to input if nothing else matches
    return 'input'


def clean_field_title(title: str) -> str:
    """
    Clean field title by removing checkbox markers and artifacts (Fix 5).
    Apply this to all field titles before creating Questions.
    """
    # Remove checkbox markers
    cleaned = re.sub(CHECKBOX_ANY, '', title)
    
    # Phase 4 Fix 9: Remove leading "!" from medical condition fields
    # Forms often use "!" as a checkbox indicator, similar to □
    cleaned = re.sub(r'^!\s*', '', cleaned)
    
    # Archivev18 Fix 1: Remove date template artifacts (e.g., ": / /" or "/ /")
    # These appear in forms as placeholder formatting (e.g., "Birth Date#: / /")
    cleaned = re.sub(r':\s*/\s*/\s*$', '', cleaned)  # Remove ": / /" at end
    cleaned = re.sub(r'/\s*/\s*$', '', cleaned)      # Remove "/ /" at end
    
    # Archivev21 Fix 1: Remove blank line placeholders (underscores)
    # These appear as fill-in-the-blank indicators in forms
    # Examples: "Today's Date ______________" -> "Today's Date"
    #           "Reason for visit? ____________" -> "Reason for visit?"
    # Remove sequences of 3 or more underscores (preserve single/double underscores in actual field names)
    cleaned = re.sub(r'_{3,}', '', cleaned)
    
    # Archivev20 Fix 7: OCR error correction
    # Archivev21 Fix 4: Enhanced OCR patterns to match collapsed text
    # Common OCR misreads from Docling output (after collapse_spaced_caps)
    ocr_corrections = {
        r'\bN[,\s]*o\s+D\s*ental\b': 'No Dental',  # "N o D ental" or "N, o D ental"
        r'\bPrim\s*ary\b': 'Primary',
        r'\bsom\s*eone\b': 'someone',
        r'\bH\s*older\b': 'Holder',
        r'\bP\s*olicy\b': 'Policy',
        # Add more patterns as needed, but keep generic
    }
    for pattern, replacement in ocr_corrections.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.I)
    
    # Remove multiple spaces
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
    # Trim whitespace
    cleaned = cleaned.strip()
    
    # Phase 4 Fix 6: Remove SSN field formatting artifacts (AFTER space normalization)
    # Forms often show "Social Security No. _______ - ____ - _________"
    # which gets captured with the dashes. Remove trailing dashes and spaces.
    # Must be AFTER space normalization since we're looking for single-space patterns
    cleaned = re.sub(r'\.\s*-\s*-\s*$', '', cleaned)  # Remove ". - -" at end
    cleaned = re.sub(r'\s*-\s*-\s*$', '', cleaned)    # Remove " - -" at end
    cleaned = re.sub(r'\s*-\s*$', '', cleaned)        # Remove trailing " -"
    
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
    """
    Classify input type based on field label according to Modento schema.
    
    Returns the appropriate input_type for the field, including:
    - "name" for name fields (first name, last name, patient name, etc.)
    - "email" for email fields
    - "phone" for phone/mobile/cell fields
    - "number" for numeric fields (age, count, quantity, years, etc.)
    - "ssn" for social security number fields
    - "zip" for zip/postal code fields
    - "initials" for initial fields
    - "text" as default fallback
    
    Note: Order matters! More specific patterns (like SSN) should be checked before
    generic patterns (like number) to avoid false matches.
    """
    l = label.lower()
    
    # Check for name fields first (new - per audit requirement)
    if NAME_RE.search(l):    return "name"
    
    # Check for SSN before number (SSN contains "number" so must be checked first)
    if SSN_RE.search(l):     return "ssn"
    
    # Check for other specific field types
    if EMAIL_RE.search(l):   return "email"
    if PHONE_RE.search(l):   return "phone"
    if NUMBER_RE.search(l):  return "number"
    if ZIP_RE.search(l):     return "zip"
    if INITIALS_RE.search(l):return "initials"
    
    # Default fallback
    return "text"


def classify_date_input(label: str) -> str:
    """
    Classify date input type according to Modento schema.
    
    Returns:
        "past" for historical dates (birth dates, signed dates)
        "future" for upcoming dates (appointments, scheduled procedures)
    
    Note: Modento schema does not support "any" as an input_type for dates.
    """
    l = label.lower()
    
    # Birth dates and DOB are always in the past
    if "birth" in l or "dob" in l:
        return "past"
    
    # Signed/signature dates are historical (document was signed in the past)
    if "sign" in l or "signature" in l or "consent" in l:
        return "past"
    
    # Appointment or scheduled dates are in the future
    if "appoint" in l or "schedul" in l or "next visit" in l:
        return "future"
    
    # Default to "past" for most date fields (safer assumption)
    # Most dental form dates are historical: treatment dates, last visit, etc.
    return "past"


def slugify(s: str, maxlen: int = 64) -> str:
    """
    Convert a string to a valid key identifier with semantic truncation.
    
    Improvements:
    - Truncates at semantic boundaries (word boundaries) instead of mid-word
    - Prioritizes keeping the most meaningful parts of the text
    - Handles consent/terms text more gracefully
    """
    s = collapse_spaced_caps(s.strip()).lower()
    
    # Fix Unicode ligatures and special characters (Production readiness)
    unicode_fixes = {
        'ﬁ': 'fi',
        'ﬂ': 'fl',
        'ﬀ': 'ff',
        'ﬃ': 'ffi',
        'ﬄ': 'ffl',
        'ﬆ': 'st',
        '–': '-',  # en dash
        '—': '-',  # em dash
    }
    for old, new in unicode_fixes.items():
        s = s.replace(old, new)
    
    # Improvement 1: Detect consent/terms blocks - extract key phrase
    # For long consent text, try to extract a meaningful identifier
    if len(s) > 100:
        # Look for key identifying phrases at the start
        consent_patterns = [
            r'^(i\s+(?:hereby\s+)?(?:certify|acknowledge|consent|agree|understand|authorize))',
            r'^(patient\s+(?:acknowledges?|consents?|agrees?))',
            r'^(by\s+signing)',
            r'^(i\s+have\s+(?:read|been\s+informed))',
        ]
        for pattern in consent_patterns:
            match = re.match(pattern, s)
            if match:
                # Use the first 4-6 words as the key
                words = s.split()[:6]
                s = '_'.join(words)
                break
    
    # Remove all non-alphanumeric except spaces (no hyphens in keys)
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "q"
    if re.match(r"^\d", s):
        s = "q_" + s
    
    # Improvement 1: Smart truncation at word boundaries
    if len(s) > maxlen:
        # Truncate at last complete word within maxlen
        truncated = s[:maxlen]
        # Find the last underscore (word boundary)
        last_underscore = truncated.rfind('_')
        if last_underscore > maxlen // 2:  # Only if we're keeping at least half
            s = truncated[:last_underscore]
        else:
            s = truncated
    
    return (s or "q")


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
    # Archivev21 Fix 5: Extended OCR corrections for spaced text
    # Common patterns where OCR misreads "I" as "r" or "u" as "rn"
    OCR_CORRECTIONS = {
        r'\brregular\b': 'Irregular',
        r'\brrregular\b': 'Irregular',
        r'\brheurnatism\b': 'Rheumatism',
        # Archivev21: Handle spaced OCR errors
        r'\bN[,\s]*o\s+D\s*ental\b': 'No Dental',  # "N o D ental" or "N, o D ental"
        r'\bPrim\s+ary\b': 'Primary',
        r'\bH\s+older\b': 'Holder',
        r'\bP\s+olicy\b': 'Policy',
        r'\bsom\s+eone\b': 'someone',
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


def norm_title(s: str) -> str:
    """
    Normalize title for comparison and grouping.
    
    Patch 2: Moved from core.py for better organization.
    Used by postprocessing functions for field consolidation.
    
    Args:
        s: Title string to normalize
        
    Returns:
        Normalized lowercase title with punctuation removed
    """
    s = (s or "").lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def generate_contextual_date_key(title: str, prev_lines: list, section: str) -> str:
    """
    Improvement 6: Generate contextual key for date fields based on surrounding context.
    
    Eliminates generic date_2, date_3 suffixes by using context clues:
    - In Signature section → "signature_date" or "date_signed"
    - After "Treatment" → "treatment_date"
    - After "Appointment" → "appointment_date"
    - In Patient Info section → "date_of_birth" or "todays_date"
    - After "Last visit" → "last_visit_date"
    
    Args:
        title: The field title/label (e.g., "Date", "Date of Birth")
        prev_lines: List of previous lines for context extraction
        section: Current section (e.g., "Signature", "Patient Information")
    
    Returns:
        Contextual date key (e.g., "signature_date", "treatment_date")
    """
    if not prev_lines:
        prev_lines = []
    
    title_lower = title.lower()
    
    # Check explicit date types in title
    if 'birth' in title_lower or 'dob' in title_lower:
        return 'date_of_birth'
    if 'signature' in title_lower or 'signed' in title_lower:
        return 'signature_date'
    if 'today' in title_lower or 'current' in title_lower:
        return 'todays_date'
    if 'treatment' in title_lower:
        return 'treatment_date'
    if 'appointment' in title_lower:
        return 'appointment_date'
    if 'visit' in title_lower:
        return 'visit_date'
    if 'procedure' in title_lower:
        return 'procedure_date'
    if 'consent' in title_lower:
        return 'consent_date'
    
    # Check previous line context (look back 2-3 lines)
    if prev_lines:
        prev_text = ' '.join(prev_lines[-3:]).lower()
        
        # Context mapping: keyword → date key
        context_map = {
            'treatment': 'treatment_date',
            'appointment': 'appointment_date',
            'last visit': 'last_visit_date',
            'next visit': 'next_visit_date',
            'visit': 'visit_date',
            'procedure': 'procedure_date',
            'next appointment': 'next_appointment_date',
            'emergency': 'emergency_date',
            'referred': 'referral_date',
            'signature': 'signature_date',
            'signed': 'signature_date',
            'consent': 'consent_date',
        }
        
        for keyword, date_key in context_map.items():
            if keyword in prev_text:
                return date_key
    
    # Section-based defaults
    if section:
        section_lower = section.lower()
        section_defaults = {
            'signature': 'signature_date',
            'patient information': 'todays_date',
            'treatment': 'treatment_date',
            'consent': 'consent_date',
            'insurance': 'insurance_date',
            'emergency': 'emergency_date',
        }
        
        for section_keyword, date_key in section_defaults.items():
            if section_keyword in section_lower:
                return date_key
    
    # Default fallback
    return 'date'


def infer_multi_select_from_context(title: str, options: list, section: str = "") -> bool:
    """
    NEW Improvement 8: Determine if a field should be multi-select based on context.
    
    Helps distinguish when a field with options should allow multiple selections (dropdown)
    vs single selection (radio).
    
    Multi-select indicators:
    - Medical history: "Do you have any of the following" → Always multi
    - Allergy lists: "Are you allergic to" → Always multi
    - "Check all that apply", "Select all" → Always multi
    - 5+ options → Usually multi-select
    
    Single-select indicators:
    - Yes/No questions → Always single
    - Gender → Always single
    - Marital status → Always single
    - 2-3 options → Usually single unless context indicates otherwise
    
    Args:
        title: Field title/label
        options: List of option names
        section: Current section name
        
    Returns:
        True if field should be multi-select, False for single-select
    """
    if not title:
        # Default based on option count
        return len(options) >= 5
    
    title_lower = title.lower()
    
    # Definite multi-select patterns
    multi_patterns = [
        r'do you have.*any of the following',
        r'have you had.*any of the following',
        r'have you ever had.*any of the following',
        r'are you allergic to.*following',
        r'allergic to.*any of the following',
        r'check all that apply',
        r'select all',
        r'select\s+any',
    ]
    
    if any(re.search(p, title_lower) for p in multi_patterns):
        return True
    
    # Definite single-select patterns
    single_patterns = [
        r'\bgendern\b',
        r'\bsex\b',
        r'marital status',
        r'\byes\s*/\s*no\b',
        r'\byes\s+or\s+no\b',
    ]
    
    if any(re.search(p, title_lower) for p in single_patterns):
        return False
    
    # Default: multi if 5+ options, single otherwise
    # This is a reasonable heuristic: fields with many options typically allow multiple selections
    return len(options) >= 5


def recognize_semantic_field_label(label: str, context_hints: Dict = None) -> str:
    """
    Improvement #4: Recognize semantic meaning from compound field labels.
    
    Transforms poorly parsed labels into semantically correct ones:
    - "Patient Name - Birth" → "Date of Birth"
    - "Patient Name - First" → "First Name"
    - "Patient Name - Street" → "Street Address"
    - "Phone - Mobile" → "Mobile Phone"
    
    Args:
        label: The field label to analyze
        context_hints: Optional dict with context like section, previous labels
        
    Returns:
        Semantically corrected label
    """
    if not label:
        return label
    
    # Common problematic patterns and their corrections
    semantic_mappings = {
        # Pattern: "name" + temporal indicator → Date field
        (r'.*name.*birth', 'date of birth'),
        (r'.*name.*dob', 'date of birth'),
        (r'.*birth.*date', 'date of birth'),
        
        # Pattern: "name" + location indicator → Address fields
        (r'.*name.*street', 'street address'),
        (r'.*name.*address', 'street address'),
        (r'.*name.*city', 'city'),
        (r'.*name.*state', 'state'),
        (r'.*name.*zip', 'zip code'),
        (r'.*name.*suite', 'suite number'),
        (r'.*name.*apt', 'apartment number'),
        
        # Pattern: "name" + contact indicator → Contact fields
        (r'.*name.*phone', 'phone number'),
        (r'.*name.*mobile', 'mobile phone'),
        (r'.*name.*cell', 'cell phone'),
        (r'.*name.*home.*phone', 'home phone'),
        (r'.*name.*work.*phone', 'work phone'),
        (r'.*name.*email', 'email address'),
        (r'.*name.*mail', 'email address'),
        (r'.*name.*fax', 'fax number'),
        
        # Pattern: "name" + employment → Employment fields
        (r'.*name.*employ', 'employer name'),
        (r'.*name.*occupation', 'occupation'),
        (r'.*name.*work', 'employer'),
        
        # Pattern: "name" + person parts → Name parts
        (r'.*name.*first', 'first name'),
        (r'.*name.*last', 'last name'),
        (r'.*name.*middle', 'middle name'),
        (r'.*name.*mi\b', 'middle initial'),
        (r'.*name.*full', 'full name'),
        
        # Pattern: "name" + identification → ID fields
        (r'.*name.*ssn', 'social security number'),
        (r'.*name.*social', 'social security number'),
        (r'.*name.*id', 'id number'),
        (r'.*name.*member', 'member id'),
        (r'.*name.*policy', 'policy number'),
        
        # Pattern: "phone" + type → Specific phone types
        (r'^phone.*mobile', 'mobile phone'),
        (r'^phone.*cell', 'cell phone'),
        (r'^phone.*home', 'home phone'),
        (r'^phone.*work', 'work phone'),
        
        # Pattern: Date + type → Specific date types
        (r'^date.*birth', 'date of birth'),
        (r'^date.*today', "today's date"),
        (r'^date.*sign', 'signature date'),
    }
    
    label_lower = label.lower().strip()
    
    # Try to match semantic patterns
    for pattern, replacement in semantic_mappings:
        if re.match(pattern, label_lower):
            return replacement.title()
    
    # If no semantic match, return cleaned original
    return label


def detect_empty_vs_filled_field(value_area: str) -> Dict:
    """
    Improvement #14: Detect if a field is empty (needs filling) or pre-filled.
    
    Analyzes the value area text to determine:
    - Is it a blank field (underscores, parentheses)?
    - Does it have a pre-filled value?
    - Is it a checkbox/radio (options provided)?
    
    Args:
        value_area: The text after the field label
        
    Returns:
        Dict with keys: is_blank, has_prefill, prefill_value, input_hint
    """
    if not value_area:
        return {'is_blank': True, 'has_prefill': False}
    
    value_stripped = value_area.strip()
    
    # Pattern 1: Long runs of underscores = blank field
    if re.match(r'^_{3,}$', value_stripped):
        return {
            'is_blank': True,
            'has_prefill': False,
            'input_hint': None
        }
    
    # Pattern 2: Parentheses or brackets alone = blank field
    if re.match(r'^\(+\s*\)+$|^\[+\s*\]+$', value_stripped):
        return {
            'is_blank': True,
            'has_prefill': False,
            'input_hint': None
        }
    
    # Pattern 3: Mix of underscores and parentheses
    if re.match(r'^[\(_\)\[\]\s]+$', value_stripped):
        return {
            'is_blank': True,
            'has_prefill': False,
            'input_hint': None
        }
    
    # Pattern 4: Checkboxes/radio options = option field (not blank, not prefilled)
    if re.search(r'\[\s*\]|☐|□', value_stripped):
        return {
            'is_blank': False,
            'has_prefill': False,
            'input_hint': 'Select one or more options'
        }
    
    # Pattern 5: Has actual text content = pre-filled
    # Exclude very short text that's likely formatting
    if len(value_stripped) > 3 and not re.match(r'^[\s_\(\)\[\]]+$', value_stripped):
        # Check if it's a reasonable value (not just form noise)
        words = value_stripped.split()
        if len(words) >= 1 and any(len(w) > 2 for w in words):
            return {
                'is_blank': False,
                'has_prefill': True,
                'prefill_value': value_stripped,
                'input_hint': None
            }
    
    # Default: treat as blank
    return {
        'is_blank': True,
        'has_prefill': False,
        'input_hint': None
    }


def infer_field_context_from_section(field_label: str, section: str) -> Dict:
    """
    Improvement #12: Use section context for better field disambiguation.
    
    When multiple fields have similar labels (e.g., "Name", "Date"),
    use the section to provide context for better naming.
    
    Args:
        field_label: The field label
        section: Current section name (e.g., "Patient Information", "Insurance")
        
    Returns:
        Dict with suggested title_prefix and hints
    """
    if not section or not field_label:
        return {}
    
    label_lower = field_label.lower()
    section_lower = section.lower()
    
    # Context-based prefixing rules
    context_rules = {
        'insurance': {
            'name': 'Insurance Holder',
            'date': 'Insurance Date',
            'phone': 'Insurance Phone',
            'employer': 'Insurance Company',
            'id': 'Policy ID',
            'number': 'Policy Number',
        },
        'emergency contact': {
            'name': 'Emergency Contact Name',
            'phone': 'Emergency Phone',
            'relationship': 'Emergency Contact Relationship',
        },
        'responsible party': {
            'name': 'Responsible Party Name',
            'relationship': 'Relationship to Patient',
            'phone': 'Responsible Party Phone',
        },
        'dental history': {
            'date': 'Last Visit Date',
            'dentist': 'Previous Dentist',
        },
        'medical history': {
            'date': 'Diagnosis Date',
            'condition': 'Medical Condition',
        },
    }
    
    # Find matching section
    for section_key, mappings in context_rules.items():
        if section_key in section_lower:
            # Check if label matches any mapping
            for label_key, prefixed_name in mappings.items():
                if label_key in label_lower:
                    return {
                        'contextual_title': prefixed_name,
                        'section_context': section
                    }
    
    # No specific context found
    return {}
