#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consent_handler.py

Consent and terms block detection and grouping.

Improvements implemented:
- Improvement #9: Consent block detection and grouping
- Improvement #10: Risk/complication list parsing
- Improvement #11: Consistent signature block handling
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# ========== Improvement #9: Consent Block Detection and Grouping ==========

CONSENT_SECTION_HEADERS = [
    'informed consent',
    'patient consent',
    'consent for treatment',
    'acknowledgment',
    'patient acknowledgment',
    'risks and complications',
    'possible risks',
    'potential complications',
    'treatment risks',
    'patient responsibilities',
    'financial responsibility',
    'insurance information',
    'payment policy',
    'notice of privacy',
    'hipaa',
    'authorization',
    'release of information',
]

CONSENT_INDICATORS = [
    r'\bi\s+(?:hereby\s+)?(?:certify|acknowledge|consent|agree|understand|authorize|give\s+permission)',
    r'\bpatient\s+(?:acknowledges?|consents?|agrees?)',
    r'\bby\s+signing\s+(?:this|below)',
    r'\bi\s+have\s+(?:read|been\s+informed|received)',
    r'\bto\s+the\s+best\s+of\s+my\s+knowledge',
    r'\bi\s+give\s+(?:my\s+)?consent',
    r'\bpossible\s+(?:risks?|complications?|side\s+effects)',
    r'\bmay\s+(?:include|result\s+in|cause)',
    r'\btreatment\s+(?:may|can|could)',
]


def is_consent_paragraph(text: str) -> bool:
    """
    Detect if a paragraph is consent/legal text.
    
    Improvement #9: Consent detection
    """
    if len(text) < 50:
        return False
    
    text_lower = text.lower()
    
    # Count consent indicators
    match_count = sum(1 for pattern in CONSENT_INDICATORS if re.search(pattern, text_lower))
    
    # Strong signal if multiple indicators
    if match_count >= 2:
        return True
    
    # Check for strong single indicators at start
    for pattern in CONSENT_INDICATORS[:6]:
        if re.match(r'^\s*' + pattern, text_lower):
            return True
    
    return False


def is_consent_section_header(line: str) -> bool:
    """
    Detect if a line is a consent section header.
    
    Improvement #9: Section header detection
    """
    line_lower = line.lower().strip()
    
    # Exact or close match
    for header in CONSENT_SECTION_HEADERS:
        if header in line_lower:
            return True
    
    # Pattern-based detection
    if len(line) < 60 and ':' not in line:
        # Short line without colon might be header
        if any(word in line_lower for word in ['consent', 'risks', 'complications', 'authorization', 'acknowledgment']):
            return True
    
    return False


def group_consecutive_consent_paragraphs(fields: List[Dict]) -> List[Dict]:
    """
    Group consecutive consent/terms fields into consolidated blocks.
    
    Improvement #9: Consent block grouping
    
    Consolidates multiple "Terms", "Terms (2)", "Terms (3)" fields into 
    fewer, more meaningful consent blocks.
    """
    if not fields:
        return fields
    
    grouped = []
    consent_buffer = []
    consent_buffer_text = []
    
    for field in fields:
        field_type = field.get('type', '')
        title = field.get('title', '')
        
        # Check if this is a consent/terms field
        is_consent = (
            field_type == 'terms' or
            is_consent_paragraph(title) or
            (len(title) > 80 and any(re.search(p, title.lower()) for p in CONSENT_INDICATORS))
        )
        
        if is_consent:
            # Add to buffer
            consent_buffer.append(field)
            consent_buffer_text.append(title)
        else:
            # Flush buffer if we have consent fields
            if consent_buffer:
                grouped_field = create_grouped_consent_field(consent_buffer, consent_buffer_text)
                grouped.append(grouped_field)
                consent_buffer = []
                consent_buffer_text = []
            
            # Add non-consent field as-is
            grouped.append(field)
    
    # Flush remaining buffer
    if consent_buffer:
        grouped_field = create_grouped_consent_field(consent_buffer, consent_buffer_text)
        grouped.append(grouped_field)
    
    return grouped


def create_grouped_consent_field(fields: List[Dict], texts: List[str]) -> Dict:
    """
    Create a single consolidated consent field from multiple fields.
    
    Improvement #9: Consent consolidation
    """
    if len(fields) == 1:
        return fields[0]
    
    # Combine texts
    combined_html = '<p>' + '</p><p>'.join(texts) + '</p>'
    
    # Use first field as base
    base_field = fields[0].copy()
    
    # Update with consolidated content
    base_field['type'] = 'terms'
    base_field['title'] = 'Terms and Conditions'
    base_field['control'] = {
        'agree_text': 'I have read and agree to the terms.',
        'html_text': combined_html
    }
    
    # Use key from first field or create generic one
    if 'key' not in base_field or base_field['key'].startswith('terms_'):
        base_field['key'] = 'consent_terms'
    
    return base_field


# ========== Improvement #10: Risk/Complication List Parsing ==========

