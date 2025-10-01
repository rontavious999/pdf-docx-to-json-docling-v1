# Technical Specification for PDF-to-JSON Fixes

This document provides detailed technical specifications for each recommended fix, including code patterns, function signatures, and integration points.

---

## Fix 1: Grid/Multi-Column Checkbox Splitting

### Current Code Issue
File: `llm_text_to_modento.py`, Function: `options_from_inline_line()`

Current behavior treats this as single option:
```
[ ] AIDS/HIV Positive    [ ] Chest Pains    [ ] Headaches
```

### Proposed Enhancement

```python
def options_from_inline_line(line: str) -> List[Tuple[str, Optional[bool]]]:
    """
    Enhanced to handle grid/multi-column layouts.
    Splits checkboxes that appear in columns with significant spacing.
    """
    # First try: existing inline choice regex
    existing_matches = list(INLINE_CHOICE_RE.finditer(line))
    
    # If we found options with existing method, use it
    if existing_matches:
        options = []
        for m in existing_matches:
            txt = m.group(1).strip()
            if txt and txt.lower() not in YESNO_SET:
                checked = None  # Can't determine from layout alone
                options.append((txt, checked))
        if options:
            return options
    
    # NEW: Grid detection - look for multiple checkboxes with wide spacing
    checkbox_positions = []
    for m in re.finditer(CHECKBOX_ANY, line):
        checkbox_positions.append(m.start())
    
    if len(checkbox_positions) >= 3:  # Multiple checkboxes suggest grid
        # Split line into segments based on checkbox positions
        options = []
        for i, start_pos in enumerate(checkbox_positions):
            # Extract text after this checkbox until next checkbox or EOL
            if i + 1 < len(checkbox_positions):
                end_pos = checkbox_positions[i + 1]
            else:
                end_pos = len(line)
            
            segment = line[start_pos:end_pos]
            # Remove checkbox token and extract label
            label = re.sub(CHECKBOX_ANY, '', segment).strip()
            
            # Clean up common artifacts
            label = re.sub(r'\s{3,}', ' ', label)  # Collapse wide spaces
            label = label.strip('[]')
            
            if label and len(label) > 1 and label.lower() not in YESNO_SET:
                options.append((label, None))
        
        if options:
            return options
    
    return []  # No options found
```

**Integration Point**: This function is called around line 750 in `parse_to_questions()`. No changes needed to call site.

---

## Fix 2: Orphaned Checkbox Association

### Current Code Issue
Checkboxes without immediate labels are skipped or create malformed entries.

### Proposed Enhancement

Add new helper function:

```python
def extract_orphaned_checkboxes_and_labels(current_line: str, next_line: str) -> List[Tuple[str, Optional[bool]]]:
    """
    When current line has checkboxes but minimal text,
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
```

**Integration in parse_to_questions()** (around line 750):

```python
# In main parsing loop, add before existing option harvesting:

# NEW: Check for orphaned checkboxes
if i + 1 < len(lines):
    orphaned_opts = extract_orphaned_checkboxes_and_labels(line, lines[i+1])
    if orphaned_opts:
        # Create dropdown or merge with existing condition collection
        if is_condition_block:  # If in medical history mode
            for (label, _) in orphaned_opts:
                options.append((label, None))
        else:
            # Create standalone dropdown
            title = "Please select all that apply:"
            key = slugify(title)
            control = {"options": [make_option(n, b) for n, b in orphaned_opts], "multi": True}
            questions.append(Question(key, title, cur_section, "dropdown", control=control))
        i += 2  # Skip both current and next line
        continue
```

---

## Fix 3: Enhanced Junk Text Filtering

### Current Code Issue
Multi-location footers and business addresses become form fields.

### Proposed Enhancement

In `scrub_headers_footers()` function (around line 250), add patterns:

```python
def scrub_headers_footers(text: str) -> List[str]:
    # ... existing code ...
    
    # NEW: Multi-location pattern detection
    MULTI_LOCATION_RE = re.compile(
        r'.*\b(Ave|Avenue|St|Street|Rd|Road|Blvd|Boulevard)\.?\b.*\b(Ave|Avenue|St|Street|Rd|Road|Blvd|Boulevard)\.?\b',
        re.I
    )
    
    # NEW: Multiple city-state-zip patterns
    CITY_STATE_ZIP_RE = re.compile(r',\s*[A-Z]{2}\s+\d{5}')
    
    # NEW: Business name patterns (multiple offices)
    OFFICE_NAMES_RE = re.compile(
        r'\b(dental|care|center|clinic|office|practice)\b.*\b(dental|care|center|clinic|office|practice)\b',
        re.I
    )
    
    keep = []
    for ln in lines:
        s = ln.strip()
        
        # Existing filters...
        if not s:
            keep.append(ln)
            continue
        if s in repeats or PAGE_NUM_RE.match(s):
            continue
        
        # NEW FILTERS:
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
        
        # Existing filters...
        if re.search(r"\bcontinued on back side\b", s, re.I):
            continue
        if re.search(r"\brev\s*\d{1,2}\s*/\s*\d{2}\b", s, re.I):
            continue
        if s in {"<<<", ">>>>"} or re.search(r"\bOC\d+\b", s):
            continue
        
        keep.append(ln)
    
    return keep
```

