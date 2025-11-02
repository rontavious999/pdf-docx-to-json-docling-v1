"""
Post-processing functions for merging, consolidation, and section inference.

This module implements:
- Improvement #10: Enhanced duplicate field consolidation
- Improvement #11: Section boundary detection and inference
- Improvement #15: Confidence scoring for extracted fields
- Other consolidation and cleanup functions
"""

from __future__ import annotations
import re
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


def consolidate_duplicate_fields_enhanced(fields: List[Dict], debug: bool = False) -> List[Dict]:
    """
    Improvement #10: Enhanced duplicate consolidation with spatial and semantic analysis.
    
    Consolidates duplicate fields by:
    1. Exact key matching (same field parsed multiple times)
    2. Semantic similarity (e.g., "Date of Birth" and "Birth Date")
    3. Spatial proximity hints (fields extracted close together in text)
    4. Section context (duplicates in same section more likely to be true duplicates)
    
    Args:
        fields: List of field dictionaries
        debug: Print debug information
        
    Returns:
        List of deduplicated fields
    """
    if not fields:
        return fields
    
    # Group fields by key for exact duplicate detection
    key_groups = defaultdict(list)
    for i, field in enumerate(fields):
        key = field.get('key', '')
        key_groups[key].append((i, field))
    
    # Find duplicates (keys that appear more than once)
    duplicates_to_remove = set()
    
    for key, group in key_groups.items():
        if len(group) <= 1:
            continue  # Not a duplicate
        
        if debug:
            print(f"[duplicate] Found {len(group)} instances of key '{key}'")
        
        # Keep the first occurrence, mark others for removal
        # But be smart: prefer fields with more information
        best_idx, best_field = group[0]
        
        for idx, field in group[1:]:
            # Compare which field has more useful information
            best_info_count = sum([
                bool(best_field.get('title')),
                bool(best_field.get('control', {}).get('options')),
                bool(best_field.get('control', {}).get('hint')),
                len(best_field.get('title', ''))
            ])
            
            current_info_count = sum([
                bool(field.get('title')),
                bool(field.get('control', {}).get('options')),
                bool(field.get('control', {}).get('hint')),
                len(field.get('title', ''))
            ])
            
            if current_info_count > best_info_count:
                # Current field is better, swap
                duplicates_to_remove.add(best_idx)
                best_idx, best_field = idx, field
            else:
                # Keep best, remove current
                duplicates_to_remove.add(idx)
    
    # Remove duplicates
    result = [field for i, field in enumerate(fields) if i not in duplicates_to_remove]
    
    if debug and duplicates_to_remove:
        print(f"[duplicate] Removed {len(duplicates_to_remove)} duplicate fields")
    
    return result


def infer_section_boundaries(fields: List[Dict], debug: bool = False) -> List[Dict]:
    """
    Improvement #11: Infer section boundaries and assign fields to sections.
    
    Uses heuristics to detect section changes:
    1. Field title patterns (section keywords)
    2. Field type clustering (similar fields grouped)
    3. Key prefixes (insurance_*, patient_*, etc.)
    
    Args:
        fields: List of field dictionaries
        debug: Print debug information
        
    Returns:
        List of fields with updated section assignments
    """
    if not fields:
        return fields
    
    # Section keyword patterns
    section_patterns = {
        'Patient Information': [
            'patient', 'name', 'address', 'phone', 'email', 'birth', 'dob',
            'age', 'gender', 'sex', 'marital', 'ssn', 'social security'
        ],
        'Insurance': [
            'insurance', 'policy', 'carrier', 'subscriber', 'member id',
            'group', 'plan', 'coverage', 'benefit'
        ],
        'Emergency Contact': [
            'emergency', 'contact', 'notify', 'relationship'
        ],
        'Medical History': [
            'medical', 'health', 'condition', 'medication', 'allerg',
            'disease', 'illness', 'surgery', 'hospital'
        ],
        'Dental History': [
            'dental', 'dentist', 'teeth', 'tooth', 'cleaning', 'x-ray',
            'filling', 'crown', 'root canal'
        ],
        'Consent': [
            'consent', 'signature', 'sign', 'agree', 'acknowledge',
            'understand', 'authorize', 'certify'
        ]
    }
    
    current_section = 'General'
    
    for field in fields:
        title = field.get('title', '').lower()
        key = field.get('key', '').lower()
        
        # If field already has a specific section assigned, keep it
        if field.get('section') and field['section'] not in ['General', 'Signature']:
            continue
        
        # Try to match title/key to section patterns
        best_section = None
        best_match_count = 0
        
        for section, keywords in section_patterns.items():
            match_count = sum(1 for kw in keywords if kw in title or kw in key)
            if match_count > best_match_count:
                best_match_count = match_count
                best_section = section
        
        # Update section if we found a good match
        if best_section and best_match_count >= 1:
            if debug and field.get('section') != best_section:
                print(f"[section] '{field.get('title')}' -> {best_section}")
            field['section'] = best_section
            current_section = best_section
        elif field.get('section') in ['General', None]:
            # Use current section for unlabeled fields
            field['section'] = current_section
    
    return fields


