"""
Text preprocessing functions for line cleanup, normalization, and soft-wrap coalescing.

This module contains functions for:
- Normalizing Unicode glyphs to ASCII representations
- Collapsing spaced-out letters and capitals
- Reading text files with encoding detection
- Detecting section headings and category headers
- Scrubbing headers/footers and practice information
- Coalescing soft-wrapped lines
"""

import re
from pathlib import Path
from typing import List, Set
from collections import Counter

# Import constants from the constants module
from .constants import (
    CHECKBOX_ANY, BULLET_RE, PAGE_NUM_RE, ADDRESS_LIKE_RE,
    DENTAL_PRACTICE_EMAIL_RE, BUSINESS_WITH_ADDRESS_RE,
    PRACTICE_NAME_PATTERN, KNOWN_FIELD_LABELS
)

# Import OCR correction functions (Category 2 Fix 2.2)
from .ocr_correction import (
    preprocess_text_with_ocr_correction,
    preprocess_field_label,
    restore_ligatures
)


def normalize_glyphs_line(s: str) -> str:
    """
    Normalize Unicode checkbox and bullet glyphs to ASCII representations.
    
    Converts various Unicode symbols for checkboxes, bullets, and checkmarks
    into standardized ASCII patterns like "[ ]", "[x]", and "•".
    
    Enhanced with OCR correction (Category 2 Fix 2.2).
    """
    # Apply OCR corrections first (ligatures, whitespace, char confusions)
    s = preprocess_text_with_ocr_correction(s, context='general')
    
    repls = {
        "☐": "[ ] ", "☑": "[x] ", "□": "[ ] ", "■": "[ ] ", "❒": "[ ] ", "◻": "[ ] ", "◽": "[ ] ",
        "▪": "[ ] ", "•": "• ", "·": "• ", "✓": "[x] ", "✔": "[x] ", "✗": "[ ] ", "✘": "[ ] ",
        "¨": "[ ] ",
    }
    for k, v in repls.items():
        s = s.replace(k, v)
    # Convert standalone "!" to checkbox pattern
    s = re.sub(r"(^|\s)!\s+(?=\w)", r"\1[ ] ", s)
    return s


def collapse_spaced_letters_any(s: str) -> str:
    """
    Collapse spaced-out letters while preserving word boundaries.
    
    Archivev20 Fix 6: Improved spaced letter collapsing
    Pattern: "H o w  d i d  y o u" → "How did you"
    Observation: 1 space between letters within words, 2+ spaces between words
    """
    def collapse_match(match):
        text = match.group(0)
        # Find all letters with their positions
        letters_with_pos = [(m.start(), m.group()) for m in re.finditer(r'[A-Za-z]', text)]
        
        if not letters_with_pos:
            return text
        
        # Build result
        result = [letters_with_pos[0][1]]  # Start with first letter
        
        for i in range(1, len(letters_with_pos)):
            prev_pos = letters_with_pos[i-1][0]
            curr_pos, curr_letter = letters_with_pos[i]
            spaces = curr_pos - prev_pos - 1
            
            # If 2+ spaces, add a word boundary
            if spaces >= 2:
                result.append(' ')
            
            result.append(curr_letter)
        
        return ''.join(result)
    
    s = re.sub(r"(?<!\w)(?:[A-Za-z]\s+){3,}[A-Za-z](?!\w)", collapse_match, s)
    return re.sub(r"\s{2,}", " ", s).strip()


def collapse_spaced_caps(s: str) -> str:
    """Collapse spaced capital letters."""
    s2 = re.sub(r"(?:(?<=\b)|^)(?:[A-Z]\s+){2,}(?=[A-Z]\b)", lambda m: m.group(0).replace(" ", ""), s)
    s2 = collapse_spaced_letters_any(s2)
    return s2.strip()


def read_text_file(p: Path) -> str:
    """
    Read a text file with automatic encoding detection.
    
    Tries UTF-8 first, falls back to latin-1 if that fails.
    Uses 'replace' error handling to avoid encoding errors.
    """
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return p.read_text(encoding="latin-1", errors="replace")


