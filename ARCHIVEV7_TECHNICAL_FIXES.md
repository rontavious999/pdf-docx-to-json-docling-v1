# Archivev7 Technical Fixes - Implementation Specifications

This document provides code-level specifications for implementing the fixes identified in the Archivev7 analysis.

---

## Fix 1: Split Multi-Question Lines

**Priority:** HIGH  
**Complexity:** MEDIUM  
**Files to Modify:** `llm_text_to_modento.py`  
**Functions:** `parse_to_questions()` - add preprocessing step

### Problem

Lines like this create no fields:
```
Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single [ ] Other:
```

### Solution

Add a preprocessing function to split multi-question lines before main parsing.

### Implementation

```python
def split_multi_question_line(line: str) -> List[str]:
    """
    Split lines containing multiple independent questions into separate lines.
    
    Example:
        Input:  "Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single"
        Output: ["Gender: [ ] Male [ ] Female", "Marital Status: [ ] Married [ ] Single"]
    
    Detection criteria:
    - Line contains 2+ patterns of "Label:" followed by checkboxes
    - Significant spacing (5+ spaces) between question segments
    - Each segment has at least one checkbox
    
    Returns:
        List of question strings (original line if no split needed)
    """
    # Pattern: Capitalized label followed by colon, then checkboxes
    # Look for significant spacing before next capitalized label
    
    # First, check if line has multiple question-like patterns
    question_pattern = r'([A-Z][^:]{2,30}:)\s*\[\s*\]'
    matches = list(re.finditer(question_pattern, line))
    
    if len(matches) < 2:
        # Single question or no recognizable questions
        return [line]
    
    # Check spacing between matches - need significant gaps
    segments = []
    for i, match in enumerate(matches):
        start_pos = match.start()
        
        # Determine end position (next match or EOL)
        if i + 1 < len(matches):
            # Check spacing before next match
            next_start = matches[i + 1].start()
            spacing = len(line[match.end():next_start]) - len(line[match.end():next_start].lstrip())
            
            # Need 5+ space gap to be considered separate questions
            if spacing < 5:
                continue  # Questions are too close, probably same question
            
            end_pos = next_start
        else:
            end_pos = len(line)
        
        segment = line[start_pos:end_pos].strip()
        
        # Validate segment has checkboxes
        if re.search(CHECKBOX_ANY, segment):
            segments.append(segment)
    
    # Return segments if we found multiple, otherwise original line
    return segments if len(segments) >= 2 else [line]


def preprocess_lines(lines: List[str]) -> List[str]:
    """
    Preprocess lines before main parsing.
    Currently handles: splitting multi-question lines.
    """
    processed = []
    for line in lines:
        # Skip empty lines
        if not line.strip():
            processed.append(line)
            continue
        
        # Try to split multi-question lines
        split_lines = split_multi_question_line(line)
        processed.extend(split_lines)
    
    return processed
```

### Integration Point

In `parse_to_questions()` function, add preprocessing step:

```python
def parse_to_questions(text: str, debug: bool = False) -> List[Question]:
    lines = scrub_headers_footers(text)
    lines = coalesce_soft_wraps(lines)
    
    # NEW: Preprocess to split multi-question lines
    lines = preprocess_lines(lines)
    
    section = "General"
    questions: List[Question] = []
    # ... rest of parsing logic
```

### Testing

Test cases:
1. `"Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single"`
   - Should create 2 separate questions
2. `"Status: [ ] Single [ ] Married"`
   - Should remain 1 question (no split needed)
3. `"First: [ ] A     Second: [ ] B     Third: [ ] C"`
   - Should create 3 questions

---

## Fix 2: Enhanced "If Yes" Detection and Follow-up Creation

**Priority:** MEDIUM  
**Complexity:** LOW-MEDIUM  
**Files to Modify:** `llm_text_to_modento.py`  
**Functions:** `extract_compound_yn_prompts()`, parsing logic in `parse_to_questions()`

### Problem

Lines like this should create a Yes/No question + conditional follow-up field, but don't:
```
Are you under a physician's care now? [ ] Yes [ ] No           If yes, please explain:
```

