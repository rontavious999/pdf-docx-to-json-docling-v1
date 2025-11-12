#!/usr/bin/env python3
"""
Comprehensive parity verification tool.
Examines input text files and JSON outputs to verify:
1. Field capture completeness
2. Correct section assignments
3. Appropriate input types
4. Line splitting accuracy
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter

def analyze_text_file(text_path):
    """Analyze a text file for potential fields."""
    text = text_path.read_text()
    lines = text.split('\n')
    
    stats = {
        'total_lines': len(lines),
        'non_empty_lines': sum(1 for line in lines if line.strip()),
        'potential_fields': [],
        'sections': [],
    }
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        # Detect sections
        if re.match(r'^[A-Z\s]{10,}$', line) and len(line) > 15:
            stats['sections'].append(line)
        
        # Detect fields with underscores
        if re.search(r'_{3,}', line):
            stats['potential_fields'].append({
                'line': i + 1,
                'type': 'input_underscore',
                'text': line[:100]
            })
        
        # Detect checkbox fields
        elif re.search(r'\[\s*\]|\[ \]', line):
            stats['potential_fields'].append({
                'line': i + 1,
                'type': 'checkbox',
                'text': line[:100]
            })
        
        # Detect label: pattern
        elif re.match(r'^[A-Z][^:]{1,50}:\s*[A-Z_]', line):
            stats['potential_fields'].append({
                'line': i + 1,
                'type': 'label_colon',
                'text': line[:100]
            })
    
    return stats

def analyze_json_file(json_path):
    """Analyze a JSON output file."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        
        stats = {
            'total_fields': len(data),
            'by_type': Counter(item['type'] for item in data),
            'by_section': Counter(item['section'] for item in data),
            'fields': data,
        }
        
        # Check for stats file
        stats_file = json_path.with_suffix('.stats.json')
        if stats_file.exists():
            with open(stats_file) as f:
                conversion_stats = json.load(f)
                stats['reused_pct'] = conversion_stats.get('reused_pct', 0)
                stats['total_items'] = conversion_stats.get('total_items', 0)
                stats['reused_from_dictionary'] = conversion_stats.get('reused_from_dictionary', 0)
        
        return stats
    except Exception as e:
        return {'error': str(e)}

def check_section_assignments(json_data):
    """Verify section assignments are appropriate."""
    issues = []
    
    for item in json_data:
        key = item.get('key', '')
        section = item.get('section', '')
        title = item.get('title', '')
        
        # Check for common misassignments
        if 'insurance' in key.lower() or 'insurance' in title.lower():
            if section not in ['Insurance', 'Patient Information']:
                issues.append(f"'{title}' in {section}, expected Insurance")
        
        if 'emergency' in key.lower() or 'emergency' in title.lower():
            if section != 'Emergency Contact':
                issues.append(f"'{title}' in {section}, expected Emergency Contact")
        
        if 'signature' in key.lower():
            if section != 'Consent':
                issues.append(f"'{title}' in {section}, expected Consent")
    
    return issues

def check_input_types(json_data):
    """Verify input types are appropriate."""
    issues = []
    
    for item in json_data:
        key = item.get('key', '')
        field_type = item.get('type', '')
        title = item.get('title', '')
        control = item.get('control', {})
        input_type = control.get('input_type', '')
        
        # Check phone fields have phone input type
        if 'phone' in key.lower():
            if field_type != 'input' or input_type != 'phone':
                issues.append(f"'{title}' has type={field_type}, input_type={input_type}, expected input/phone")
        
        # Check email fields
        if 'email' in key.lower():
            if field_type != 'input' or input_type != 'email':
                issues.append(f"'{title}' has type={field_type}, input_type={input_type}, expected input/email")
        
        # Check date fields
        if 'date' in key.lower() or 'birth' in key.lower():
            if field_type != 'date':
                issues.append(f"'{title}' has type={field_type}, expected date")
    
    return issues