def is_heading(line: str) -> bool:
    """
    Determine if a line is a section heading.
    
    Section headings are typically:
    - All uppercase or title case
    - <= 120 characters
    - End with a colon or no punctuation
    - Do NOT contain checkboxes
    - Do NOT match known field label patterns
    - Do NOT contain question marks
    """
    t = collapse_spaced_caps(line.strip())
    if not t:
        return False
    
    # Archivev10 Fix 1: Don't treat lines with checkboxes as headings
    if re.search(CHECKBOX_ANY, t):
        return False
    
    # Archivev12 Fix: Don't treat known field labels as headings
    # Archivev13 Fix: Use search instead of match, and allow # suffix
    # Check against common form field patterns
    for field_key, pattern in KNOWN_FIELD_LABELS.items():
        if re.search(pattern, t, re.I):
            return False
    
    # Archivev10 Fix 1: Don't treat multi-column grid headers as headings
    # (e.g., "Appearance    Function    Habits    Previous Comfort Options")
    # These have 3+ words/phrases separated by significant spacing
    parts = re.split(r'\s{3,}', t)
    if len(parts) >= 3 and all(len(p.split()) <= 4 for p in parts):
        # Looks like a multi-column grid header, not a section heading
        return False
    
    # Archivev19 Fix 1: Don't treat short single-word field labels as headings
    # e.g., "Comments:", "Notes:", "Explanation:" should be field labels, not headings
    # Section headings are typically multi-word or clearly descriptive
    if t.endswith(":"):
        # Remove the colon and check the remaining text
        label = t[:-1].strip()
        # Single word that's not all caps -> likely a field label
        if len(label.split()) == 1 and not label.isupper():
            common_field_labels = ['comments', 'notes', 'explanation', 'details', 'remarks']
            if label.lower() in common_field_labels:
                return False
    
    # Archivev19 Fix 4: Lines with question marks are questions/fields, never headings
    # e.g., "Have you ever had surgery? If so, what type:" should be a field
    if "?" in t:
        return False
    
    # Enhancement: Lines with underscores/dashes/parentheses are fillable fields, not headings
    # e.g., "Unit ___", "Apt ____", "Phone (   )"
    if re.search(r'_{3,}|[\-]{3,}|\(\s*\)', t):
        return False
    
    if len(t) <= 120 and (t.isupper() or (t.istitle() and not t.endswith("."))):
        if not t.endswith("?"):
            return True
    return t.endswith(":") and len(t) <= 120


def is_category_header(line: str, next_line: str = "") -> bool:
    """
    Archivev10 Fix 2 + Archivev11 Fix 4: Enhanced category header detection in medical/dental grids.
    Category headers are short lines without checkboxes that precede lines with checkboxes.
    
    Examples: "Cancer", "Cardiovascular", "Endocrinology", "Pain/Discomfort", "Appearance"
    
    Archivev11 Fix 4: Added detection for common label patterns like "Frequency", "Pattern", "Conditions"
    """
    cleaned = collapse_spaced_caps(line.strip())
    
    # Must be reasonably short (category headers or multi-column grid headers)
    if not cleaned or len(cleaned) > 80:
        return False
    
    # Must NOT have checkboxes
    if re.search(CHECKBOX_ANY, cleaned):
        return False
    
    # Must NOT be a question
    if cleaned.endswith("?"):
        return False
    
    # Must NOT end with a colon (that's a field label, not a category header)
    # Examples: "Last Name:", "Work Phone:", "Zip:"
    if cleaned.endswith(":"):
        return False
    
    # Must NOT end with a colon followed by content (that's also a field label)
    if re.search(r':\s*\S', cleaned):
        return False
    
    # Must NOT be a common form field pattern (even without colon)
    # Examples: "Ext#", "Apt#", "SSN", "DOB", "Zip", "State"
    form_field_patterns = [
        r'\b(ext|extension|apt|apartment|ssn|dob|zip|zipcode|state)\s*#?\b',
        r'\b(phone|email|fax|mobile|cell|home|work)\b',
        r'\b(first|last|middle|full)\s+name\b',
    ]
    for pattern in form_field_patterns:
        if re.search(pattern, cleaned, re.I):
            return False
    
    # Archivev11 Fix 4: Check for common label patterns
    # These are often found in forms and should be treated as headers/labels, not fields
    label_keywords = ['frequency', 'pattern', 'conditions', 'health', 'comments', 
                      'how much', 'how long', 'additional comments']
    cleaned_lower = cleaned.lower()
    is_label_pattern = any(kw in cleaned_lower for kw in label_keywords)
    
    # Known category header patterns in medical/dental forms
    category_keywords = [
        'cancer', 'cardiovascular', 'endocrinology', 'musculoskeletal', 
        'respiratory', 'gastrointestinal', 'neurological', 'hematologic',
        'appearance', 'function', 'habits', 'social', 'periodontal',
        'pain', 'discomfort', 'comfort', 'allergies', 'women', 'type',
        'viral infections', 'medical allergies', 'sleep pattern'
    ]
    
    is_known_category = any(kw in cleaned_lower for kw in category_keywords)
    
    # Archivev11 Fix 4: Label patterns with next line having checkboxes are headers
    if is_label_pattern and next_line and re.search(CHECKBOX_ANY, next_line):
        return True
    
    # Next line should have checkboxes (indicates this is a header for checkbox items)
    if next_line and re.search(CHECKBOX_ANY, next_line):
        # Check word count - category headers are usually 1-6 words (or multiple short phrases)
        # E.g., "Appearance Function Habits Previous Comfort Options" = 5 words but valid
        word_count = len(cleaned.split())
        if word_count <= 6 or is_known_category:
            return True
    
    # Also consider it a category header if it's a known category even without next line check
    # (some grids have category headers that span columns)
    if is_known_category and len(cleaned.split()) <= 3:
        return True
    
    return False


