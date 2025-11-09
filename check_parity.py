#!/usr/bin/env python3
"""
Check parity between input text and JSON output.
Helps identify missing fields and validate section assignments.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def count_input_patterns(text):
    """Count potential form fields in input text."""
    patterns = {
        'underscores': len(re.findall(r'_{3,}', text)),  # Lines with multiple underscores
        'checkboxes': len(re.findall(r'\[\s*\]|\[ \]|!', text)),  # Checkbox markers
        'colons': len(re.findall(r'^[A-Z][^:]*:', text, re.MULTILINE)),  # Label: patterns
        'date_patterns': len(re.findall(r'Date[^:]*:|DOB[^:]*:|Birth[^:]*:', text, re.IGNORECASE)),
        'phone_patterns': len(re.findall(r'Phone[^:]*:|Tel[^:]*:|Mobile[^:]*:', text, re.IGNORECASE)),
        'name_patterns': len(re.findall(r'Name[^:]*:|First[^:]*:|Last[^:]*:', text, re.IGNORECASE)),
        'address_patterns': len(re.findall(r'Address[^:]*:|City[^:]*:|State[^:]*:|Zip[^:]*:', text, re.IGNORECASE)),
    }
    return patterns

def analyze_json_output(json_path):
    """Analyze JSON output structure."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        
        stats = {
            'total_fields': len(data),
            'by_section': defaultdict(int),
            'by_type': defaultdict(int),
            'field_titles': []
        }
        
        for item in data:
            stats['by_section'][item['section']] += 1
            stats['by_type'][item['type']] += 1
            stats['field_titles'].append(item.get('title', item.get('key')))
        
        return stats
    except Exception as e:
        return {'error': str(e)}

def check_parity(text_file, json_file):
    """Compare input text with JSON output."""
    print(f"\n{'='*80}")
    print(f"Parity Check: {text_file.name}")
    print(f"{'='*80}")
    
    # Read input text
    try:
        text = text_file.read_text()
    except:
        print(f"❌ Could not read {text_file}")
        return
    
    if not text.strip():
        print(f"⚠️  Empty text file - skipping")
        return
    
    # Analyze input
    input_stats = count_input_patterns(text)
    print(f"\nInput Text Analysis:")
    print(f"  Lines: {len(text.splitlines())}")
    print(f"  Characters: {len(text)}")
    print(f"  Potential fields:")
    for key, val in input_stats.items():
        print(f"    {key}: {val}")
    
    # Analyze output
    if json_file.exists():
        json_stats = analyze_json_output(json_file)
        print(f"\nJSON Output Analysis:")
        if 'error' in json_stats:
            print(f"  ❌ Error: {json_stats['error']}")
        else:
            print(f"  Total fields: {json_stats['total_fields']}")
            print(f"  By section:")
            for section, count in sorted(json_stats['by_section'].items()):
                print(f"    {section}: {count}")
            print(f"  By type:")
            for ftype, count in sorted(json_stats['by_type'].items()):
                print(f"    {ftype}: {count}")
        
        # Check stats file
        stats_file = json_file.with_suffix('.stats.json')
        if stats_file.exists():
            try:
                with open(stats_file) as f:
                    stats = json.load(f)
                print(f"\nDictionary Reuse:")
                print(f"  Reused: {stats.get('reused_from_dictionary', 0)}/{stats.get('total_items', 0)}")
                print(f"  Percentage: {stats.get('reused_pct', 0):.1f}%")
            except:
                pass
    else:
        print(f"\n❌ JSON file not found: {json_file}")

def main():
    output_dir = Path('output')
    json_dir = Path('JSONs')
    
    # Focus on key forms
    focus_forms = ['npf1', 'npf', 'Chicago-Dental-Solutions_Form']
    
    print("="*80)
    print("PDF-to-JSON Parity Analysis")
    print("="*80)
    
    for text_file in sorted(output_dir.glob('*.txt')):
        # Skip if not in focus list (unless running all)
        stem = text_file.stem
        if focus_forms and stem not in focus_forms:
            continue
        
        json_file = json_dir / f"{stem}.modento.json"
        check_parity(text_file, json_file)
    
    print(f"\n{'='*80}")
    print("Summary")
    print(f"{'='*80}")
    
    # Count all JSON files
    json_files = list(json_dir.glob('*.modento.json'))
    print(f"Total forms processed: {len(json_files)}")
    
    # Get average field count
    total_fields = 0
    for json_file in json_files:
        try:
            with open(json_file) as f:
                data = json.load(f)
            total_fields += len(data)
        except:
            pass
    
    if json_files:
        avg_fields = total_fields / len(json_files)
        print(f"Average fields per form: {avg_fields:.1f}")
        print(f"Total fields captured: {total_fields}")

if __name__ == '__main__':
    main()
