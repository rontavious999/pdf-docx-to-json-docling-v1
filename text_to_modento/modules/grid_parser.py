"""
Multi-column grid detection and parsing.

This module handles detection and parsing of multi-column checkbox grids
and table layouts commonly found in medical/dental forms.

Functions:
- looks_like_grid_header - Detect grid header patterns
- detect_table_layout - Detect table structure
- parse_table_to_questions - Parse table rows into questions
- chunk_by_columns - Split line into columns
- detect_column_boundaries - Find column positions
- detect_multicolumn_checkbox_grid - Detect multi-column checkbox grids
- parse_multicolumn_checkbox_grid - Parse multi-column checkbox grids
- extract_text_for_checkbox - Extract text associated with checkboxes
- extract_text_only_items_at_columns - Extract text-only items at columns
"""

import re
from typing import List, Optional, Dict, TYPE_CHECKING

# Import from other modules
from .text_preprocessing import collapse_spaced_caps, is_heading
from .constants import CHECKBOX_ANY, CHECKBOX_MARK_RE
from .question_parser import clean_option_text

# Type hints for circular import - these are actually imported from core at runtime
if TYPE_CHECKING:
    from typing import Any as Question  # Placeholder for type checking
else:
    # These will be set by core.py after it imports this module
    # to avoid circular dependency issues
    Question = None
    make_option = None
    slugify = None
    