### Solution

Enhance detection pattern and ensure follow-up fields are created.

### Implementation

```python
# Add to regex patterns section (around line 33)
IF_YES_FOLLOWUP_RE = re.compile(
    r'(.+?)\s*\[\s*\]\s*Yes\s*\[\s*\]\s*No\s+If\s+yes[,:]?\s*(?:please\s+)?explain',
    re.I
)

# Alternative pattern for standalone "If yes" on same line
IF_YES_INLINE_RE = re.compile(
    r'(.+?)\s*\[\s*\]\s*Yes\s*\[\s*\]\s*No\s+If\s+yes',
    re.I
)


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
) -> List[Question]:
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
        key_base = normalize_key(question_text)
    
    # Main Yes/No question
    main_q = Question(
        key=key_base,
        qtype="radio",
        title=question_text,
        section=section,
        optional=False
    )
    main_q.options = [
        ("Yes", None),
        ("No", None)
    ]
    
    # Follow-up input field
    followup_q = Question(
        key=f"{key_base}_explanation",
        qtype="input",
        title="Please explain",
        section=section,
        optional=False
    )
    followup_q.input_type = "text"
    followup_q.hint = "Please provide details"
    
    # Add conditional - only show if main question is "yes"
    followup_q.conditional_on = [(key_base, "yes")]
    
    return [main_q, followup_q]
```

### Integration Point

In `parse_to_questions()`, when processing lines:

```python
# Check for Yes/No question with follow-up
question_text, has_followup = extract_yn_with_followup(line)

if question_text:
    if has_followup:
        # Create both question and follow-up
        new_questions = create_yn_question_with_followup(
            question_text,
            section
        )
        questions.extend(new_questions)
    else:
        # Create just the Yes/No question
        q = Question(...)
        # ... standard logic
        questions.append(q)
    
    i += 1
    continue
```

### Testing

Test cases:
1. `"Are you under a physician's care now? [ ] Yes [ ] No           If yes, please explain:"`
   - Should create 2 fields: radio + conditional input
2. `"Do you smoke? [ ] Yes [ ] No"`
   - Should create 1 field: radio only
3. `"Taking medications? Y or N If yes please explain"`
   - Should create 2 fields: radio + conditional input

---

## Fix 3: Consolidate Malformed Medical Conditions

**Priority:** HIGH  
**Complexity:** MEDIUM  
**Files to Modify:** `llm_text_to_modento.py`  
**Functions:** `postprocess_consolidate_medical_conditions()`

### Problem

npf1 creates 6 separate malformed medical condition dropdowns with nonsensical titles.

### Solution

Enhance the existing consolidation function to detect and merge malformed condition fields.

### Implementation

```python
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
        'anemia', 'glaucoma'
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
    Enhanced version that consolidates both well-formed and malformed condition dropdowns.
    """
    # Original logic for well-formed fields
    def looks_condition(opt_name: str) -> bool:
        opt_low = opt_name.lower()
        return any(tok in opt_low for tok in _COND_TOKENS)
    
    # Separate handling for malformed vs well-formed
    malformed_indices = []
    wellformed_groups_by_section: Dict[str, List[int]] = defaultdict(list)
    
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
                        'value': opt_value if opt_value else normalize_key(opt_name)
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
                name = o.get('name', '')
                if name and name not in seen:
                    merged.append(o)
                    seen.add(name)
        
        payload[keep]['control']['options'] = sorted(merged, key=lambda x: x.get('name', ''))
        payload[keep]['title'] = f"Do you have or have you had any of the following?"
        
        for i in sorted(groups[1:], reverse=True):
            payload.pop(i)
    
    return payload
```

### Testing

Test with npf1 form - should consolidate 6 malformed dropdowns into 1 or organized by category.

---

## Fix 4: Grid/Table Layout Detection (Advanced)

**Priority:** CRITICAL  
**Complexity:** HIGH  
**Files to Modify:** `llm_text_to_modento.py`  
**Functions:** New function `detect_and_parse_table()`, integration in `parse_to_questions()`

