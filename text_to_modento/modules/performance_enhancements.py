#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
performance_enhancements.py

Performance Recommendation Implementations:
- Recommendation 1: Dictionary expansion tracking
- Recommendation 2: Specialized consent form handling  
- Recommendation 3: Enhanced checkbox/radio detection
- Recommendation 4: OCR dependency validation (in unstructured_extract.py)
- Recommendation 5: Generic pattern templates (throughout codebase)

All implementations are form-agnostic and use generic patterns.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Set
from .question_parser import slugify, classify_input_type, clean_field_title


# ========== Constants ==========

# Dictionary expansion thresholds
DEFAULT_MIN_OCCURRENCES = 2  # Minimum times a field must appear to suggest dictionary addition

# Consent text detection thresholds
MIN_PROCEDURAL_TEXT_LENGTH = 40  # Minimum text length to consider for procedural consent
MIN_TEXT_LENGTH_FOR_TERM_CHECK = 100  # Minimum length for medical term density check
MIN_MEDICAL_TERMS = 3  # Minimum medical terms required per 100 chars for procedural text

# Consent consolidation thresholds
MIN_CONSENT_BUFFER_SIZE = 2  # Minimum number of consent fields to consolidate


# ========== Recommendation 1: Dictionary Expansion Tracking ==========

def track_unmatched_field_for_expansion(field: Dict, unmatched_tracker: Dict) -> None:
    """
    Track unmatched fields for potential dictionary expansion.
    
    This helps identify common fields across documents that should be
    added to the dictionary to improve match rates.
    
    Args:
        field: The field dictionary to track
        unmatched_tracker: Dictionary to accumulate unmatched field data
    """
    key = field.get('key', '')
    title = field.get('title', '')
    field_type = field.get('type', '')
    section = field.get('section', 'General')
    
    if not key or not title:
        return
    
    # Initialize tracking structure if needed
    if key not in unmatched_tracker:
        unmatched_tracker[key] = {
            'title': title,
            'type': field_type,
            'section': section,
            'count': 0,
            'documents': []
        }
    
    # Increment count
    unmatched_tracker[key]['count'] += 1


def suggest_dictionary_additions(unmatched_tracker: Dict, min_occurrences: int = DEFAULT_MIN_OCCURRENCES) -> List[Dict]:
    """
    Generate suggestions for fields to add to the dictionary.
    
    Fields that appear in multiple documents are good candidates for
    dictionary inclusion to improve future match rates.
    
    Args:
        unmatched_tracker: Accumulated unmatched field data
        min_occurrences: Minimum number of occurrences to suggest (default: 2)
        
    Returns:
        List of field definitions to potentially add to dictionary
    """
    suggestions = []
    
    for key, data in unmatched_tracker.items():
        if data['count'] >= min_occurrences:
            # Create a dictionary-ready field definition
            suggestion = {
                'key': key,
                'type': data['type'],
                'title': data['title'],
                'section': data['section'],
                'optional': False,  # Will be adjusted based on context
                'occurrence_count': data['count'],
                'suggested_priority': 'high' if data['count'] >= 5 else 'medium'
            }
            
            # Add control hints for specific types
            if data['type'] == 'date':
                suggestion['control'] = {'input_type': 'any'}
            elif data['type'] == 'input':
                suggestion['control'] = {'input_type': classify_input_type(data['title'])}
            
            suggestions.append(suggestion)
    
    # Sort by occurrence count (most common first)
    suggestions.sort(key=lambda x: x['occurrence_count'], reverse=True)
    
    return suggestions


# ========== Recommendation 2: Specialized Consent Form Handling ==========