def verify_form(text_path, json_path):
    """Verify a single form's parity."""
    print(f"\n{'='*80}")
    print(f"Verifying: {text_path.name}")
    print(f"{'='*80}")
    
    # Analyze input
    text_stats = analyze_text_file(text_path)
    print(f"\n📄 Input Text Analysis:")
    print(f"  Total lines: {text_stats['total_lines']}")
    print(f"  Non-empty lines: {text_stats['non_empty_lines']}")
    print(f"  Potential fields: {len(text_stats['potential_fields'])}")
    if text_stats['sections']:
        print(f"  Sections found: {len(text_stats['sections'])}")
        for section in text_stats['sections'][:5]:
            print(f"    - {section[:50]}")
    
    # Analyze output
    if not json_path.exists():
        print(f"\n❌ No JSON output found!")
        return {'status': 'missing'}
    
    json_stats = analyze_json_file(json_path)
    if 'error' in json_stats:
        print(f"\n❌ Error reading JSON: {json_stats['error']}")
        return {'status': 'error'}
    
    print(f"\n📋 JSON Output Analysis:")
    print(f"  Total fields: {json_stats['total_fields']}")
    print(f"  Dictionary reuse: {json_stats.get('reused_from_dictionary', 0)}/{json_stats.get('total_items', 0)} ({json_stats.get('reused_pct', 0):.1f}%)")
    print(f"\n  Fields by type:")
    for ftype, count in sorted(json_stats['by_type'].items()):
        print(f"    {ftype}: {count}")
    print(f"\n  Fields by section:")
    for section, count in sorted(json_stats['by_section'].items()):
        print(f"    {section}: {count}")
    
    # Check for issues
    section_issues = check_section_assignments(json_stats['fields'])
    type_issues = check_input_types(json_stats['fields'])
    
    if section_issues:
        print(f"\n⚠️  Section Assignment Issues:")
        for issue in section_issues[:5]:
            print(f"    - {issue}")
    
    if type_issues:
        print(f"\n⚠️  Input Type Issues:")
        for issue in type_issues[:5]:
            print(f"    - {issue}")
    
    # Calculate capture rate (rough estimate)
    capture_rate = (json_stats['total_fields'] / len(text_stats['potential_fields']) * 100 
                   if text_stats['potential_fields'] else 100)
    
    print(f"\n📊 Capture Rate: {capture_rate:.1f}% (estimated)")
    
    return {
        'status': 'ok',
        'text_stats': text_stats,
        'json_stats': json_stats,
        'section_issues': len(section_issues),
        'type_issues': len(type_issues),
        'capture_rate': capture_rate,
    }

def main():
    output_dir = Path('output')
    json_dir = Path('JSONs')
    
    if not output_dir.exists() or not json_dir.exists():
        print("❌ Error: output/ and JSONs/ directories must exist")
        print("Run 'python3 run_all.py' first to generate output")
        return
    
    print("="*80)
    print("COMPREHENSIVE PARITY VERIFICATION")
    print("="*80)
    
    # Process all forms
    results = []
    for text_path in sorted(output_dir.glob('*.txt')):
        json_path = json_dir / f"{text_path.stem}.modento.json"
        result = verify_form(text_path, json_path)
        result['name'] = text_path.name
        results.append(result)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    total_forms = len(results)
    successful = sum(1 for r in results if r['status'] == 'ok')
    total_fields = sum(r.get('json_stats', {}).get('total_fields', 0) for r in results if r['status'] == 'ok')
    total_section_issues = sum(r.get('section_issues', 0) for r in results)
    total_type_issues = sum(r.get('type_issues', 0) for r in results)
    
    print(f"\nTotal forms processed: {total_forms}")
    print(f"Successful: {successful}/{total_forms}")
    print(f"Total fields captured: {total_fields}")
    print(f"Average fields per form: {total_fields/successful:.1f}" if successful else "N/A")
    
    if total_section_issues:
        print(f"\n⚠️  Total section assignment issues: {total_section_issues}")
    if total_type_issues:
        print(f"⚠️  Total input type issues: {total_type_issues}")
    
    # Top performers
    ok_results = [r for r in results if r['status'] == 'ok']
    if ok_results:
        print(f"\n📈 Top 5 forms by field count:")
        top_5 = sorted(ok_results, key=lambda r: r['json_stats']['total_fields'], reverse=True)[:5]
        for r in top_5:
            print(f"  {r['name']}: {r['json_stats']['total_fields']} fields")
        
        print(f"\n📉 Bottom 5 forms by field count:")
        bottom_5 = sorted(ok_results, key=lambda r: r['json_stats']['total_fields'])[:5]
        for r in bottom_5:
            print(f"  {r['name']}: {r['json_stats']['total_fields']} fields")
    
    print(f"\n{'='*80}")
    print("✅ Verification complete")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()