def normalize_section_name(raw: str) -> str:
    """
    Normalize a section heading to a standard section name.
    
    Maps various heading text to standard section names like:
    - Patient Information
    - Insurance
    - Medical History
    - etc.
    """
    t = collapse_spaced_caps(raw).strip().lower()
    if "signature" in t:
        return "Signature"
    table = {
        "Patient Information": ["patient information", "patient info", "patient details", "demographic", "registration"],
        "Insurance": ["insurance", "subscriber", "policy", "carrier", "dental benefit plan"],
        "Medical History": ["medical history", "health history", "medical"],
        "Medications": ["medication", "medications", "current medicines", "rx"],
        "Allergies": ["allergy", "allergies"],
        "Dental History": ["dental history", "dental information", "dental"],
        "HIPAA": ["hipaa"],
        "Financial Policy": ["financial", "payment policy", "billing"],
        "Emergency Contact": ["emergency contact"],
        "Appointment Policy": ["appointment policy", "cancellation", "missed appointment", "late policy"],
        "Consent": ["consent", "authorization", "informed consent", "release"],
    }
    best = ("General", 0)
    for norm, kws in table.items():
        score = sum(1 for k in kws if k in t)
        if score > best[1]:
            best = (norm, score)
    return best[0] if best[1] else "General"


def detect_repeated_lines(lines: List[str], min_count: int = 3, max_len: int = 80) -> Set[str]:
    """
    Detect lines that repeat multiple times (likely headers/footers).
    
    Returns a set of line texts that appear at least min_count times
    and are <= max_len characters.
    """
    counter = Counter([collapse_spaced_caps(l.strip()) for l in lines if l.strip() and len(l.strip()) <= max_len])
    return {s for s, c in counter.items() if c >= min_count}


def is_address_block(block: List[str]) -> bool:
    """
    Check if a block is primarily business/practice address information (not form content).
    
    Returns True only if the block looks like header/footer practice info,
    not if it contains actual form fields.
    """
    # Count different types of content
    address_hits = 0
    form_field_hits = 0
    business_hits = 0
    
    for ln in block:
        ln_lower = ln.lower()
        
        # Check for actual street addresses (with numbers + street type)
        if re.search(r'\b\d+\s+[NS]?\s*\w+\s+(ave|avenue|rd|road|st|street|blvd|boulevard)\b', ln, re.I):
            address_hits += 1
        
        # Check for business/practice names
        if re.search(r'\b(dental|dentistry)\s+(care|center|design|solutions|office)\b', ln, re.I):
            business_hits += 1
        
        # Check for form field labels (labels with colons that indicate form fields)
        if re.search(r'\b(last\s+name|first\s+name|patient\s+name|birth\s+date|dob|address|city|state|zip\s*code?|phone|email|gender|marital|emergency|ssn|insurance)\s*:', ln, re.I):
            form_field_hits += 1
    
    # Only consider it an address block if:
    # 1. It has business/address information AND
    # 2. It has NO form field labels (or very few relative to address content)
    has_business_content = (address_hits >= 2 or business_hits >= 1)
    has_form_content = form_field_hits >= 3
    
    # If it has significant form content, it's not just an address block
    if has_form_content:
        return False
    
    return len(block) >= 3 and has_business_content