---

## Fix 4: "If yes, please explain" Follow-up Fields

### Current Code Issue
Follow-up fields not consistently created for Y/N questions with explanation prompts.

### Proposed Enhancement

In `parse_to_questions()`, after creating Y/N radio fields (around line 820):

```python
# After extracting compound Y/N prompts and creating radio fields:
for prompt_text in prompts:
    qkey = slugify(prompt_text)
    questions.append(Question(qkey, prompt_text, cur_section, "radio", 
                             control={"options": [{"name": "Yes", "value": True}, 
                                                 {"name": "No", "value": False}]}))
    
    # NEW: Check for follow-up explanation prompt
    # Look in current line or next line
    has_explanation_prompt = IF_GUIDANCE_RE.search(line)
    if not has_explanation_prompt and i + 1 < len(lines):
        has_explanation_prompt = IF_GUIDANCE_RE.search(lines[i+1])
    
    if has_explanation_prompt:
        # Create follow-up explanation field
        follow_up_key = qkey + "_explanation"
        follow_up_title = "Please explain"
        
        # Extract more specific prompt if available
        guidance_match = IF_GUIDANCE_RE.search(line) or IF_GUIDANCE_RE.search(lines[i+1] if i+1 < len(lines) else "")
        if guidance_match:
            guidance_text = guidance_match.group(0)
            if "explain" in guidance_text.lower():
                follow_up_title = guidance_text.strip().rstrip(':')
        
        questions.append(Question(
            follow_up_key,
            follow_up_title,
            cur_section,
            "input",
            control={"input_type": "text"}
        ))
        
        # Note: Conditional visibility would be added in JSON generation phase
        # by detecting the "_explanation" suffix pattern
```

---

## Fix 5: Better Line Coalescing

### Current Code Issue
Multi-line questions not properly joined when they span lines.

### Proposed Enhancement

In `coalesce_soft_wraps()` function (around line 300):

```python
def coalesce_soft_wraps(lines: List[str]) -> List[str]:
    # ... existing code ...
    
    # Enhanced logic for detecting line continuations:
    while i < len(lines):
        cur = lines[i].rstrip()
        
        # Start with current line
        merged = cur
        
        # NEW: More aggressive line continuation detection
        j = i + 1
        while j < len(lines):
            nxt = lines[j].strip()
            if not nxt:
                break
            
            # Continuation indicators:
            # 1. Current line ends with "/" or "-" (hyphenation)
            # 2. Current line ends without punctuation and next starts lowercase
            # 3. Current line appears incomplete (ends mid-phrase)
            # 4. Next line continues medical terminology
            
            ends_with_continuation = (
                cur.endswith('/') or 
                cur.endswith('-') or
                cur.endswith('or') or
                cur.endswith('and')
            )
            
            next_is_continuation = (
                nxt[0].islower() if nxt else False
            )
            
            ends_incomplete = (
                not cur.endswith(('.', '?', ':', ']')) and
                len(cur) > 20 and
                not re.search(r'\[\s*\]', cur[-10:])  # No checkbox at end
            )
            
            # Medical term continuation (common in forms)
            is_medical_continuation = (
                re.search(r'\b(containing|including|such as|e\.g\.|i\.e\.)\s*$', cur, re.I) or
                re.search(r'^\w+\s*\??\s*$', nxt)  # Single word/term on next line
            )
            
            should_merge = (
                ends_with_continuation or
                (next_is_continuation and ends_incomplete) or
                is_medical_continuation
            )
            
            if should_merge:
                # Merge with appropriate spacing
                if cur.endswith(('-', '/')):
                    merged = merged.rstrip('-/') + nxt
                else:
                    merged += ' ' + nxt
                cur = merged
                j += 1
            else:
                break
        
        out.append(merged)
        i = j
    
    return out
```

---

## Fix 6: Communication Preference Field Separation

### Current Code Issue
Opt-in checkboxes merged with contact fields.

### Proposed Enhancement

Add new regex pattern at top of file (around line 50):

```python
# NEW: Consent/opt-in checkbox pattern
CONSENT_CHECKBOX_RE = re.compile(
    r'\[\s*\]\s*(?:Yes|No)?,?\s+(send me|allow|consent|agree|authorize|opt.?in)',
    re.I
)
```

In `parse_to_questions()`, add special handling (around line 650):

```python
# After processing phone/email fields, check for consent checkbox on same line

# NEW: Split off consent checkboxes
consent_match = CONSENT_CHECKBOX_RE.search(line)
if consent_match:
    # Extract just the consent part
    consent_text = line[consent_match.start():]
    main_text = line[:consent_match.start()].strip()
    
    # Process main field first (if any)
    if main_text and ':' in main_text:
        # ... process as usual ...
        pass
    
    # Create separate consent checkbox
    consent_label = consent_match.group(0).strip('[]').strip()
    consent_key = slugify(consent_label)
    questions.append(Question(
        consent_key,
        consent_label,
        cur_section,
        "radio",
        control={"options": [{"name": "Yes", "value": True}, {"name": "No", "value": False}]}
    ))
    i += 1
    continue
```