def is_procedural_consent_text(text: str) -> bool:
    """
    Detect specialized procedural consent/instructional text that should
    be filtered or grouped differently.
    
    Targets: endodontic, implant, extraction, sedation consent forms.
    Uses generic patterns, not form-specific hardcoding.
    
    Args:
        text: Text to analyze
        
    Returns:
        True if text appears to be procedural consent/instruction
    """
    if len(text) < MIN_PROCEDURAL_TEXT_LENGTH:
        return False
    
    text_lower = text.lower()
    
    # Generic procedural patterns (form-agnostic)
    procedural_indicators = [
        # Treatment procedure descriptions
        r'\b(?:procedure|treatment|therapy|surgery|operation)\s+(?:involves|includes|consists\s+of|is|may)',
        r'\bthe\s+(?:procedure|treatment|therapy)\s+(?:will|may|can|should)',
        
        # Risk/complication descriptions  
        r'\b(?:risks?|complications?)\s+(?:include|may\s+include|are|can\s+be)',
        r'\b(?:possible|potential)\s+(?:risks?|complications?|side\s+effects)',
        r'\bmay\s+(?:result\s+in|cause|lead\s+to|experience)',
        
        # Success/failure statements
        r'\b(?:success\s+rate|no\s+guarantee|cannot\s+guarantee|alternatives?\s+(?:include|are))',
        r'\b(?:may|might)\s+(?:not|fail|be\s+unsuccessful)',
        
        # Detailed medical descriptions
        r'\b(?:tooth|teeth|gum|tissue|bone|nerve|jaw|sinus)\s+(?:may|will|can)\s+(?:be|need)',
        r'\b(?:anesthetic|anesthesia|medication|medicine)\s+(?:will|may)\s+be\s+(?:used|administered)',
    ]
    
    match_count = sum(1 for pattern in procedural_indicators if re.search(pattern, text_lower))
    
    # High confidence if multiple indicators
    if match_count >= 2:
        return True
    
    # Medium confidence - check for dense medical terminology
    medical_terms = [
        'anesthesia', 'anesthetic', 'sedation', 'extraction', 'implant',
        'periodontal', 'endodontic', 'prosthetic', 'restoration', 'surgical',
        'incision', 'sutures', 'healing', 'infection', 'swelling', 'bleeding'
    ]
    
    term_count = sum(1 for term in medical_terms if term in text_lower)
    
    # Procedural text typically has MIN_MEDICAL_TERMS+ medical terms per 100 chars
    if len(text) > MIN_TEXT_LENGTH_FOR_TERM_CHECK and term_count >= MIN_MEDICAL_TERMS:
        return True
    
    return False


def consolidate_procedural_consent_blocks(fields: List[Dict]) -> List[Dict]:
    """
    Consolidate multiple procedural consent paragraphs into organized blocks.
    
    Improves accuracy for specialized consent forms by reducing noise
    and creating more meaningful consent structures.
    
    Args:
        fields: List of field dictionaries
        
    Returns:
        Consolidated field list with procedural blocks grouped
    """
    if not fields:
        return fields
    
    result = []
    consent_buffer = []
    
    for field in fields:
        title = field.get('title', '')
        field_type = field.get('type', '')
        
        # Check if this is procedural consent text
        if is_procedural_consent_text(title) or field_type == 'terms':
            consent_buffer.append(field)
        else:
            # Flush buffer if we have consent fields
            if len(consent_buffer) >= MIN_CONSENT_BUFFER_SIZE:
                # Create consolidated consent block
                consolidated = create_procedural_consent_block(consent_buffer)
                result.append(consolidated)
                consent_buffer = []
            elif len(consent_buffer) == 1:
                # Single consent field, add as-is
                result.append(consent_buffer[0])
                consent_buffer = []
            
            # Add non-consent field
            result.append(field)
    
    # Flush remaining buffer
    if len(consent_buffer) >= MIN_CONSENT_BUFFER_SIZE:
        consolidated = create_procedural_consent_block(consent_buffer)
        result.append(consolidated)
    elif len(consent_buffer) == 1:
        result.append(consent_buffer[0])
    
    return result