def scrub_headers_footers(text: str) -> List[str]:
    """
    Remove headers, footers, and practice information from extracted text.
    
    This function:
    1. Splits text into blocks
    2. Filters out address/business blocks
    3. Removes repeated lines (headers/footers)
    4. Filters out page numbers, practice info, and junk text
    
    Returns a list of cleaned lines.
    """
    raw_lines = text.splitlines()
    blocks: List[List[str]] = []
    cur: List[str] = []
    for ln in raw_lines:
        if ln.strip():
            cur.append(ln)
        else:
            if cur:
                blocks.append(cur); cur=[]
    if cur:
        blocks.append(cur)

    kept_blocks: List[List[str]] = []
    for b in blocks:
        b_trim = [collapse_spaced_caps(x) for x in b]
        if is_address_block(b_trim):
            continue
        kept_blocks.append(b)

    lines = []
    for b in kept_blocks:
        lines.extend(b); lines.append("")

    # Enhanced junk text filtering patterns (Fix 3)
    MULTI_LOCATION_RE = re.compile(
        r'.*\b(Ave|Avenue|St|Street|Rd|Road|Blvd|Boulevard)\.?\b.*\b(Ave|Avenue|St|Street|Rd|Road|Blvd|Boulevard)\.?\b',
        re.I
    )
    CITY_STATE_ZIP_RE = re.compile(r',\s*[A-Z]{2}\s+\d{5}')
    OFFICE_NAMES_RE = re.compile(
        r'\b(dental|care|center|clinic|office|practice)\b.*\b(dental|care|center|clinic|office|practice)\b',
        re.I
    )

    repeats = detect_repeated_lines(lines)
    keep = []
    first_block = True
    block_hits = 0
    form_field_hits = 0  # Count form field indicators
    for ln in lines:
        s = collapse_spaced_caps(ln.strip())
        if s:
            if first_block:
                # Check for actual business addresses (not form field labels)
                # Business addresses have: street name + Ave/Rd/St + city/state pattern
                is_business_address = bool(re.search(r'\b\d+\s+[NS]?\s*\w+\s+(Ave|Avenue|Rd|Road|St|Street|Blvd|Boulevard)\b', s, re.I))
                # Also check for practice names
                is_practice_name = bool(re.search(r'\b(dental|dentistry)\s+(care|center|design|solutions)\b', s, re.I))
                
                if is_business_address or is_practice_name:
                    block_hits += 1
                
                # Count form field indicators (fields with colons that are form labels)
                if re.search(r'\b(name|phone|email|address|city|state|zip|birth|date|ssn|gender|marital)\s*:', s, re.I):
                    form_field_hits += 1
        else:
            if first_block:
                # Only drop first block if it has business addresses AND no form fields
                # This prevents dropping the patient registration section
                if block_hits >= 2 and form_field_hits == 0:
                    # drop first block entirely - it's just header/practice info
                    keep = []
                    first_block = False
                    block_hits = 0
                    form_field_hits = 0
                    continue
                first_block = False
        if not s:
            keep.append(ln); continue
        if s in repeats or PAGE_NUM_RE.match(s): continue
        
        # NEW FILTERS (Fix 3):
        # Filter out lines with multiple street addresses
        if MULTI_LOCATION_RE.search(s):
            continue
        
        # Filter out lines with multiple city-state-zip patterns
        if len(CITY_STATE_ZIP_RE.findall(s)) >= 2:
            continue
        
        # Filter out lines that look like multiple office names
        if OFFICE_NAMES_RE.search(s) and len(s) > 80:
            continue
        
        # Filter out lines with multiple zip codes
        if len(re.findall(r'\b\d{5}\b', s)) >= 2:
            continue
        
        # Archivev8 Fix 2: Enhanced Header/Business Information Filtering
        # Get the line index for top-of-document check
        idx = lines.index(ln) if ln in lines else 999
        
        # Filter lines with dental practice email addresses + business keywords
        if DENTAL_PRACTICE_EMAIL_RE.search(s):
            # Check if line also has practice/business keywords
            if re.search(r'\b(?:dental|dentistry|family|cosmetic|implant|orthodontics)\b', s, re.I):
                continue
        
        # Filter long lines combining business name with address
        if BUSINESS_WITH_ADDRESS_RE.search(s):
            # Additional check: line is quite long (likely a header)
            if len(s) > 50:
                continue
        
        # Filter lines at top of document (first 20 lines) that look like practice headers
        if idx < 20:
            # Check for practice name + address pattern
            has_practice_keyword = bool(re.search(r'\b(?:dental|dentistry|orthodontics|family|cosmetic|implant)\b', s, re.I))
            has_address_keyword = bool(re.search(r'\b(?:suite|ste\.?|ave|avenue|rd|road|st|street|blvd)\b', s, re.I))
            has_contact = bool(re.search(r'(?:@|phone|tel|fax|\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', s, re.I))
            
            # If it has 2+ of these indicators and is long, likely a header
            score = sum([has_practice_keyword, has_address_keyword, has_contact])
            if score >= 2 and len(s) > 40:
                continue
        
        # Existing filters
        if re.search(r"\bcontinued on back side\b", s, re.I): continue
        if re.search(r"\brev\s*\d{1,2}\s*/\s*\d{2}\b", s, re.I): continue
        if s in {"<<<", ">>>"} or re.search(r"\bOC\d+\b", s): continue
        keep.append(ln)
    return keep