### Problem

Complex table layouts like this are parsed incorrectly:
```
Cancer               Endocrinology        Musculoskeletal      Respiratory
[ ] Type             [ ] Diabetes         [ ] Arthritis        [ ] Asthma
[ ] Chemotherapy     [ ] Hepatitis        [ ] Artificial       [ ] Emphysema
```

### Solution

Detect table structures and parse by column.

### Implementation

```python
def detect_table_layout(lines: List[str], start_idx: int, max_rows: int = 15) -> Optional[dict]:
    """
    Detect if lines starting at start_idx form a table layout.
    
    Returns:
        dict with table info if detected, None otherwise
        {
            'header_line': int,  # index of header line
            'data_lines': List[int],  # indices of data lines
            'num_columns': int,
            'column_positions': List[int]  # approximate column start positions
        }
    """
    if start_idx >= len(lines):
        return None
    
    # Look for header line: multiple capitalized words, evenly spaced
    header_line = lines[start_idx].strip()
    
    # Check if line looks like headers
    # Should have 3+ capitalized words with significant spacing
    capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', header_line)
    
    if len(capitalized_words) < 3:
        return None
    
    # Find column positions based on header words
    column_positions = []
    for word in capitalized_words:
        pos = header_line.find(word)
        if pos >= 0:
            column_positions.append(pos)
    
    # Check if next few lines have checkboxes aligned with these columns
    data_lines = []
    checkbox_pattern = re.compile(CHECKBOX_ANY)
    
    for i in range(start_idx + 1, min(start_idx + max_rows, len(lines))):
        line = lines[i]
        
        # Count checkboxes
        checkboxes = list(checkbox_pattern.finditer(line))
        
        if len(checkboxes) >= 2:
            # Check if checkboxes align roughly with column positions
            checkbox_positions = [cb.start() for cb in checkboxes]
            
            # Allow ±10 char tolerance for alignment
            aligned = 0
            for cb_pos in checkbox_positions:
                for col_pos in column_positions:
                    if abs(cb_pos - col_pos) <= 10:
                        aligned += 1
                        break
            
            if aligned >= 2:  # At least 2 checkboxes align
                data_lines.append(i)
        elif not line.strip():
            # Empty line might signal end of table
            break
        elif len(checkboxes) == 0 and data_lines:
            # No checkboxes and we've seen data lines = end of table
            break
    
    # Valid table if we found at least 2 data lines
    if len(data_lines) >= 2:
        return {
            'header_line': start_idx,
            'data_lines': data_lines,
            'num_columns': len(column_positions),
            'column_positions': column_positions,
            'headers': capitalized_words
        }
    
    return None


def parse_table_to_questions(
    lines: List[str],
    table_info: dict,
    section: str
) -> List[Question]:
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
                key=normalize_key(header),
                qtype="dropdown",
                title=f"{header} - Please mark any that apply",
                section=section,
                optional=False
            )
            q.options = options
            q.multi = True
            
            questions.append(q)
    
    return questions
```

### Integration Point

In `parse_to_questions()`, add table detection before normal line processing:

```python
def parse_to_questions(text: str, debug: bool = False) -> List[Question]:
    lines = scrub_headers_footers(text)
    lines = coalesce_soft_wraps(lines)
    lines = preprocess_lines(lines)
    
    section = "General"
    questions: List[Question] = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # NEW: Check for table layout
        table_info = detect_table_layout(lines, i)
        if table_info:
            # Parse entire table at once
            table_questions = parse_table_to_questions(lines, table_info, section)
            questions.extend(table_questions)
            
            # Skip past the table
            i = max(table_info['data_lines']) + 1
            continue
        
        # ... rest of normal line-by-line processing
```

### Testing

Test with:
1. npf1 medical conditions grid (lines 94-100)
2. npf1 dental history grid (lines 76-84)
3. Ensure simple inline checkboxes still work

---

## Fix 5: Enhanced Inline Options (Polish)

