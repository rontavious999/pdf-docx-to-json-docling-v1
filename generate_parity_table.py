#!/usr/bin/env python3
"""
Generate a comprehensive parity analysis table for each form/consent.
This script analyzes the input PDFs/DOCXs, extracted text, and JSON outputs
to determine the parity percentage and what was missed.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict


def analyze_text_fields(text: str) -> Dict:
    """Analyze the extracted text to count potential fields."""
    lines = text.split('\n')
    
    # Count different types of fields
    checkbox_count = 0
    input_field_count = 0
    date_field_count = 0
    signature_count = 0
    text_blocks = 0
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 2:
            continue
        
        # Count checkboxes
        checkbox_count += len(re.findall(r'\[\s*\]', line))
        
        # Count input fields (underscores)
        if re.search(r'_{3,}', line):
            input_field_count += 1
        
        # Count date fields
        if re.search(r'\bdate\b', line, re.IGNORECASE):
            date_field_count += 1
        
        # Count signature fields
        if re.search(r'\bsignature\b', line, re.IGNORECASE):
            signature_count += 1
        
        # Count substantial text blocks (consent text, instructions)
        if len(line) > 100 and not re.search(r'\[\s*\]', line):
            text_blocks += 1
    
    return {
        'checkbox_count': checkbox_count,
        'input_field_count': input_field_count,
        'date_field_count': date_field_count,
        'signature_count': signature_count,
        'text_blocks': text_blocks,
        'total_potential_fields': checkbox_count + input_field_count + min(date_field_count, 3) + min(signature_count, 2)
    }


def analyze_json_output(json_data: List[Dict]) -> Dict:
    """Analyze the JSON output to categorize captured fields."""
    field_types = defaultdict(int)
    sections = defaultdict(int)
    
    has_signature = False
    has_date = False
    has_patient_name = False
    
    for item in json_data:
        field_type = item.get('type', '')
        section = item.get('section', '')
        key = item.get('key', '')
        
        field_types[field_type] += 1
        sections[section] += 1
        
        if 'signature' in key.lower():
            has_signature = True
        if 'date' in key.lower():
            has_date = True
        if 'name' in key.lower() or 'patient' in key.lower():
            has_patient_name = True
    
    return {
        'total_fields': len(json_data),
        'field_types': dict(field_types),
        'sections': dict(sections),
        'has_signature': has_signature,
        'has_date': has_date,
        'has_patient_name': has_patient_name
    }


def calculate_parity(text_analysis: Dict, json_analysis: Dict, stats: Dict) -> Tuple[float, List[str]]:
    """Calculate parity percentage and identify what's missing."""
    notes = []
    
    # Get dictionary reuse rate (primary parity metric)
    dict_reuse_pct = stats.get('reused_pct', 0)
    
    # Get counts
    captured_fields = json_analysis['total_fields']
    potential_fields = text_analysis['total_potential_fields']
    
    # Check for missing elements
    if not json_analysis['has_signature'] and text_analysis['signature_count'] > 0:
        notes.append("Missing signature field")
    
    if not json_analysis['has_date'] and text_analysis['date_field_count'] > 0:
        notes.append("Missing date field")
    
    if not json_analysis['has_patient_name']:
        notes.append("Missing patient name field")
    
    # Check dictionary reuse (key quality metric)
    if dict_reuse_pct < 50:
        notes.append(f"Low dictionary reuse ({dict_reuse_pct:.0f}%)")
    
    # Check checkbox coverage
    checkbox_in_json = json_analysis['field_types'].get('checkbox', 0)
    checkbox_in_text = text_analysis['checkbox_count']
    if checkbox_in_text > 0:
        checkbox_coverage = (checkbox_in_json / checkbox_in_text) * 100
        if checkbox_coverage < 70:
            notes.append(f"Low checkbox coverage ({checkbox_coverage:.0f}%)")
    
    # Calculate overall parity (weighted)
    # 50% weight on dictionary reuse (quality)
    # 30% weight on field capture vs potential
    # 20% weight on having key fields (signature, date, name)
    
    capture_ratio = min((captured_fields / potential_fields) * 100, 100) if potential_fields > 0 else 100
    
    key_fields_score = 0
    if json_analysis['has_signature']:
        key_fields_score += 33
    if json_analysis['has_date']:
        key_fields_score += 33
    if json_analysis['has_patient_name']:
        key_fields_score += 34
    
    parity_pct = (dict_reuse_pct * 0.5) + (capture_ratio * 0.3) + (key_fields_score * 0.2)
    
    # Add specific notes about what's lacking
    if parity_pct < 100:
        if dict_reuse_pct < 100:
            notes.append(f"Need better field matching to dictionary ({100 - dict_reuse_pct:.0f}% gap)")
        if capture_ratio < 100:
            missing = int(potential_fields - captured_fields)
            if missing > 0:
                notes.append(f"~{missing} fields not captured from form")
    
    return parity_pct, notes


