#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
field_detection.py

Advanced field detection and splitting for form parsing.
Implements improvements for achieving 100% parity.

Improvements implemented:
- Improvement #1: Parse combined registration/insurance blocks
- Improvement #2: Multi-sub-field label splitting (enhanced)
- Improvement #7: Smart field type detection
- Improvement #8: Enhanced checkbox/radio detection
- Improvement #14: Handle "Other:" specify fields
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from .question_parser import slugify, classify_input_type, clean_field_title


# ========== Improvement #1: Parse Combined Registration/Insurance Blocks ==========

def split_colon_delimited_fields(line: str) -> List[Dict]:
    """
    Split lines with multiple 'Label:' patterns into separate fields.
    
    Improvement #1: Handles insurance/registration blocks like:
    "Name of Insurance Company: State: Policy Holder Name: Birth Date#: / /"
    
    Enhanced to handle long concatenated form lines with many fields.
    
    Args:
        line: Input line with multiple colon-separated labels
        
    Returns:
        List of field dictionaries, or empty list if not applicable
    """
    # Only process lines that look like they have multiple fields
    # Need at least 2 colons and reasonable length
    if line.count(':') < 2 or len(line) < 40:
        return []
    
    # Avoid splitting if line starts as a question or statement
    if re.match(r'^(I|You|We|The)\s', line):
        return []
    
    # Improved pattern: Capitalized words (possibly multi-word) followed by colon
    # This pattern better handles underscores and blanks between labels
    # Matches: "Name:", "Birth Date:", "Member ID:", "SS#:"
    # Uses non-greedy matching and excludes long underscore sequences
    pattern = r'([A-Z][A-Za-z\s/#\.\-]{1,45}?):\s*'
    
    matches = list(re.finditer(pattern, line))
    
    # Need at least 2 matches to split
    if len(matches) < 2:
        return []
    
    fields = []
    for i, match in enumerate(matches):
        label_raw = match.group(1).strip()
        
        # Clean up label: remove trailing underscores and excess whitespace
        # "Nickname_____________" -> "Nickname"
        label = re.sub(r'[_\s]+$', '', label_raw).strip()
        
        # Skip very short labels (likely not field labels)
        if len(label) < 2:
            continue
            
        # Extract value area (text between this label and next, or to end)
        start_pos = match.end()
        if i < len(matches) - 1:
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(line)
        
        value_area = line[start_pos:end_pos].strip()
        
        # Skip if this looks like a continuation word rather than field label
        label_lower = label.lower()
        skip_words = ['or', 'and', 'if', 'of the', 'to', 'for', 'from', 'with', 'by']
        if label_lower in skip_words:
            continue
        
        # Skip labels that are likely part of questions rather than field labels
        # e.g., "What is your preferred method of contact?"
        if '?' in label or label_lower.startswith(('what', 'who', 'when', 'where', 'why', 'how')):
            continue
        
        # Create field with inferred type
        field = create_field_from_label(label, value_area)
        if field:
            fields.append(field)
    
    return fields if len(fields) >= 2 else []


def create_field_from_label(label: str, value_hint: str = "") -> Optional[Dict]:
    """
    Create a field dictionary from a label, inferring the appropriate type.
    
    Improvement #7: Smart field type detection
    
    Args:
        label: The field label/title
        value_hint: Optional value area text for additional context
        
    Returns:
        Field dictionary or None if invalid
    """
    if not label or len(label) < 2:
        return None
    
    # Clean and normalize label
    clean_label = clean_field_title(label)
    label_lower = label.lower()
    value_lower = value_hint.lower() if value_hint else ""
    
    # Infer field type based on label and value hints
    field_type, control = infer_field_type_from_label(label, value_hint)
    
    # Generate key from label
    key = slugify(clean_label)
    
    field = {
        "key": key,
        "type": field_type,
        "title": clean_label,
        "section": "General",  # Will be updated during section inference
        "optional": False,
        "value_area": value_hint,  # Store value area for potential sub-field extraction
    }
    
    if control:
        field["control"] = control
    
    return field


# ========== Improvement #7: Smart Field Type Detection ==========