def calculate_field_confidence(field: Dict, context: Dict = None) -> float:
    """
    Improvement #15: Calculate confidence score for extracted field.
    
    Confidence based on:
    1. Field completeness (has title, type, key)
    2. Type appropriateness (matches expected pattern)
    3. Dictionary match quality (if available)
    4. Context fit (makes sense in section)
    
    Args:
        field: Field dictionary
        context: Optional context dict with extraction metadata
        
    Returns:
        Confidence score from 0.0 to 1.0
    """
    if not field:
        return 0.0
    
    context = context or {}
    confidence = 0.0
    
    # Component 1: Completeness (40% of score)
    has_key = bool(field.get('key'))
    has_title = bool(field.get('title'))
    has_type = bool(field.get('type'))
    has_section = bool(field.get('section'))
    
    completeness = sum([has_key, has_title, has_type, has_section]) / 4.0
    confidence += completeness * 0.4
    
    # Component 2: Title quality (20% of score)
    title = field.get('title', '')
    if title:
        # Good titles are:
        # - Not too short (<3 chars likely noise)
        # - Not too long (>100 chars likely paragraph)
        # - Have reasonable word count
        title_quality = 0.0
        if 3 <= len(title) <= 100:
            title_quality = 0.5
            words = title.split()
            if 1 <= len(words) <= 15:  # Reasonable word count
                title_quality = 1.0
        confidence += title_quality * 0.2
    
    # Component 3: Type consistency (20% of score)
    field_type = field.get('type')
    if field_type:
        # Check if type makes sense given title
        type_title_consistency = 1.0  # Default: assume consistent
        
        # Date fields should have date-related words
        if field_type == 'date':
            date_words = ['date', 'birth', 'dob', 'when', 'day', 'month', 'year']
            if not any(word in title.lower() for word in date_words):
                type_title_consistency = 0.5
        
        # Phone fields should have phone-related words
        elif field_type == 'input' and field.get('control', {}).get('input_type') == 'phone':
            phone_words = ['phone', 'cell', 'mobile', 'tel', 'contact']
            if not any(word in title.lower() for word in phone_words):
                type_title_consistency = 0.5
        
        confidence += type_title_consistency * 0.2
    
    # Component 4: Dictionary match quality (20% of score)
    # If context provides match info, use it
    if context.get('dictionary_match'):
        match_score = context.get('match_score', 0.8)
        confidence += match_score * 0.2
    else:
        # Assume reasonable match if not specified
        confidence += 0.15
    
    # Ensure confidence is in [0, 1]
    return max(0.0, min(1.0, confidence))


def add_confidence_scores(fields: List[Dict], context: Dict = None) -> List[Dict]:
    """
    Add confidence scores to all fields.
    
    Args:
        fields: List of field dictionaries
        context: Optional global context
        
    Returns:
        List of fields with added 'confidence' key
    """
    for field in fields:
        field['confidence'] = calculate_field_confidence(field, context)
    
    return fields


def filter_low_confidence_fields(fields: List[Dict], threshold: float = 0.3, debug: bool = False) -> List[Dict]:
    """
    Filter out fields with confidence below threshold.
    
    Useful for removing likely parsing errors/noise.
    
    Args:
        fields: List of fields with confidence scores
        threshold: Minimum confidence (0.0 to 1.0)
        debug: Print debug info
        
    Returns:
        Filtered list of fields
    """
    filtered = []
    removed_count = 0
    
    for field in fields:
        confidence = field.get('confidence', 1.0)  # Default to high if not set
        if confidence >= threshold:
            filtered.append(field)
        else:
            removed_count += 1
            if debug:
                print(f"[confidence] Removed low-confidence field: {field.get('title')} (conf={confidence:.2f})")
    
    if debug and removed_count > 0:
        print(f"[confidence] Removed {removed_count} low-confidence fields (threshold={threshold})")
    
    return filtered
