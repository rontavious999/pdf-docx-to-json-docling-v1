# Archivev8 Technical Fixes - Detailed Implementation Guide

This document provides detailed, copy-paste-ready code for implementing the 4 fixes identified in the Archivev8 analysis.

---

## Fix 1: Orphaned Checkbox Labels Detection

**File:** `llm_text_to_modento.py`  
**Location:** Add new helper functions before `parse_to_questions()`, around line 990

### Implementation

```python
# ---------- Fix: Orphaned Checkbox Labels

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
    
    A label line should:
    - Have no checkboxes
    - Have multiple words/phrases separated by significant whitespace
    
    Returns:
        List of label strings
    """
    # Must have no checkboxes to be orphaned labels
    if re.search(CHECKBOX_ANY, label_line):
        return []
    
    stripped = label_line.strip()
    if not stripped:
        return []
    
    # Split by 3+ spaces to get individual labels
    # This is a common pattern in grid layouts
    labels = re.split(r'\s{3,}', stripped)
    
    # Clean and filter labels
    cleaned_labels = []
    for label in labels:
        label = label.strip()
        # Must be at least 2 characters and look like a medical term
        if len(label) >= 2 and not label.isdigit():
            cleaned_labels.append(label)
    
    return cleaned_labels


def associate_orphaned_labels_with_checkboxes(
    checkbox_line: str,
    label_line: str
) -> List[Tuple[str, Optional[bool]]]:
    """
    Associate orphaned labels with checkboxes based on occurrence order.
    
    Args:
        checkbox_line: Line with checkboxes but minimal text
        label_line: Next line with labels but no checkboxes
    
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
    
    # Total labels should match or be close to total checkboxes
    total_labels = len(labels) + len(checkbox_line_labels)
    
    # If we have orphaned labels and checkboxes, associate them
    options = []
    
    # First, add labels from the label line (left to right)
    for i, label in enumerate(labels):
        if i < num_checkboxes:
            options.append((label, None))
    
    # Then add any label from the checkbox line itself
    for label in checkbox_line_labels:
        options.append((label, None))
    
    return options
```

### Integration into `parse_to_questions()`

**Location:** In the main parsing loop, around line 1550-1600

```python
def parse_to_questions(text: str, debug: bool=False) -> List[Question]:
    # ... existing code ...
    
    while i < len(lines):
        raw = lines[i]
        line = collapse_spaced_caps(raw.strip())
        if not line:
            i += 1
            continue
        
        # ... existing section/heading logic ...
        
        # NEW: Check for orphaned checkbox pattern
        if has_orphaned_checkboxes(line) and i + 1 < len(lines):
            next_line = lines[i + 1]
            orphaned_options = associate_orphaned_labels_with_checkboxes(line, next_line)
            
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
        
        # ... rest of existing parsing logic ...
        
        i += 1
    
    return questions
```

---

## Fix 2: Header/Business Information Filtering

**File:** `llm_text_to_modento.py`  
**Location:** In `scrub_headers_footers()`, around line 250-280

### Implementation

Add new regex patterns at the top of the file (around line 66):

```python
# Enhanced header filtering patterns (Fix 2)
DENTAL_PRACTICE_EMAIL_RE = re.compile(
    r'@.*?(?:dental|dentistry|orthodontics|smiles).*?\.(com|net|org)',
    re.I
)

BUSINESS_WITH_ADDRESS_RE = re.compile(
    r'(?:dental|dentistry|orthodontics|family|cosmetic|implant).{20,}?(?:suite|ste\.?|ave|avenue|rd|road|st(?:\.|(?:\s))))',
    re.I
)

PRACTICE_NAME_PATTERN = re.compile(
    r'^(?:.*?(?:dental|dentistry|orthodontics|family|cosmetic|implant).*?){1,3}$',
    re.I
)
```

Then enhance `scrub_headers_footers()`:

```python
def scrub_headers_footers(text: str) -> List[str]:
    raw_lines = text.splitlines()
    blocks: List[List[str]] = []
    cur: List[str] = []
    for ln in raw_lines:
        if ln.strip():
            cur.append(ln)
        else:
            if cur:
                blocks.append(cur)
                cur = []
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
        lines.extend(b)
        lines.append("")

    # Enhanced junk text filtering patterns (Fix 3 - already exists)
    MULTI_LOCATION_RE = re.compile(
        r'.*\b(Ave|Avenue|St|Street|Rd|Road|Blvd|Boulevard)\.?\b.*\b(Ave|Avenue|St|Street|Rd|Road|Blvd|Boulevard)\.?\b',
        re.I
    )
    CITY_STATE_ZIP_RE = re.compile(r',\s*[A-Z]{2}\s+\d{5}')
    OFFICE_NAMES_RE = re.compile(
        r'(dental|dentistry|orthodontics).{20,}(dental|dentistry|orthodontics|center|office)',
        re.I
    )

    repeats = detect_repeated_lines(lines)
    keep: List[str] = []
    
    for idx, ln in enumerate(lines):
        s = collapse_spaced_caps(ln.strip())
        if not s:
            keep.append(ln)
            continue
        
        if s in repeats or PAGE_NUM_RE.match(s):
            continue
        
        # Existing filters (Fix 3)...
        if MULTI_LOCATION_RE.search(s):
            continue
        if len(CITY_STATE_ZIP_RE.findall(s)) >= 2:
            continue
        if OFFICE_NAMES_RE.search(s) and len(s) > 80:
            continue
        if len(re.findall(r'\b\d{5}\b', s)) >= 2:
            continue
        
        # NEW FILTERS (Fix 2):
        
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
        
        # Existing filters continue...
        if re.search(r"\bcontinued on back side\b", s, re.I):
            continue
        if re.search(r"\brev\s*\d{1,2}\s*/\s*\d{2}\b", s, re.I):
            continue
        if s in {"<<<", ">>>"}or re.search(r"\bOC\d+\b", s):
            continue
        
        keep.append(ln)
    
    return keep
```

