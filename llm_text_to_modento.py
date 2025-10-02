#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_text_to_modento.py — v2.9

TXT (LLMWhisperer layout_preserving) -> Modento-compliant JSON

What’s new vs v2.8 (focused changes):
  • "If yes, please explain" now creates a separate follow-up input field for details.
  • Medical/Dental History sections are now parsed into a single multi-select dropdown.
  • Expanded aliases for better matching of common fields like "Spouse's Name" and "Date Signed".
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

PAGE_NUM_RE = re.compile(r"^\s*(?:page\s*\d+(?:\s*/\s*\d+)?|\d+\s*/\s*\d+)\s*$", re.I)
ADDRESS_LIKE_RE = re.compile(
    r"\b(?:street|suite|ste\.?|ave|avenue|rd|road|blvd|zip|postal|fax|tel|phone|www\.|https?://|\.com|\.net|\.org|welcome|new\s+patients)\b",
    re.I,
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
    if len(t) <= 120 and (t.isupper() or (t.istitle() and not t.endswith("."))):
        if not t.endswith("?"):
            return True
    return t.endswith(":") and len(t) <= 120

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
            
            # Join if: hyphen/slash at end, OR (not sentence-ending punctuation AND (starts lowercase OR small word OR starts with paren OR ends with ?))
            if a_end in "-/" or (not ends_with_question and a_end not in ".:;?!" and (starts_lower or small_word or starts_with_paren)):
                merged = (merged.rstrip("- ") + " " + b_str).strip()
                i += 1; continue
            break
        out.append(merged)
        i += 1
    return out

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
    
    # Remove multiple spaces
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
    # Trim whitespace
    cleaned = cleaned.strip()
    
    # Remove trailing colons if followed by nothing
    cleaned = re.sub(r':\s*$', '', cleaned)
    
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

def options_from_inline_line(ln: str) -> List[Tuple[str, Optional[bool]]]:
    """
    Enhanced to handle grid/multi-column layouts (Fix 1).
    Splits checkboxes that appear in columns with significant spacing.
    """
    s_norm = normalize_glyphs_line(ln)
    
    # First try: existing inline choice regex
    items: List[Tuple[str, Optional[bool]]] = []
    for m in INLINE_CHOICE_RE.finditer(s_norm):
        label = clean_token(m.group(1))
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
            
            # Clean up common artifacts
            label = re.sub(r'\s{3,}', ' ', label)  # Collapse wide spaces
            label = label.strip('[]')
            label = clean_token(label)
            
            if label and len(label) > 1 and label.lower() not in YESNO_SET:
                options.append((label, None))
        
        if len(options) >= 3:  # Only use grid parsing if we got enough options
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

def make_option(name: str, bool_value: Optional[bool]) -> Dict:
    if bool_value is True:  return {"name": "Yes", "value": True}
    if bool_value is False: return {"name": "No",  "value": False}
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

def chunk_by_columns(line: str, ncols: int) -> List[str]:
    line = collapse_spaced_caps(line.strip())
    if "|" in line:
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < ncols: cols += [""] * (ncols - len(cols))
        return cols[:ncols]
    parts = [p.strip() for p in re.split(r"\s{3,}", line)]
    if len(parts) < ncols: parts += [""] * (ncols - len(parts))
    return parts[:ncols]

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

    questions: List[Question] = []
    cur_section = "General"
    seen_signature = False
    insurance_scope: Optional[str] = None  # "__primary" / "__secondary"

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = collapse_spaced_caps(raw.strip())
        if not line:
            i += 1; continue

        # Insurance anchoring
        if INSURANCE_BLOCK_RE.search(line):
            cur_section = "Insurance"; insurance_scope = None
        if INSURANCE_PRIMARY_RE.search(line):
            cur_section = "Insurance"; insurance_scope = "__primary"
        if INSURANCE_SECONDARY_RE.search(line):
            cur_section = "Insurance"; insurance_scope = "__secondary"

        # Section heading
        if is_heading(line):
            cur_section = normalize_section_name(line)
            low = line.lower()
            if "insurance" in low:
                if "primary" in low: insurance_scope = "__primary"
                elif "secondary" in low: insurance_scope = "__secondary"
                else: insurance_scope = None
            else:
                insurance_scope = None
            i += 1; continue

        # --- NEW: Medical History Multi-select block ---
        if cur_section in {"Medical History", "Dental History"}:
            if re.search(r"\b(have you ever had|do you have|are you taking)\b", line, re.I) and not extract_compound_yn_prompts(line):
                main_prompt_title = line
                options: List[Tuple[str, Optional[bool]]] = []
                k = i + 1
                while k < len(lines) and lines[k].strip() and not is_heading(lines[k]):
                    option_line = lines[k]
                    prompts = extract_compound_yn_prompts(option_line)
                    if prompts:
                        for p in prompts:
                            options.append((p, None))
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

        # Grid
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

        # Compound Yes/No on one line
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
                
                # Create follow-up field if needed
                if create_follow_up:
                    follow_up_key = slugify(ptxt + "_details")
                    # Check if not already created
                    if not any(q.key == follow_up_key for q in questions):
                        follow_up_title = f"{ptxt} - Please explain"
                        questions.append(Question(follow_up_key, follow_up_title, cur_section, "input", control={"input_type": "text"}))
                
                questions.append(Question(key, ptxt, cur_section, "radio", control=control))
                emitted_compound = True
            if re.search(r"name\s+of\s+school", line, re.I):
                questions.append(Question("name_of_school","Name of School",cur_section,"input",control={"input_type":"text"}))
        if emitted_compound:
            i += 1; continue

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
            questions.append(Question(key, title or "Date", cur_section, "date",
                                      control={"input_type": classify_date_input(title)}))
            i += 1; continue

        collected = opts_inline or opts_block
        if collected:
            # Fix 1: Clean title if it has inline checkboxes or concatenated options
            clean_title = title
            
            # If we have inline options (especially multiple ones), check if title needs cleaning
            if opts_inline and len(opts_inline) >= 2:
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
                if extracted and len(extracted) > 3:
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
    def is_junk(q: Question) -> bool:
        t = q.title.strip().lower()
        return (q.key == "q" or len(q.title.strip()) <= 1 or
                t in {"<<<", ">>>", "-", "—", "continued on back side"})
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
    """Remove duplicate simple inputs that are identical semantically (same title/section/type/input_type)."""
    seen: Set[Tuple[str,str,str,str]] = set()
    out: List[dict] = []
    for q in payload:
        if q.get("type") == "input":
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
    payload = [
        {"key": q.key, "title": q.title, "section": q.section,
         "optional": q.optional, "type": q.type, "control": q.control or {}}
        for q in questions
    ]
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

def postprocess_consolidate_medical_conditions(payload: List[dict]) -> List[dict]:
    def looks_condition(opt_name: str) -> bool:
        w = _norm_title(opt_name)
        return any(t in w for t in _COND_TOKENS)
    groups_by_section: Dict[str, List[int]] = defaultdict(list)
    for i,q in enumerate(payload):
        if q.get("type")=="dropdown" and q.get("control",{}).get("multi",False) and q.get("section") in {"Medical History","Dental History"}:
            opts = q.get("control",{}).get("options") or []
            if len(opts) >= 5 and sum(looks_condition(o.get("name","")) for o in opts) >= 3:
                groups_by_section[q.get("section")].append(i)
    for section, groups in list(groups_by_section.items()):
        if len(groups) <= 1: 
            continue
        keep = groups[0]
        seen: Set[str] = set()
        merged: List[dict] = []
        for i in groups:
            for o in (payload[i].get("control",{}).get("options") or []):
                name = SPELL_FIX.get(o.get("name",""), o.get("name",""))
                norm = normalize_opt_name(name)
                if not norm or norm in seen: continue
                seen.add(norm)
                merged.append({"name": name, "value": o.get("value", slugify(name,80))})
        if section == "Medical History":
            payload[keep]["title"] = "Medical Conditions"
            payload[keep]["key"] = "medical_conditions"
        payload[keep]["control"]["options"] = merged
        for i in sorted(groups[1:], reverse=True):
            payload.pop(i)
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
    if not catalog:
        return payload, 0
    used = 0
    out: List[dict] = []
    for q in payload:
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
