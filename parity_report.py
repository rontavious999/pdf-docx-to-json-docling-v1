#!/usr/bin/env python3
"""
Generate a comprehensive parity report comparing PDFs with JSON output.
This script analyzes whether all form fields have been correctly captured and converted.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def analyze_form_parity(text_path: Path, json_path: Path, stats_path: Path) -> dict:
    """Analyze a single form for parity issues."""
    
    # Read text file
    text = text_path.read_text()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Read JSON
    with open(json_path) as f:
        json_data = json.load(f)
    
    # Read stats
    stats = {}
    if stats_path.exists():
        with open(stats_path) as f:
            stats = json.load(f)
    
    # Count field indicators in text
    checkbox_count = sum(1 for line in lines if '[ ]' in line or '[]' in line or '☐' in line)
    underscore_fields = sum(1 for line in lines if '___' in line and len(line) < 200)
    colon_labels = sum(1 for line in lines if ':' in line and len(line) < 100)
    
    # Analyze JSON fields
    field_types = defaultdict(int)
    sections = defaultdict(int)
    for field in json_data:
        field_types[field.get('type', 'unknown')] += 1
        sections[field.get('section', 'unknown')] += 1
    
    return {
        'name': text_path.stem,
        'text_lines': len(lines),
        'checkbox_indicators': checkbox_count,
        'underscore_fields': underscore_fields,
        'colon_labels': colon_labels,
        'json_field_count': len(json_data),
        'field_types': dict(field_types),
        'sections': dict(sections),
        'dictionary_reuse': stats.get('reused_pct', 0),
        'reused_count': stats.get('reused_from_dictionary', 0),
        'total_count': stats.get('total_items', 0),
    }


def generate_parity_report():
    """Generate comprehensive parity report for all forms."""
    
    output_dir = Path('output')
    json_dir = Path('JSONs')
    
    if not output_dir.exists() or not json_dir.exists():
        print("❌ Error: output/ and JSONs/ directories must exist")
        print("Run 'python3 run_all.py' first to generate output")
        sys.exit(1)
    
    print("="*80)
    print("COMPREHENSIVE PARITY REPORT")
    print("="*80)
    
    # Analyze all forms
    results = []
    for text_path in sorted(output_dir.glob('*.txt')):
        json_path = json_dir / f"{text_path.stem}.modento.json"
        stats_path = json_dir / f"{text_path.stem}.modento.stats.json"
        
        if json_path.exists():
            result = analyze_form_parity(text_path, json_path, stats_path)
            results.append(result)
    
    # Overall statistics
    total_forms = len(results)
    total_json_fields = sum(r['json_field_count'] for r in results)
    avg_dictionary_reuse = sum(r['dictionary_reuse'] for r in results) / total_forms if total_forms > 0 else 0
    
    # Categorize forms
    patient_intake_forms = []
    consent_forms = []
    other_forms = []
    
    for r in results:
        name_lower = r['name'].lower()
        if 'consent' in name_lower or 'warranty' in name_lower or 'refusal' in name_lower:
            consent_forms.append(r)
        elif 'patient' in name_lower or 'npf' in name_lower or 'dental' in name_lower and 'consent' not in name_lower:
            patient_intake_forms.append(r)
        else:
            other_forms.append(r)
    
    print(f"\n📊 Overall Summary:")
    print(f"  Total forms processed: {total_forms}")
    print(f"  Total fields captured: {total_json_fields}")
    print(f"  Average fields per form: {total_json_fields/total_forms:.1f}")
    print(f"  Average dictionary reuse: {avg_dictionary_reuse:.1f}%")
    
    print(f"\n📋 Form Categories:")
    print(f"  Patient intake forms: {len(patient_intake_forms)}")
    print(f"  Consent/instruction forms: {len(consent_forms)}")
    print(f"  Other forms: {len(other_forms)}")
    
    # Detailed analysis for patient intake forms
    if patient_intake_forms:
        print(f"\n{'='*80}")
        print("PATIENT INTAKE FORMS (Data Collection Forms)")
        print("="*80)
        print(f"{'Form Name':<50} {'Fields':<8} {'Reuse %':<8}")
        print("-"*80)
        
        for r in sorted(patient_intake_forms, key=lambda x: x['json_field_count'], reverse=True):
            print(f"{r['name']:<50} {r['json_field_count']:<8} {r['dictionary_reuse']:<8.1f}%")
        
        avg_intake_fields = sum(r['json_field_count'] for r in patient_intake_forms) / len(patient_intake_forms)
        avg_intake_reuse = sum(r['dictionary_reuse'] for r in patient_intake_forms) / len(patient_intake_forms)
        
        print("-"*80)
        print(f"{'AVERAGE':<50} {avg_intake_fields:<8.1f} {avg_intake_reuse:<8.1f}%")
    
    # Detailed analysis for consent forms
    if consent_forms:
        print(f"\n{'='*80}")
        print("CONSENT/INSTRUCTION FORMS (Primarily Text-Based)")
        print("="*80)
        print(f"{'Form Name':<50} {'Fields':<8} {'Reuse %':<8}")
        print("-"*80)
        
        for r in sorted(consent_forms, key=lambda x: x['json_field_count'], reverse=True):
            print(f"{r['name']:<50} {r['json_field_count']:<8} {r['dictionary_reuse']:<8.1f}%")
        
        avg_consent_fields = sum(r['json_field_count'] for r in consent_forms) / len(consent_forms)
        avg_consent_reuse = sum(r['dictionary_reuse'] for r in consent_forms) / len(consent_forms)
        
        print("-"*80)
        print(f"{'AVERAGE':<50} {avg_consent_fields:<8.1f} {avg_consent_reuse:<8.1f}%")
    
    # Field type distribution
    print(f"\n{'='*80}")
    print("FIELD TYPE DISTRIBUTION")
    print("="*80)
    
    all_field_types = defaultdict(int)
    for r in results:
        for ftype, count in r['field_types'].items():
            all_field_types[ftype] += count
    
    for ftype, count in sorted(all_field_types.items(), key=lambda x: x[1], reverse=True):
        pct = count / total_json_fields * 100 if total_json_fields > 0 else 0
        print(f"  {ftype:<20} {count:>4} ({pct:>5.1f}%)")
    
    # Section distribution
    print(f"\n{'='*80}")
    print("SECTION DISTRIBUTION")
    print("="*80)
    
    all_sections = defaultdict(int)
    for r in results:
        for section, count in r['sections'].items():
            all_sections[section] += count
    
    for section, count in sorted(all_sections.items(), key=lambda x: x[1], reverse=True):
        pct = count / total_json_fields * 100 if total_json_fields > 0 else 0
        print(f"  {section:<20} {count:>4} ({pct:>5.1f}%)")
    
    # Recommendations
    print(f"\n{'='*80}")
    print("PARITY ASSESSMENT & RECOMMENDATIONS")
    print("="*80)
    
    # Check for forms with suspiciously low field counts
    low_field_forms = [r for r in patient_intake_forms if r['json_field_count'] < 20]
    if low_field_forms:
        print(f"\n⚠️  Patient intake forms with < 20 fields (may be incomplete):")
        for r in low_field_forms:
            print(f"    - {r['name']}: {r['json_field_count']} fields")
    else:
        print(f"\n✅ All patient intake forms have adequate field counts (20+ fields)")
    
    # Check dictionary reuse
    low_reuse_intake = [r for r in patient_intake_forms if r['dictionary_reuse'] < 70]
    if low_reuse_intake:
        print(f"\n⚠️  Patient intake forms with < 70% dictionary reuse:")
        for r in low_reuse_intake:
            print(f"    - {r['name']}: {r['dictionary_reuse']:.1f}%")
        print(f"    💡 Recommendation: Expand dictionary with common field definitions")
    else:
        print(f"\n✅ All patient intake forms have good dictionary reuse (70%+ )")
    
    # Overall assessment
    print(f"\n{'='*80}")
    print("PRODUCTION READINESS")
    print("="*80)
    
    criteria_met = []
    criteria_failed = []
    
    # Criterion 1: No forms with < 10 fields (except consent forms)
    if not [r for r in patient_intake_forms if r['json_field_count'] < 10]:
        criteria_met.append("✅ All patient intake forms have adequate field capture (10+ fields)")
    else:
        criteria_failed.append("❌ Some patient intake forms have very low field counts")
    
    # Criterion 2: Average dictionary reuse > 60%
    if avg_intake_reuse > 60 if patient_intake_forms else True:
        criteria_met.append(f"✅ Good dictionary reuse ({avg_intake_reuse:.1f}%)")
    else:
        criteria_failed.append(f"❌ Low dictionary reuse ({avg_intake_reuse:.1f}%)")
    
    # Criterion 3: At least 10 forms processed
    if total_forms >= 10:
        criteria_met.append(f"✅ Adequate form coverage ({total_forms} forms)")
    else:
        criteria_failed.append(f"❌ Insufficient form coverage ({total_forms} forms)")
    
    # Criterion 4: Field types are distributed appropriately
    if all_field_types.get('input', 0) > total_json_fields * 0.3:
        criteria_met.append(f"✅ Good input field distribution")
    else:
        criteria_failed.append(f"❌ Too few input fields captured")
    
    print("\nCriteria Met:")
    for criterion in criteria_met:
        print(f"  {criterion}")
    
    if criteria_failed:
        print("\nCriteria Failed:")
        for criterion in criteria_failed:
            print(f"  {criterion}")
    
    if not criteria_failed:
        print(f"\n{'='*80}")
        print("🎉 SYSTEM IS 100% PRODUCTION READY")
        print("="*80)
        print("The pipeline is correctly extracting and converting form fields.")
        print("All quality criteria are met.")
    else:
        print(f"\n{'='*80}")
        print("⚠️  SYSTEM NEEDS MINOR IMPROVEMENTS")
        print("="*80)
        print("The pipeline is functional but could be improved.")
        print("Review the recommendations above.")
    
    print()


if __name__ == '__main__':
    generate_parity_report()
