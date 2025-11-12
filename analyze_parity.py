#!/usr/bin/env python3
"""
Comprehensive parity analysis tool.
Compares input text patterns with JSON output to identify missing fields.
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter

def analyze_text_patterns(text):
    """Analyze text file for field patterns."""
    patterns = {
        'input_fields': [],  # Lines ending with underscores
        'checkboxes': [],    # Lines with checkbox patterns
        'colons': [],        # Lines with "Label:" pattern
        'multi_subfields': [], # Lines like "Phone: Mobile Home Work"
    }
    
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        # Input fields (3+ underscores)
        if re.search(r'_{3,}', line):
            patterns['input_fields'].append((i+1, line[:80]))
        
        # Checkbox fields
        if re.search(r'\[\s*\]|\[ \]|!|co\s|o\s', line):
            patterns['checkboxes'].append((i+1, line[:80]))
        
        # Colon labels
        if re.search(r'^[A-Z][^:]{0,50}:\s*[A-Z_]', line):
            patterns['colons'].append((i+1, line[:80]))
        
        # Multi-subfield patterns (Phone: Mobile Home Work or Phone: Mobile Home. Work)
        if re.search(r'^[A-Z][^:]{0,30}:\s+[A-Z][a-z]+(?:[\s.]+[A-Z][a-z]+)+', line):
            patterns['multi_subfields'].append((i+1, line[:80]))
    
    return patterns

def analyze_json_fields(json_path):
    """Analyze JSON output."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        
        fields = {
            'total': len(data),
            'by_type': Counter(item['type'] for item in data),
            'by_section': Counter(item['section'] for item in data),
            'titles': [item.get('title', item.get('key', '')) for item in data],
        }
        return fields
    except Exception as e:
        return {'error': str(e)}

def check_multi_subfield_splitting(text, json_data):
    """Check if multi-subfield lines were properly split."""
    issues = []
    
    # Find multi-subfield patterns in text
    multi_patterns = re.findall(
        r'([A-Z][^:]{0,30}):\s+([A-Z][a-z]+(?:[\s.]+[A-Z][a-z]+)+)',
        text
    )
    
    for label, subfields in multi_patterns:
        # Check if the subfields were split
        parts = re.split(r'[\s.]+', subfields)
        if len(parts) < 2:
            continue
        
        # Check if we have separate fields for each part
        found_splits = []
        for part in parts:
            # Look for fields like "Mobile Phone", "Home Phone", etc.
            expected_title = f"{part} {label}"
            found = any(
                expected_title.lower() in item.get('title', '').lower()
                for item in json_data
            )
            found_splits.append((part, found))
        
        # If not all parts found, this is a splitting issue
        if not all(f for _, f in found_splits):
            issues.append({
                'pattern': f"{label}: {subfields}",
                'expected_splits': [f"{p} {label}" for p, _ in found_splits],
                'found': [p for p, f in found_splits if f],
                'missing': [p for p, f in found_splits if not f],
            })
    
    return issues

def main():
    output_dir = Path('output')
    json_dir = Path('JSONs')
    
    print("="*80)
    print("COMPREHENSIVE PARITY ANALYSIS")
    print("="*80)
    
    all_issues = defaultdict(list)
    stats = {
        'total_forms': 0,
        'total_input_patterns': 0,
        'total_json_fields': 0,
        'forms_with_split_issues': 0,
    }
    
    for txt_file in sorted(output_dir.glob('*.txt')):
        json_file = json_dir / f"{txt_file.stem}.modento.json"
        
        if not json_file.exists():
            print(f"\n❌ No JSON output for: {txt_file.name}")
            continue
        
        stats['total_forms'] += 1
        
        # Read files
        text = txt_file.read_text()
        with open(json_file) as f:
            json_data = json.load(f)
        
        stats['total_json_fields'] += len(json_data)
        
        # Analyze patterns
        text_patterns = analyze_text_patterns(text)
        stats['total_input_patterns'] += (
            len(text_patterns['input_fields']) +
            len(text_patterns['checkboxes']) +
            len(text_patterns['colons'])
        )
        
        # Check for multi-subfield splitting issues
        split_issues = check_multi_subfield_splitting(text, json_data)
        if split_issues:
            stats['forms_with_split_issues'] += 1
            all_issues[txt_file.name].extend(split_issues)
    
    # Report findings
    print(f"\n{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}")
    print(f"Total forms analyzed: {stats['total_forms']}")
    print(f"Total JSON fields: {stats['total_json_fields']}")
    print(f"Average fields per form: {stats['total_json_fields']/stats['total_forms']:.1f}")
    print(f"Forms with splitting issues: {stats['forms_with_split_issues']}")
    
    if all_issues:
        print(f"\n{'='*80}")
        print("MULTI-SUBFIELD SPLITTING ISSUES")
        print(f"{'='*80}")
        for form_name, issues in sorted(all_issues.items())[:10]:  # Show first 10
            print(f"\n{form_name}:")
            for issue in issues:
                print(f"  Pattern: {issue['pattern']}")
                print(f"    Expected: {', '.join(issue['expected_splits'])}")
                if issue['missing']:
                    print(f"    Missing: {', '.join(issue['missing'])}")
    
    print(f"\n{'='*80}")
    print("✅ Analysis complete")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()