---

## Fix 3: Preserve Conditional Follow-up Fields

**File:** `llm_text_to_modento.py`  
**Location:** In `apply_templates_and_count()`, around line 2239-2256

### Implementation

```python
def apply_templates_and_count(payload: List[dict], catalog: Optional[TemplateCatalog], dbg: DebugLogger) -> Tuple[List[dict], int]:
    """
    Apply template matching and count matches.
    
    Enhanced to preserve conditional follow-up fields (Fix 3).
    """
    if not catalog:
        return payload, 0
    
    used = 0
    out: List[dict] = []
    
    for q in payload:
        # NEW: Check if this is a conditional/explanation field
        # These should not have templates applied to avoid breaking conditional relationships
        is_conditional_field = (
            bool(q.get("conditional_on")) or
            "_explanation" in q.get("key", "") or
            "_followup" in q.get("key", "") or
            "_details" in q.get("key", "") or
            (q.get("title", "").lower().strip() in ["please explain", "explanation", "details", "comments"])
        )
        
        if is_conditional_field:
            # Skip template matching for conditional fields
            out.append(q)
            if dbg.enabled:
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
```

---

## Fix 4: Clean Malformed Medical Condition Text

**File:** `llm_text_to_modento.py`  
**Location:** Add helper function around line 450, modify `make_option()` around line 460

### Implementation

```python
# ---------- Fix: Clean Malformed Option Text

def clean_option_text(text: str) -> str:
    """
    Clean malformed option text.
    
    Fixes:
    1. Repeated words: "Blood Blood Transfusion" -> "Blood Transfusion"
    2. Slash-separated malformed: "Epilepsy/ Excessive Seizers Bleeding" -> "Epilepsy"
    
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
    if '/' in text:
        parts = [p.strip() for p in text.split('/')]
        
        # Check if we have a clean first part and a messy second part
        if len(parts) >= 2:
            first_part = parts[0]
            second_part = parts[1]
            
            # Heuristics for "messy" second part:
            # - More than 3 words (likely run-on text)
            # - Contains multiple spaces (formatting artifact)
            # - Doesn't start with capital (incomplete/malformed)
            is_messy_second = (
                len(second_part.split()) > 3 or
                '  ' in second_part or
                (len(second_part) > 0 and not second_part[0].isupper())
            )
            
            # If first part looks complete and second is messy, use just first
            if len(first_part) >= 3 and first_part[0].isupper() and is_messy_second:
                text = first_part
    
    # Fix 3: Clean extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()
```

Then modify `make_option()`:

```python
def make_option(name: str, checked: Optional[bool] = None) -> Dict:
    """Create a Modento option object with cleaned text."""
    # Apply text cleaning (Fix 4)
    name = clean_option_text(name)
    
    val = slugify(name)
    opt = {"name": name, "value": val}
    if checked is True:
        opt["checked"] = True
    return opt
```

---

## Testing Commands

After implementing fixes, run these commands to verify:

```bash
# Run with debug to see what's happening
python3 llm_text_to_modento.py --in /path/to/archivev8/output --out /tmp/test_out --debug

# Check specific fixes:

# Fix 1: Check for orphaned labels
grep -i "anemia\|convulsions\|hay fever\|leukemia" /tmp/test_out/Chicago-Dental-Solutions_Form.modento.json

# Fix 2: Check no header fields
grep -i "prestige dental" /tmp/test_out/npf.modento.json

# Fix 3: Count explanation fields
grep -i "explanation" /tmp/test_out/Chicago-Dental-Solutions_Form.modento.json | grep "key" | wc -l
# Should be 4, not 1

# Fix 4: Check no repeated words
grep -i "blood blood" /tmp/test_out/Chicago-Dental-Solutions_Form.modento.json
# Should return nothing
```

---

## Summary

All 4 fixes are:
- ✅ **General pattern-based** (no hard-coding)
- ✅ **Backward compatible** (no breaking changes)
- ✅ **Independently testable**
- ✅ **Well-documented** with comments

Implementation order recommendation:
1. Fix #2 (easiest)
2. Fix #3 (easy)
3. Fix #4 (easy)
4. Fix #1 (medium complexity)