def create_procedural_consent_block(fields: List[Dict]) -> Dict:
    """
    Create a consolidated procedural consent block from multiple fields.
    
    Args:
        fields: List of consent field dictionaries
        
    Returns:
        Single consolidated field
    """
    if len(fields) == 1:
        return fields[0]
    
    # Combine titles into HTML paragraphs
    paragraphs = [f['title'] for f in fields]
    html_content = '<p>' + '</p><p>'.join(paragraphs) + '</p>'
    
    # Use first field as base
    base_field = fields[0].copy()
    
    # Update with consolidated content
    base_field['type'] = 'terms'
    base_field['title'] = 'Procedure Information and Consent'
    base_field['key'] = 'procedure_consent'
    base_field['section'] = 'Consent'
    base_field['control'] = {
        'agree_text': 'I have read and understand the procedure information.',
        'html_text': html_content
    }
    
    return base_field


# ========== Recommendation 3: Enhanced Checkbox/Radio Detection ==========

def detect_inline_checkbox_options(line: str) -> Optional[Tuple[str, List[Dict]]]:
    """
    Enhanced detection of inline checkbox/radio options in a single line.
    
    Improvements:
    - Better handling of mixed checkbox and text
    - Detection of common option patterns (Yes/No, Gender, etc.)
    - Improved option extraction
    
    Args:
        line: Line to analyze
        
    Returns:
        Tuple of (field_label, options_list) or None if not detected
    """
    # Pattern 1: Label followed by multiple checkbox options
    # Example: "Gender: [ ] Male [ ] Female [ ] Other"
    pattern1 = r'^([^:\[\]]+?):\s*((?:\[\s*\]\s*\w+\s*)+)$'
    match1 = re.match(pattern1, line)
    
    if match1:
        label = match1.group(1).strip()
        options_text = match1.group(2).strip()
        
        # Extract options
        option_pattern = r'\[\s*\]\s*(\w+(?:\s+\w+)?)'
        option_matches = re.findall(option_pattern, options_text)
        
        if len(option_matches) >= 2:
            options = []
            for opt_name in option_matches:
                opt_value = opt_name.lower().replace(' ', '_')
                options.append({'name': opt_name, 'value': opt_value})
            
            return (label, options)
    
    # Pattern 2: Label with checkbox symbols (Unicode)
    # Example: "Marital Status: □ Single □ Married □ Divorced"
    pattern2 = r'^([^:\□☐\[\]]+?):\s*((?:[\□☐\[\]\s]+\w+\s*)+)$'
    match2 = re.match(pattern2, line)
    
    if match2:
        label = match2.group(1).strip()
        options_text = match2.group(2).strip()
        
        # Normalize checkbox symbols
        normalized = options_text.replace('□', '[ ]').replace('☐', '[ ]')
        
        # Extract options
        option_pattern = r'\[\s*\]\s*(\w+(?:\s+\w+)?)'
        option_matches = re.findall(option_pattern, normalized)
        
        if len(option_matches) >= 2:
            options = []
            for opt_name in option_matches:
                opt_value = opt_name.lower().replace(' ', '_')
                options.append({'name': opt_name, 'value': opt_value})
            
            return (label, options)
    
    # Pattern 3: No label, just options (use context-based label)
    # Example: "[ ] Yes [ ] No"
    pattern3 = r'^((?:\[\s*\]\s*\w+\s*)+)$'
    match3 = re.match(pattern3, line)
    
    if match3:
        options_text = match3.group(1).strip()
        
        option_pattern = r'\[\s*\]\s*(\w+)'
        option_matches = re.findall(option_pattern, options_text)
        
        if len(option_matches) >= 2:
            # Check for common Yes/No pattern
            option_set = {opt.lower() for opt in option_matches}
            
            if option_set == {'yes', 'no'}:
                options = [
                    {'name': 'Yes', 'value': True},
                    {'name': 'No', 'value': False}
                ]
                return ('Response', options)  # Generic label
            else:
                options = []
                for opt_name in option_matches:
                    opt_value = opt_name.lower().replace(' ', '_')
                    options.append({'name': opt_name, 'value': opt_value})
                
                return ('Selection', options)  # Generic label
    
    return None