**Priority:** MEDIUM  
**Complexity:** LOW  
**Files to Modify:** `llm_text_to_modento.py`  
**Functions:** `options_from_inline_line()`

### Problem

Current function works for simple cases but could be more robust for edge cases.

### Solution

Add better spacing detection and cleanup.

### Implementation

```python
def options_from_inline_line(line: str) -> List[Tuple[str, Optional[bool]]]:
    """
    Enhanced to handle various inline checkbox formats.
    
    Works for:
    - [ ] Option1  [ ] Option2  [ ] Option3
    - [ ] Opt1    [ ] Opt2    [ ] Opt3  (wider spacing)
    - [x] Checked  [ ] Unchecked
    """
    # Try existing pattern first
    existing_matches = list(INLINE_CHOICE_RE.finditer(line))
    
    if existing_matches:
        options = []
        for m in existing_matches:
            txt = m.group(1).strip()
            if txt and txt.lower() not in YESNO_SET:
                # Try to determine if checked (basic heuristic)
                checked = None
                options.append((txt, checked))
        
        if options:
            return options
    
    # NEW: Manual extraction for edge cases
    # Find all checkboxes
    checkbox_matches = list(re.finditer(CHECKBOX_ANY, line))
    
    if len(checkbox_matches) >= 2:
        options = []
        
        for i, match in enumerate(checkbox_matches):
            # Extract text after this checkbox until next checkbox or EOL
            start = match.end()
            
            if i + 1 < len(checkbox_matches):
                end = checkbox_matches[i + 1].start()
            else:
                end = len(line)
            
            label = line[start:end].strip()
            
            # Clean up
            label = re.sub(r'\s{3,}', ' ', label)  # Collapse wide spaces
            label = label.strip('[]():,')
            
            # Skip if too short, empty, or looks like yes/no
            if len(label) < 2 or label.lower() in YESNO_SET:
                continue
            
            options.append((label, None))
        
        if len(options) >= 2:
            return options
    
    return []
```

---

## Testing Strategy

### Unit Tests

Create test cases for each fix:

```python
# test_fixes.py

def test_split_multi_question():
    line = "Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single"
    result = split_multi_question_line(line)
    assert len(result) == 2
    assert "Gender" in result[0]
    assert "Marital Status" in result[1]

def test_yn_with_followup():
    line = "Are you pregnant? [ ] Yes [ ] No If yes, please explain"
    question, has_followup = extract_yn_with_followup(line)
    assert question == "Are you pregnant?"
    assert has_followup == True

def test_malformed_condition_detection():
    field = {
        'type': 'dropdown',
        'title': 'Artificial Angina (chest Heart pain) Valve Thyroid Disease Neurological Anxiety',
        'control': {'multi': True, 'options': [...]}
    }
    assert is_malformed_condition_field(field) == True

# ... more tests
```

### Integration Tests

Run against actual forms:

```bash
# Test against Archivev7 forms
python llm_text_to_modento.py --in-dir /tmp/archivev7/output --out-dir /tmp/test_output

# Compare results
python compare_jsons.py /tmp/archivev7/JSONs /tmp/test_output
```

### Validation Checklist

After each fix:
- [ ] Chicago-Dental-Solutions: Gender/Marital fields present
- [ ] Chicago-Dental-Solutions: 4 "if yes" questions with follow-ups
- [ ] npf1: Medical conditions consolidated (1-5 fields instead of 6+)
- [ ] npf1: Dental history table parsed correctly
- [ ] All forms: No regression on working fields
- [ ] All forms: Junk filtering still works

---

## Implementation Order

1. **Fix 1** - Split multi-question lines (quick win)
2. **Fix 2** - Enhanced "if yes" detection (quick win)
3. **Fix 3** - Consolidate malformed conditions (high impact)
4. **Fix 4** - Grid/table detection (most complex, highest impact)
5. **Fix 5** - Polish inline options (optional enhancement)

---

## Notes

- All fixes use general patterns - no hard-coding
- Each fix is independent and can be tested separately
- Fixes are backwards-compatible with existing forms
- Start with simpler fixes to build confidence before tackling table detection
