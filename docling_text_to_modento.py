#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docling_text_to_modento.py — v2.20

TXT (Docling) -> Modento-compliant JSON

What's new vs v2.19 (Archivev19 continued):
  • Archivev19 Fix 4: Never treat lines with question marks as section headings (captures "Question? If so, detail:" patterns)
  • Previous (v2.19/Archivev19 Fix 3): Inline checkbox field title extraction preserves labels on same line as options
  • Previous (v2.18/Archivev19 Fix 1-2): Single-word field labels, multi-line questions with mid-line checkboxes
  • Previous (v2.17/Archivev18): Date template artifacts, instructional text filtering, explain field titles
  • Previous (v2.16): Multi-sub-field label splitting, enhanced employer/insurance patterns
  • Previous (v2.15): OCR typo correction for "rregular" -> "Irregular"
  • Previous (v2.14): Enhanced category header detection, unique "Please explain" titles
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from difflib import SequenceMatcher
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

# ---------- Paths

DEFAULT_IN_DIR = "output"
DEFAULT_OUT_DIR = "JSONs"

# ---------- Regex / tokens

CHECKBOX_ANY = r"(?:\[\s*\]|\[x\]|☐|☑|□|■|❒|◻|✓|✔|✗|✘)"
BULLET_RE = re.compile(r"^\s*(?:[-*•·]|" + CHECKBOX_ANY + r")\s+")
CHECKBOX_MARK_RE = re.compile(r"^\s*(" + CHECKBOX_ANY + r")\s+")

INLINE_CHOICE_RE = re.compile(
    rf"(?:^|\s){CHECKBOX_ANY}\s*([^\[\]•·\-\u2022]+?)(?=(?:\s*{CHECKBOX_ANY}|\s*[•·\-]|$))"
)

YESNO_SET = {"yes", "no", "y", "n"}

PHONE_RE   = re.compile(r"\b(phone|cell|mobile|telephone)\b", re.I)
EMAIL_RE   = re.compile(r"\bemail\b", re.I)
ZIP_RE     = re.compile(r"\b(zip|postal)\b", re.I)
SSN_RE     = re.compile(r"\b(ssn|social security|soc(?:ial)?\s*sec(?:urity)?|ss#)\b", re.I)
STATE_LABEL_RE = re.compile(r"^\s*state\b", re.I)
DATE_LABEL_RE  = re.compile(r"\b(date|dob|birth)\b", re.I)
INITIALS_RE    = re.compile(r"\binitials?\b", re.I)
WITNESS_RE     = re.compile(r"\bwitness\b", re.I)

IF_GUIDANCE_RE = re.compile(r"\b(if\s+(yes|no)[^)]*|if\s+so|if\s+applicable|explain below|please explain|please list)\b", re.I)

# Enhanced "If Yes" detection patterns (Fix 2)
IF_YES_FOLLOWUP_RE = re.compile(
    r'(.+?)\s*\[\s*\]\s*Yes\s*\[\s*\]\s*No\s+If\s+yes[,:]?\s*(?:please\s+)?explain',
    re.I
)
IF_YES_INLINE_RE = re.compile(
    r'(.+?)\s*\[\s*\]\s*Yes\s*\[\s*\]\s*No\s+If\s+yes',
    re.I
)

PAGE_NUM_RE = re.compile(r"^\s*(?:page\s*\d+(?:\s*/\s*\d+)?|\d+\s*/\s*\d+)\s*$", re.I)
ADDRESS_LIKE_RE = re.compile(
    r"\b(?:street|suite|ste\.?|ave|avenue|rd|road|blvd|zip|postal|fax|tel|phone|www\.|https?://|\.com|\.net|\.org|welcome|new\s+patients)\b",
    re.I,
)

# Enhanced header filtering patterns (Archivev8 Fix 2)
DENTAL_PRACTICE_EMAIL_RE = re.compile(
    r'@.*?(?:dental|dentistry|orthodontics|smiles).*?\.(com|net|org)',
    re.I
)
BUSINESS_WITH_ADDRESS_RE = re.compile(
    r'(?:dental|dentistry|orthodontics|family|cosmetic|implant).{20,}?(?:suite|ste\.?|ave|avenue|rd|road|st\.?|street)',
    re.I
)
PRACTICE_NAME_PATTERN = re.compile(
    r'^(?:.*?(?:dental|dentistry|orthodontics|family|cosmetic|implant).*?){1,3}$',
    re.I
)

INSURANCE_PRIMARY_RE   = re.compile(r"\bprimary\b.*\binsurance\b", re.I)
INSURANCE_SECONDARY_RE = re.compile(r"\bsecondary\b.*\binsurance\b", re.I)
INSURANCE_BLOCK_RE     = re.compile(r"(dental\s+benefit\s+plan|insurance\s+information|insurance\s+details)", re.I)

SINGLE_SELECT_TITLES_RE = re.compile(r"\b(marital\s+status|relationship|gender|sex)\b", re.I)

HEAR_ABOUT_RE   = re.compile(r"how\s+did\s+you\s+hear\s+about\s+us", re.I)
REFERRED_BY_RE  = re.compile(r"\b(referred\s+by|who\s+can\s+we\s+thank)\b", re.I)

RESP_PARTY_RE   = re.compile(r"responsible\s+party.*other\s+than\s+patient", re.I)
SINGLE_BOX_RE   = re.compile(r"^\s*\[\s*\]\s*(.+)$")

# broader Y/N capture (no boxes)
YN_SIMPLE_RE = re.compile(r"(?P<prompt>.*?)(?:\bYes\b|\bY\b)\s*(?:/|,|\s+)\s*(?:\bNo\b|\bN\b)", re.I)

# parent/guardian
PARENT_RE = re.compile(r"\b(parent|guardian|mother|father|legal\s+guardian)\b", re.I)

# Archivev12 Fix 2: Special field patterns for common fields without perfect formatting
SEX_GENDER_PATTERNS = [
    re.compile(r'\b(sex|gender)\s*[:\-]?\s*(?:M\s*or\s*F|M/F|Male/Female)', re.I),
    re.compile(r'\b(sex|gender)\s*\[\s*\]\s*(?:male|female|M|F)', re.I),
]

MARITAL_STATUS_PATTERNS = [
    re.compile(r'(?:please\s+)?circle\s+one\s*:?\s*(single|married|divorced|separated|widowed)', re.I),
    re.compile(r'\bmarital\s+status\s*:?\s*(?:\[\s*\]|single|married)', re.I),
]

PHONE_PATTERNS = [
    (r'work\s+phone', 'work_phone'),
    (r'home\s+phone', 'home_phone'),
    (r'(?:cell|mobile)\s+phone', 'cell_phone'),
]

ALLOWED_TYPES = {"input", "date", "states", "radio", "dropdown", "terms", "signature"}

PRIMARY_SUFFIX = "__primary"
SECONDARY_SUFFIX = "__secondary"

# ---------- Debug/Reporting

@dataclass
class MatchEvent:
    title: str
    parsed_key: str
    section: str
    matched_key: Optional[str]
    reason: str
    score: float
    coverage: float

class DebugLogger:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.events: List[MatchEvent] = []
        self.near_misses: List[MatchEvent] = []
        self.gates: List[str] = []

    def log(self, ev: MatchEvent):
        if self.enabled:
            self.events.append(ev)

    def log_near(self, ev: MatchEvent):
        if self.enabled:
            self.near_misses.append(ev)

    def gate(self, msg: str):
        if self.enabled:
            self.gates.append(msg)

    def print_summary(self):
        if not self.enabled:
            return
        print("  [debug] template matches:")
        for ev in self.events:
            print(f"    ✓ '{ev.title}' -> {ev.matched_key} ({ev.reason}, score={ev.score:.2f}, cov={ev.coverage:.2f})")
        if self.near_misses:
            print("  [debug] near-misses (score>=0.75 but rejected):")
            for ev in self.near_misses:
                print(f"    ~ '{ev.title}' -> {ev.matched_key or '—'} ({ev.reason}, score={ev.score:.2f}, cov={ev.coverage:.2f})")
        if self.gates:
            print("  [debug] gates:")
            for g in self.gates:
                print(f"    • {g}")

# ---------- Normalization helpers

SPELL_FIX = {
    "rregular": "Irregular",
    "hyploglycemia": "Hypoglycemia",
    "diabates": "Diabetes",
    "osteoperosis": "Osteoporosis",
    "artritis": "Arthritis",
    "rheurnatism": "Rheumatism",
    "e": "Email",
}

def normalize_glyphs_line(s: str) -> str:
    repls = {
        "☐": "[ ] ", "☑": "[x] ", "□": "[ ] ", "■": "[ ] ", "❒": "[ ] ", "◻": "[ ] ", "◽": "[ ] ",
        "▪": "[ ] ", "•": "• ", "·": "• ", "✓": "[x] ", "✔": "[x] ", "✗": "[ ] ", "✘": "[ ] ",
        "¨": "[ ] ",
    }
    for k, v in repls.items():
        s = s.replace(k, v)
    s = re.sub(r"(^|\s)!\s+(?=\w)", r"\1[ ] ", s)
    return s

def collapse_spaced_letters_any(s: str) -> str:
    s = re.sub(r"(?<!\w)(?:[A-Za-z]\s+){3,}[A-Za-z](?!\w)", lambda m: m.group(0).replace(" ", ""), s)
    return re.sub(r"\s{2,}", " ", s).strip()

def collapse_spaced_caps(s: str) -> str:
    s2 = re.sub(r"(?:(?<=\b)|^)(?:[A-Z]\s+){2,}(?=[A-Z]\b)", lambda m: m.group(0).replace(" ", ""), s)
    s2 = collapse_spaced_letters_any(s2)
    return s2.strip()