def infer_field_type_from_label(label: str, value_hint: str = "") -> Tuple[str, Optional[Dict]]:
    """
    Infer appropriate field type and control from label and value hint.
    
    Improvement #7: Comprehensive type inference
    
    Returns:
        Tuple of (field_type, control_dict)
    """
    label_lower = label.lower()
    value_lower = value_hint.lower() if value_hint else ""
    
    # Date fields
    if any(word in label_lower for word in ['date', 'birth', 'dob', 'birthday', 'born']):
        return ('date', {'input_type': 'any'})
    
    # Phone fields
    if any(word in label_lower for word in ['phone', 'mobile', 'cell', 'tel', 'telephone', 'fax']):
        return ('input', {'input_type': 'phone', 'phone_prefix': '+1'})
    
    # Email fields
    if 'email' in label_lower or '@' in value_hint:
        return ('input', {'input_type': 'email', 'hint': 'joe@example.com'})
    
    # SSN/ID fields
    if any(pattern in label_lower for pattern in ['ssn', 'social security', 'ss#', 'soc sec', 'member id', 'policy id', 'id number']):
        # Check if it looks like a general ID vs SSN
        if 'social' in label_lower or 'ssn' in label_lower or 'ss#' in label_lower:
            return ('input', {'input_type': 'ssn'})
        else:
            return ('input', {'input_type': 'text'})
    
    # Name fields
    if any(word in label_lower for word in ['name', 'first', 'last', 'middle', 'full name', 'patient name']):
        return ('input', {'input_type': 'name'})
    
    # Address fields
    if any(word in label_lower for word in ['address', 'street', 'apt', 'city', 'state', 'zip', 'postal']):
        return ('input', {'input_type': 'address' if 'address' in label_lower else 'text'})
    
    # Employer/Occupation
    if any(word in label_lower for word in ['employer', 'occupation', 'job', 'work']):
        return ('input', {'input_type': 'text'})
    
    # Group/Policy numbers
    if any(word in label_lower for word in ['group', 'policy', 'plan', 'member']):
        if any(word in label_lower for word in ['number', '#', 'no.', 'id']):
            return ('input', {'input_type': 'text'})
    
    # Radio/checkbox hints in value
    if value_hint and any(symbol in value_hint for symbol in ['[ ]', '□', '!', '☐']):
        # Extract options from value hint
        options = extract_options_from_text(value_hint)
        if options:
            # Check if it's yes/no or multiple options
            if len(options) == 2 and set([o.lower() for o in options]) == {'yes', 'no'}:
                return ('radio', {
                    'options': [
                        {'name': 'Yes', 'value': True},
                        {'name': 'No', 'value': False}
                    ]
                })
            else:
                # Multi-option radio or checkbox
                return ('radio', {
                    'options': [{'name': opt, 'value': opt.lower().replace(' ', '_')} for opt in options]
                })
    
    # Relationship fields - typically radio
    if 'relationship' in label_lower:
        return ('radio', {
            'options': [
                {'name': 'Self', 'value': 'self'},
                {'name': 'Spouse', 'value': 'spouse'},
                {'name': 'Parent', 'value': 'parent'},
                {'name': 'Child', 'value': 'child'},
                {'name': 'Other', 'value': 'other'}
            ]
        })
    
    # Gender fields
    if 'gender' in label_lower or 'sex' in label_lower:
        return ('radio', {
            'options': [
                {'name': 'Male', 'value': 'male'},
                {'name': 'Female', 'value': 'female'}
            ]
        })
    
    # Marital status
    if 'marital' in label_lower:
        return ('radio', {
            'options': [
                {'name': 'Married', 'value': 'married'},
                {'name': 'Single', 'value': 'single'},
                {'name': 'Divorced', 'value': 'divorced'},
                {'name': 'Widowed', 'value': 'widowed'}
            ]
        })
    
    # Default: text input
    return ('input', {'input_type': 'text'})


# ========== Improvement #8: Enhanced Checkbox/Radio Detection ==========

def extract_options_from_text(text: str) -> List[str]:
    """
    Extract option names from text with checkboxes/radio symbols.
    
    Improvement #8: Enhanced checkbox detection
    """
    # Normalize checkbox symbols
    normalized = normalize_checkbox_symbols(text)
    
    # Pattern: checkbox symbol followed by text
    pattern = r'\[\s*\]\s*([A-Za-z][A-Za-z0-9\s\-]+?)(?=\s*\[\s*\]|$|:)'
    matches = re.findall(pattern, normalized)
    
    # Clean up options
    options = [opt.strip() for opt in matches if len(opt.strip()) > 1]
    
    return options[:10]  # Reasonable limit