def coalesce_soft_wraps(lines: List[str]) -> List[str]:
    """
    Intelligently join lines that were soft-wrapped in the PDF.
    
    Lines are joined if:
    - Previous line ends with hyphen or slash
    - Next line starts with lowercase or small connector word
    - Previous line ends with Yes/No checkboxes and next starts lowercase
    
    Returns a list of lines with soft wraps coalesced.
    """
    out: List[str] = []
    i = 0
    while i < len(lines):
        a = lines[i]
        if not a.strip():
            out.append(a); i += 1; continue
        merged = a.rstrip()
        while i + 1 < len(lines):
            b = lines[i+1]
            b_str = b.strip()
            if not b_str: break
            if is_heading(b_str): break
            if BULLET_RE.match(b_str): break
            a_end = merged[-1] if merged else ""
            starts_lower = bool(re.match(r"^[a-z(]", b_str))
            small_word  = bool(re.match(r"^(and|or|if|but|then|with|of|for|to)\b", b_str, re.I))
            
            # Enhanced line coalescing (Fix 5):
            # More aggressive continuation for incomplete questions
            ends_with_question = a_end == "?"
            starts_with_paren = b_str.startswith("(")
            
            # Archivev19 Fix 2: Handle multi-line questions where line 1 ends with "/ [ ] Yes [ ] No"
            # and line 2 starts with lowercase continuation (e.g., bisphosphonates question)
            # Pattern: "...Actonel/ [ ] Yes [ ] No" followed by "other medications..."
            ends_with_yes_no = bool(re.search(r'/\s*\[\s*\]\s*(?:Yes|No)\s*(?:\[\s*\]\s*(?:Yes|No)\s*)?$', merged, re.I))
            
            # Join if: 
            # 1. hyphen/slash at end, OR
            # 2. (not sentence-ending punctuation AND (starts lowercase OR small word OR starts with paren)), OR
            # 3. Archivev19: ends with Yes/No checkboxes and next line starts with lowercase (continuation)
            if (a_end in "-/" or 
                (not ends_with_question and a_end not in ".:;?!" and (starts_lower or small_word or starts_with_paren)) or
                (ends_with_yes_no and starts_lower)):
                merged = (merged.rstrip("- ") + " " + b_str).strip()
                i += 1; continue
            break
        out.append(merged)
        i += 1
    return out