def generate_parity_table():
    """Generate the main parity analysis table."""
    output_dir = Path('output')
    json_dir = Path('JSONs')
    
    if not output_dir.exists() or not json_dir.exists():
        print("Error: Run 'python3 run_all.py' first to generate output")
        return
    
    results = []
    
    # Process each form
    for text_path in sorted(output_dir.glob('*.txt')):
        form_name = text_path.stem
        json_path = json_dir / f"{form_name}.modento.json"
        stats_path = json_dir / f"{form_name}.modento.stats.json"
        
        if not json_path.exists():
            continue
        
        # Load data
        text = text_path.read_text()
        with open(json_path) as f:
            json_data = json.load(f)
        
        stats = {}
        if stats_path.exists():
            with open(stats_path) as f:
                stats = json.load(f)
        
        # Analyze
        text_analysis = analyze_text_fields(text)
        json_analysis = analyze_json_output(json_data)
        parity_pct, notes = calculate_parity(text_analysis, json_analysis, stats)
        
        results.append({
            'name': form_name,
            'parity': parity_pct,
            'notes': notes,
            'dict_reuse': stats.get('reused_pct', 0),
            'captured': json_analysis['total_fields'],
            'potential': text_analysis['total_potential_fields']
        })
    
    # Sort by parity (lowest first to highlight issues)
    results.sort(key=lambda x: x['parity'])
    
    # Print table header
    print("\n" + "="*120)
    print("COMPREHENSIVE PARITY ANALYSIS TABLE")
    print("="*120)
    print(f"\n{'Form/Consent Name':<50} {'Parity %':<12} {'Dict %':<10} {'Fields':<10} {'Notes'}")
    print("-"*120)
    
    # Print each form
    for r in results:
        notes_str = "; ".join(r['notes']) if r['notes'] else "✓ Good parity"
        if len(notes_str) > 65:
            notes_str = notes_str[:62] + "..."
        
        parity_display = f"{r['parity']:.1f}%"
        dict_display = f"{r['dict_reuse']:.0f}%"
        fields_display = f"{r['captured']}/{r['potential']}"
        
        print(f"{r['name']:<50} {parity_display:<12} {dict_display:<10} {fields_display:<10} {notes_str}")
    
    # Print summary statistics
    print("-"*120)
    avg_parity = sum(r['parity'] for r in results) / len(results) if results else 0
    avg_dict_reuse = sum(r['dict_reuse'] for r in results) / len(results) if results else 0
    forms_above_90 = sum(1 for r in results if r['parity'] >= 90)
    forms_above_80 = sum(1 for r in results if r['parity'] >= 80)
    
    print(f"\nSUMMARY:")
    print(f"  Total forms analyzed: {len(results)}")
    print(f"  Average parity: {avg_parity:.1f}%")
    print(f"  Average dictionary reuse: {avg_dict_reuse:.1f}%")
    print(f"  Forms with parity ≥90%: {forms_above_90} ({forms_above_90/len(results)*100:.0f}%)")
    print(f"  Forms with parity ≥80%: {forms_above_80} ({forms_above_80/len(results)*100:.0f}%)")
    
    print("\n" + "="*120)
    
    # Print detailed analysis for forms with low parity
    print("\nDETAILED ANALYSIS FOR FORMS WITH PARITY <70%:")
    print("="*120)
    
    low_parity_forms = [r for r in results if r['parity'] < 70]
    if not low_parity_forms:
        print("  ✓ All forms have parity ≥70%")
    else:
        for r in low_parity_forms:
            print(f"\n{r['name']} (Parity: {r['parity']:.1f}%)")
            print(f"  Dictionary reuse: {r['dict_reuse']:.0f}%")
            print(f"  Fields captured: {r['captured']} out of ~{r['potential']} potential")
            print(f"  Issues:")
            for note in r['notes']:
                print(f"    - {note}")
    
    print("\n" + "="*120)
    
    # Print recommendations
    print("\nRECOMMENDATIONS FOR 100% PARITY:")
    print("="*120)
    print("""
1. IMPROVE DICTIONARY MATCHING (Top Priority)
   - Forms with <70% dictionary reuse need template expansion
   - Add more aliases and fuzzy matching patterns
   - Review unmatched fields and add to dictionary
   
2. ENHANCE FIELD DETECTION
   - Improve checkbox extraction for complex grids
   - Better multi-field label splitting
   - Detect inline checkboxes more reliably
   
3. ADD MISSING KEY FIELDS
   - Ensure signature fields are always captured
   - Detect and capture date fields consistently
   - Always include patient name/identifier
   
4. CONTEXT-AWARE PARSING
   - Use section headers to improve field classification
   - Better detection of consent text vs data fields
   - Improve handling of nested/composite fields
   
5. FORM-SPECIFIC TUNING (if needed)
   - For forms with <50% parity, may need custom patterns
   - Document any form-specific quirks
   - Add validation rules for known form types
""")
    print("="*120)


if __name__ == '__main__':
    generate_parity_table()