def infer_radio_vs_checkbox(options: List[Dict], label: str = "") -> str:
    """
    Infer whether options should be radio (single select) or checkbox (multi-select).
    
    Args:
        options: List of option dictionaries
        label: Optional field label for context
        
    Returns:
        'radio' or 'checkbox'
    """
    label_lower = label.lower() if label else ""
    
    # Patterns that suggest single-select (radio)
    radio_indicators = [
        'gender', 'sex', 'marital', 'status', 'select one',
        'choose one', 'yes/no', 'yes or no'
    ]
    
    if any(indicator in label_lower for indicator in radio_indicators):
        return 'radio'
    
    # If only 2 options, likely radio (especially Yes/No)
    if len(options) == 2:
        option_names = {opt.get('name', '').lower() for opt in options}
        if option_names == {'yes', 'no'}:
            return 'radio'
    
    # Patterns that suggest multi-select (checkbox)
    checkbox_indicators = [
        'select all', 'check all', 'applies', 'conditions',
        'symptoms', 'allergies', 'medications'
    ]
    
    if any(indicator in label_lower for indicator in checkbox_indicators):
        return 'checkbox'
    
    # Default: If 3+ options, likely checkbox; 2 options likely radio
    return 'checkbox' if len(options) > 2 else 'radio'


def enhance_field_type_detection(field: Dict) -> Dict:
    """
    Enhanced field type detection with improved accuracy.
    
    Applies smarter heuristics to determine field types, especially
    for checkbox/radio fields.
    
    Args:
        field: Field dictionary to enhance
        
    Returns:
        Enhanced field dictionary
    """
    field_type = field.get('type', 'input')
    title = field.get('title', '')
    title_lower = title.lower()
    
    # Skip if already well-defined
    if field_type in ['block_signature', 'terms', 'date']:
        return field
    
    # Check for checkbox/radio patterns
    control = field.get('control', {})
    options = control.get('options', [])
    
    if options:
        # Already has options, refine the type
        correct_type = infer_radio_vs_checkbox(options, title)
        field['type'] = correct_type
        return field
    
    # Look for implicit checkbox/radio indicators in title
    if any(phrase in title_lower for phrase in ['yes [ ] no', '[ ] yes', 'check one:', 'select one:']):
        # Add Yes/No options
        field['type'] = 'radio'
        field['control'] = {
            'options': [
                {'name': 'Yes', 'value': True},
                {'name': 'No', 'value': False}
            ]
        }
        return field
    
    # Gender field detection
    if any(word in title_lower for word in ['gender', 'sex (m/f)', 'sex:']):
        field['type'] = 'radio'
        field['control'] = {
            'options': [
                {'name': 'Male', 'value': 'male'},
                {'name': 'Female', 'value': 'female'}
            ]
        }
        return field
    
    return field


# ========== Utility Functions ==========

def calculate_improvement_metrics(baseline: Dict, current: Dict) -> Dict:
    """
    Calculate improvement metrics between baseline and current performance.
    
    Args:
        baseline: Baseline performance metrics
        current: Current performance metrics
        
    Returns:
        Dictionary of improvement metrics
    """
    improvements = {}
    
    # Match rate improvement
    baseline_match = baseline.get('overall_match_rate', 0)
    current_match = current.get('overall_match_rate', 0)
    improvements['match_rate_delta'] = current_match - baseline_match
    improvements['match_rate_pct_change'] = (
        ((current_match - baseline_match) / baseline_match * 100) if baseline_match > 0 else 0
    )
    
    # Accuracy improvement
    baseline_acc = baseline.get('avg_accuracy', 0)
    current_acc = current.get('avg_accuracy', 0)
    improvements['accuracy_delta'] = current_acc - baseline_acc
    improvements['accuracy_pct_change'] = (
        ((current_acc - baseline_acc) / baseline_acc * 100) if baseline_acc > 0 else 0
    )
    
    # Field extraction improvement
    baseline_fields = baseline.get('total_items', 0)
    current_fields = current.get('total_items', 0)
    improvements['fields_delta'] = current_fields - baseline_fields
    
    # Dictionary coverage improvement
    baseline_matched = baseline.get('total_matched', 0)
    current_matched = current.get('total_matched', 0)
    improvements['matched_fields_delta'] = current_matched - baseline_matched
    
    return improvements