def _get_question_deps():
    """Get Question, make_option, slugify from core - called at runtime."""
    global Question, make_option, slugify
    if Question is None:
        from ..core import Question as Q, make_option as mo, slugify as slug
        Question, make_option, slugify = Q, mo, slug
    return Question, make_option, slugify
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
    Question, make_option, slugify = _get_question_deps()
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
    Archivev10 Fix 3 + Enhancement 3 + Category 1 Fix 1.4: Whitespace-Based Column Detection.
    
    Analyzes multiple lines to detect consistent column positions based on checkbox locations.
    Enhanced to be more robust with irregular spacing and partial column data.
    NEW: Uses clustering to better detect tightly-spaced columns.
    
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
        
        # Enhancement 3: Be more lenient - accept lines with just 1 checkbox
        # as they might be part of an irregular grid
        if len(checkboxes) >= 1:
            positions = [cb.start() for cb in checkboxes]
            all_positions.append(positions)
    
    if len(all_positions) < 2:
        return None
    
    # Category 1 Fix 1.4: Use clustering approach for better column detection
    # Flatten all positions and cluster them
    flat_positions = []
    for positions in all_positions:
        flat_positions.extend(positions)
    
    if not flat_positions:
        return None
    
    # Sort all positions
    flat_positions.sort()
    
    # Cluster positions that are within 3 chars of each other
    clusters = []
    current_cluster = [flat_positions[0]]
    
    for pos in flat_positions[1:]:
        if pos - current_cluster[-1] <= 3:
            # Add to current cluster
            current_cluster.append(pos)
        else:
            # Start new cluster
            clusters.append(current_cluster)
            current_cluster = [pos]
    
    # Don't forget the last cluster
    if current_cluster:
        clusters.append(current_cluster)
    
    # For each cluster, compute the median position (more robust than mean)
    # and count how many lines contributed to this cluster
    cluster_info = []
    for cluster in clusters:
        median_pos = sorted(cluster)[len(cluster) // 2]  # Median
        # Count how many different lines contributed to this cluster
        line_contributions = set()
        for line_idx, positions in enumerate(all_positions):
            if any(abs(pos - median_pos) <= 3 for pos in positions):
                line_contributions.add(line_idx)
        
        # Calculate support (percentage of lines with checkbox at this position)
        support = len(line_contributions) / len(all_positions)
        cluster_info.append((median_pos, support, len(cluster)))
    
    # Filter clusters by support (at least 50% of lines should have it)
    # Lower threshold from 60% to 50% to catch more columns in sparse grids
    consistent_positions = [
        pos for pos, support, count in cluster_info 
        if support >= 0.5
    ]
    
    # Need at least 3 consistent columns
    if len(consistent_positions) >= 3:
        return sorted(consistent_positions)
    
    # Category 1 Fix 1.4: Fallback - if we have 2 columns with high support, accept it
    # This helps with simple 2-column grids
    if len(consistent_positions) == 2:
        # Check if both have strong support (>=70%)
        strong_columns = [
            pos for pos, support, count in cluster_info 
            if support >= 0.7
        ]
        if len(strong_columns) >= 2:
            return sorted(strong_columns)
    
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
    
    # Priority 2.2: Capture category headers if present
    category_header = None
    
    # If first line doesn't have checkboxes, look ahead (might be category headers)
    if len(checkboxes) < 3 and start_idx + 3 < len(lines):
        # Check if the first line might be a category header
        first_line_text = lines[start_idx].strip()
        if first_line_text and len(first_line_text.split()) <= 6:
            # Might be a category header - look for slashes, pipes, or multiple spaced words
            if '/' in first_line_text or '|' in first_line_text or re.search(r'\s{3,}', first_line_text):
                category_header = first_line_text
        
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
        result = {
            'start_line': start_idx,
            'first_data_line': first_data_line_idx,
            'data_lines': data_lines,
            'num_columns': len(column_positions),
            'column_positions': column_positions,
            'section': section
        }
        # Priority 2.2: Include category header if found
        if category_header:
            result['category_header'] = category_header
        return result
    
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
    Priority 2.2: Uses category headers to prefix option names when available.
    """
    Question, make_option, slugify = _get_question_deps()
    data_lines = grid_info['data_lines']
    column_positions = grid_info['column_positions']
    section = grid_info['section']
    
    # Priority 2.2: Parse category headers if present
    category_headers = None
    if 'category_header' in grid_info:
        category_header_text = grid_info['category_header']
        # Parse headers (separated by slashes, pipes, or significant spacing)
        if '/' in category_header_text:
            category_headers = [h.strip() for h in category_header_text.split('/')]
        elif '|' in category_header_text:
            category_headers = [h.strip() for h in category_header_text.split('|')]
        else:
            # Split by 3+ spaces
            category_headers = [h.strip() for h in re.split(r'\s{3,}', category_header_text) if h.strip()]
        
        if debug and category_headers:
            print(f"  [debug] grid category headers: {category_headers}")
    
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
            
            # Priority 2.2: Prefix with category header if available
            # Patch 1: Relax strict length check to handle headers spanning multiple columns
            if category_headers and len(category_headers) > 0:
                # Determine which column this checkbox is in
                # Find the closest column position to this checkbox
                col_idx = 0
                min_distance = abs(cb_pos - column_positions[0])
                for idx, col_pos in enumerate(column_positions):
                    distance = abs(cb_pos - col_pos)
                    if distance < min_distance:
                        min_distance = distance
                        col_idx = idx
                
                # Use the closest available header (handle cases where headers < columns)
                header_idx = min(col_idx, len(category_headers) - 1)
                if header_idx >= 0 and category_headers[header_idx]:
                    item_text = f"{category_headers[header_idx]} - {item_text}"
            
            all_options.append((item_text, None))
        
        # Archivev11 Fix 2: Also look for text-only items at column positions
        # Only do this for lines that have fewer checkboxes than expected columns
        if len(checkboxes) < len(column_positions):
            text_only_items = extract_text_only_items_at_columns(line, column_positions, checkbox_positions)
            for item in text_only_items:
                if debug:
                    print(f"    [debug] text-only item at line {line_idx}: '{item}'")
                
                # Patch 1: Apply category prefix to text-only items as well
                if category_headers and len(category_headers) > 0:
                    # Find which column this text item is in (approximate based on position)
                    # Since we don't have exact position, use the item's index in the list
                    # This is a best-effort approach for text-only items
                    text_col_idx = len(all_options) % len(column_positions) if column_positions else 0
                    header_idx = min(text_col_idx, len(category_headers) - 1)
                    if header_idx >= 0 and category_headers[header_idx]:
                        item = f"{category_headers[header_idx]} - {item}"
                
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


def detect_medical_conditions_grid(lines: List[str], start_idx: int, debug: bool = False) -> Optional[dict]:
    """
    Improvement 4: Detect medical history checkbox grids with multiple columns.
    
    Pattern:
    - Question line: "Do you have, or have you had..."
    - Multiple lines with inline checkboxes
    - Typically 20-50+ options across 2-3 columns
    
    Args:
        lines: List of text lines
        start_idx: Starting index to check
        debug: Enable debug output
    
    Returns:
        dict with grid info if detected, None otherwise
        {
            'title': 'Medical Conditions',
            'options': [{'name': 'Chest Pains', 'value': 'chest_pains'}, ...],
            'layout': 'multicolumn',
            'end_idx': int  # Index where grid ends
        }
    """
    _get_question_deps()  # Ensure dependencies are loaded
    
    if start_idx >= len(lines):
        return None
    
    # Check for medical condition question pattern
    question_patterns = [
        r'do\s+you\s+have.*(?:or\s+have\s+you\s+had).*(?:any\s+of\s+the\s+following|conditions)',
        r'medical\s+(?:history|conditions)',
        r'health\s+(?:history|conditions)',
        r'have\s+you\s+(?:ever\s+)?had\s+any\s+of\s+the\s+following',
    ]
    
    first_line = lines[start_idx].lower()
    matched_pattern = False
    for pattern in question_patterns:
        if re.search(pattern, first_line):
            matched_pattern = True
            break
    
    if not matched_pattern:
        return None
    
    if debug:
        print(f"  [debug] detect_medical_conditions_grid: Found question pattern at line {start_idx}")
    
    # Collect all checkbox lines that follow
    checkbox_lines = []
    i = start_idx + 1
    max_lines = min(len(lines), start_idx + 30)  # Max 30 lines to check
    
    while i < max_lines:
        line = lines[i]
        line_stripped = line.strip()
        
        if re.search(CHECKBOX_ANY, line):
            checkbox_lines.append((i, line))
        elif line_stripped and not is_heading(line_stripped):
            # Check if this is still part of the grid or a new section
            # If we've collected checkboxes and now see non-checkbox text, might be done
            if len(checkbox_lines) >= 5:
                # Check if it's just descriptive text between options
                if len(line_stripped) > 50:  # Long text likely not an option
                    break
            elif len(checkbox_lines) > 0 and len(line_stripped) > 30:
                # Short grid but hit substantial text - stop
                break
        i += 1
    
    if len(checkbox_lines) < 5:  # Minimum threshold for medical grid
        if debug:
            print(f"  [debug] detect_medical_conditions_grid: Only {len(checkbox_lines)} checkbox lines, need 5+")
        return None
    
    if debug:
        print(f"  [debug] detect_medical_conditions_grid: Found {len(checkbox_lines)} checkbox lines")
    
    # Extract all options using Improvement 7's enhanced extraction
    options = []
    seen_options = set()  # Deduplicate
    
    for line_idx, line in checkbox_lines:
        # Use Improvement 7: extract_clean_checkbox_options for better option parsing
        clean_options = extract_clean_checkbox_options(line)
        
        for option_text in clean_options:
            # Skip if empty
            if not option_text or len(option_text) < 2:
                continue
            
            # NEW Improvement 5: Enhanced deduplication with normalization
            # Normalize: lowercase, replace slashes with space, remove punctuation, normalize whitespace
            normalized = option_text.lower().replace('/', ' ')  # Treat slashes as space
            normalized = re.sub(r'[^\w\s]', '', normalized).strip()
            normalized = ' '.join(normalized.split())  # Normalize whitespace
            
            if normalized in seen_options:
                if debug:
                    print(f"  [debug] Skipping duplicate condition: '{option_text}'")
                continue
            
            seen_options.add(normalized)
            options.append({
                'name': option_text,
                'value': slugify(option_text)
            })
    
    if len(options) < 5:  # Need meaningful number of options
        if debug:
            print(f"  [debug] detect_medical_conditions_grid: Only {len(options)} valid options extracted")
        return None
    
    # Extract title from first line
    title_line = lines[start_idx].strip()
    # Remove trailing punctuation
    title = title_line.rstrip(':?.').strip()
    
    # If title is too long (>100 chars), shorten it
    if len(title) > 100:
        title = "Medical Conditions"
    
    if debug:
        print(f"  [debug] detect_medical_conditions_grid: SUCCESS - extracted {len(options)} options")
        print(f"  [debug]   Title: {title}")
        print(f"  [debug]   Sample options: {[o['name'] for o in options[:5]]}")
    
    return {
        'title': title,
        'options': options,
        'layout': 'multicolumn',
        'end_idx': checkbox_lines[-1][0] if checkbox_lines else start_idx + 1,
        'type': 'dropdown',
        'multi': True
    }


def extract_clean_checkbox_options(line: str) -> List[str]:
    """
    Improvement 7: Extract clean option text from line with multiple checkboxes.
    
    Handles:
    - Adjacent checkboxes: "[ ] Option1 [ ] Option2"
    - Slash-separated: "[ ] Opt1/Opt2" → separate options
    - Repeated words (OCR errors): "Blood Blood Transfusion" → "Blood Transfusion"
    - Truncates long options to first 3-5 words
    
    Args:
        line: Line containing checkboxes and option text
    
    Returns:
        List of clean option strings
    """
    # Split by checkbox markers
    parts = re.split(CHECKBOX_ANY, line)
    
    options = []
    for i, part in enumerate(parts[1:], 1):  # Skip text before first checkbox
        text = part.strip()
        
        if not text:
            continue
        
        # Text between this checkbox and next (if exists)
        if i < len(parts) - 1:
            # Look ahead to find where next checkbox would be
            # Search for checkbox marker patterns in the text
            next_checkbox_pos = len(text)
            
            # Check for explicit checkbox characters
            for marker in ['□', '☐', '☑', '■', '❒', '◻', '✓', '✔']:
                pos = text.find(marker)
                if pos > 0:
                    next_checkbox_pos = min(next_checkbox_pos, pos)
            
            # Check for bracket patterns like [ ] or [x]
            bracket_match = re.search(r'\[[\sx]\]', text)
            if bracket_match and bracket_match.start() > 0:
                next_checkbox_pos = min(next_checkbox_pos, bracket_match.start())
            
            # Also check for "!" which is sometimes used as checkbox
            excl_pos = text.find('!')
            if excl_pos > 5:  # Only if not at the start (might be part of text)
                next_checkbox_pos = min(next_checkbox_pos, excl_pos)
            
            text = text[:next_checkbox_pos].strip()
        
        # Clean the extracted text
        if text:
            # Remove duplicate words (common OCR error)
            # Example: "Blood Blood Transfusion" → "Blood Transfusion"
            words = text.split()
            clean_words = []
            for word in words:
                if not clean_words or word.lower() != clean_words[-1].lower():
                    clean_words.append(word)
            text = ' '.join(clean_words)
            
            # Handle slash-separated options (but not URLs or file paths)
            # Example: "Arthritis/Gout" should become two options
            # But "AIDS/HIV Positive" or "Heart Attack/Failure" should stay as one
            if '/' in text and len(text.split('/')) == 2 and not text.startswith('http'):
                # Only split if BOTH parts are exactly single words (no spaces)
                sub_parts = text.split('/')
                if all(len(p.strip().split()) == 1 for p in sub_parts):
                    # Also check that both parts are capitalized (medical condition names)
                    if all(p.strip() and p.strip()[0].isupper() for p in sub_parts):
                        # Split into multiple options
                        sub_opts = [s.strip() for s in sub_parts if s.strip()]
                        options.extend(sub_opts)
                        continue
            
            # Take first 3-5 words as option name (medical conditions are typically short)
            # But keep full text if it's already short
            words = text.split()
            if len(words) <= 5:
                option_text = text
            else:
                # For longer text, take first 5 words
                option_text = ' '.join(words[:5])
            
            # Apply clean_option_text for final cleanup
            option_text = clean_option_text(option_text)
            
            if option_text and len(option_text) >= 2:
                options.append(option_text)
    
    return options