def is_risk_list_header(line: str) -> bool:
    """
    Detect if a line introduces a risk/complication list.
    
    Improvement #10: Risk list detection
    """
    line_lower = line.lower().strip()
    
    risk_headers = [
        'risks and complications',
        'possible risks',
        'potential complications',
        'these potential risks',
        'complications include',
        'risks include',
        'may include',
        'following risks',
        'following complications',
    ]
    
    return any(header in line_lower for header in risk_headers)


def is_risk_list_item(text: str) -> bool:
    """
    Detect if text is a risk/complication list item.
    
    Improvement #10: Risk item detection
    """
    text = text.strip()
    
    # Short statements ending with period
    if len(text) < 150 and text.endswith('.'):
        # Common risk item patterns
        risk_patterns = [
            r'^[A-Z][a-z]+ing\s+',  # "Bleeding", "Swelling"
            r'^[A-Z][a-z]+\s+(?:of|to|in)\s+',  # "Damage to", "Injury of"
            r'^[A-Z][a-z]+\s+or\s+',  # "Pain or discomfort"
            r'^\w+\s+(?:may|can|could)\s+',  # "Treatment may cause"
        ]
        
        if any(re.match(pattern, text) for pattern in risk_patterns):
            return True
        
        # Check for medical/risk keywords
        risk_keywords = [
            'pain', 'infection', 'swelling', 'bleeding', 'damage', 'injury',
            'numbness', 'tingling', 'bruising', 'discomfort', 'sensitivity',
            'failure', 'fracture', 'breakage', 'allergic', 'reaction',
        ]
        
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in risk_keywords):
            return True
    
    return False


def group_risk_list_items(fields: List[Dict], start_idx: int) -> Tuple[List[Dict], int]:
    """
    Group consecutive risk list items into a single terms field.
    
    Improvement #10: Risk list grouping
    
    Returns:
        Tuple of (grouped_fields, next_index)
    """
    risk_items = []
    current_idx = start_idx
    
    # Collect consecutive risk items
    while current_idx < len(fields):
        field = fields[current_idx]
        title = field.get('title', '')
        
        if is_risk_list_item(title):
            risk_items.append(title)
            current_idx += 1
        else:
            break
    
    # If we found risk items, create grouped field
    if risk_items:
        # Create bullet list
        risk_html = '<ul>'
        for item in risk_items:
            risk_html += f'<li>{item}</li>'
        risk_html += '</ul>'
        
        grouped_field = {
            'key': 'risks_and_complications',
            'type': 'terms',
            'title': 'Risks and Complications',
            'section': 'Consent',
            'optional': False,
            'control': {
                'agree_text': 'I understand and acknowledge these risks.',
                'html_text': f'<p>Treatment includes the following risks and potential complications:</p>{risk_html}'
            }
        }
        
        # Return non-risk fields plus the grouped field
        return (fields[:start_idx] + [grouped_field] + fields[current_idx:], start_idx + 1)
    
    return (fields, start_idx)


# ========== Improvement #11: Consistent Signature Block Handling ==========

def is_signature_line(line: str) -> bool:
    """
    Detect if a line is a signature field.
    
    Improvement #11: Signature detection
    """
    line_lower = line.lower().strip()
    
    # Direct signature indicators
    if any(word in line_lower for word in ['signature', 'sign here', 'signed', 'patient signature']):
        return True
    
    # Pattern: "_____ Date _____" or similar
    if re.search(r'_{3,}.*date.*_{3,}', line_lower):
        return True
    
    return False


def normalize_signature_field(field: Dict) -> Dict:
    """
    Ensure signature fields use consistent block_signature type.
    
    Improvement #11: Signature normalization
    """
    title = field.get('title', '').lower()
    
    # Check if this should be a signature field
    if any(word in title for word in ['signature', 'sign', 'patient signature', 'guardian signature']):
        # Convert to block_signature type
        field['type'] = 'block_signature'
        field['title'] = 'Signature'
        field['key'] = 'signature'
        field['control'] = {
            'language': 'en',
            'variant': 'adult_no_guardian_details'
        }
        field['section'] = 'Signature'
    
    return field


def detect_signature_block_components(lines: List[str]) -> Optional[Dict]:
    """
    Detect multi-part signature blocks (signature, printed name, date, witness).
    
    Improvement #11: Signature block detection
    
    Returns field dict if signature block detected, else None.
    """
    # Look for patterns like:
    # "Signature:_____ Printed Name:_____ Date:_____"
    # "Patient/Parent/Guardian Signature Date"
    
    combined = ' '.join(lines).lower()
    
    has_signature = 'signature' in combined or 'signed' in combined
    has_date = 'date' in combined
    
    if has_signature and has_date:
        # Create comprehensive signature block
        return {
            'key': 'signature',
            'type': 'block_signature',
            'title': 'Signature',
            'section': 'Signature',
            'optional': False,
            'control': {
                'language': 'en',
                'variant': 'adult_with_guardian_details' if 'guardian' in combined else 'adult_no_guardian_details'
            }
        }
    
    return None