def normalize_checkbox_symbols(text: str) -> str:
    """
    Normalize various checkbox symbols to standard [ ] format.
    
    Improvement #8: Symbol normalization
    """
    # Replace various checkbox symbols with standard format
    symbols = {
        '□': '[ ]',
        '☐': '[ ]',
        '☑': '[x]',
        '■': '[x]',
        '✓': '[x]',
        '✔': '[x]',
        '✗': '[ ]',
        '✘': '[ ]',
        '!': '[ ]',  # Common in some forms
    }
    
    result = text
    for symbol, replacement in symbols.items():
        result = result.replace(symbol, replacement)
    
    return result


# ========== Improvement #2: Enhanced Multi-Sub-Field Label Splitting ==========

def split_multi_subfield_line(line: str) -> List[Dict]:
    """
    Enhanced splitting for patterns like "Phone: Mobile ___ Home ___ Work ___".
    
    Improvement #2: Multi-sub-field label splitting
    
    This enhances the existing implementation to handle more patterns.
    """
    # Pattern 1: "MainLabel: SubLabel1___ SubLabel2___ SubLabel3___"
    # Example: "Phone: Mobile_______ Home_______ Work_______"
    pattern1 = r'^([A-Z][^:]+):\s*(.+)$'
    match1 = re.match(pattern1, line)
    
    if match1:
        main_label = match1.group(1).strip()
        rest = match1.group(2).strip()
        
        # Look for sublabels before blanks
        # Pattern: Word followed by underscores or blanks
        subfield_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[_\s]{3,}'
        subfields = re.findall(subfield_pattern, rest)
        
        if len(subfields) >= 2:
            fields = []
            main_lower = main_label.lower()
            
            for sublabel in subfields:
                # Combine main and sub label
                full_label = f"{main_label} - {sublabel}" if main_lower not in ['phone', 'email', 'address'] else sublabel
                
                field = create_field_from_label(full_label, "")
                if field:
                    # Adjust key to include both parts
                    field['key'] = slugify(f"{main_label}_{sublabel}")
                    fields.append(field)
            
            if len(fields) >= 2:
                return fields
    
    # Pattern 2: "Label (Type1)___ (Type2)___ (Type3)___"
    # Example: "Insurance (Primary)___ (Secondary)___"
    pattern2 = r'^([A-Z][^(]+)\s*(.+)$'
    match2 = re.match(pattern2, line)
    
    if match2:
        main_label = match2.group(1).strip().rstrip(':')
        rest = match2.group(2).strip()
        
        # Look for parenthetical types
        type_pattern = r'\(([^)]+)\)\s*[_\s]{3,}'
        types = re.findall(type_pattern, rest)
        
        if len(types) >= 2:
            fields = []
            for type_label in types:
                full_label = f"{main_label} ({type_label})"
                field = create_field_from_label(full_label, "")
                if field:
                    field['key'] = slugify(f"{main_label}_{type_label}")
                    fields.append(field)
            
            if len(fields) >= 2:
                return fields
    
    return []


# ========== Improvement #14: Handle "Other:" Specify Fields ==========

def is_other_specify_field(label: str, parent_label: str = "") -> bool:
    """
    Detect if a field is an "Other:" specify field that should be conditional.
    
    Improvement #14: Proper handling of "Other" fields
    """
    label_lower = label.lower().strip()
    
    # Check if it's just "Other" or "Other:" with optional blank
    if label_lower in ['other', 'other:', 'other specify', 'please specify']:
        return True
    
    # Check if starts with "other"
    if label_lower.startswith('other') and len(label_lower) < 30:
        return True
    
    return False


def should_split_line_into_fields(line: str) -> bool:
    """
    Determine if a line should be split into multiple fields.
    
    Returns True if the line contains multiple field indicators.
    """
    # Check for multiple colon patterns
    if line.count(':') >= 2:
        # Verify they look like field labels, not sentences
        # Don't reject based on '?' if there are many colons (>= 5) - likely a form line with a question embedded
        if line.count(':') >= 5:
            return True
        # For fewer colons, check if it starts like a question/statement
        if not re.match(r'^(I|You|We|The)\s', line):
            return True
    
    # Check for multi-subfield patterns
    if re.search(r'[A-Z][a-z]+\s*[_\s]{3,}[A-Z][a-z]+\s*[_\s]{3,}', line):
        return True
    
    return False