def read_text_file(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return p.read_text(encoding="latin-1", errors="replace")

def is_heading(line: str) -> bool:
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
    
    # Must NOT end with a colon followed by content (that's a field label)
    if re.search(r':\s*\S', cleaned):
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

def detect_repeated_lines(lines: List[str], min_count: int = 3, max_len: int = 80) -> set:
    counter = Counter([collapse_spaced_caps(l.strip()) for l in lines if l.strip() and len(l.strip()) <= max_len])
    return {s for s, c in counter.items() if c >= min_count}

def is_address_block(block: List[str]) -> bool:
    hits = sum(1 for ln in block if ADDRESS_LIKE_RE.search(ln))
    return len(block) >= 3 and hits >= 2

def scrub_headers_footers(text: str) -> List[str]:
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
    for ln in lines:
        s = collapse_spaced_caps(ln.strip())
        if s:
            if first_block:
                if ADDRESS_LIKE_RE.search(s):
                    block_hits += 1
        else:
            if first_block:
                if block_hits >= 2:
                    # drop first block entirely
                    keep = []
                    first_block = False
                    block_hits = 0
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

# ---------- Fix 1: Split Multi-Question Lines

def split_multi_question_line(line: str) -> List[str]:
    """
    Split lines containing multiple independent questions into separate lines.
    
    Example:
        Input:  "Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single"
        Output: ["Gender: [ ] Male [ ] Female", "Marital Status: [ ] Married [ ] Single"]
    
    Detection criteria:
    - Line contains 2+ question labels
    - Significant spacing (4+ spaces) separates the questions
    - Each segment should have checkboxes
    
    Returns:
        List of question strings (original line if no split needed)
    """
    # Strategy: Look for patterns like "...] ... 4+spaces ... Label:"
    # This finds where one question ends (with ]) and another begins (with Label:)
    
    # Pattern: closing bracket, some text/spaces, then 4+ spaces, then a label with colon
    split_pattern = r'\]\s+([^\[]{0,50}?)\s{4,}([A-Z][A-Za-z\s]+?):\s*\['
    matches = list(re.finditer(split_pattern, line))
    
    if not matches:
        # No clear split points found
        return [line]
    
    # Build segments by splitting at the match positions
    segments = []
    last_end = 0
    
    for match in matches:
        # The split point is right before the label (group 2)
        split_pos = match.start() + len(match.group(0)) - len(match.group(2)) - 1 - len(': [')
        
        # Add the segment from last_end to split_pos
        segment = line[last_end:split_pos].strip()
        if segment and re.search(CHECKBOX_ANY, segment):
            segments.append(segment)
        
        last_end = split_pos
    
    # Add the final segment
    final_segment = line[last_end:].strip()
    if final_segment and re.search(CHECKBOX_ANY, final_segment):
        segments.append(final_segment)
    
    # Return segments if we successfully split, otherwise original line
    return segments if len(segments) >= 2 else [line]


# ---------- Archivev12 Fix 1: Enhanced Multi-Field Line Splitting

# Known field labels dictionary for pattern matching
KNOWN_FIELD_LABELS = {
    # Name fields
    'first_name': r'\bfirst\s+name\b',
    'last_name': r'\blast\s+name\b',
    'preferred_name': r'\bpreferred\s+name\b',
    'middle_initial': r'\b(?:middle\s+initial|m\.?i\.?)\b',
    'patient_name': r'\bpatient\s+name\b',
    'parent_name': r'\bparent\s+name\b',
    # Date/Age fields
    'birth_date': r'\b(?:birth\s+date|date\s+of\s+birth|birthdate)\b',
    'dob': r'\bdob\b',
    'age': r'\bage\b',
    'mother_dob': r"\bmother'?s?\s+dob\b",
    'father_dob': r"\bfather'?s?\s+dob\b",
    # Demographics
    'sex': r'\bsex\b',
    'gender': r'\bgender\b',
    'marital_status': r'\b(?:marital\s+status|please\s+circle\s+one)\b',
    # Contact fields
    'work_phone': r'\bwork\s+phone\b',
    'home_phone': r'\bhome\s+phone\b',
    'cell_phone': r'\b(?:cell|mobile)\s+phone\b',
    'parent_phone': r'\bparent\s+phone\b',
    'email': r'\be-?mail(?:\s+address)?\b',
    'emergency_contact': r'\bemergency\s+contact\b',
    'phone': r'\bphone\b',
    'ext': r'\bext\s*#?\b',
    'extension': r'\bextension\b',
    # Employment/Education
    'occupation': r'\boccupation\b',
    'employer': r'\b(?:employer|employed\s+by)\b',
    'parent_employer': r'\bparent\s+employer\b',
    'patient_employer': r'\bpatient\s+employed\s+by\b',
    'student': r'\b(?:full\s+time\s+)?student\b',
    # ID fields
    'ssn': r'\b(?:ssn|soc\.?\s*sec\.?|social\s+security)\b',
    'drivers_license': r'\bdrivers?\s+license\s*#?',
    'member_id': r'\bmember\s+id\b',
    'policy_holder': r'\bpolicy\s+holder\b',
    # Address fields
    'address': r'\b(?:mailing\s+)?address\b',
    'city': r'\bcity\b',
    'state': r'\bstate\b',
    'zip': r'\bzip(?:\s+code)?\b',
    'apt': r'\bapt\s*#?\b',
    # Insurance fields
    'group_number': r'\b(?:group\s*#|plan\s*/\s*group\s+number)\b',
    'local_number': r'\blocal\s*#',
    'insurance_company': r'\b(?:insurance\s+company|name\s+of\s+insurance)\b',
    'dental_plan_name': r'\bdental\s+plan\s+name\b',
    'plan_group_number': r'\bplan\s*/\s*group\s+number\b',
    'insured_name': r"\b(?:name\s+of\s+)?insured(?:'?s)?\s+name\b",
    'relationship_to_insured': r'\b(?:patient\s+)?relationship\s+to\s+insured\b',
    'id_number': r'\bid\s+number\b',
    # Misc
    'reason_for_visit': r'\breason\s+for\s+(?:today\'?s\s+)?visit\b',
    'previous_dentist': r'\bprevious\s+dentist\b',
}


def split_by_checkboxes_no_colon(line: str) -> List[str]:
    """
    Archivev12 Fix 1a: Split lines with checkboxes but no colons.
    Pattern: Label [ ] options ... Label [ ] options
    
    Strategy: Find field labels (capitalized words) that are followed by checkboxes,
    separated by 4+ spaces from the next field label.
    """
    # Find all potential field starts: Capital letter word followed by checkbox pattern
    # Look for pattern: 4+ spaces, then Capital letter starting a new field label
    # The key is to detect where one field ends and another begins by looking for spacing
    
    # Pattern to find split points: 4+ spaces followed by a capitalized label
    split_pattern = r'\s{4,}(?=[A-Z][A-Za-z\s]{2,30}?\s*\[)'
    
    split_positions = [m.start() for m in re.finditer(split_pattern, line)]
    
    if not split_positions:
        return [line]
    
    # Split at these positions
    segments = []
    last_pos = 0
    
    for pos in split_positions:
        segment = line[last_pos:pos].strip()
        if segment and re.search(CHECKBOX_ANY, segment):
            segments.append(segment)
        last_pos = pos
    
    # Add final segment
    final_segment = line[last_pos:].strip()
    if final_segment and re.search(CHECKBOX_ANY, final_segment):
        segments.append(final_segment)
    
    return segments if len(segments) >= 2 else [line]


def split_by_known_labels(line: str) -> List[str]:
    """
    Archivev12 Fix 1b: Split lines based on known field labels with spacing.
    Handles: Work Phone (   )         Occupation
    Also handles: Are you a student? ... Mother's DOB ... Father's DOB
    """
    # Find all known label matches in the line
    label_matches = []
    for field_key, pattern in KNOWN_FIELD_LABELS.items():
        for match in re.finditer(pattern, line, re.I):
            label_matches.append((match.start(), match.end(), field_key, match.group(0)))
    
    # Sort by position
    label_matches.sort()
    
    if len(label_matches) < 2:
        return [line]
    
    # Remove overlapping matches - keep the longer/more specific one
    filtered_matches = []
    for i, match in enumerate(label_matches):
        # Check if this match overlaps with any previous match
        overlaps = False
        for prev_match in filtered_matches:
            # Check if ranges overlap
            if not (match[1] <= prev_match[0] or match[0] >= prev_match[1]):
                # They overlap - keep the longer match
                overlaps = True
                break
        if not overlaps:
            filtered_matches.append(match)
    
    label_matches = filtered_matches
    
    if len(label_matches) < 2:
        return [line]
    
    # Check if labels are separated by sufficient spacing (4+ spaces)
    segments = []
    last_added_idx = -1
    
    # If first label doesn't start at position 0, check for text before first big spacing gap
    # This handles cases like "Are you a student? Yes or No    Mother's DOB    Father's DOB"
    if label_matches[0][0] > 0:
        # Look for the first significant spacing gap (4+ spaces) before the second label
        if len(label_matches) >= 2:
            # Check text from start to second label
            text_before_second = line[:label_matches[1][0]]
            # Find position of first 4+ space gap
            gap_match = re.search(r'\s{4,}', text_before_second)
            if gap_match:
                # Extract everything before the gap as first segment
                before_gap = line[:gap_match.start()].strip()
                if before_gap and len(before_gap) > 5:
                    segments.append(before_gap)
    
    for i in range(len(label_matches)):
        start_pos = label_matches[i][0]
        
        if i + 1 < len(label_matches):
            # Check spacing between this label end and next label start
            end_this = label_matches[i][1]
            start_next = label_matches[i + 1][0]
            between = line[end_this:start_next]
            
            # Must have 4+ consecutive spaces to be considered separate fields
            if not re.search(r'\s{4,}', between):
                continue
            
            # This is a valid split point
            end_pos = start_next
            segment = line[start_pos:end_pos].strip()
            if segment:
                segments.append(segment)
                last_added_idx = i
        else:
            # Last match - add from here to end
            segment = line[start_pos:].strip()
            if segment:
                segments.append(segment)
    
    # Only return segments if we got at least 2
    return segments if len(segments) >= 2 else [line]


def split_label_with_subfields(line: str) -> List[str]:
    """
    Archivev17 Fix: Handle pattern "Label: Sub1    Sub2    Sub3"
    
    Detects lines where a single label (ending with colon) is followed by multiple
    sub-labels separated by wide spacing (4+ spaces).
    
    Example: "Phone: Mobile                                  Home                                  Work"
    Should create: ["Phone: Mobile", "Phone: Home", "Phone: Work"]
    Or better: ["Mobile Phone", "Home Phone", "Work Phone"]
    """
    # Pattern: Label ending with colon, followed by multiple capitalized words separated by 4+ spaces
    # Must have at least 2 sub-labels to consider splitting
    match = re.match(r'^([A-Za-z][^:]{0,30}:)\s+([A-Z][a-z]+(?:\s{4,}[A-Z][a-z]+)+)\s*$', line.strip(), re.I)
    
    if not match:
        return [line]
    
    main_label = match.group(1).strip(':').strip()  # e.g., "Phone"
    sublabels_text = match.group(2)  # e.g., "Mobile    Home    Work"
    
    # Split by 4+ spaces to get individual sub-labels
    sublabels = [s.strip() for s in re.split(r'\s{4,}', sublabels_text) if s.strip()]
    
    # Must have at least 2 sub-labels to be valid
    if len(sublabels) < 2:
        return [line]
    
    # Create separate field entries
    # Format: "Sublabel Main-label" (e.g., "Mobile Phone", "Home Phone", "Work Phone")
    segments = []
    for sublabel in sublabels:
        # Create a natural-sounding field name
        if main_label.lower() in ['phone', 'number', 'address']:
            # For phone/number/address: "Mobile Phone", "Home Phone"
            segments.append(f"{sublabel} {main_label}")
        else:
            # For others: keep original format "Label: Sublabel"
            segments.append(f"{main_label}: {sublabel}")
    
    return segments if len(segments) >= 2 else [line]


def split_conditional_field_line(line: str) -> List[str]:
    """
    Archivev13 Fix: Handle conditional multi-field lines.
    Pattern: "Question? ... If condition: field1 ... field2"
    Example: "Are you a student? Yes or No If patient is a minor: Mother's DOB    Father's DOB"
    """
    # Look for "If ... :" pattern
    conditional_match = re.search(r'\b(if\s+[^:]{5,40}:)', line, re.I)
    if not conditional_match:
        return [line]
    
    conditional_text = conditional_match.group(0)
    conditional_start = conditional_match.start()
    
    # Split into:
    # 1. Text before conditional (should be a question)
    # 2. Text after conditional (contains multiple fields)
    before_conditional = line[:conditional_start].strip()
    after_conditional = line[conditional_match.end():].strip()
    
    segments = []
    
    # Add the question before conditional if it exists and is meaningful
    if before_conditional and len(before_conditional) > 5:
        segments.append(before_conditional)
    
    # Try to split the after_conditional part using known labels
    if after_conditional:
        after_segments = split_by_known_labels(after_conditional)
        if len(after_segments) > 1:
            segments.extend(after_segments)
        else:
            segments.append(after_conditional)
    
    return segments if len(segments) >= 2 else [line]


def enhanced_split_multi_field_line(line: str) -> List[str]:
    """
    Archivev12 Fix 1: Enhanced multi-field line splitting.
    Tries multiple strategies in order:
    0. Archivev15: Field label with inline checkbox (DON'T split these)
    1. Archivev17: Label with sub-fields (Phone: Mobile Home Work)
    2. Conditional field patterns (Archivev13)
    3. Existing pattern (colon + checkbox)
    4. Checkboxes without colons
    5. Known label patterns with spacing
    """
    # Archivev15 Fix 1: Check if this is a field with inline checkbox option
    # These should NOT be split, so return early
    if detect_field_with_inline_checkbox(line):
        return [line]
    
    # Archivev17 Fix: Check if this is "Label: Sub1  Sub2  Sub3" pattern
    result = split_label_with_subfields(line)
    if len(result) > 1:
        return result
    
    # Try conditional field pattern first (Archivev13)
    result = split_conditional_field_line(line)
    if len(result) > 1:
        return result
    
    # Try existing pattern (backward compatible)
    result = split_multi_question_line(line)
    if len(result) > 1:
        return result
    
    # Try checkboxes without colons
    result = split_by_checkboxes_no_colon(line)
    if len(result) > 1:
        return result
    
    # Try known label detection
    result = split_by_known_labels(line)
    if len(result) > 1:
        return result
    
    return [line]


def detect_sex_gender_field(line: str) -> Optional[Tuple[str, str]]:
    """
    Archivev12 Fix 2a: Detect sex/gender field patterns.
    Returns: (field_type, segment) or None
    
    For lines with checkboxes (e.g., "Sex [ ] Male [ ] Female"), extract the entire field.
    For lines with text options (e.g., "Sex M or F"), extract up to the pattern.
    """
    for pattern in SEX_GENDER_PATTERNS:
        match = pattern.search(line)
        if match:
            # Check if this is a checkbox-based field
            # Look for checkboxes after the label
            after_label = line[match.end():]
            has_checkboxes = bool(re.search(CHECKBOX_ANY, after_label))
            
            if has_checkboxes:
                # Extract the entire sex/gender field including all checkboxes until next field or end
                # Look for 4+ spaces followed by a capital letter (indicating next field)
                next_field_match = re.search(r'\s{4,}[A-Z]', line[match.start():])
                if next_field_match:
                    # Extract up to next field
                    end_pos = match.start() + next_field_match.start()
                    return ("sex_gender", line[:end_pos].strip())
                else:
                    # No next field, extract to end
                    return ("sex_gender", line.strip())
            else:
                # Text-based options (M or F), extract up to match end
                return ("sex_gender", line[:match.end()].strip())
    return None


def detect_marital_status_field(line: str) -> Optional[Tuple[str, str]]:
    """
    Archivev12 Fix 2b: Detect marital status field patterns.
    Returns: (field_type, extracted_segment) or None
    """
    for pattern in MARITAL_STATUS_PATTERNS:
        match = pattern.search(line)
        if match:
            # For "Please Circle One:" pattern, need to capture options after it
            if "circle" in match.group(0).lower():
                # Extract from "Please Circle One:" onwards
                segment = line[match.start():].strip()
                return ("marital_status", segment)
            else:
                return ("marital_status", line[match.start():].strip())
    return None


def split_complex_multi_field_line(line: str) -> List[str]:
    """
    Archivev12 Fix 2c: Handle complex lines with multiple fields of different types.
    E.g., "Sex M or F   Soc. Sec. #   Please Circle One: Single Married..."
    """
    segments = []
    remaining = line
    
    # Try to detect and extract sex/gender field
    sex_result = detect_sex_gender_field(line)
    if sex_result:
        field_type, segment = sex_result
        segments.append(segment)
        # Remove this segment from remaining, accounting for position
        sex_pos = line.find(segment)
        if sex_pos == 0:
            remaining = line[len(segment):].strip()
        else:
            remaining = line[sex_pos + len(segment):].strip()
    
    # Try to detect and extract marital status field from remaining
    marital_result = detect_marital_status_field(remaining)
    if marital_result:
        field_type, segment = marital_result
        # Find the position of marital status segment in remaining
        marital_start = remaining.lower().find("please circle") if "please circle" in remaining.lower() else remaining.lower().find("marital")
        
        if marital_start > 0:
            # There's content before marital status (like SSN)
            before = remaining[:marital_start].strip()
            if before and len(before) > 3:  # Has significant content before
                segments.append(before)
        
        # Add the marital status field
        segments.append(segment)
        remaining = ""
    elif remaining:
        # If we extracted sex/gender, add remaining as separate field
        if segments and len(remaining) > 3:
            segments.append(remaining)
    
    return segments if len(segments) >= 2 else [line]


def preprocess_lines(lines: List[str]) -> List[str]:
    """
    Preprocess lines before main parsing.
    Currently handles: splitting multi-question lines with enhanced strategies.
    """
    processed = []
    for line in lines:
        # Skip empty lines
        if not line.strip():
            processed.append(line)
            continue
        
        # Archivev12 Fix: Try multiple splitting strategies
        # Strategy 1: Check if line has sex/gender or marital patterns - use complex split first
        has_sex_gender = any(p.search(line) for p in SEX_GENDER_PATTERNS)
        has_marital = any(p.search(line) for p in MARITAL_STATUS_PATTERNS)
        
        if has_sex_gender or has_marital:
            # Try complex multi-field detection first for these special cases
            split_lines = split_complex_multi_field_line(line)
            if len(split_lines) == 1:
                # If complex didn't split, try enhanced
                split_lines = enhanced_split_multi_field_line(line)
        else:
            # Strategy 2: Enhanced multi-field splitting for regular cases
            split_lines = enhanced_split_multi_field_line(line)
        
        processed.extend(split_lines)
    
    return processed

# ---------- Options & typing

def extract_orphaned_checkboxes_and_labels(current_line: str, next_line: str) -> List[Tuple[str, Optional[bool]]]:
    """
    Fix 2: When current line has checkboxes but minimal text,
    and next line has label text, associate them by column position.
    
    Example:
      Current: "[ ]           [ ]           [ ]"
      Next:    "Anemia        Diabetes      Cancer"
      Returns: [("Anemia", None), ("Diabetes", None), ("Cancer", None)]
    """
    # Count checkboxes on current line
    checkbox_matches = list(re.finditer(CHECKBOX_ANY, current_line))
    if len(checkbox_matches) < 2:
        return []
    
    # Check if current line has minimal text (mostly just checkboxes)
    text_after_boxes = re.sub(CHECKBOX_ANY, '', current_line).strip()
    if len(text_after_boxes) > 50:  # Has substantial text, not orphaned
        return []
    
    # Check if next line has no checkboxes but has text
    if re.search(CHECKBOX_ANY, next_line):
        return []  # Next line also has checkboxes, not the label line
    
    next_stripped = next_line.strip()
    if not next_stripped or len(next_stripped) < 3:
        return []
    
    # Split next line into words/phrases by whitespace
    # Assume labels align roughly with checkbox positions
    words = re.split(r'\s{2,}', next_stripped)  # Split on 2+ spaces
    words = [w.strip() for w in words if w.strip()]
    
    # Match count: ideally num_words == num_checkboxes
    num_boxes = len(checkbox_matches)
    if len(words) < 2 or len(words) > num_boxes + 2:  # Some tolerance
        return []
    
    # Associate words with checkboxes
    options = []
    for word in words[:num_boxes]:  # Take up to num_boxes words
        if len(word) > 1:
            options.append((word, None))
    
    return options if len(options) >= 2 else []

def extract_title_from_inline_checkboxes(line: str) -> str:
    """
    Extract the question/prompt text before the first checkbox marker (Fix 1).
    
    Example:
        "How did you hear? [ ] Google [ ] Friend" -> "How did you hear?"
        "Gender: [ ] Male [ ] Female" -> "Gender:"
    """
    # Pattern to match text before first checkbox
    match = re.match(r'^(.*?)(?:\[\s*\]|\[x\]|☐|☑|□|■|❒|◻)', line)
    if match:
        title = match.group(1).strip()
        # Clean up trailing colons, question marks, etc
        title = title.rstrip(':? ').strip()
        if title:
            return title
    # Fallback: return cleaned line
    return re.sub(CHECKBOX_ANY, '', line).strip()

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

def option_from_bullet_line(ln: str) -> Optional[Tuple[str, Optional[bool]]]:
    s = ln.strip()
    if not BULLET_RE.match(s):
        return None
    # Check if there are multiple checkboxes on this line (grid format, not bullet)
    checkbox_count = len(re.findall(CHECKBOX_ANY, s))
    if checkbox_count > 1:
        return None  # This is inline grid format, not a bullet
    s = CHECKBOX_MARK_RE.sub("", s, count=1)
    s = re.sub(r"^\s*[-*•·]\s+", "", s)
    name = clean_token(s)
    if not name:
        return None
    low = name.lower()
    if low in ("yes", "y"): return ("Yes", True)
    if low in ("no", "n"):  return ("No", False)
    return (name, None)

def detect_field_with_inline_checkbox(line: str) -> Optional[Tuple[str, str]]:
    """
    Archivev15 Fix 1: Detect lines with field label followed by inline checkbox option.
    
    Pattern: "Field Label:    <spaces>    [ ] Option text"
    
    Returns:
        Tuple of (field_label, checkbox_option) if pattern detected, None otherwise
    
    Examples:
        "Cell Phone:                         [ ] Yes, send me Text Message alerts"
        -> ("Cell Phone", "Yes, send me Text Message alerts")
        
        "E-mail Address:                     [ ] Yes, send me alerts via Email"
        -> ("E-mail Address", "Yes, send me alerts via Email")
    """
    # Look for pattern: text ending with colon, followed by spaces, then checkbox and text
    pattern = r'^(.+?):\s{5,}' + CHECKBOX_ANY + r'\s+(.+)$'
    match = re.match(pattern, line.strip())
    
    if match:
        field_label = match.group(1).strip()
        checkbox_text = match.group(2).strip()
        
        # Validate: field label should be reasonably short (not a question)
        # and checkbox text should be meaningful
        if len(field_label) <= 50 and len(checkbox_text) >= 5:
            return (field_label, checkbox_text)
    
    return None


def options_from_inline_line(ln: str) -> List[Tuple[str, Optional[bool]]]:
    """
    Enhanced to handle grid/multi-column layouts (Fix 1).
    Splits checkboxes that appear in columns with significant spacing.
    """
    s_norm = normalize_glyphs_line(ln)
    
    # First try: existing inline choice regex
    items: List[Tuple[str, Optional[bool]]] = []
    for m in INLINE_CHOICE_RE.finditer(s_norm):
        raw_label = m.group(1)
        
        # Fix 3: Split on excessive spacing BEFORE clean_token (which collapses spaces)
        parts = re.split(r'\s{5,}', raw_label)
        if len(parts) > 1:
            # Take only first part (the actual checkbox label)
            original = raw_label
            raw_label = next((p.strip() for p in parts if p.strip()), raw_label)
            # DEBUG
            if 'Bad Bite' in original and 'Please list' in original:
                import sys
                print(f"DEBUG: Split '{original[:60]}...' -> '{raw_label}'", file=sys.stderr)
        
        label = clean_token(raw_label)
        if not label: continue
        low = label.lower()
        if low in ("yes", "y"): items.append(("Yes", True))
        elif low in ("no", "n"): items.append(("No", False))
        else: items.append((label, None))
    
    # If we found options with existing method, use it (unless it looks like grid layout)
    if items and len(items) < 3:
        return items
    
    # NEW: Grid detection - look for multiple checkboxes with wide spacing (Fix 1)
    checkbox_positions = []
    for m in re.finditer(CHECKBOX_ANY, s_norm):
        checkbox_positions.append(m.start())
    
    if len(checkbox_positions) >= 3:  # Multiple checkboxes suggest grid
        # Split line into segments based on checkbox positions
        options = []
        for i, start_pos in enumerate(checkbox_positions):
            # Extract text after this checkbox until next checkbox or EOL
            if i + 1 < len(checkbox_positions):
                end_pos = checkbox_positions[i + 1]
            else:
                end_pos = len(s_norm)
            
            segment = s_norm[start_pos:end_pos]
            # Remove checkbox token and extract label
            label = re.sub(CHECKBOX_ANY, '', segment).strip()
            
            # Fix 3: Better cleaning for grid layouts
            # 1. Split on excessive spacing (5+ spaces = likely column boundary)
            parts = re.split(r'\s{5,}', label)
            if len(parts) > 1:
                # Take the first non-empty part (the actual label)
                label = next((p.strip() for p in parts if p.strip()), label)
            
            # 2. Split on category headers that appear mid-text (Fix 3 enhancement)
            # Pattern: text followed by category name followed by more text
            category_pattern = r'\b(Cardiovascular|Gastrointestinal|Neurological|Viral|Hematologic|Lymphatic|Infections?)\b'
            # Check if category appears in middle of text
            match = re.search(category_pattern, label, re.I)
            if match:
                # Split before the category and take the first part
                label = label[:match.start()].strip()
            
            # 3. Handle merged medical terms (Fix 3 - complex case)
            # Pattern: "Word1 Word2 (parenthetical) Word3" where Word3 looks unrelated
            # Example: "Artificial Angina (chest pain) Valve" should become "Artificial Heart Valve" or just "Artificial Valve"
            # If we have pattern like "X Y (...) Z" where Y and Z are both medical terms, keep only first part
            paren_match = re.search(r'^(.+?)\s+\w+\s*\([^)]+\)\s+(\w+)$', label)
            if paren_match:
                # This looks like merged terms. Try to clean it up.
                first_part = paren_match.group(1).strip()
                last_word = paren_match.group(2).strip()
                # If first part is short (1-2 words), combine with last word
                if len(first_part.split()) <= 2:
                    label = f"{first_part} {last_word}"
                else:
                    # Keep first part only
                    label = first_part
            
            # 4. Collapse remaining multiple spaces
            label = re.sub(r'\s{2,}', ' ', label)
            
            # 5. Remove trailing checkbox artifacts
            label = label.strip('[]')
            
            # 6. Filter out standalone category headers
            category_headers = r'^(Type|Cardiovascular|Gastrointestinal|Neurological|Viral|Women|Hematologic|Lymphatic|Infections?|Additional)$'
            if re.match(category_headers, label.strip(), re.I):
                continue
            
            # 7. Apply standard token cleaning
            label = clean_token(label)
            
            if label and len(label) > 1 and label.lower() not in YESNO_SET:
                options.append((label, None))
        
        if len(options) >= 2:  # Changed from >= 3 to be more permissive (Fix 3)
            return options
    
    return items  # Fall back to existing method

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

# ---------- Model

@dataclass
class Question:
    key: str
    title: str
    section: str
    type: str
    optional: bool = False
    control: Dict = field(default_factory=dict)

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

# ---------- Archivev8 Fix 4: Clean Malformed Option Text

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

# ---------- Composite / multi-label fan-out

CANON_LABELS = {
    "last name": "Last Name",
    "first name": "First Name",
    "mi": "MI",
    "middle initial": "MI",
    "nickname": "Preferred Name",
    "preferred name": "Preferred Name",
    "patient name": "Patient Name",
    "date of birth": "Date of Birth",
    "dob": "Date of Birth",
    "age": "Age",
    "address": "Address",
    "mailing address": "Address",
    "city": "City",
    "state": "State",
    "zip": "Zipcode",
    "zipcode": "Zipcode",
    "email": "Email",
    "e mail": "Email",
    "phone": "Phone",
    "home phone": "Home Phone",
    "mobile phone": "Mobile Phone",
    "cell phone": "Mobile Phone",
    "work phone": "Work Phone",
    "ssn": "SSN",
    "social security": "SSN",
    "soc sec": "SSN",
    "ss#": "SSN",
    "employer": "Employer",
    "employer (if different from above)": "Employer",
    "occupation": "Occupation",
    "emergency contact": "Emergency Contact",
    "emergency name": "Emergency Contact Name",
    "emergency phone": "Emergency Phone",
    "emergency relationship": "Emergency Relationship",
    "relationship": "Relationship",
    "person responsible for account": "Responsible Party Name",
    "responsible party name": "Responsible Party Name",
    "responsible party": "Responsible Party Name",
    "drivers license #": "Driver's License #",
    "driver's license #": "Driver's License #",
    "drivers license": "Driver's License #",
    "driver license": "Driver's License #",
    "name of parent": "Parent Name",
    "parent name": "Parent Name",
    "parent soc. sec. #": "Parent SSN",
    "parent ssn": "Parent SSN",
    # Insurance
    "insureds name": "Insured's Name",
    "insured name": "Insured's Name",
    "insureds": "Insured's Name",
    "insured": "Insured's Name",
    "subscriber name": "Insured's Name",
    "member name": "Insured's Name",
    "policy holder": "Insured's Name",
    "relationship to insured": "Relationship to Insured",
    "relationship to subscriber": "Relationship to Insured",
    "relationship to policy holder": "Relationship to Insured",
    "relationship to member": "Relationship to Insured",
    "id number": "ID Number",
    "id no": "ID Number",
    "member id": "ID Number",
    "policy id": "ID Number",
    "identification number": "ID Number",
    "group number": "Group Number",
    "group #": "Group Number",
    "grp #": "Group Number",
    "plan/group number": "Group Number",
    "insurance company": "Insurance Company",
    "insurance phone": "Insurance Phone",
    "insurance phone #": "Insurance Phone",
    "customer service phone": "Insurance Phone",
    "cust svc phone": "Insurance Phone",
    "address on card": "Insurance Address",
    "insurance address": "Insurance Address",
}

LABEL_ALTS = sorted(CANON_LABELS.keys(), key=len, reverse=True)

def _sanitize_words(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def try_split_known_labels(line: str) -> List[str]:
    s_raw = normalize_glyphs_line(line)
    s = collapse_spaced_caps(s_raw).strip()
    if not s or len(s) > 220 or s.endswith("."):
        return []
    # collapse repeated phrases like "Insured's Name Insured's Name"
    s_de_rep = re.sub(r"(\binsured'?s?\s+name\b)(\s+\1)+", r"\1", s, flags=re.I)
    s_sanit = _sanitize_words(s_de_rep)
    hits: List[Tuple[int, str]] = []
    for phrase in LABEL_ALTS:
        p = _sanitize_words(phrase)
        idx = s_sanit.find(p)
        if idx >= 0:
            hits.append((idx, CANON_LABELS.get(phrase, phrase.title())))
    if len(hits) < 2:
        return []
    hits.sort(key=lambda t: t[0])
    labels = []
    for _pos, canon in hits:
        if canon not in labels:
            labels.append(canon)
    return labels

# ---------- Grids

def looks_like_grid_header(s: str) -> Optional[List[str]]:
    line = collapse_spaced_caps(s.strip().strip(":"))
    if "|" in line:
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) >= 3: return cols
    parts = [p.strip() for p in re.split(r"\s{3,}", line) if p.strip()]
    return parts if len(parts) >= 3 else None

# ---------- Fix 4: Enhanced Table/Grid Detection

def detect_table_layout(lines: List[str], start_idx: int, max_rows: int = 15) -> Optional[dict]:
    """
    Archivev10 Fix 5: Enhanced Grid Boundary Detection.
    
    Detect if lines starting at start_idx form a table layout.
    Enhanced to handle header-less grids and inconsistent column counts.
    
    Returns:
        dict with table info if detected, None otherwise
        {
            'header_line': int,  # index of header line
            'data_lines': List[int],  # indices of data lines
            'num_columns': int,
            'column_positions': List[int],  # approximate column start positions
            'headers': List[str]  # column headers
        }
    """
    if start_idx >= len(lines):
        return None
    
    # Look for header line: multiple capitalized words, evenly spaced
    header_line = lines[start_idx].strip()
    
    # Don't treat as table if it has checkboxes (it's data, not a header)
    if re.search(CHECKBOX_ANY, header_line):
        return None
    
    # Split by significant spacing (5+ spaces) to find potential headers
    parts = re.split(r'\s{5,}', header_line)
    
    # Filter to keep only capitalized parts that look like headers
    potential_headers = []
    header_positions = []
    
    current_pos = 0
    for part in parts:
        # Find position of this part in original line
        pos = header_line.find(part, current_pos)
        part = part.strip()
        
        # Archivev10 Fix 5: More flexible header detection
        # Check if part looks like a header (starts with capital, not too long)
        # Also allow lowercase if it's a medical term or short phrase
        is_valid_header = False
        if part and 2 <= len(part) <= 35:
            if part[0].isupper():
                is_valid_header = True
            elif part.lower() in ['health', 'history', 'social', 'women', 'type']:
                is_valid_header = True
        
        if is_valid_header:
            potential_headers.append(part)
            header_positions.append(pos)
        
        current_pos = pos + len(part)
    
    # Archivev10 Fix 5: Accept 2+ columns (was 3+) for smaller grids
    if len(potential_headers) < 2:
        return None
    
    headers = potential_headers
    column_positions = header_positions
    
    # Check if next few lines have checkboxes aligned with these columns
    data_lines = []
    checkbox_pattern = re.compile(CHECKBOX_ANY)
    
    # Archivev10 Fix 5: Use column boundary detection for better accuracy
    precise_columns = detect_column_boundaries(lines, start_idx + 1, max_rows)
    if precise_columns and len(precise_columns) >= len(column_positions) * 0.7:
        column_positions = precise_columns
    
    for i in range(start_idx + 1, min(start_idx + max_rows, len(lines))):
        line = lines[i]
        
        # Count checkboxes
        checkboxes = list(checkbox_pattern.finditer(line))
        
        # Archivev10 Fix 5: More flexible - accept rows with 2+ checkboxes (was 3+)
        min_checkboxes = max(2, len(column_positions) // 2)
        
        if len(checkboxes) >= min_checkboxes:
            # Check if checkboxes align roughly with column positions
            checkbox_positions = [cb.start() for cb in checkboxes]
            
            # Allow ±15 char tolerance for alignment
            aligned = 0
            for cb_pos in checkbox_positions:
                for col_pos in column_positions:
                    if abs(cb_pos - col_pos) <= 15:
                        aligned += 1
                        break
            
            # Archivev10 Fix 5: More flexible alignment requirement
            min_aligned = max(2, len(column_positions) // 2)
            if aligned >= min_aligned:
                data_lines.append(i)
        elif not line.strip():
            # Empty line might signal end of table
            break
        elif len(checkboxes) == 0 and data_lines:
            # No checkboxes and we've seen data lines = end of table
            break
    
    # Archivev10 Fix 5: More flexible - accept 2+ data lines (was 3+)
    if len(data_lines) >= 2:
        return {
            'header_line': start_idx,
            'data_lines': data_lines,
            'num_columns': len(column_positions),
            'column_positions': column_positions,
            'headers': headers
        }
    
    return None


def parse_table_to_questions(
    lines: List[str],
    table_info: dict,
    section: str
) -> List['Question']:
    """
    Parse a detected table into separate questions, one per column.
    
    Each column becomes a multi-select dropdown with the column header as title.
    """
    questions = []
    
    headers = table_info['headers']
    column_positions = table_info['column_positions']
    data_lines = table_info['data_lines']
    
    # Create one question per column
    for col_idx, header in enumerate(headers):
        col_pos = column_positions[col_idx]
        
        # Determine column width (to next column or EOL)
        if col_idx + 1 < len(column_positions):
            col_width = column_positions[col_idx + 1] - col_pos
        else:
            col_width = None  # Last column goes to EOL
        
        # Extract items for this column
        options = []
        
        for line_idx in data_lines:
            line = lines[line_idx]
            
            # Extract this column's segment
            if col_width:
                segment = line[col_pos:col_pos + col_width]
            else:
                segment = line[col_pos:]
            
            # Check if segment has a checkbox
            if not re.search(CHECKBOX_ANY, segment):
                continue
            
            # Extract label (remove checkbox)
            label = re.sub(CHECKBOX_ANY, '', segment).strip()
            
            # Clean up extra whitespace
            label = re.sub(r'\s{3,}', ' ', label)
            
            # Skip if too short or empty
            if len(label) < 2:
                continue
            
            # Skip common junk patterns
            if label.lower() in {'', 'n/a', 'none', 'other'}:
                continue
            
            options.append((label, None))
        
        # Create question if we found options
        if len(options) >= 2:
            q = Question(
                slugify(header),
                f"{header} - Please mark any that apply",
                section,
                "dropdown",
                control={"options": [make_option(n, b) for n, b in options], "multi": True}
            )
            
            questions.append(q)
    
    return questions

def chunk_by_columns(line: str, ncols: int) -> List[str]:
    line = collapse_spaced_caps(line.strip())
    if "|" in line:
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < ncols: cols += [""] * (ncols - len(cols))
        return cols[:ncols]
    parts = [p.strip() for p in re.split(r"\s{3,}", line)]
    if len(parts) < ncols: parts += [""] * (ncols - len(parts))
    return parts[:ncols]


# ---------- Archivev10 Fix 1: Enhanced Multi-Column Checkbox Grid Detection

def detect_column_boundaries(lines: List[str], start_idx: int, max_lines: int = 10) -> Optional[List[int]]:
    """
    Archivev10 Fix 3: Whitespace-Based Column Detection.
    
    Analyzes multiple lines to detect consistent column positions based on checkbox locations.
    Returns list of character positions where columns start, or None if no pattern found.
    
    Example:
      Input lines with checkboxes at positions [5, 35, 65, 95]
      Returns: [5, 35, 65, 95]
    """
    checkbox_pattern = re.compile(CHECKBOX_ANY)
    
    # Collect checkbox positions from multiple lines
    all_positions = []
    
    for i in range(start_idx, min(start_idx + max_lines, len(lines))):
        line = lines[i]
        checkboxes = list(checkbox_pattern.finditer(line))
        
        if len(checkboxes) >= 2:  # Need at least 2 checkboxes to define columns
            positions = [cb.start() for cb in checkboxes]
            all_positions.append(positions)
    
    if len(all_positions) < 2:
        return None
    
    # Find consistent positions across lines (±3 chars tolerance)
    # Start with the first line's positions as a baseline
    baseline_positions = all_positions[0]
    consistent_positions = []
    
    for base_pos in baseline_positions:
        # Count how many lines have a checkbox near this position
        matches = 0
        for positions in all_positions:
            if any(abs(pos - base_pos) <= 3 for pos in positions):
                matches += 1
        
        # If most lines (>= 60%) have a checkbox near this position, it's consistent
        if matches >= len(all_positions) * 0.6:
            consistent_positions.append(base_pos)
    
    # Need at least 3 consistent columns
    if len(consistent_positions) >= 3:
        return sorted(consistent_positions)
    
    return None


def detect_multicolumn_checkbox_grid(lines: List[str], start_idx: int, section: str, max_rows: int = 20) -> Optional[dict]:
    """
    Detect multi-column checkbox grids (3+ checkboxes per line with significant spacing).
    
    This handles the common dental/medical form pattern where checkboxes are arranged
    in multiple columns across the page:
    
    [ ] Item1        [ ] Item4        [ ] Item7
    [ ] Item2        [ ] Item5        [ ] Item8
    [ ] Item3        [ ] Item6        [ ] Item9
    
    Returns dict with grid info or None if not detected.
    """
    if start_idx >= len(lines):
        return None
    
    # Look for lines with 3+ checkboxes separated by significant whitespace (8+ spaces)
    checkbox_pattern = re.compile(CHECKBOX_ANY)
    
    # Check if first line has multiple checkboxes with spacing
    # If not, look ahead a few lines (might have category headers first)
    first_data_line_idx = start_idx
    first_line = lines[start_idx]
    checkboxes = list(checkbox_pattern.finditer(first_line))
    
    # If first line doesn't have checkboxes, look ahead (skip category headers)
    if len(checkboxes) < 3 and start_idx + 3 < len(lines):
        for look_ahead in range(1, min(4, len(lines) - start_idx)):
            candidate_line = lines[start_idx + look_ahead]
            candidate_checkboxes = list(checkbox_pattern.finditer(candidate_line))
            if len(candidate_checkboxes) >= 3:
                first_line = candidate_line
                checkboxes = candidate_checkboxes
                first_data_line_idx = start_idx + look_ahead
                break
    
    if len(checkboxes) < 3:
        return None
    
    # Check spacing between checkboxes - should be 8+ spaces for multi-column
    checkbox_positions = [cb.start() for cb in checkboxes]
    min_spacing = min(checkbox_positions[i+1] - checkbox_positions[i] 
                     for i in range(len(checkbox_positions)-1))
    
    if min_spacing < 8:
        return None
    
    # Found a multi-column line! Now find all consecutive lines with similar pattern
    data_lines = []
    
    # Archivev10 Fix 3: Try to detect more accurate column boundaries
    precise_columns = detect_column_boundaries(lines, first_data_line_idx, max_rows)
    column_positions = precise_columns if precise_columns else checkbox_positions
    
    for i in range(first_data_line_idx, min(start_idx + max_rows, len(lines))):
        line = lines[i]
        
        # Skip empty lines
        if not line.strip():
            break
        
        # Skip category headers (lines without checkboxes that look like headers)
        if not re.search(CHECKBOX_ANY, line):
            # Check if it's a category header (short, no colon, not a question)
            cleaned = collapse_spaced_caps(line.strip())
            if cleaned and len(cleaned.split()) <= 4 and not cleaned.endswith('?') and not cleaned.endswith(':'):
                # Likely a category header, skip
                continue
            else:
                # Not a checkbox line and not a category header, end of grid
                break
        
        # Count checkboxes
        line_checkboxes = list(checkbox_pattern.finditer(line))
        
        # Line should have at least 1 checkbox
        # (Changed from 2 for Archivev11 Fix 2: some lines have text-only items in other columns)
        if len(line_checkboxes) >= 1:
            data_lines.append(i)
    
    # Valid grid if we found at least 3 data lines
    if len(data_lines) >= 3:
        return {
            'start_line': start_idx,
            'first_data_line': first_data_line_idx,
            'data_lines': data_lines,
            'num_columns': len(column_positions),
            'column_positions': column_positions,
            'section': section
        }
    
    return None


def extract_text_for_checkbox(line: str, cb_end: int, column_positions: List[int], cb_pos: int) -> str:
    """
    Archivev10 Fix 3 + Archivev11 Fix 1: Enhanced text extraction using column boundaries.
    
    Extracts text after a checkbox, using column positions to determine boundaries.
    Archivev11 Fix 1: Also removes known label patterns from adjacent columns.
    """
    text_after = line[cb_end:]
    checkbox_pattern = re.compile(CHECKBOX_ANY)
    
    # Determine which column this checkbox is in
    current_col_idx = None
    for idx, col_pos in enumerate(column_positions):
        if abs(cb_pos - col_pos) <= 5:
            current_col_idx = idx
            break
    
    # Determine the boundary for this column
    if current_col_idx is not None and current_col_idx + 1 < len(column_positions):
        # Use next column position as boundary
        next_col_pos = column_positions[current_col_idx + 1]
        boundary = next_col_pos - cb_end
        if boundary > 0:
            item_text = text_after[:boundary].strip()
        else:
            item_text = text_after.strip()
    else:
        # Last column or no column match - look for next checkbox or large gap
        next_cb = checkbox_pattern.search(text_after)
        if next_cb:
            item_text = text_after[:next_cb.start()].strip()
        else:
            # Split by 8+ spaces to find boundary
            parts = re.split(r'\s{8,}', text_after, maxsplit=1)
            item_text = parts[0].strip() if parts else text_after.strip()
    
    # Archivev11 Fix 1: Remove known label patterns from adjacent columns
    # These are common labels that appear in adjacent columns and shouldn't be part of the field name
    LABEL_PATTERNS = [
        r'\s+Frequency\s*$',           # "Alcohol Frequency", "Drugs Frequency"
        r'\s+How\s+much\s*$',          # "How much"
        r'\s+How\s+long\s*$',          # "How long"
        r'\s+Comments?\s*:?\s*$',      # "Comments", "Comment:"
        r'\s+Additional\s+Comments?\s*:?\s*$',  # "Additional Comments"
    ]
    
    for pattern in LABEL_PATTERNS:
        item_text = re.sub(pattern, '', item_text, flags=re.I)
    
    # Clean up trailing artifacts
    item_text = re.sub(r'\s+[A-Z]\s*$', '', item_text)  # Remove trailing single caps
    item_text = re.sub(r'\s*\([^)]{0,5}\s*$', '', item_text)  # Remove incomplete parentheticals
    item_text = re.sub(r'\s+$', '', item_text)  # Trim trailing spaces
    
    return item_text


def extract_text_only_items_at_columns(line: str, column_positions: List[int], checkboxes_found: List[int]) -> List[str]:
    """
    Archivev11 Fix 2: Extract text-only items at column positions.
    
    Looks for text at expected column positions that don't have checkboxes.
    Validates that text is not a category header or label.
    
    Args:
        line: The line to extract from
        column_positions: List of character positions where columns are expected
        checkboxes_found: List of positions where checkboxes were found on this line
        
    Returns:
        List of text items found at column positions without checkboxes
    """
    text_items = []
    
    # Labels that should NOT be captured as items
    KNOWN_LABELS = [
        'frequency', 'how much', 'how long', 'comments', 'additional comments',
        'tobacco', 'alcohol', 'drugs', 'social', 'pattern', 'conditions',
        'sleep pattern or conditions', 'how much how long'
    ]
    
    # Category headers that should be skipped
    CATEGORY_HEADERS = [
        'appearance', 'function', 'habits', 'previous comfort options',
        'pain/discomfort', 'periodontal', 'gum health', 'sleep pattern',
        'cancer', 'cardiovascular', 'endocrinology', 'musculoskeletal',
        'respiratory', 'gastrointestinal', 'neurological', 'hematologic',
        'medical allergies', 'women', 'viral infections', 'sleep pattern or conditions'
    ]
    
    for col_pos in column_positions:
        # Skip if there's a checkbox at or near this position
        has_checkbox = any(abs(cb_pos - col_pos) <= 5 for cb_pos in checkboxes_found)
        if has_checkbox:
            continue
        
        # Extract text starting from this column position
        # Look ahead to next column or 40 characters, whichever is shorter
        next_col_idx = column_positions.index(col_pos) + 1 if col_pos in column_positions else -1
        if next_col_idx > 0 and next_col_idx < len(column_positions):
            end_pos = column_positions[next_col_idx]
        else:
            end_pos = col_pos + 40
        
        # Make sure we don't go past end of line
        end_pos = min(end_pos, len(line))
        
        if col_pos < len(line):
            text = line[col_pos:end_pos].strip()
            
            # Validate this looks like an item, not a label or header
            if len(text) < 3:
                continue
            
            # Skip if it's just whitespace or punctuation
            if not re.search(r'[a-zA-Z]', text):
                continue
            
            # Skip known labels (exact match only)
            if text.lower() in KNOWN_LABELS:
                continue
            
            # Archivev13 Fix: Don't skip compound labels that contain known labels
            # Only skip if text is a single-word label
            # (e.g., skip "Tobacco" alone, but not "Alcohol Frequency")
            text_words = text.lower().split()
            if len(text_words) == 1 and any(label == text.lower() for label in KNOWN_LABELS):
                continue
            
            # Skip category headers
            if text.lower() in CATEGORY_HEADERS:
                continue
            
            # Skip if any category header is in text
            if any(header in text.lower() for header in CATEGORY_HEADERS if len(header) > 3):
                continue
            
            # Skip if it's "Pattern or Conditions" type text
            if re.match(r'^(Pattern|Conditions?|Health)\s*$', text, re.I):
                continue
            
            # Skip if text starts with lowercase (likely truncated)
            if text and text[0].islower():
                continue
            
            # Skip if it looks like a checkbox label remnant (e.g., "[ ]" without the bracket)
            if text.strip() in ['[', ']', '[ ]', '[]']:
                continue
            
            # Clean up the text (remove trailing punctuation, whitespace)
            text = text.rstrip('.:;,')
            
            # If it still has reasonable length, add it
            if len(text) >= 3 and len(text) <= 50:
                text_items.append(text)
    
    return text_items


def parse_multicolumn_checkbox_grid(lines: List[str], grid_info: dict, debug: bool = False) -> Optional['Question']:
    """
    Parse a multi-column checkbox grid into a single multi-select field.
    
    Extracts all checkbox items across all rows and columns, creating clean option names.
    Uses Archivev10 Fix 3 for enhanced column-aware text extraction.
    Uses Archivev11 Fix 2 for text-only item detection.
    """
    data_lines = grid_info['data_lines']
    column_positions = grid_info['column_positions']
    section = grid_info['section']
    
    # Collect all options
    all_options = []
    checkbox_pattern = re.compile(CHECKBOX_ANY)
    
    for line_idx in data_lines:
        line = lines[line_idx]
        
        # Find all checkboxes in this line
        checkboxes = list(checkbox_pattern.finditer(line))
        checkbox_positions = [cb.start() for cb in checkboxes]
        
        # Extract checkbox items
        for checkbox in checkboxes:
            cb_pos = checkbox.start()
            cb_end = checkbox.end()
            
            # Archivev10 Fix 3 + Archivev11 Fix 1: Use enhanced text extraction with column awareness
            item_text = extract_text_for_checkbox(line, cb_end, column_positions, cb_pos)
            
            # Skip if too short or looks like junk
            if len(item_text) < 2:
                continue
            
            # Skip common noise patterns
            if item_text.lower() in ['', 'n/a', 'none', 'other', 'and', 'or']:
                continue
            
            # Skip if it's just a category name (single capitalized word with no descriptors)
            words = item_text.split()
            if len(words) == 1 and item_text[0].isupper() and item_text.lower() in [
                'cancer', 'cardiovascular', 'endocrinology', 'musculoskeletal', 
                'respiratory', 'gastrointestinal', 'neurological', 'hematologic',
                'appearance', 'function', 'habits', 'social', 'women', 'type'
            ]:
                continue
            
            all_options.append((item_text, None))
        
        # Archivev11 Fix 2: Also look for text-only items at column positions
        # Only do this for lines that have fewer checkboxes than expected columns
        if len(checkboxes) < len(column_positions):
            text_only_items = extract_text_only_items_at_columns(line, column_positions, checkbox_positions)
            for item in text_only_items:
                if debug:
                    print(f"    [debug] text-only item at line {line_idx}: '{item}'")
                all_options.append((item, None))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_options = []
    for opt, checked in all_options:
        opt_lower = opt.lower()
        if opt_lower not in seen:
            seen.add(opt_lower)
            unique_options.append((opt, checked))
    
    # Create question if we have enough options
    if len(unique_options) >= 5:
        # Determine title based on section
        if section == "Medical History":
            title = "Medical History - Please mark any conditions that apply"
        elif section == "Dental History":
            title = "Dental History - Please mark any conditions that apply"
        else:
            title = "Please mark any that apply"
        
        # Look back a few lines for a better title (including the start line itself)
        if grid_info['start_line'] >= 0:
            # Check from 3 lines back up to and including the start line
            for i in range(max(0, grid_info['start_line'] - 3), grid_info['start_line'] + 1):
                if i >= len(lines):
                    break
                potential_title = collapse_spaced_caps(lines[i].strip())
                if debug:
                    print(f"    [debug] checking line {i} for title: '{potential_title[:60]}'")
                if potential_title and not re.search(CHECKBOX_ANY, potential_title):
                    # Check if it looks like a section title (has "please mark" or similar)
                    if re.search(r'\b(please mark|indicate|select|check|do you have)\b', potential_title, re.I):
                        if len(potential_title) < 150:
                            title = potential_title.rstrip(':?.')
                            
                            # Clean up extraneous text from title
                            # Remove "Patient Name (print)" and similar artifacts
                            title = re.sub(r'\s+Patient\s+Name\s*\([^)]+\)\s*$', '', title, flags=re.I)
                            title = re.sub(r'\s+Patient\s+Name\s*$', '', title, flags=re.I)
                            # Remove trailing numbers or codes
                            title = re.sub(r'\s+\d+\s*$', '', title)
                            # Trim again
                            title = title.rstrip(':?. ')
                            
                            # Archivev10 Fix: Infer section from title if it mentions Medical/Dental History
                            if 'medical history' in title.lower():
                                section = "Medical History"
                                if debug:
                                    print(f"    [debug] inferred section=Medical History from title")
                            elif 'dental history' in title.lower():
                                section = "Dental History"
                                if debug:
                                    print(f"    [debug] inferred section=Dental History from title")
                            break
        
        key = slugify(title) if len(title) < 50 else (
            "medical_conditions" if section == "Medical History" else "dental_conditions"
        )
        
        if debug:
            print(f"  [debug] multicolumn_grid -> '{title}' with {len(unique_options)} options from {len(data_lines)} lines")
        
        return Question(
            key,
            title,
            section,
            "dropdown",
            control={"options": [make_option(n, b) for n, b in unique_options], "multi": True}
        )
    
    return None

# ---------- Compound Yes/No

COMPOUND_YN_RE = re.compile(
    rf"(?P<prompt>[^[]*?)\s*{CHECKBOX_ANY}\s*(?:Yes|Y)\s*{CHECKBOX_ANY}\s*(?:No|N)\b",
    re.I,
)

def extract_compound_yn_prompts(line: str) -> List[str]:
    prompts = []
    for m in COMPOUND_YN_RE.finditer(normalize_glyphs_line(line)):
        p = collapse_spaced_caps(m.group("prompt")).strip(" :;-")
        if p:
            # Archivev19 Fix 2: Check if there's continuation text after the Yes/No checkboxes
            # Example: "...Actonel/ [ ] Yes [ ] No other medications containing bisphosphonates?"
            # We want to include the continuation text in the prompt
            match_end = m.end()
            remaining_text = line[match_end:].strip()
            
            # If there's text after Yes/No and it starts with lowercase or connecting words,
            # it's likely a continuation of the question
            if remaining_text and (
                re.match(r'^[a-z(]', remaining_text) or 
                re.match(r'^(and|or|if|but|then|with|of|for|to|other|additional)\b', remaining_text, re.I)
            ):
                # Remove any leading "and" or similar connectors that might cause awkwardness
                continuation = remaining_text
                # Append continuation to prompt
                p = p + " " + continuation
            
            prompts.append(p)
    if not prompts:
        m2 = YN_SIMPLE_RE.search(line)
        if m2:
            p = collapse_spaced_caps(m2.group("prompt")).strip(" :;-")
            if p: prompts.append(p)
    seen = set(); out=[]
    for p in prompts:
        if p not in seen:
            out.append(p); seen.add(p)
    return out

# ---------- Archivev8 Fix 1: Orphaned Checkbox Labels Detection

def has_orphaned_checkboxes(line: str) -> bool:
    """
    Detect if a line has multiple checkboxes but very little text (orphaned checkboxes).
    
    Example: "[ ]                       [ ]                               [ ]"
    
    Returns:
        True if checkboxes appear orphaned (labels likely on next line)
    """
    checkbox_count = len(re.findall(CHECKBOX_ANY, line))
    if checkbox_count < 2:
        return False
    
    # Remove checkboxes and see how much text remains
    text_without_checkboxes = re.sub(CHECKBOX_ANY, '', line).strip()
    
    # Split by whitespace to count words
    words = [w for w in text_without_checkboxes.split() if w.strip()]
    
    # Heuristic: If we have many checkboxes but very few words, labels are likely orphaned
    # Allow 1-2 short words per checkbox (like "Sickle Cell Disease" at the end)
    # But if most checkboxes have no adjacent text, they're orphaned
    if checkbox_count >= 3 and len(words) <= 2:
        return True
    
    # Alternative check: very sparse text density
    if len(text_without_checkboxes) < (checkbox_count * 5):
        return True
    
    return False


def extract_orphaned_labels(label_line: str) -> List[str]:
    """
    Extract labels from a line that appears to contain orphaned labels.
    
    A label line may have some checkboxes at the end, but should have
    labels without checkboxes at the beginning/middle.
    
    Returns:
        List of label strings
    """
    stripped = label_line.strip()
    if not stripped:
        return []
    
    # Split by 3+ spaces to get individual labels
    # This is a common pattern in grid layouts
    parts = re.split(r'\s{3,}', stripped)
    
    # Clean and filter labels
    cleaned_labels = []
    for part in parts:
        part = part.strip()
        # Skip if this part starts with a checkbox (it's properly paired)
        if re.match(CHECKBOX_ANY, part):
            # This part has a checkbox, extract the label after it
            label = re.sub(CHECKBOX_ANY, '', part).strip()
            if label and len(label) >= 2 and not label.isdigit():
                cleaned_labels.append(label)
        else:
            # This part has no checkbox - it's an orphaned label
            if len(part) >= 2 and not part.isdigit():
                cleaned_labels.append(part)
    
    return cleaned_labels


def associate_orphaned_labels_with_checkboxes(
    checkbox_line: str,
    label_line: str
) -> List[Tuple[str, Optional[bool]]]:
    """
    Associate orphaned labels with checkboxes based on occurrence order.
    
    Args:
        checkbox_line: Line with checkboxes but minimal text
        label_line: Next line with labels (may have some checkboxes at end)
    
    Returns:
        List of (label, checked_state) tuples
    """
    # Check if this actually looks like orphaned pattern
    if not has_orphaned_checkboxes(checkbox_line):
        return []
    
    labels = extract_orphaned_labels(label_line)
    if not labels:
        return []
    
    # Count checkboxes in the checkbox line
    checkbox_matches = list(re.finditer(CHECKBOX_ANY, checkbox_line))
    num_checkboxes = len(checkbox_matches)
    
    if num_checkboxes == 0:
        return []
    
    # Also check if checkbox line has any labels at the end
    # e.g., "[ ]  [ ]  [ ]  [ ]  [ ] Sickle Cell Disease"
    text_after_last_checkbox = checkbox_line[checkbox_matches[-1].end():].strip()
    checkbox_line_labels = []
    if text_after_last_checkbox and len(text_after_last_checkbox) > 3:
        # There's a label on the checkbox line itself
        checkbox_line_labels.append(text_after_last_checkbox)
    
    # If we have orphaned labels and checkboxes, associate them
    options = []
    
    # Add all labels from the label line
    for label in labels:
        options.append((label, None))
    
    # Then add any label from the checkbox line itself
    for label in checkbox_line_labels:
        options.append((label, None))
    
    return options

# ---------- Fix 2: Enhanced "If Yes" Detection

def extract_yn_with_followup(line: str) -> Tuple[Optional[str], bool]:
    """
    Extract Yes/No question and determine if it has a follow-up.
    
    Returns:
        (question_text, has_followup)
    
    Examples:
        "Are you pregnant? [ ] Yes [ ] No If yes, please explain"
        -> ("Are you pregnant?", True)
        
        "Do you smoke? [ ] Yes [ ] No"
        -> ("Do you smoke?", False)
    """
    # Try explicit "if yes" pattern first
    match = IF_YES_FOLLOWUP_RE.search(line)
    if match:
        question = match.group(1).strip()
        return (question, True)
    
    # Try inline "if yes" pattern
    match = IF_YES_INLINE_RE.search(line)
    if match:
        question = match.group(1).strip()
        return (question, True)
    
    # Try existing compound pattern
    prompts = extract_compound_yn_prompts(line)
    if prompts:
        # Check if line mentions "if yes" anywhere
        has_followup = bool(re.search(r'\bif\s+yes\b', line, re.I))
        return (prompts[0], has_followup)
    
    return (None, False)


def create_yn_question_with_followup(
    question_text: str,
    section: str,
    key_base: Optional[str] = None
) -> List['Question']:
    """
    Create a Yes/No radio question with a conditional follow-up input field.
    
    Args:
        question_text: The question text
        section: Current section
        key_base: Base key (if None, generated from question_text)
    
    Returns:
        List of 2 Questions: [radio_question, followup_input]
    """
    if not key_base:
        key_base = slugify(question_text)
    
    # Main Yes/No question
    main_q = Question(
        key_base,
        question_text,
        section,
        "radio",
        control={"options": [make_option("Yes", True), make_option("No", False)]}
    )
    
    # Follow-up input field
    followup_q = Question(
        f"{key_base}_explanation",
        "Please explain",
        section,
        "input",
        control={"input_type": "text", "hint": "Please provide details"}
    )
    
    # Add conditional - only show if main question is "yes"
    followup_q.conditional_on = [(key_base, "yes")]
    
    return [main_q, followup_q]

# ---------- Template dictionary (matching)

def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("date of birth", "dob").replace("birth date", "dob")
    s = s.replace("zip code", "zipcode").replace("e-mail", "email")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s

def _slug_key_norm(s: str) -> str:
    s = _norm_text(s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s: s = "q"
    if re.match(r"^\d", s): s = "q_" + s
    return s[:64]

def _token_set_ratio(a: str, b: str) -> float:
    A = set(_norm_text(a).split())
    B = set(_norm_text(b).split())
    if not A or not B: return 0.0
    inter = len(A & B); union = len(A | B)
    return inter / union if union else 0.0

EXTRA_ALIASES = {
    # General
    "birth date": "date_of_birth", "dob": "date_of_birth",
    "zip": "zipcode", "zip code": "zipcode",
    "cell phone": "mobile_phone", "mobile": "mobile_phone",
    "home phone": "home_phone", "e mail": "email", "email address": "email",
    "emergency contact": "emergency_name", "emergency contact name": "emergency_name",
    "emergency phone": "emergency_phone", "relationship to patient": "emergency_relationship",
    "drivers license": "drivers_license", "driver's license": "drivers_license",
    "drivers license #": "drivers_license",
    "person responsible for account": "responsible_party_name",
    "responsible party": "responsible_party_name",
    "occupation": "occupation",
    "spouse's name": "spouse_name", "name of spouse": "spouse_name",
    "date": "date_signed",
    "patient name": "full_name",
    # Parent/Guardian
    "parent ssn": "parent_ssn", "guardian ssn": "parent_ssn",
    "parent phone": "parent_phone", "guardian phone": "parent_phone",
    "parent name": "parent_name", "guardian name": "parent_name",
    # Insurance (avoid tiny 'id #' tokens)
    "insureds name": "insurance_holder", "insured name": "insurance_holder",
    "subscriber name": "insurance_holder", "member name": "insurance_holder",
    "policy holder name": "insurance_holder",
    "relationship to insured": "insurance_relationship",
    "relationship to subscriber": "insurance_relationship",
    "relationship to policy holder": "insurance_relationship",
    "relationship to member": "insurance_relationship",
    "subscriber id": "insurance_id_number", "subscriber #": "insurance_id_number",
    "policy #": "insurance_id_number", "member #": "insurance_id_number",
    "id number": "insurance_id_number", "id no": "insurance_id_number",
    "member id": "insurance_id_number", "policy id": "insurance_id_number",
    "identification number": "insurance_id_number",
    "group number": "insurance_group_number", "group #": "insurance_group_number",
    "grp #": "insurance_group_number", "plan group number": "insurance_group_number",
    "insurance company": "insurance_company",
    "insurance phone": "insurance_phone_number", "insurance phone #": "insurance_phone_number",
    "customer service phone": "insurance_phone_number", "cust svc phone": "insurance_phone_number",
    "address on card": "insurance_address_card", "insurance address": "insurance_address",
    # Referrals
    "who can we thank": "referred_by", "referred by": "referred_by",
}

# helper: detect conditions-like control to gate matching
_COND_TOKENS = {"diabetes","arthritis","rheumat","hepatitis","asthma","stroke","ulcer",
                "thyroid","cancer","anemia","glaucoma","osteoporosis","seizure","tb","tuberculosis",
                "hiv","aids","blood","pressure","heart","kidney","liver","bleeding","sinus",
                "smoke","chew","alcohol","drug","allergy","pregnan","anxiety","depression","pacemaker",
                "irregular","rregular"}

def _is_conditions_control(parsed_q: Optional[dict]) -> bool:
    if not parsed_q: return False
    if parsed_q.get("type") != "dropdown": return False
    ctrl = parsed_q.get("control") or {}
    if not ctrl.get("multi"): return False
    opts = ctrl.get("options") or []
    if len(opts) < 8: return False
    hits = 0
    for o in opts:
        w = re.sub(r"[^\w\s]","", (o.get("name") or "").lower())
        if any(t in w for t in _COND_TOKENS): hits += 1
    return hits >= 3

def _sanitize_words_set(s: str) -> Set[str]:
    return set(_sanitize_words(s).split())

def _alias_tokens_ok(alias_phrase: str, title: str) -> bool:
    alias_tokens = [t for t in _sanitize_words(alias_phrase).split() if len(t) >= 2]
    if not alias_tokens: return False
    tks = _sanitize_words_set(title)
    return all(tok in tks for tok in alias_tokens)

@dataclass
class FindResult:
    tpl: Optional[dict]
    scope: str
    reason: str
    score: float
    coverage: float
    best_key: Optional[str]

class TemplateCatalog:
    def __init__(self, by_key: Dict[str, dict], alias_map: Dict[str, str], titles_map: Dict[str, str]):
        merged_aliases = dict(alias_map)
        for a, k in EXTRA_ALIASES.items():
            merged_aliases.setdefault(_norm_text(a), k)
        self.by_key = by_key
        self.alias_map = merged_aliases
        self.titles_map = titles_map  # norm_title -> key

    @classmethod
    def from_path(cls, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        by_key: Dict[str, dict] = {}
        titles_map: Dict[str, str] = {}
        for cat, items in data.items():
            if cat.startswith("_") or cat == "aliases":
                continue
            if not isinstance(items, list):
                continue
            for obj in items:
                k = obj.get("key")
                if not k: 
                    continue
                by_key.setdefault(k, obj)
                t = obj.get("title") or ""
                titles_map.setdefault(_norm_text(t), k)
        alias_map: Dict[str, str] = {}
        for a, canonical in (data.get("aliases") or {}).items():
            alias_map[_norm_text(a)] = canonical
        return cls(by_key, alias_map, titles_map)

    def _strip_scope(self, key: str) -> Tuple[str, str]:
        if key.endswith(PRIMARY_SUFFIX):   return key[:-len(PRIMARY_SUFFIX)], PRIMARY_SUFFIX
        if key.endswith(SECONDARY_SUFFIX): return key[:-len(SECONDARY_SUFFIX)], SECONDARY_SUFFIX
        return key, ""

    def _options_overlap(self, parsed_q: dict, tpl_q: dict) -> float:
        if not parsed_q or not tpl_q: return 1.0
        p_opts = [o.get("name","") for o in (parsed_q.get("control",{}).get("options") or [])]
        t_opts = [o.get("name","") for o in (tpl_q.get("control",{}).get("options") or [])]
        if not p_opts or not t_opts: return 1.0
        P = {normalize_opt_name(x) for x in p_opts if x}
        T = {normalize_opt_name(x) for x in t_opts if x}
        if not P or not T: return 1.0
        inter = len(P & T); union = len(P | T)
        return inter/union if union else 1.0

    def _context_adjust(self, parsed_section: str, tpl_section: str) -> float:
        if not parsed_section or not tpl_section:
            return 0.0
        if parsed_section == tpl_section:
            return 0.05
        a = parsed_section.lower(); b = tpl_section.lower()
        if ("insurance" in a) ^ ("insurance" in b):
            return -0.10
        return 0.0

    def find(self, key: Optional[str], title: Optional[str], parsed_q: Optional[dict]=None) -> FindResult:
        scope = ""; reason = ""; score = 0.0; coverage = 0.0; best_key = None
        parsed_section = (parsed_q or {}).get("section","")
        is_conditions = _is_conditions_control(parsed_q)
        norm_title = _norm_text(title or "")
        long_title = len(norm_title) > 120 or len(norm_title.split()) > 15
        has_parent = bool(PARENT_RE.search(title or ""))

        # 1) Exact key (incl. scope base)
        if key:
            base, scope = self._strip_scope(key)
            if key in self.by_key:
                return FindResult(self.by_key[key], scope, "key_exact", 1.0, 1.0, key)
            if base in self.by_key:
                return FindResult(self.by_key[base], scope, "key_base_exact", 0.98, 1.0, base)

        if not title:
            return FindResult(None, "", "", 0.0, 0.0, None)

        # 2) Title exact (normalized)
        tk = self.titles_map.get(norm_title)
        if tk and tk in self.by_key:
            tpl = self.by_key[tk]
            ov = self._options_overlap(parsed_q, tpl)
            sc = 0.95*ov + self._context_adjust(parsed_section, tpl.get("section",""))
            return FindResult(tpl, "", "title_exact", sc, 1.0, tk)

        # 3) Alias exact
        alias_key = self.alias_map.get(norm_title)
        if alias_key and alias_key in self.by_key:
            # guard: if alias points to generic SSN but title contains parent terms, skip
            if alias_key == "ssn" and has_parent:
                return FindResult(None, "", "", 0.0, 0.0, None)
            tpl = self.by_key[alias_key]
            ov = self._options_overlap(parsed_q, tpl)
            sc = 0.96*ov + self._context_adjust(parsed_section, tpl.get("section",""))
            return FindResult(tpl, "", "alias_exact", sc, 1.0, alias_key)

        # Special: “How did you hear...” should never be hijacked by aliases/fuzzy
        if HEAR_ABOUT_RE.search(title or ""):
            return FindResult(None, "", "", 0.0, 0.0, None)

        # Long titles without options → block alias/fuzzy
        if long_title and parsed_q:
            has_opts = bool((parsed_q.get("control") or {}).get("options"))
            if not has_opts:
                return FindResult(None, "", "", 0.0, 0.0, None)

        # 4) Alias contains — token-boundary & context rules
        for alias_phrase, canonical in self.alias_map.items():
            # guard generics: don't allow generic ssn to match parent/guardian titles
            if canonical == "ssn" and has_parent:
                continue
            tpl = self.by_key.get(canonical)
            if not tpl:
                continue
            if not _alias_tokens_ok(alias_phrase, title or ""):
                continue
            if ("insurance" in (tpl.get("section","").lower() or "")) and ("insurance" not in (parsed_section or "").lower()):
                continue
            ov = self._options_overlap(parsed_q, tpl)
            sc = 0.93*ov + self._context_adjust(parsed_section, tpl.get("section",""))
            return FindResult(tpl, "", "alias_contains", sc, 1.0, canonical)

        # 5) Fuzzy (gated): never for conditions collectors
        if is_conditions:
            return FindResult(None, "", "", 0.0, 0.0, None)

        best_k, best_score, best_cov = None, 0.0, 0.0
        for cand_title_norm, cand_key in self.titles_map.items():
            jac = _token_set_ratio(norm_title, cand_title_norm)
            seq = SequenceMatcher(None, norm_title, cand_title_norm).ratio()
            cand_tokens = set(cand_title_norm.split()); title_tokens = set(norm_title.split())
            cov_needed = 0.8 if len(cand_tokens) > 3 else 0.65
            cov = len(cand_tokens & title_tokens) / max(1, len(cand_tokens))
            sc = 0.45 * jac + 0.45 * seq
            if cov >= cov_needed:
                if sc > best_score:
                    best_k, best_score, best_cov = cand_key, sc, cov

        if best_k:
            tpl = self.by_key[best_k]
            ov = self._options_overlap(parsed_q, tpl)
            sc = best_score + 0.10 * ov + self._context_adjust(parsed_section, tpl.get("section",""))
            if sc >= 0.85:
                return FindResult(tpl, "", "fuzzy", sc, best_cov, best_k)
            if sc >= 0.75:
                return FindResult(None, "", "near", sc, best_cov, best_k)

        return FindResult(None, "", "", 0.0, 0.0, None)

def merge_with_template(parsed_q: dict, template_q: dict, scope_suffix: str = "") -> dict:
    merged = copy.deepcopy(template_q)
    if parsed_q.get("title"):
        merged["title"] = parsed_q["title"]
    if parsed_q.get("section"):
        merged["section"] = parsed_q["section"]
    if "optional" in parsed_q:
        merged["optional"] = bool(parsed_q["optional"])
    out_key = merged.get("key") or parsed_q.get("key") or _slug_key_norm(parsed_q.get("title") or "")
    if scope_suffix and not out_key.endswith(scope_suffix):
        out_key = f"{out_key}{scope_suffix}"
    merged["key"] = out_key
    return merged

def _dedupe_keys_dicts(items: List[dict]) -> List[dict]:
    seen: Dict[str, int] = {}
    out: List[dict] = []
    for q in items:
        key = q.get("key") or "q"
        if q.get("type") == "signature":
            q["key"] = "signature"
            out.append(q); continue
        base = key
        if base not in seen:
            seen[base] = 1; q["key"] = base
        else:
            seen[base] += 1; q["key"] = f"{base}_{seen[base]}"
        out.append(q)
    return out

# ---------- Parsing

def _emit_parent_guardian_override(title: str, key: str, qtype: str, ctrl: Dict, section: str, insurance_scope: Optional[str], debug: bool):
    """Route parent/guardian-labeled fields to parent_* keys when appropriate."""
    if not PARENT_RE.search(title):
        return key, qtype, ctrl
    low = title.lower()
    if SSN_RE.search(low):
        if debug: print(f"  [debug] gate: parent_routing -> '{title}' -> parent_ssn")
        return "parent_ssn", "input", {"input_type":"ssn"}
    if PHONE_RE.search(low):
        if debug: print(f"  [debug] gate: parent_routing -> '{title}' -> parent_phone")
        return "parent_phone", "input", {"input_type":"phone"}
    if re.search(r"\b(name)\b", low):
        if debug: print(f"  [debug] gate: parent_routing -> '{title}' -> parent_name")
        return "parent_name", "input", {"input_type":"text"}
    return key, qtype, ctrl

def _insurance_scope_key(key: str, section: str, insurance_scope: Optional[str], title: str, debug: bool) -> str:
    """Attach __primary/__secondary to SSN/ID under insurance context; prefer patient-level elsewhere."""
    low = title.lower()
    if "insurance" in section.lower() or insurance_scope or re.search(r"\b(insured|subscriber|policy|member)\b", low):
        if key == "ssn" and insurance_scope:
            if debug: print(f"  [debug] gate: ssn_scoped -> '{title}' -> ssn{insurance_scope}")
            return f"ssn{insurance_scope}"
    return key

def _insurance_id_ssn_fanout(title: str) -> Optional[List[Tuple[str, str, Dict]]]:
    """Detect lines that contain both ID and SS tokens and fan-out to two controls."""
    t = _sanitize_words(title)
    has_id = bool(re.search(r"\b(id|member\s*id|policy\s*id|identification\s*number|subscriber\s*id|policy\s*#|member\s*#)\b", t))
    has_ss = bool(re.search(r"\b(ssn|social\s*security|ss#|soc\s*sec)\b", t))
    if has_id and has_ss:
        return [("insurance_id_number", "input", {"input_type":"text"}), ("ssn", "input", {"input_type":"ssn"})]
    return None

def parse_to_questions(text: str, debug: bool=False) -> List[Question]:
    lines = [normalize_glyphs_line(x) for x in scrub_headers_footers(text)]
    lines = coalesce_soft_wraps(lines)
    
    # Fix 1: Preprocess to split multi-question lines
    lines = preprocess_lines(lines)

    questions: List[Question] = []
    cur_section = "General"
    seen_signature = False
    insurance_scope: Optional[str] = None  # "__primary" / "__secondary"

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = collapse_spaced_caps(raw.strip())
        
        # Debug specific lines
        if debug and 'Appearance' in raw and 'Function' in raw:
            print(f"  [debug] PROCESSING line {i}: '{raw[:80]}' (section={cur_section})")
        
        if not line:
            i += 1; continue

        # Insurance anchoring
        if INSURANCE_BLOCK_RE.search(line):
            cur_section = "Insurance"; insurance_scope = None
        if INSURANCE_PRIMARY_RE.search(line):
            cur_section = "Insurance"; insurance_scope = "__primary"
        if INSURANCE_SECONDARY_RE.search(line):
            cur_section = "Insurance"; insurance_scope = "__secondary"

        # Archivev12 Fix: Check for special field patterns BEFORE heading detection
        # to prevent them from being treated as headings
        is_special_sex_field = any(p.search(line) for p in SEX_GENDER_PATTERNS)
        is_special_marital_field = any(p.search(line) for p in MARITAL_STATUS_PATTERNS)
        is_special_field = is_special_sex_field or is_special_marital_field
        
        # Fix 2: Section heading with multi-line header detection
        if not is_special_field and is_heading(line):
            # Look ahead to see if the next line is also a heading (multi-line header)
            potential_headers = [line]
            j = i + 1
            while j < len(lines) and j < i + 3:  # Look ahead up to 2 lines
                next_raw = lines[j]
                next_line = collapse_spaced_caps(next_raw.strip())
                if not next_line:
                    break
                # Archivev12 Fix: Don't include special fields in multi-line headers
                is_next_special_sex = any(p.search(next_line) for p in SEX_GENDER_PATTERNS)
                is_next_special_marital = any(p.search(next_line) for p in MARITAL_STATUS_PATTERNS)
                is_next_special = is_next_special_sex or is_next_special_marital
                
                if is_heading(next_line) and not is_next_special:
                    potential_headers.append(next_line)
                    j += 1
                else:
                    break
            
            # If we found multiple consecutive headings, combine them
            if len(potential_headers) > 1:
                combined = " ".join(potential_headers)
                new_section = normalize_section_name(combined)
                cur_section = new_section
                if debug:
                    print(f"  [debug] multi-line header: {potential_headers} -> {cur_section}")
                i = j  # Skip past all the header lines
                continue
            else:
                new_section = normalize_section_name(line)
                # Archivev10 Fix: Don't override Medical/Dental History sections with "General"
                # This prevents random headings within those sections from changing the section
                # But DO allow changing between specific sections
                if cur_section in {"Medical History", "Dental History"} and new_section == "General":
                    # Keep the current specific section, don't change to General
                    pass
                else:
                    cur_section = new_section
            
            low = line.lower()
            if "insurance" in low:
                if "primary" in low: insurance_scope = "__primary"
                elif "secondary" in low: insurance_scope = "__secondary"
                else: insurance_scope = None
            else:
                insurance_scope = None
            i += 1; continue
        
        # Archivev10 Fix 2: Enhanced category header detection
        # Check if this is a category header that precedes a multi-column grid
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            is_cat_header = is_category_header(line, next_line)
            if debug and is_cat_header:
                print(f"  [debug] is_category_header=True for line {i}: '{line[:60]}' (section={cur_section})")
            if is_cat_header:
                # Before skipping, check if this is actually a multi-column grid header
                # (e.g., "Appearance    Function    Habits")
                if cur_section in {"Medical History", "Dental History"}:
                    # Check if line has multiple column-like parts and next line has multiple checkboxes
                    parts = re.split(r'\s{5,}', line.strip())
                    next_checkboxes = len(list(re.finditer(CHECKBOX_ANY, next_line)))
                    
                    if debug:
                        print(f"  [debug] category header check: '{line[:60]}' - parts={len(parts)}, next_cb={next_checkboxes}")
                    
                    if len(parts) >= 3 and next_checkboxes >= 3:
                        # This is a multi-column grid header! Try to detect and parse the grid
                        if debug:
                            print(f"  [debug] attempting multicolumn_grid detection from category header line {i}")
                        multicolumn_grid = detect_multicolumn_checkbox_grid(lines, i, cur_section)
                        if multicolumn_grid:
                            grid_question = parse_multicolumn_checkbox_grid(lines, multicolumn_grid, debug)
                            if grid_question:
                                questions.append(grid_question)
                                i = max(multicolumn_grid['data_lines']) + 1
                                continue
                        elif debug:
                            print(f"  [debug] multicolumn_grid detection failed")
                
                # If not a grid header, skip as before
                if debug:
                    print(f"  [debug] skipping category header: '{line[:60]}'")
                i += 1
                continue

        # Archivev8 Fix 1: Check for orphaned checkbox pattern
        # Use raw line (not collapsed) to preserve spacing
        if has_orphaned_checkboxes(raw) and i + 1 < len(lines):
            next_line = lines[i + 1]
            orphaned_options = associate_orphaned_labels_with_checkboxes(raw, next_line)
            
            if orphaned_options and len(orphaned_options) >= 2:
                # Found orphaned labels! Create a medical conditions question
                # Look back for a title
                title = None
                if i > 0 and len(lines[i-1].strip()) < 100:
                    prev_stripped = collapse_spaced_caps(lines[i-1].strip())
                    if prev_stripped and not re.search(CHECKBOX_ANY, prev_stripped):
                        title = prev_stripped.rstrip(':?.')
                
                if not title:
                    title = "Medical Conditions"
                
                key = slugify(title)
                q = Question(
                    key,
                    title,
                    cur_section,
                    "dropdown",
                    control={"options": [make_option(name, checked) for name, checked in orphaned_options], "multi": True}
                )
                questions.append(q)
                
                if debug:
                    print(f"  [debug] gate: orphaned_labels -> '{title}' with {len(orphaned_options)} options")
                
                # Skip the next line since we consumed it
                i += 2
                continue

        # --- NEW: Medical History Multi-select block ---
        if cur_section in {"Medical History", "Dental History"}:
            if re.search(r"\b(have you ever had|do you have|are you taking)\b", line, re.I) and not extract_compound_yn_prompts(line):
                main_prompt_title = line
                options: List[Tuple[str, Optional[bool]]] = []
                k = i + 1
                while k < len(lines) and lines[k].strip() and not is_heading(lines[k]):
                    option_line = lines[k]
                    
                    # Fix 3: Skip category headers within medical blocks
                    if k + 1 < len(lines) and is_category_header(option_line, lines[k + 1]):
                        k += 1
                        continue
                    
                    # Archivev8 Fix 1: Check for orphaned checkboxes within the medical history block
                    if has_orphaned_checkboxes(lines[k]) and k + 1 < len(lines):
                        orphaned_opts = associate_orphaned_labels_with_checkboxes(lines[k], lines[k + 1])
                        if orphaned_opts:
                            options.extend(orphaned_opts)
                            k += 2  # Skip both the checkbox line and label line
                            continue
                    
                    # Try compound Y/N prompts first (e.g., "Question? [ ] Yes [ ] No")
                    prompts = extract_compound_yn_prompts(option_line)
                    if prompts:
                        for p in prompts:
                            options.append((p, None))
                    else:
                        # Try inline options (e.g., "[ ] Option1 [ ] Option2")
                        inline_opts = options_from_inline_line(option_line)
                        if inline_opts:
                            options.extend(inline_opts)
                    
                    k += 1

                if len(options) >= 3: # Threshold to be considered a conditions block
                    control = {"options": [make_option(n, b) for n,b in options], "multi": True}
                    key = "medical_conditions" if cur_section == "Medical History" else "dental_conditions"
                    questions.append(Question(key, main_prompt_title, cur_section, "dropdown", control=control))
                    i = k
                    continue

        # Drop witness
        if WITNESS_RE.search(line):
            i += 1; continue

        # Signature (+ optional date)
        if "signature" in line.lower():
            if not seen_signature:
                questions.append(Question("signature", line.rstrip(":"), "Signature", "signature"))
                seen_signature = True
                # Adjacent Date (normalized title)
                if i + 1 < len(lines) and DATE_LABEL_RE.search(lines[i+1]):
                    title_dt = "Date Signed"
                    questions.append(Question(slugify(title_dt), title_dt, "Signature", "date", control={"input_type":"any"}))
                    i += 1
            i += 1; continue

        # Archivev10 Fix 1: Try multi-column checkbox grid detection first
        # This handles grids with 3+ checkboxes per line (common in medical/dental forms)
        if cur_section in {"Medical History", "Dental History"}:
            # Check if this line or upcoming lines form a multi-column checkbox grid
            multicolumn_grid = detect_multicolumn_checkbox_grid(lines, i, cur_section)
            if multicolumn_grid:
                grid_question = parse_multicolumn_checkbox_grid(lines, multicolumn_grid, debug)
                if grid_question:
                    questions.append(grid_question)
                    # Skip past the grid
                    i = max(multicolumn_grid['data_lines']) + 1
                    continue
            
            # Also check if this is a category header line followed by a grid
            # (e.g., "Appearance    Function    Habits    Previous Comfort Options")
            if not re.search(CHECKBOX_ANY, line):
                # Check if it looks like multiple column headers
                parts = re.split(r'\s{5,}', line.strip())
                if len(parts) >= 3 and all(len(p.split()) <= 4 for p in parts):
                    # Might be category headers, check if next line has multiple checkboxes
                    if i + 1 < len(lines):
                        next_checkboxes = len(list(re.finditer(CHECKBOX_ANY, lines[i + 1])))
                        if next_checkboxes >= 3:
                            # This is a category header line before a grid!
                            multicolumn_grid = detect_multicolumn_checkbox_grid(lines, i, cur_section)
                            if multicolumn_grid:
                                grid_question = parse_multicolumn_checkbox_grid(lines, multicolumn_grid, debug)
                                if grid_question:
                                    questions.append(grid_question)
                                    i = max(multicolumn_grid['data_lines']) + 1
                                    continue
        
        # Fix 4: Enhanced Table/Grid Detection - try multi-row table first
        table_info = detect_table_layout(lines, i)
        if table_info:
            # Parse entire table at once
            table_questions = parse_table_to_questions(lines, table_info, cur_section)
            questions.extend(table_questions)
            
            # Skip past the table
            i = max(table_info['data_lines']) + 1
            continue

        # Grid (existing logic for simpler cases)
        hdr_cols = looks_like_grid_header(line)
        if hdr_cols:
            ncols = len(hdr_cols)
            col_options: List[List[Tuple[str, Optional[bool]]]] = [[] for _ in range(ncols)]
            k = i + 1
            while k < len(lines) and lines[k].strip():
                row = collapse_spaced_caps(lines[k])
                if is_heading(row): break
                cells = chunk_by_columns(row, ncols)
                for cidx, cell in enumerate(cells):
                    if not cell.strip(): continue
                    opts=[]
                    if BULLET_RE.match(cell): 
                        o = option_from_bullet_line(cell); 
                        if o: opts.append(o)
                    else:
                        opts += options_from_inline_line(cell)
                    if not opts and ("," in cell or "/" in cell or ";" in cell):
                        for tok in re.split(r"[,/;]", cell):
                            tok = clean_token(tok)
                            if tok: opts.append((tok, None))
                    col_options[cidx].extend(opts)
                k += 1
            for cidx, col in enumerate(hdr_cols):
                opts = col_options[cidx]
                if not opts: continue
                options = [make_option(n,b) for (n,b) in opts]
                control = {"options": options, "multi": True}
                qkey = slugify(col)
                if insurance_scope and "insurance" in cur_section.lower():
                    qkey = f"{qkey}{insurance_scope}"
                questions.append(Question(qkey, col, cur_section, "dropdown", control=control))
            i = k; continue

        # --- Insurance ID/SSN fan-out (before other logic) ---
        fan = _insurance_id_ssn_fanout(line)
        if fan:
            for (kname, ktype, kctrl) in fan:
                qkey = _insurance_scope_key(kname, cur_section, insurance_scope, line, debug)
                questions.append(Question(qkey, CANON_LABELS.get(kname, kname.replace("_"," ").title()), "Insurance" if "insurance" in cur_section else cur_section, ktype, control=kctrl))
            if debug: print(f"  [debug] gate: insurance_fanout -> '{line}' -> ['insurance_id_number','ssn(+scope)']")
            i += 1; continue

        # Archivev15 Fix 1: Check for field label with inline checkbox option
        # Pattern: "Field Label:    <spaces>    [ ] Option text"
        # This must be checked BEFORE try_split_known_labels which incorrectly splits these lines
        # Use raw line (not collapsed) to preserve spacing
        field_checkbox_split = detect_field_with_inline_checkbox(raw)
        if field_checkbox_split:
            field_label, checkbox_option = field_checkbox_split
            
            # Create the main field (e.g., "Cell Phone")
            field_title = field_label.strip()
            field_key = slugify(field_title)
            field_itype = classify_input_type(field_title)
            
            questions.append(Question(
                field_key,
                field_title,
                cur_section,
                "input",
                control={"input_type": field_itype or "text"}
            ))
            
            # Create the checkbox field (e.g., "Yes, send me Text Message alerts")
            checkbox_title = checkbox_option.strip()
            # Use a prefix to ensure unique key that won't conflict with main field
            checkbox_key = f"opt_in_{slugify(checkbox_title)}"
            
            questions.append(Question(
                checkbox_key,
                checkbox_title,
                cur_section,
                "radio",
                control={"options": [make_option("Yes", True), make_option("No", False)]}
            ))
            
            if debug:
                print(f"  [debug] gate: field_with_inline_checkbox -> '{field_title}' + '{checkbox_title}'")
            
            i += 1
            continue

        # --- Composite / multi-label fan-out ---
        composite_labels = try_split_known_labels(line)
        if composite_labels:
            for ttl in composite_labels:
                if ttl.lower().startswith("state"):
                    qtype, ctrl = "states", {}
                elif "date" in ttl.lower() or "birth" in ttl.lower() or "dob" in ttl.lower():
                    qtype, ctrl = "date", {"input_type": classify_date_input(ttl)}
                else:
                    itype = classify_input_type(ttl)
                    qtype, ctrl = "input", ({"input_type": itype} if itype else {})
                key = slugify(ttl)
                # parent/guardian override
                key, qtype, ctrl = _emit_parent_guardian_override(ttl, key, qtype, ctrl, cur_section, insurance_scope, debug)
                # insurance scoping for SSN
                key = _insurance_scope_key(key, cur_section, insurance_scope, ttl, debug)
                if insurance_scope and "insurance" in cur_section.lower() and not key.endswith((PRIMARY_SUFFIX, SECONDARY_SUFFIX)) and key in {"ssn","insurance_id_number"}:
                    key = f"{key}{insurance_scope}"
                questions.append(Question(key, ttl, cur_section, qtype, control=ctrl))
            i += 1; continue

        # Single-checkbox → boolean radio (e.g., Responsible Party …)
        mbox = SINGLE_BOX_RE.match(line)
        if mbox and RESP_PARTY_RE.search(line):
            title = "Responsible party is someone other than patient?"
            key = slugify(title)
            if insurance_scope and "insurance" in cur_section.lower():
                key = f"{key}{insurance_scope}"
            control = {"options":[make_option("Yes",True), make_option("No",False)]}
            questions.append(Question(key, title, "Insurance", "radio", control=control))
            if debug: print(f"  [debug] gate: bool_single_box -> '{line}' -> radio Yes/No")
            i += 1; continue

        # Fix 4: Check for orphaned checkboxes (enhanced)
        if i + 1 < len(lines):
            orphaned_opts = extract_orphaned_checkboxes_and_labels(line, lines[i+1])
            if orphaned_opts:
                # Check if in medical/dental history section for condition collection
                is_condition_block = cur_section in {"Medical History", "Dental History"}
                
                # Try to find a better title from previous line
                title = "Please select all that apply:"
                if i > 0:
                    prev_line = collapse_spaced_caps(lines[i-1].strip())
                    if prev_line and not re.search(CHECKBOX_ANY, prev_line) and not is_heading(prev_line):
                        # Use previous line as title if it looks like a question
                        if prev_line.endswith('?') or prev_line.endswith(':') or len(prev_line) > 20:
                            title = prev_line.rstrip(':').strip()
                
                if is_condition_block:
                    # Add to a medical conditions dropdown
                    control = {"options": [make_option(n, b) for n, b in orphaned_opts], "multi": True}
                    key = "medical_conditions" if cur_section == "Medical History" else "dental_conditions"
                    questions.append(Question(key, title, cur_section, "dropdown", control=control))
                else:
                    # Create standalone dropdown
                    key = slugify(title)
                    control = {"options": [make_option(n, b) for n, b in orphaned_opts], "multi": True}
                    questions.append(Question(key, title, cur_section, "dropdown", control=control))
                
                if debug: print(f"  [debug] gate: orphaned_checkboxes -> found {len(orphaned_opts)} options")
                i += 2  # Skip both current and next line
                continue

        # Bullet -> terms (explanatory lists)
        if line.lstrip().startswith(("•","·")):
            terms_lines = [line]; k = i+1
            while k < len(lines) and lines[k].strip() and not is_heading(lines[k]):
                if lines[k].lstrip().startswith(("•","·")):
                    terms_lines.append(lines[k])
                else:
                    terms_lines[-1] += " " + lines[k].strip()
                k += 1
            txt_terms = " ".join(collapse_spaced_caps(x).strip() for x in terms_lines)
            questions.append(Question(
                slugify("terms_"+(terms_lines[0][:20] if terms_lines else "list")),
                "Terms", "Consent", "terms",
                control={"agree_text":"I have read and agree to the terms.","html_text":txt_terms}
            ))
            i = k; continue

        # Special: “Please share the following dates”
        if re.search(r"please\s+share\s+the\s+following\s+dates", line, re.I):
            harvested = " ".join(collapse_spaced_caps(lines[j].strip()) for j in range(i, min(i+3,len(lines))))
            for lbl in ["Cleaning","Cancer Screening","X-Rays","X Rays","Xray"]:
                if re.search(lbl.replace(" ", r"\s*"), harvested, re.I):
                    questions.append(Question(slugify(lbl), lbl, cur_section, "date", control={"input_type":"any"}))
            i += 1; continue

        # Robust 1..10 detection (pain scale etc.)
        digits = [int(x) for x in re.findall(r"\b\d+\b", line)]
        if digits and digits == list(range(1, 11)):
            title = line
            options = [{"name": str(n), "value": n} for n in range(1,11)]
            questions.append(Question(slugify(title), title, cur_section, "radio", control={"options": options}))
            i += 1; continue

        # Comms consent
        if re.search(r"\bsend me\b.*\btext\b", line, re.I):
            questions.append(Question("consent_text_alerts","Consent to Text Message alerts",cur_section,"radio",
                                      control={"options":[make_option("Yes",True),make_option("No",False)]}))
            i += 1; continue
        if re.search(r"\bsend me\b.*\bemail\b", line, re.I):
            questions.append(Question("consent_email_alerts","Consent to Email alerts",cur_section,"radio",
                                      control={"options":[make_option("Yes",True),make_option("No",False)]}))
            i += 1; continue

        # Fix 2: Enhanced "If Yes" Detection - try new pattern first
        question_text, has_followup = extract_yn_with_followup(line)
        if question_text and has_followup:
            # Create both question and follow-up using the new helper
            new_questions = create_yn_question_with_followup(question_text, cur_section)
            questions.extend(new_questions)
            if debug: print(f"  [debug] gate: yn_with_followup -> '{question_text}' + explanation field")
            i += 1
            continue
        
        # Compound Yes/No on one line (existing logic)
        compound_prompts = extract_compound_yn_prompts(line)
        emitted_compound = False
        if compound_prompts:
            for ptxt in compound_prompts:
                key = slugify(ptxt)
                if insurance_scope and "insurance" in cur_section.lower():
                    key = f"{key}{insurance_scope}"
                control = {"options":[make_option("Yes",True),make_option("No",False)]}
                
                # Fix 2: Enhanced follow-up field detection
                create_follow_up = False
                if re.search(IF_GUIDANCE_RE, line):
                    control["extra"] = {"type":"Input","hint":"If yes, please explain"}
                    create_follow_up = True
                
                # Check same line for "if yes, please explain"
                if re.search(r'\b(if\s+yes|please\s+explain|if\s+so|explain\s+below)\b', line, re.I):
                    create_follow_up = True
                
                # Check next line for follow-up indicators
                if i + 1 < len(lines):
                    next_line = collapse_spaced_caps(lines[i+1].strip())
                    if re.search(r'^\s*(if\s+yes|please\s+explain|explain|comment|list|details?)', next_line, re.I):
                        create_follow_up = True
                
                # Create follow-up field if needed with conditional
                if create_follow_up:
                    follow_up_key = f"{key}_explanation"
                    # Check if not already created
                    if not any(q.key == follow_up_key for q in questions):
                        follow_up_q = Question(
                            follow_up_key,
                            "Please explain",
                            cur_section,
                            "input",
                            control={"input_type": "text", "hint": "Please provide details"}
                        )
                        # Add conditional to only show if Yes
                        follow_up_q.conditional_on = [(key, "yes")]
                        questions.append(follow_up_q)
                
                questions.append(Question(key, ptxt, cur_section, "radio", control=control))
                emitted_compound = True
            if re.search(r"name\s+of\s+school", line, re.I):
                questions.append(Question("name_of_school","Name of School",cur_section,"input",control={"input_type":"text"}))
        if emitted_compound:
            i += 1; continue

        # Archivev12 Fix 3: Special handling for Sex/Gender with text options (M or F)
        sex_match = re.search(r'\b(sex|gender)\s*[:\-]?\s*(?:M\s*or\s*F|M/F|Male/Female|Mor\s*F)', line, re.I)
        if sex_match:
            key = "sex"
            title = sex_match.group(1).title()
            control = {
                "options": [
                    {"name": "Male", "value": "male"},
                    {"name": "Female", "value": "female"},
                    {"name": "Other", "value": "other"},
                    {"name": "Prefer not to self identify", "value": "not_say"}
                ]
            }
            questions.append(Question(key, title, cur_section, "radio", control=control))
            i += 1
            continue
        
        # Archivev12 Fix 4: Special handling for "Please Circle One:" marital status
        marital_match = re.search(r'(?:please\s+)?circle\s+one\s*:?\s*(.*?)$', line, re.I)
        if marital_match:
            # Extract options from the rest of the line
            options_text = marital_match.group(1).strip()
            # Common marital status options
            marital_options = []
            for opt in ['Single', 'Married', 'Divorced', 'Separated', 'Widowed', 'Widow']:
                if opt.lower() in options_text.lower():
                    if opt == 'Widow':
                        opt = 'Widowed'  # Normalize
                    if opt not in [o['name'] for o in marital_options]:
                        marital_options.append({"name": opt, "value": opt.lower()})
            
            if marital_options:
                # Add standard options if not present
                if not any(o['name'] == 'Prefer not to say' for o in marital_options):
                    marital_options.append({"name": "Prefer not to say", "value": "not say"})
                
                control = {"options": marital_options}
                questions.append(Question("marital_status", "Marital Status", cur_section, "radio", control=control))
                i += 1
                continue


        # Option harvesting for a single prompt (incl. “hear about us”)
        opts_inline = options_from_inline_line(line)
        opts_block: List[Tuple[str, Optional[bool]]] = []
        j = i + 1
        # collect bullets immediately below
        while j < len(lines):
            cand = collapse_spaced_caps(lines[j])
            if not cand.strip(): break
            o = option_from_bullet_line(cand)
            if o: opts_block.append(o); j += 1; continue
            # NEW: Also collect inline checkbox options from following lines (Fix 1 enhancement)
            inline_opts = options_from_inline_line(cand)
            if inline_opts:  # Any checkboxes found
                if len(inline_opts) >= 2:  # Multiple options on this line - definitely collect
                    opts_block.extend(inline_opts)
                    j += 1
                    continue
                elif len(inline_opts) == 1 and opts_block:  # Single option but we already have options - continue collecting
                    opts_block.extend(inline_opts)
                    j += 1
                    continue
            # No valid options found on this line - check if it's a continuation or break
            if not re.search(CHECKBOX_ANY, cand):  # No checkboxes at all
                break
            # Has checkboxes but no valid labels - might be orphaned checkboxes, continue
            j += 1
            continue

        title = line.rstrip(":").strip()
        is_hear = bool(HEAR_ABOUT_RE.search(title))
        
        # Fix 1: If current line starts with checkbox and we have opts_block, look back for title
        if opts_block and re.match(r'^\s*' + CHECKBOX_ANY, line):
            if i > 0:
                prev_line = collapse_spaced_caps(lines[i-1].strip())
                if prev_line and not re.search(CHECKBOX_ANY, prev_line) and not is_heading(prev_line):
                    title = prev_line.rstrip(':').strip()
                    is_hear = bool(HEAR_ABOUT_RE.search(title))

        # “How did you hear...” — aggressively collect same line + next two non-heading lines
        if is_hear and not (opts_inline or opts_block):
            # Fix 1: Check if next line has inline checkboxes - if so, skip and let next line handle it
            # Fix 1: Check if next line(s) have inline checkboxes - skip blanks
            check_idx = i + 1
            while check_idx < len(lines) and not lines[check_idx].strip():
                check_idx += 1  # Skip blank lines
            if check_idx < len(lines):
                next_line_check = lines[check_idx].strip()
                if next_line_check and re.search(CHECKBOX_ANY, next_line_check):
                    next_opts_check = options_from_inline_line(next_line_check)
                    if len(next_opts_check) >= 2:
                        # Next line will handle this, skip for now
                        i += 1
                        continue
            
            # same line split
            for tok in re.split(r"[,/;]", title):
                tok = clean_token(tok)
                if tok and tok.lower() not in {"how did you hear about us", "referred by"}:
                    opts_inline.append((tok, None))
            k = i + 1
            extra_lines = 0
            while k < len(lines) and extra_lines < 2:
                cand = collapse_spaced_caps(lines[k]).strip()
                if not cand or is_heading(cand): break
                ob = option_from_bullet_line(cand)
                if ob:
                    opts_block.append(ob); k += 1; continue
                for tok in re.split(r"[,/;]", cand):
                    tok = clean_token(tok)
                    if tok: opts_block.append((tok, None))
                k += 1; extra_lines += 1
            j = max(j, k)

        # Simple labeled fields
        if STATE_LABEL_RE.match(title):
            key = slugify(title or "state")
            if insurance_scope and "insurance" in cur_section.lower(): key = f"{key}{insurance_scope}"
            questions.append(Question(key, title or "State", cur_section, "states", control={}))
            i += 1; continue

        if DATE_LABEL_RE.search(title):
            key = slugify(title or "date")
            if insurance_scope and "insurance" in cur_section.lower(): key = f"{key}{insurance_scope}"
            # Archivev18 Fix 1: Clean date field titles to remove template artifacts
            clean_title = clean_field_title(title) if title else "Date"
            questions.append(Question(key, clean_title, cur_section, "date",
                                      control={"input_type": classify_date_input(title)}))
            i += 1; continue

        collected = opts_inline or opts_block
        if collected:
            # Fix 1: Clean title if it has inline checkboxes or concatenated options
            clean_title = title
            
            # If we have inline options (especially multiple ones), check if title needs cleaning
            if opts_inline and len(opts_inline) >= 2:
                # Archivev19 Fix 3: Only look back if current line doesn't have a clear label before checkboxes
                # Extract text before first checkbox to see if we have a meaningful title
                extracted_title = extract_title_from_inline_checkboxes(line)
                
                # If we extracted a meaningful title from the current line, use it
                if extracted_title and len(extracted_title) >= 5 and ':' in line[:line.find('[') if '[' in line else len(line)]:
                    # Current line has "Label: [ ] options" format - use the extracted label
                    clean_title = extracted_title
                else:
                    # Title likely includes the options. Look back for a better title (skip blank lines).
                    lookback_idx = i - 1
                    while lookback_idx >= 0 and not lines[lookback_idx].strip():
                        lookback_idx -= 1  # Skip blank lines
                    if lookback_idx >= 0:
                        prev_line = collapse_spaced_caps(lines[lookback_idx].strip())
                        if prev_line and not re.search(CHECKBOX_ANY, prev_line) and not is_heading(prev_line):
                            # Use previous line if it looks like a question/prompt
                            if len(prev_line) >= 5:
                                clean_title = prev_line.rstrip(':').strip()
            
            # If title still has checkbox markers, try to extract clean text
            if re.search(CHECKBOX_ANY, clean_title):
                extracted = extract_title_from_inline_checkboxes(clean_title)
                # Archivev12 Fix: Allow short field names like "Sex", "Age"
                if extracted and len(extracted) >= 2:
                    clean_title = extracted
                else:
                    # Couldn't extract - fallback to looking back or generic title
                    if i > 0 and clean_title == title:  # Haven't already looked back
                        prev_line = collapse_spaced_caps(lines[i-1].strip())
                        if prev_line and not re.search(CHECKBOX_ANY, prev_line) and not is_heading(prev_line):
                            clean_title = prev_line.rstrip(':').strip()
                        else:
                            clean_title = "Please select"
                    else:
                        clean_title = "Please select"
            
            lowset = {n.lower() for (n,_b) in collected}
            if {"yes","no"} <= lowset or lowset <= YESNO_SET:
                control = {"options":[make_option("Yes",True), make_option("No",False)]}
                if re.search(IF_GUIDANCE_RE, clean_title):
                    control["extra"] = {"type":"Input","hint":"If yes, please explain"}
                    # --- Fix 2: Add separate input for "if yes" (enhanced) ---
                    if j < len(lines):
                        next_line = collapse_spaced_caps(lines[j].strip())
                        if re.search(r"\b(list|explain|if so|name of)\b", next_line, re.I):
                            follow_up_title = f"{clean_title} - Details"
                            follow_up_key = slugify(follow_up_title)
                            questions.append(Question(follow_up_key, follow_up_title, cur_section, "input", control={"input_type": "text"}))
                key = slugify(clean_title)
                if insurance_scope and "insurance" in cur_section.lower(): key = f"{key}{insurance_scope}"
                questions.append(Question(key, clean_field_title(clean_title), cur_section, "radio", control=control))
            else:
                make_radio = bool(SINGLE_SELECT_TITLES_RE.search(clean_title))
                options = [make_option(n, b) for (n,b) in collected]
                if not options and ("," in clean_title or "/" in clean_title or ";" in clean_title):
                    for tok in re.split(r"[,/;]", clean_title):
                        tok = clean_token(tok)
                        if tok: options.append(make_option(tok, None))
                control: Dict = {"options": options}
                if not make_radio:
                    control["multi"] = True
                if is_hear:
                    control["extra"] = {"type":"Input","hint":"Other (please specify)"}
                    if (REFERRED_BY_RE.search(clean_title) or (j < len(lines) and REFERRED_BY_RE.search(lines[j]))):
                        questions.append(Question("referred_by","Referred by",cur_section,"input",control={"input_type":"text"}))
                key = slugify(clean_title)
                if insurance_scope and "insurance" in cur_section.lower(): key = f"{key}{insurance_scope}"
                qtype = "radio" if make_radio else "dropdown"
                questions.append(Question(key, clean_field_title(clean_title), cur_section, qtype, control=control))
            i = j if not opts_inline else i + 1
            continue

        # Long paragraph → terms
        para = [lines[i]]; k = i+1
        while k < len(lines) and lines[k].strip() and not BULLET_RE.match(lines[k].strip()):
            if is_heading(lines[k]): break
            para.append(lines[k]); k += 1
        joined = " ".join(collapse_spaced_caps(x).strip() for x in para)
        if len(joined) > 250 and joined.count(".") >= 2:
            chunks: List[List[str]] = []; cur: List[str] = []
            for s in para:
                if is_heading(s.strip()) and cur:
                    chunks.append(cur); cur=[s]
                else:
                    cur.append(s)
            if cur: chunks.append(cur)
            for idx2, chunk in enumerate(chunks):
                t = " ".join(collapse_spaced_caps(x).strip() for x in chunk).strip()
                if not t: continue
                questions.append(Question(
                    slugify((chunk[0].strip() if is_heading(chunk[0].strip()) else (title or "terms")) + (f"_{idx2+1}" if idx2 else "")),
                    (collapse_spaced_caps(chunk[0].strip().rstrip(":")) if is_heading(chunk[0].strip()) else "Terms"),
                    "Consent",
                    "terms",
                    control={"agree_text":"I have read and agree to the terms.","html_text":t},
                ))
            i = k; continue

        # Default: input
        # Fix 1: Skip if next line has inline options that will use this as title
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and re.search(CHECKBOX_ANY, next_line):
                # Check if next line has inline options
                next_opts = options_from_inline_line(next_line)
                if len(next_opts) >= 2:
                    # Next line will create a field using this line as title, so skip
                    i += 1
                    continue
        
        itype = classify_input_type(title)
        key = slugify(title)
        # parent/guardian routing
        key, qtype, ctrl = _emit_parent_guardian_override(title, key, "input", {"input_type": itype} if itype else {}, cur_section, insurance_scope, debug)
        # employer patient-first: only map to insurance_employer if insurance context tokens are present
        if key == "employer":
            if "insurance" in cur_section.lower() or re.search(r"\b(insured|subscriber|policy|member|insurance)\b", title.lower()):
                pass  # allow later dictionary to map to insurance_employer if template title says so
            else:
                if debug: print(f"  [debug] gate: employer_patient_first -> '{title}' -> employer (patient)")
        key = _insurance_scope_key(key, cur_section, insurance_scope, title, debug)
        if insurance_scope and "insurance" in cur_section.lower() and not key.endswith((PRIMARY_SUFFIX, SECONDARY_SUFFIX)) and key in {"ssn","insurance_id_number"}:
            key = f"{key}{insurance_scope}"
        questions.append(Question(key, title, cur_section, qtype, control=ctrl))
        i += 1

    # Final sanitation & signature rule
    def is_instructional_text(text: str) -> bool:
        """
        Archivev18 Fix 2: Detect instructional/paragraph text that shouldn't be captured as fields.
        Returns True if the text is likely instructions/guidance rather than a field label.
        """
        text_lower = text.lower().strip()
        
        # Check for common instructional phrases
        instructional_phrases = [
            "thank you for",
            "medication that you may be taking",
            "could have an important",
            "interrelationship with",
            "health problems that you may have",
            "please read",
            "i understand that providing incorrect",
            "to the best of my knowledge",
            "the questions on this form have been",
            "accurately answered",
            "providing incorrect information can be",
            "although dental professionals",
            "your mouth is a part of",
        ]
        
        if any(phrase in text_lower for phrase in instructional_phrases):
            return True
        
        # If text is very long (>150 chars) and contains connecting phrases, likely instructional
        if len(text) > 150:
            connecting_phrases = [" that you ", " which ", " could ", " should ", " would "]
            if any(phrase in text_lower for phrase in connecting_phrases):
                return True
        
        return False
    
    def is_junk(q: Question) -> bool:
        t = q.title.strip().lower()
        return (q.key == "q" or len(q.title.strip()) <= 1 or
                t in {"<<<", ">>>", "-", "—", "continued on back side"} or
                is_instructional_text(q.title))
    questions = [q for q in questions if not is_junk(q)]
    questions = [q for q in questions if not WITNESS_RE.search(q.title)]

    sig_idxs = [idx for idx,q in enumerate(questions) if q.type=="signature"]
    if not sig_idxs:
        questions.append(Question("signature","Signature","Signature","signature"))
    elif len(sig_idxs) > 1:
        for idx in reversed(sig_idxs[1:]): questions.pop(idx)

    return questions

# ---------- Validation / normalization

def ensure_control_present(q: Question) -> None:
    if q.control is None: q.control = {}
    if q.type == "radio":    q.control.setdefault("options", [])
    if q.type == "dropdown": q.control.setdefault("options", []); q.control.setdefault("multi", True)
    if q.type == "date":     q.control.setdefault("input_type", "any")
    if q.type == "input":    q.control.setdefault("input_type", "text")
    if q.type == "terms":
        q.control.setdefault("agree_text","I have read and agree to the terms.")
        q.control.setdefault("html_text","")

def fill_missing_option_values(q: Question) -> None:
    if q.type not in ("radio","dropdown"): return
    opts = q.control.get("options") or []
    fixed=[]
    for opt in opts:
        name = (opt.get("name") or "").strip() or "Option"
        val  = opt.get("value")
        if val in (None, ""):
            vlow = name.strip().lower()
            if vlow == "yes": val = True
            elif vlow == "no": val = False
            else: val = slugify(name, 80)
        fixed.append({"name": name, "value": val})
    q.control["options"] = fixed

def _semantic_dedupe(payload: List[dict]) -> List[dict]:
    """
    Remove duplicate simple inputs that are identical semantically (same title/section/type/input_type).
    
    Archivev8 Fix 3: Skip deduplication for conditional fields (they can have same title).
    """
    seen: Set[Tuple[str,str,str,str]] = set()
    out: List[dict] = []
    for q in payload:
        if q.get("type") == "input":
            # Archivev8 Fix 3: Don't dedupe conditional fields
            if q.get("if") or "conditional" in q.get("key", "").lower() or "_explanation" in q.get("key", "").lower():
                out.append(q)
                continue
            
            itype = (q.get("control") or {}).get("input_type","text")
            sig = (q.get("title","").strip().lower(), q.get("section",""), "input", itype)
            if sig in seen:
                continue
            seen.add(sig)
        out.append(q)
    return out

def dedupe_keys(questions: List[Question]) -> None:
    seen: Dict[str,int] = {}
    for q in questions:
        base = "signature" if q.type=="signature" else (q.key or "q")
        if q.type=="signature":
            q.key = "signature"; continue
        if base not in seen: seen[base]=1; q.key=base
        else: seen[base]+=1; q.key=f"{base}_{seen[base]}"

def validate_form(questions: List[Question]) -> List[str]:
    errs=[]
    for q in questions:
        if q.type not in ALLOWED_TYPES:
            errs.append(f"Unsupported type for {q.key}: {q.type}")
    sig = [q for q in questions if q.type=="signature"]
    if len(sig)!=1 or sig[0].key!="signature":
        errs.append("Signature rule violated (need exactly one with key='signature').")
    for q in questions:
        if q.type in ("radio","dropdown"):
            for opt in q.control.get("options", []):
                if opt.get("value") in (None,""):
                    errs.append(f"Empty option value in {q.key}")
    return errs

def questions_to_json(questions: List[Question]) -> List[Dict]:
    for q in questions:
        ensure_control_present(q)
        fill_missing_option_values(q)
    dedupe_keys(questions)
    errs = validate_form(questions)
    if errs:
        print("Validation warnings:", *errs, sep="\n  ", file=sys.stderr)
    payload = []
    for q in questions:
        item = {"key": q.key, "title": q.title, "section": q.section,
                "optional": q.optional, "type": q.type, "control": q.control or {}}
        
        # Fix 2: Add conditional "if" property for follow-up fields
        if hasattr(q, 'conditional_on') and q.conditional_on:
            # Convert conditional_on to "if" array format
            item["if"] = [{"key": cond_key, "value": cond_val} for cond_key, cond_val in q.conditional_on]
        
        payload.append(item)
    
    payload = _semantic_dedupe(payload)
    return payload

# ---------- Post-processing helpers

def _norm_title(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def postprocess_merge_hear_about_us(payload: List[dict]) -> List[dict]:
    idxs = [i for i,q in enumerate(payload) if HEAR_ABOUT_RE.search(q.get("title",""))]
    if len(idxs) <= 1:
        return payload
    keep = idxs[0]
    all_opts: Dict[str, dict] = {}
    extras: List[dict] = []
    for i in idxs:
        q = payload[i]
        for o in (q.get("control",{}).get("options") or []):
            k = normalize_opt_name(o.get("name",""))
            if not k: continue
            all_opts[k] = {"name": o.get("name",""), "value": o.get("value", slugify(o.get("name",""),80))}
        extra = q.get("control",{}).get("extra")
        if extra: extras.append(extra)
    payload[keep]["control"]["options"] = list(all_opts.values())
    payload[keep]["control"]["multi"] = True
    if extras:
        payload[keep]["control"]["extra"] = {"type":"Input","hint":"Other (please specify)"}
    for i in sorted(idxs[1:], reverse=True):
        payload.pop(i)
    return payload

# ---------- Fix 3: Enhanced Malformed Conditions Detection

def is_malformed_condition_field(field: dict) -> bool:
    """
    Detect if a field is a malformed medical/dental condition field.
    
    Criteria:
    - Type is dropdown with multi=True
    - Title is unusually long (5+ words) or contains multiple condition keywords
    - Options contain medical/health terms
    
    Examples of malformed titles:
    - "Artificial Angina (chest Heart pain) Valve Thyroid Disease..."
    - "Bleeding, Swollen, Irritated gums Tobacco"
    - "Heart Surgery Ulcers (Stomach) Dizziness AIDS"
    """
    if field.get('type') != 'dropdown':
        return False
    
    if not field.get('control', {}).get('multi'):
        return False
    
    title = field.get('title', '')
    title_lower = title.lower()
    
    # Check 1: Title has multiple medical condition keywords
    condition_keywords = [
        'diabetes', 'cancer', 'heart', 'disease', 'arthritis', 'hepatitis',
        'asthma', 'anxiety', 'depression', 'ulcer', 'thyroid', 'kidney',
        'liver', 'tuberculosis', 'hiv', 'aids', 'stroke', 'bleeding',
        'anemia', 'glaucoma', 'angina', 'valve', 'neurological'
    ]
    
    keyword_count = sum(1 for kw in condition_keywords if kw in title_lower)
    
    # If title has 3+ condition keywords, likely malformed
    if keyword_count >= 3:
        return True
    
    # Check 2: Title is very long and has some condition keywords
    word_count = len(title.split())
    if word_count >= 8 and keyword_count >= 2:
        return True
    
    # Check 3: Title contains multiple capitalized words that look like conditions
    capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', title)
    if len(capitalized_words) >= 4 and keyword_count >= 1:
        return True
    
    return False


def postprocess_consolidate_medical_conditions(payload: List[dict]) -> List[dict]:
    """
    Enhanced version that consolidates both well-formed and malformed condition dropdowns,
    plus individual checkbox/radio fields that look like medical conditions (Fix 1).
    """
    def looks_condition(opt_name: str) -> bool:
        w = _norm_title(opt_name)
        return any(t in w for t in _COND_TOKENS)
    
    # Medical condition keywords for identifying individual condition fields
    CONDITION_KEYWORDS = [
        'diabetes', 'cancer', 'heart', 'disease', 'arthritis', 'hepatitis',
        'asthma', 'anxiety', 'depression', 'ulcer', 'thyroid', 'kidney',
        'liver', 'tuberculosis', 'hiv', 'aids', 'stroke', 'bleeding',
        'anemia', 'glaucoma', 'angina', 'valve', 'neurological', 'alzheimer',
        'blood pressure', 'cholesterol', 'pacemaker', 'chemotherapy', 'radiation',
        'convulsion', 'seizure', 'epilepsy', 'migraine', 'allergy'
    ]
    
    # Separate handling for malformed dropdowns, well-formed dropdowns, and individual checkboxes
    malformed_indices = []
    wellformed_groups_by_section: Dict[str, List[int]] = defaultdict(list)
    individual_condition_indices: Dict[str, List[int]] = defaultdict(list)
    
    for i, q in enumerate(payload):
        section = q.get('section', 'General')
        
        # Check if malformed
        if is_malformed_condition_field(q):
            malformed_indices.append(i)
            continue
        
        # Check if well-formed medical condition field (original logic)
        if (q.get('type') == 'dropdown' and 
            q.get('control', {}).get('multi', False) and 
            q.get('section') in {'Medical History', 'Dental History'}):
            
            opts = q.get('control', {}).get('options') or []
            if len(opts) >= 5 and sum(looks_condition(o.get('name', '')) for o in opts) >= 3:
                wellformed_groups_by_section[section].append(i)
                continue
        
        # Check if individual checkbox/radio that looks like a medical condition (Fix 1)
        if q.get('type') in ['checkbox', 'radio'] and section in {'Medical History', 'General'}:
            title = q.get('title', '').lower()
            # Check if title contains medical condition keywords
            has_condition_keyword = any(kw in title for kw in CONDITION_KEYWORDS)
            # Or if it's a short title (1-4 words) in Medical History section
            is_short_medical = section == 'Medical History' and len(title.split()) <= 4
            
            if has_condition_keyword or is_short_medical:
                individual_condition_indices[section].append(i)
    
    # Consolidate malformed fields
    if malformed_indices:
        # Extract all options from malformed fields
        all_options = []
        sections = set()
        
        for idx in malformed_indices:
            field = payload[idx]
            sections.add(field.get('section', 'Medical History'))
            
            # Extract options from the malformed field
            opts = field.get('control', {}).get('options', [])
            for opt in opts:
                opt_name = opt.get('name', '')
                opt_value = opt.get('value', '')
                
                # Clean up option name
                opt_name = opt_name.strip()
                
                # Skip if too short or looks like junk
                if len(opt_name) < 3:
                    continue
                
                # Add to consolidated list if not duplicate
                if opt_name not in [o['name'] for o in all_options]:
                    all_options.append({
                        'name': opt_name,
                        'value': opt_value if opt_value else slugify(opt_name, 80)
                    })
        
        # Create consolidated field
        if all_options:
            consolidated_section = list(sections)[0] if len(sections) == 1 else 'Medical History'
            
            consolidated_field = {
                'key': 'medical_conditions_consolidated',
                'type': 'dropdown',
                'title': 'Do you have or have you had any of the following medical conditions?',
                'section': consolidated_section,
                'optional': False,
                'control': {
                    'options': sorted(all_options, key=lambda x: x['name']),
                    'multi': True
                }
            }
            
            # Replace first malformed field with consolidated
            payload[malformed_indices[0]] = consolidated_field
            
            # Remove other malformed fields
            for idx in sorted(malformed_indices[1:], reverse=True):
                payload.pop(idx)
    
    # Original consolidation logic for well-formed fields
    for section, groups in list(wellformed_groups_by_section.items()):
        if len(groups) <= 1:
            continue
        
        keep = groups[0]
        seen: Set[str] = set()
        merged: List[dict] = []
        
        for i in groups:
            for o in (payload[i].get('control', {}).get('options') or []):
                name = SPELL_FIX.get(o.get('name', ''), o.get('name', ''))
                norm = normalize_opt_name(name)
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                merged.append({'name': name, 'value': o.get('value', slugify(name, 80))})
        
        if section == 'Medical History':
            payload[keep]['title'] = 'Medical Conditions'
            payload[keep]['key'] = 'medical_conditions'
        payload[keep]['control']['options'] = merged
        
        for i in sorted(groups[1:], reverse=True):
            payload.pop(i)
    
    # New: Consolidate individual checkbox/radio fields that are medical conditions (Fix 1)
    for section, indices in list(individual_condition_indices.items()):
        # Only consolidate if we have 5+ individual condition fields
        if len(indices) < 5:
            continue
        
        # Create consolidated dropdown
        consolidated_options = []
        seen_names: Set[str] = set()
        
        for idx in indices:
            field = payload[idx]
            title = field.get('title', '').strip()
            
            # Normalize the title for duplicate detection
            norm_title = normalize_opt_name(title)
            if norm_title and norm_title not in seen_names:
                seen_names.add(norm_title)
                consolidated_options.append({
                    'name': title,
                    'value': slugify(title, 80)
                })
        
        if consolidated_options:
            # Replace first field with consolidated dropdown
            payload[indices[0]] = {
                'key': 'medical_conditions' if section == 'Medical History' else 'dental_conditions',
                'type': 'dropdown',
                'title': 'Do you have or have you had any of the following?',
                'section': section,
                'optional': False,
                'control': {
                    'options': sorted(consolidated_options, key=lambda x: x['name']),
                    'multi': True
                }
            }
            
            # Remove other individual condition fields
            for idx in sorted(indices[1:], reverse=True):
                payload.pop(idx)
    
    return payload

def postprocess_signature_uniqueness(payload: List[dict]) -> List[dict]:
    sig_idx = [i for i,q in enumerate(payload) if q.get("type")=="signature"]
    if not sig_idx:
        payload.append({"key":"signature","title":"Signature","section":"Signature","type":"signature","control":{}})
    elif len(sig_idx) > 1:
        for i in sorted(sig_idx[1:], reverse=True):
            payload.pop(i)
        payload[sig_idx[0]].update({"key":"signature","title":"Signature","section":"Signature","type":"signature"})
    else:
        i = sig_idx[0]
        payload[i].update({"key":"signature","title":"Signature","section":"Signature","type":"signature"})
    return payload

def postprocess_rehome_by_key(payload: List[dict], dbg: Optional[DebugLogger]=None) -> List[dict]:
    ins_keys = ("insurance_", "insured", "policy", "group", "member id", "id number")
    demo_keys = ("last_name","first_name","mi","date_of_birth","address","city","state","zipcode","email","phone",
                 "mobile_phone","home_phone","work_phone","drivers_license","employer","occupation","parent_")
    for q in payload:
        t = _norm_title(q.get("title",""))
        k = q.get("key","")
        sec = q.get("section","General")
        if (sec not in {"Insurance"} and (t.count("insurance") or any(s in k for s in ins_keys))):
            q["section"] = "Insurance"
            if dbg: dbg.gate(f"rehome -> Insurance :: {q.get('title','')}")
        if (sec not in {"Patient Information","Insurance"} and (any(k.startswith(d) for d in demo_keys) or "parent" in k)):
            q["section"] = "Patient Information"
            if dbg: dbg.gate(f"rehome -> Patient Information :: {q.get('title','')}")
    return payload

def postprocess_infer_sections(payload: List[dict], dbg: Optional[DebugLogger] = None) -> List[dict]:
    """
    Reassign fields from 'General' to more specific sections based on content.
    Uses keyword matching to identify medical and dental questions.
    """
    MEDICAL_KEYWORDS = [
        'physician', 'doctor', 'hospital', 'surgery', 'surgical', 'operation',
        'medication', 'medicine', 'prescription', 'drug',
        'illness', 'disease', 'condition', 'diagnosis',
        'allergy', 'allergic', 'reaction',
        'symptom', 'pain', 'discomfort', 'health'
    ]
    
    DENTAL_KEYWORDS = [
        'tooth', 'teeth', 'gum', 'gums',
        'dental', 'dentist', 'orthodontic', 'orthodontist',
        'cleaning', 'cavity', 'cavities', 'crown', 'filling',
        'bite', 'jaw', 'tmj', 'smile'
    ]
    
    for item in payload:
        if item.get('section') == 'General':
            title_lower = item.get('title', '').lower()
            key_lower = item.get('key', '').lower()
            combined = title_lower + ' ' + key_lower
            
            # Count keyword matches
            medical_score = sum(1 for kw in MEDICAL_KEYWORDS if kw in combined)
            dental_score = sum(1 for kw in DENTAL_KEYWORDS if kw in combined)
            
            # Reassign if strong signal (2+ matching keywords)
            if medical_score >= 2 and medical_score > dental_score:
                if dbg:
                    dbg.gate(f"section_inference -> Medical History :: {item.get('title', '')} (score={medical_score})")
                item['section'] = 'Medical History'
            elif dental_score >= 2 and dental_score > medical_score:
                if dbg:
                    dbg.gate(f"section_inference -> Dental History :: {item.get('title', '')} (score={dental_score})")
                item['section'] = 'Dental History'
    
    return payload

def postprocess_consolidate_duplicates(payload: List[dict], dbg: Optional[DebugLogger] = None) -> List[dict]:
    """
    Remove duplicate fields, keeping the one in the most appropriate section.
    Focuses on common fields like DOB, phone, email, address, SSN.
    """
    # Common fields that might be duplicated with their preferred section
    COMMON_FIELDS = {
        'date_of_birth': 'Patient Information',
        'dob': 'Patient Information',
        'phone': 'Patient Information',
        'mobile_phone': 'Patient Information',
        'home_phone': 'Patient Information',
        'work_phone': 'Patient Information',
        'cell_phone': 'Patient Information',
        'email': 'Patient Information',
        'address': 'Patient Information',
        'ssn': 'Patient Information',
        'social_security': 'Patient Information',
    }
    
    # Track seen keys and their indices
    seen_keys = {}
    to_remove = []
    
    for i, item in enumerate(payload):
        key = item.get('key', '')
        # Normalize key by removing numeric suffixes and scope markers
        key_base = re.sub(r'_\d+$', '', key)  # Remove _2, _3, etc.
        key_base = re.sub(r'__\w+$', '', key_base)  # Remove __primary, __secondary, etc.
        
        # Check if this is a common field that might be duplicated
        if key_base in COMMON_FIELDS:
            if key_base in seen_keys:
                # Duplicate found - determine which to keep
                prev_idx = seen_keys[key_base]
                prev_section = payload[prev_idx].get('section', 'General')
                curr_section = item.get('section', 'General')
                preferred_section = COMMON_FIELDS[key_base]
                
                if curr_section == preferred_section and prev_section != preferred_section:
                    # Current is in preferred section, remove previous
                    to_remove.append(prev_idx)
                    seen_keys[key_base] = i
                    if dbg:
                        dbg.gate(f"duplicate_consolidation -> Removed {key_base} from {prev_section}, kept in {curr_section}")
                elif prev_section == preferred_section and curr_section != preferred_section:
                    # Previous is in preferred section, remove current
                    to_remove.append(i)
                    if dbg:
                        dbg.gate(f"duplicate_consolidation -> Removed {key} from {curr_section}, kept {key_base} in {prev_section}")
                else:
                    # Neither in preferred or both in preferred, keep first occurrence
                    to_remove.append(i)
                    if dbg:
                        dbg.gate(f"duplicate_consolidation -> Removed duplicate {key} from {curr_section}")
            else:
                seen_keys[key_base] = i
    
    # Remove duplicates in reverse order to maintain indices
    for idx in sorted(set(to_remove), reverse=True):
        payload.pop(idx)
    
    return payload


def postprocess_consolidate_malformed_grids(payload: List[dict], dbg: Optional[DebugLogger] = None) -> List[dict]:
    """
    Archivev10 Fix 4: Consolidate malformed multi-column checkbox fields.
    
    Detects fields with concatenated condition names in titles (e.g.,
    "Radiation Therapy Jaundice Jaw Joint Pain") and consolidates them
    into cleaner multi-select fields.
    """
    # Identify malformed fields in Medical/Dental History
    malformed_indices = []
    
    for i, item in enumerate(payload):
        section = item.get('section', '')
        title = item.get('title', '')
        item_type = item.get('type', '')
        
        # Only check dropdown fields in Medical/Dental History
        if section not in {'Medical History', 'Dental History'}:
            continue
        
        if item_type != 'dropdown':
            continue
        
        # Check if title looks malformed (3+ medical/dental terms concatenated)
        # Split title into words and count capitalized medical terms
        words = title.split()
        capitalized_words = [w for w in words if w and w[0].isupper() and len(w) > 2]
        
        # Check for medical/dental keywords
        medical_keywords = [
            'therapy', 'disease', 'disorder', 'condition', 'illness', 'syndrome',
            'pain', 'fever', 'bleeding', 'valve', 'joint', 'respiratory',
            'cardiovascular', 'hematologic', 'psychiatric', 'gastrointestinal',
            'arthritis', 'diabetes', 'asthma', 'seizure', 'allergy', 'nursing',
            'teeth', 'grinding', 'clenching', 'sucking', 'biting', 'chewing',
            'discolored', 'worn', 'crooked', 'spaces', 'overbite', 'sensitivity',
            'anesthesia', 'sulfa', 'drugs'
        ]
        
        title_lower = title.lower()
        keyword_count = sum(1 for kw in medical_keywords if kw in title_lower)
        
        # Enhanced detection: Malformed if title lacks connecting words
        # Good titles have "please mark", "do you", "have you", etc.
        has_instruction = bool(re.search(r'\b(please|mark|any|conditions|apply|do you|have you)\b', title_lower))
        
        # Malformed if: (4+ capitalized words AND no instructions) OR (4+ keywords AND no instructions)
        is_malformed = False
        if not has_instruction:
            if len(capitalized_words) >= 4 or keyword_count >= 4:
                is_malformed = True
        
        if is_malformed:
            # Also check that options exist and are reasonable
            options = item.get('control', {}).get('options', [])
            if len(options) >= 2:
                malformed_indices.append(i)
                if dbg:
                    dbg.gate(f"malformed_grid_detected -> '{title[:60]}...' with {len(options)} options")
    
    # If we found malformed fields, consolidate them by section
    if not malformed_indices:
        return payload
    
    # Group malformed fields by section
    by_section = {}
    for idx in malformed_indices:
        section = payload[idx].get('section', 'General')
        if section not in by_section:
            by_section[section] = []
        by_section[section].append(idx)
    
    # Consolidate each section's malformed fields
    to_remove = []
    new_fields = []
    
    for section, indices in by_section.items():
        # Skip if only 1 field (not worth consolidating)
        if len(indices) <= 1:
            continue
        
        # Collect all options from malformed fields
        all_options = []
        for idx in indices:
            options = payload[idx].get('control', {}).get('options', [])
            all_options.extend(options)
            to_remove.append(idx)
        
        # Remove duplicates
        seen = set()
        unique_options = []
        for opt in all_options:
            opt_name = opt.get('name', '') if isinstance(opt, dict) else opt
            if opt_name and opt_name.lower() not in seen:
                seen.add(opt_name.lower())
                unique_options.append(opt)
        
        # Create consolidated field
        if len(unique_options) >= 5:
            if section == "Medical History":
                title = "Medical History - Please mark any conditions that apply"
                key = "medical_conditions_consolidated"
            elif section == "Dental History":
                title = "Dental History - Please mark any conditions that apply"
                key = "dental_conditions_consolidated"
            else:
                title = f"{section} - Please mark any that apply"
                key = slugify(title)
            
            new_field = {
                'key': key,
                'title': title,
                'section': section,
                'type': 'dropdown',
                'optional': False,
                'control': {
                    'options': unique_options,
                    'multi': True
                }
            }
            
            new_fields.append((indices[0], new_field))  # Insert at position of first malformed field
            
            if dbg:
                dbg.gate(f"malformed_grid_consolidated -> {len(indices)} fields into '{title}' with {len(unique_options)} options")
    
    # Remove malformed fields in reverse order
    for idx in sorted(set(to_remove), reverse=True):
        payload.pop(idx)
    
    # Insert consolidated fields
    for insert_pos, new_field in sorted(new_fields, reverse=True):
        # Adjust insert position if we've already removed items
        adjusted_pos = insert_pos
        for removed_idx in sorted(to_remove):
            if removed_idx < insert_pos:
                adjusted_pos -= 1
        payload.insert(adjusted_pos, new_field)
    
    return payload


def postprocess_consolidate_continuation_options(payload: List[dict], dbg: Optional[DebugLogger] = None) -> List[dict]:
    """
    Archivev18 Fix 4: Consolidate checkbox fields that are continuations of previous fields.
    
    Pattern: Field with title that's just concatenated option names (e.g., "Local Anesthesia Sulfa Drugs Other")
    following a field with a proper question title in the same section.
    
    Example:
    Field 1: "Are you allergic to any of the following?" with options [Aspirin, Penicillin, ...]
    Field 2: "Local Anesthesia Sulfa Drugs Other" with options [Local Anesthesia, Sulfa Drugs, Other]
    
    Should consolidate Field 2's options into Field 1 and remove Field 2.
    """
    i = 0
    while i < len(payload):
        item = payload[i]
        title = item.get('title', '')
        
        # Check if this field looks like concatenated options (3+ capitalized words, no question marks/colons)
        # and is a dropdown with multiple options
        words = title.split()
        capitalized = [w for w in words if w and w[0].isupper()]
        
        is_concatenated = (
            len(capitalized) >= 3 and 
            '?' not in title and 
            not title.endswith(':') and
            item.get('type') in ('dropdown', 'radio')
        )
        
        if is_concatenated and i > 0:
            prev_item = payload[i - 1]
            prev_title = prev_item.get('title', '').lower()
            
            # Check if previous field is in same section and is a question about selecting/checking items
            same_section = item.get('section') == prev_item.get('section')
            is_selection_question = any(phrase in prev_title for phrase in [
                'allergic', 'any of the following', 'select', 'choose', 'check', 'mark'
            ])
            prev_is_dropdown = prev_item.get('type') in ('dropdown', 'radio')
            
            if same_section and is_selection_question and prev_is_dropdown:
                # Consolidate: add current field's options to previous field
                current_options = item.get('control', {}).get('options', [])
                prev_options = prev_item.get('control', {}).get('options', [])
                
                # Check if options in current field match parts of its title (confirmation it's concatenated)
                option_names = [opt.get('name', '') if isinstance(opt, dict) else opt for opt in current_options]
                title_has_options = sum(1 for opt_name in option_names if opt_name in title)
                
                if title_has_options >= 2:  # At least 2 option names appear in title
                    # Merge options
                    combined_options = prev_options + current_options
                    
                    # Remove duplicates
                    seen = set()
                    unique_options = []
                    for opt in combined_options:
                        opt_name = opt.get('name', '') if isinstance(opt, dict) else opt
                        if opt_name and opt_name.lower() not in seen:
                            seen.add(opt_name.lower())
                            unique_options.append(opt)
                    
                    prev_item['control']['options'] = unique_options
                    
                    if dbg:
                        dbg.gate(f"continuation_consolidated -> Merged '{title}' ({len(current_options)} opts) into '{prev_item['title']}' (total: {len(unique_options)} opts)")
                    
                    # Remove current field
                    payload.pop(i)
                    continue
        
        i += 1
    
    return payload


def postprocess_clean_overflow_titles(payload: List[dict], dbg: Optional[DebugLogger] = None) -> List[dict]:
    """
    Archivev11 Fix 3: Clean up field titles that have column overflow artifacts.
    
    Removes known label patterns that appear at the end of titles due to
    text extraction extending into adjacent columns.
    """
    LABEL_PATTERNS = [
        r'\s+Frequency\s*$',           # "Alcohol Frequency", "Drugs Frequency"
        r'\s+How\s+much\s*$',          # "How much"
        r'\s+How\s+long\s*$',          # "How long"
        r'\s+Comments?\s*:?\s*$',      # "Comments", "Comment:"
        r'\s+Additional\s+Comments?\s*:?\s*$',  # "Additional Comments"
        r'\s+Pattern\s*$',             # "Pattern"
        r'\s+Conditions?\s*$',         # "Conditions"
    ]
    
    for item in payload:
        title = item.get('title', '')
        original_title = title
        
        # Check if title ends with a known label pattern
        for pattern in LABEL_PATTERNS:
            if re.search(pattern, title, re.I):
                # Truncate at the pattern
                title = re.sub(pattern, '', title, flags=re.I).strip()
                
                if dbg and title != original_title:
                    dbg.gate(f"overflow_title_cleaned -> '{original_title}' → '{title}'")
                
                item['title'] = title
                break
    
    return payload


def postprocess_make_explain_fields_unique(payload: List[dict], dbg: Optional[DebugLogger] = None) -> List[dict]:
    """
    Archivev11 Fix 5: Make duplicate titles unique by adding context.
    
    When multiple fields have the same title in a section, add context from:
    - Preceding field (for explanation/follow-up fields)
    - Numeric suffix (for repeated fields like "Insured's Name")
    - Key information (as a last resort)
    """
    # Track title occurrences by section
    title_counts = {}
    
    for i, item in enumerate(payload):
        title = item.get('title', '').strip()
        section = item.get('section', 'General')
        key = item.get('key', '')
        
        # Create a unique identifier for this title in this section
        section_title = f"{section}:{title}"
        
        # Archivev18 Fix 3: Handle generic explanation titles even on first occurrence
        generic_titles = ['please explain', 'explanation', 'details', 'comments', 'if yes, please explain']
        is_generic = any(gt in title.lower() for gt in generic_titles)
        
        # If this is a generic title following a yes/no question, improve it immediately
        if is_generic and i > 0:
            prev_item = payload[i - 1]
            prev_title = prev_item.get('title', '')
            
            # If previous field is a yes/no question, use it as context
            if any(yn in prev_title.lower() for yn in ['yes or no', 'y or n', 'have you', 'are you', 'do you']):
                # Use full parent question title, but truncate if too long
                # Remove trailing question mark and colon for better readability
                context = prev_title.rstrip('?:').strip()
                
                # If context is too long (>60 chars), use first few words
                if len(context) > 60:
                    words = context.split()[:5]
                    context = ' '.join(words)
                
                new_title = f"{context} - Please explain"
                
                if dbg:
                    dbg.gate(f"unique_title -> '{title}' → '{new_title}' (context)")
                
                item['title'] = new_title
                # Update title for duplicate tracking
                title = new_title
                section_title = f"{section}:{title}"
        
        # Check if this is a duplicate
        if section_title in title_counts:
            count = title_counts[section_title]
            title_counts[section_title] = count + 1
            
            # Note: Generic titles are now handled above, before duplicate check
            
            # Strategy 2: For repeated fields (like Insurance fields), add numeric suffix
            # Check if key has a numeric suffix or scope marker
            key_has_suffix = bool(re.search(r'(_\d+|__\w+)$', key))
            if key_has_suffix:
                # Extract suffix info
                if '__primary' in key:
                    new_title = f"{title} (Primary)"
                elif '__secondary' in key:
                    new_title = f"{title} (Secondary)"
                elif re.search(r'_(\d+)$', key):
                    match = re.search(r'_(\d+)$', key)
                    num = match.group(1)
                    new_title = f"{title} #{num}"
                else:
                    new_title = f"{title} ({count + 1})"
                
                if dbg:
                    dbg.gate(f"unique_title -> '{title}' → '{new_title}' (suffix)")
                
                item['title'] = new_title
                continue
            
            # Strategy 3: Fallback - add numeric suffix
            new_title = f"{title} ({count + 1})"
            
            if dbg:
                dbg.gate(f"unique_title -> '{title}' → '{new_title}' (numeric)")
            
            item['title'] = new_title
        else:
            title_counts[section_title] = 1
    
    return payload

# ---------- Dictionary application + reporting

@dataclass
class Stats:
    total: int
    used: int
    counts_by_section: Dict[str,int]
    counts_by_type: Dict[str,int]
    matches: List[MatchEvent]
    near_misses: List[MatchEvent]

def apply_templates_and_count(payload: List[dict], catalog: Optional[TemplateCatalog], dbg: DebugLogger) -> Tuple[List[dict], int]:
    """
    Apply template matching and count matches.
    
    Enhanced to preserve conditional follow-up fields (Archivev8 Fix 3).
    """
    if not catalog:
        return payload, 0
    
    used = 0
    out: List[dict] = []
    
    for q in payload:
        # Archivev8 Fix 3: Check if this is a conditional/explanation field
        # Archivev15 Fix: Also skip opt-in preference fields (inline checkbox options)
        # These should not have templates applied to avoid breaking conditional relationships or changing keys
        is_conditional_field = (
            bool(q.get("conditional_on")) or
            "_explanation" in q.get("key", "") or
            "_followup" in q.get("key", "") or
            "_details" in q.get("key", "") or
            q.get("key", "").startswith("opt_in_") or  # Archivev15: Skip opt-in preference fields
            (q.get("title", "").lower().strip() in ["please explain", "explanation", "details", "comments"])
        )
        
        if is_conditional_field:
            # Skip template matching for conditional fields
            out.append(q)
            if dbg.enabled and not q.get("key", "").startswith("opt_in_"):
                print(f"  [debug] template: skipping conditional field '{q.get('key')}' to preserve relationship")
            continue
        
        # Normal template matching for non-conditional fields
        fr = catalog.find(q.get("key"), q.get("title"), parsed_q=q)
        if fr.tpl:
            used += 1
            merged = merge_with_template(q, fr.tpl, scope_suffix=fr.scope)
            out.append(merged)
            dbg.log(MatchEvent(q.get("title",""), q.get("key",""), q.get("section",""), fr.tpl.get("key"), fr.reason, fr.score, fr.coverage))
        else:
            out.append(q)
            if fr.reason == "near":
                dbg.log_near(MatchEvent(q.get("title",""), q.get("key",""), q.get("section",""), fr.best_key, "near", fr.score, fr.coverage))
    
    out = _dedupe_keys_dicts(out)
    return out, used

def write_stats_sidecar(out_path: Path, payload: List[dict], used: int, dbg: DebugLogger):
    total = len(payload)
    counts_by_section = defaultdict(int)
    counts_by_type = defaultdict(int)
    for q in payload:
        counts_by_section[q.get("section","General")] += 1
        counts_by_type[q.get("type","input")] += 1
    stats = {
        "file": out_path.name,
        "total_items": total,
        "reused_from_dictionary": used,
        "reused_pct": (used/total*100.0 if total else 0.0),
        "counts_by_section": dict(counts_by_section),
        "counts_by_type": dict(counts_by_type),
        "matches": [ev.__dict__ for ev in dbg.events] if dbg.enabled else [],
        "near_misses": [ev.__dict__ for ev in dbg.near_misses] if dbg.enabled else [],
        "gates": dbg.gates if dbg.enabled else [],
    }
    sidecar = out_path.with_suffix(".stats.json")
    sidecar.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- IO

def process_one(txt_path: Path, out_dir: Path, catalog: Optional[TemplateCatalog] = None, debug: bool=False) -> Optional[Path]:
    raw = read_text_file(txt_path)
    if not raw.strip():
        print(f"[skip] empty file: {txt_path.name}")
        return None
    # Parse → normalize JSON
    questions = parse_to_questions(raw, debug=debug)
    payload = questions_to_json(questions)

    # Post-process merges + normalization
    payload = postprocess_merge_hear_about_us(payload)
    payload = postprocess_consolidate_medical_conditions(payload)
    payload = postprocess_signature_uniqueness(payload)

    # Apply templates + count
    dbg = DebugLogger(enabled=debug)
    payload, used = apply_templates_and_count(payload, catalog, dbg)

    # Re-home after template merge
    payload = postprocess_rehome_by_key(payload, dbg=dbg)
    
    # New post-processing steps (Archivev9 fixes)
    payload = postprocess_infer_sections(payload, dbg=dbg)
    payload = postprocess_consolidate_duplicates(payload, dbg=dbg)
    
    # Archivev10 Fix 4: Consolidate malformed grid fields
    payload = postprocess_consolidate_malformed_grids(payload, dbg=dbg)
    
    # Archivev11 Fix 3: Clean up column overflow in field titles
    payload = postprocess_clean_overflow_titles(payload, dbg=dbg)
    
    # Archivev18 Fix 4: Consolidate continuation checkbox options
    payload = postprocess_consolidate_continuation_options(payload, dbg=dbg)
    
    # Archivev11 Fix 5: Make generic "Please explain" fields unique
    payload = postprocess_make_explain_fields_unique(payload, dbg=dbg)

    out_path = out_dir / (txt_path.stem + ".modento.json")
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(payload)
    pct = (used * 100 // total) if total else 0
    print(f"[✓] {txt_path.name} -> {out_path.name} ({total} items)")
    print(f"    ↳ reused {used}/{total} from dictionary ({pct}%)")

    if debug:
        dbg.print_summary()
    write_stats_sidecar(out_path, payload, used, dbg)
    return out_path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="in_dir",  default=DEFAULT_IN_DIR,  help="Folder with LLMWhisperer .txt files (default: output)")
    ap.add_argument("--out", dest="out_dir", default=DEFAULT_OUT_DIR, help="Folder to write JSONs (default: JSONs)")
    ap.add_argument("--debug", action="store_true", help="Verbose debug logs + near-miss reporting; write *.stats.json sidecars")
    args = ap.parse_args()

    in_dir = Path(args.in_dir); out_dir = Path(args.out_dir)
    if not in_dir.exists():
        print(f"ERROR: input folder not found: {in_dir}", file=sys.stderr); sys.exit(2)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load dictionary
    dict_path = Path(__file__).resolve().parent / "dental_form_dictionary.json"
    catalog: Optional[TemplateCatalog] = None
    if dict_path.exists():
        try:
            catalog = TemplateCatalog.from_path(dict_path)
        except Exception as e:
            print(f"[warn] dictionary unavailable ({e}). Proceeding without templates.")
    else:
        print(f"[warn] dictionary file not found at {dict_path.name}. Proceeding without templates.")

    txts = sorted([p for p in in_dir.rglob("*.txt") if p.is_file()])
    if not txts:
        print(f"WARNING: no .txt files found under {in_dir}")
        return

    for p in txts:
        try:
            process_one(p, out_dir, catalog=catalog, debug=args.debug)
        except Exception as e:
            print(f"[x] failed on {p.name}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