---

## Fix 7: Enhanced Medical History Section Detection

### Proposed Enhancement

In `parse_to_questions()`, enhance condition block detection (around line 900):

```python
# When entering Medical/Dental History section:
if is_heading(line):
    section_candidate = collapse_spaced_caps(line.strip(": "))
    
    # NEW: Track if we're in condition collection mode
    is_medical_section = any(term in section_candidate.lower() 
                             for term in ['medical', 'dental', 'health history'])
    
    if is_medical_section:
        # Set flag for aggressive condition collection
        in_condition_mode = True
        condition_prompt = None

# When in condition mode:
if in_condition_mode:
    # Look for intro question
    if re.search(r'do you have.*following', line, re.I):
        condition_prompt = line.rstrip(':')
        condition_options = []
        # Start collecting ALL checkboxes until section ends
        continue
    
    # Collect checkboxes while in this mode
    opts = options_from_inline_line(line)
    orphaned = extract_orphaned_checkboxes_and_labels(line, lines[i+1] if i+1 < len(lines) else "")
    
    if opts or orphaned:
        condition_options.extend(opts if opts else orphaned)
        if orphaned:
            i += 1  # Skip next line if we used it
        continue
    
    # Exit condition mode on new section or after many blank lines
    if is_heading(line) or (not line.strip() and blank_count > 2):
        # Finalize condition dropdown
        if condition_options and len(condition_options) >= 5:
            key = "medical_conditions" if "medical" in cur_section.lower() else "dental_conditions"
            control = {"options": [make_option(n, b) for n, b in condition_options], "multi": True}
            questions.append(Question(key, condition_prompt or "Medical Conditions", cur_section, "dropdown", control=control))
        in_condition_mode = False
        condition_options = []
```

---

## Fix 8: Better Terms Field Detection

### Proposed Enhancement

Add new helper function:

```python
def should_be_terms_field(text: str) -> bool:
    """
    Detect if a paragraph should be a 'terms' field requiring agreement.
    """
    if len(text) < 150:  # Too short for terms
        return False
    
    # Count sentences
    sentence_ends = text.count('.') + text.count('!') + text.count('?')
    if sentence_ends < 3:  # Need multiple sentences
        return False
    
    # Look for consent language
    consent_keywords = [
        'i understand', 'i agree', 'i authorize', 'i consent',
        'i acknowledge', 'i certify', 'my responsibility',
        'i have read', 'to the best of my knowledge'
    ]
    
    text_lower = text.lower()
    consent_count = sum(1 for kw in consent_keywords if kw in text_lower)
    
    return consent_count >= 2  # Multiple consent phrases
```

In `parse_to_questions()` (around line 850):

```python
# NEW: Terms paragraph detection
if not line.strip().startswith('[') and len(line) > 100:
    # Collect multi-line paragraph
    para_lines = [line]
    j = i + 1
    while j < len(lines) and lines[j].strip() and not is_heading(lines[j]):
        para_lines.append(lines[j])
        j += 1
    
    full_para = ' '.join(para_lines)
    
    if should_be_terms_field(full_para):
        # Create terms field
        key = slugify(full_para[:50])
        questions.append(Question(
            key,
            "Terms",
            cur_section or "Consent",
            "terms",
            control={
                "agree_text": "I have read and agree to the terms.",
                "html_text": full_para
            }
        ))
        i = j
        continue
```

---

## Testing Strategy

1. **Unit Tests**: Test each helper function independently with mock data
2. **Integration Tests**: Run on all three sample forms from Archivev5.zip
3. **Regression Tests**: Ensure existing working forms don't break
4. **Manual Review**: Inspect JSON outputs for correctness

## Validation Checklist

- [ ] Grid checkboxes split into individual options
- [ ] Orphaned checkboxes associated with labels
- [ ] Multi-location footers filtered out
- [ ] Y/N questions create follow-up fields
- [ ] Multi-line questions properly joined
- [ ] Consent checkboxes separated from contact fields
- [ ] Medical conditions consolidated into single dropdown
- [ ] Long paragraphs become terms fields
- [ ] No regressions on existing forms

---

## Implementation Order

1. Fix 3 (junk filtering) - prevents bad data from entering pipeline
2. Fix 5 (line coalescing) - ensures proper line grouping early
3. Fix 1 (grid checkboxes) - improves option parsing
4. Fix 2 (orphaned checkboxes) - complements Fix 1
5. Fix 4 (follow-up fields) - enhances Y/N questions
6. Fix 7 (medical section) - leverages Fixes 1 & 2
7. Fix 6 (consent separation) - polishes contact fields
8. Fix 8 (terms fields) - final polish

Each fix is independent and can be implemented incrementally.
