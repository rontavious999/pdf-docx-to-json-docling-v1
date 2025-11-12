#!/usr/bin/env python3
"""
Generate a detailed parity report with specific examples from each form.
Shows what fields were captured, what was missed, and recommendations.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set


def get_unmatched_fields(stats: Dict) -> List[str]:
    """Extract unmatched fields from stats."""
    unmatched = []
    if 'unmatched_fields' in stats:
        for field in stats['unmatched_fields']:
            if isinstance(field, dict):
                unmatched.append(field.get('title', field.get('key', 'Unknown')))
            else:
                unmatched.append(str(field))
    return unmatched


def get_matched_fields(json_data: List[Dict]) -> List[str]:
    """Get list of captured field titles."""
    return [item.get('title', item.get('key', 'Unknown')) for item in json_data]


def analyze_missing_patterns(text: str, captured_fields: List[str]) -> Dict:
    """Analyze what types of fields might be missing."""
    missing = {
        'dates': [],
        'signatures': [],
        'names': [],
        'checkboxes': [],
        'text_inputs': []
    }
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if len(line) < 3:
            continue
        
        # Check for date fields not in captured
        if re.search(r'\bdate\b', line, re.IGNORECASE):
            if not any(re.search(r'\bdate\b', field, re.IGNORECASE) for field in captured_fields):
                # Extract a reasonable context
                match = re.search(r'([^.]{0,50}\bdate\b[^.]{0,20})', line, re.IGNORECASE)
                if match and len(missing['dates']) < 3:
                    missing['dates'].append(match.group(1).strip())
        
        # Check for signature fields
        if re.search(r'\bsignature\b', line, re.IGNORECASE):
            if not any(re.search(r'\bsignature\b', field, re.IGNORECASE) for field in captured_fields):
                match = re.search(r'([^.]{0,50}\bsignature\b[^.]{0,20})', line, re.IGNORECASE)
                if match and len(missing['signatures']) < 2:
                    missing['signatures'].append(match.group(1).strip())
        
        # Check for name fields
        if re.search(r'\bname\b', line, re.IGNORECASE):
            if not any(re.search(r'\bname\b', field, re.IGNORECASE) for field in captured_fields):
                match = re.search(r'([^.]{0,50}\bname\b[^.]{0,30})', line, re.IGNORECASE)
                if match and len(missing['names']) < 2:
                    context = match.group(1).strip()
                    # Skip long instructional text
                    if len(context) < 80:
                        missing['names'].append(context)
    
    return missing


def generate_detailed_report():
    """Generate detailed parity report for each form."""
    output_dir = Path('output')
    json_dir = Path('JSONs')
    
    if not output_dir.exists() or not json_dir.exists():
        print("Error: Run 'python3 run_all.py' first to generate output")
        return
    
    print("="*100)
    print("DETAILED PARITY ANALYSIS REPORT")
    print("="*100)
    print("\nThis report provides detailed analysis for each form/consent including:")
    print("  • Parity percentage calculation")
    print("  • Dictionary reuse rate")
    print("  • Specific fields captured")
    print("  • Specific fields missed")
    print("  • Actionable recommendations")
    print("\n" + "="*100)
    
    # Process each form
    forms_data = []
    
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
        
        dict_reuse_pct = stats.get('reused_pct', 0)
        total_fields = len(json_data)
        
        # Get matched and unmatched fields
        matched_fields = get_matched_fields(json_data)
        unmatched_fields = get_unmatched_fields(stats)
        
        # Analyze missing patterns
        missing_patterns = analyze_missing_patterns(text, matched_fields)
        
        forms_data.append({
            'name': form_name,
            'dict_reuse': dict_reuse_pct,
            'total_fields': total_fields,
            'matched_fields': matched_fields,
            'unmatched_fields': unmatched_fields,
            'missing_patterns': missing_patterns,
            'stats': stats
        })
    
    # Sort by dictionary reuse (lowest first)
    forms_data.sort(key=lambda x: x['dict_reuse'])
    
    # Print detailed analysis for each form
    for idx, form in enumerate(forms_data, 1):
        print(f"\n{'='*100}")
        print(f"[{idx}/{len(forms_data)}] {form['name']}")
        print(f"{'='*100}")
        
        # Summary metrics
        print(f"\n📊 METRICS:")
        print(f"  • Dictionary Reuse: {form['dict_reuse']:.1f}%")
        print(f"  • Total Fields Captured: {form['total_fields']}")
        print(f"  • Unmatched Fields: {len(form['unmatched_fields'])}")
        
        # Calculate parity estimate
        if form['dict_reuse'] >= 90:
            parity_status = "✅ EXCELLENT"
        elif form['dict_reuse'] >= 70:
            parity_status = "✓ GOOD"
        elif form['dict_reuse'] >= 50:
            parity_status = "⚠️  NEEDS IMPROVEMENT"
        else:
            parity_status = "❌ POOR"
        
        print(f"  • Parity Status: {parity_status}")
        
        # Show sample of captured fields
        if form['matched_fields']:
            print(f"\n✓ CAPTURED FIELDS (sample):")
            for field in form['matched_fields'][:10]:
                if len(field) > 70:
                    field = field[:67] + "..."
                print(f"  • {field}")
            if len(form['matched_fields']) > 10:
                print(f"  ... and {len(form['matched_fields']) - 10} more")
        
        # Show unmatched fields
        if form['unmatched_fields']:
            print(f"\n❌ UNMATCHED FIELDS ({len(form['unmatched_fields'])}):")
            for field in form['unmatched_fields'][:8]:
                if len(field) > 70:
                    field = field[:67] + "..."
                print(f"  • {field}")
            if len(form['unmatched_fields']) > 8:
                print(f"  ... and {len(form['unmatched_fields']) - 8} more")
        
        # Show missing patterns
        has_missing = any(form['missing_patterns'].values())
        if has_missing:
            print(f"\n⚠️  POTENTIALLY MISSING:")
            
            if form['missing_patterns']['dates']:
                print(f"  Dates:")
                for date_field in form['missing_patterns']['dates']:
                    print(f"    • {date_field}")
            
            if form['missing_patterns']['signatures']:
                print(f"  Signatures:")
                for sig_field in form['missing_patterns']['signatures']:
                    print(f"    • {sig_field}")
            
            if form['missing_patterns']['names']:
                print(f"  Names:")
                for name_field in form['missing_patterns']['names']:
                    print(f"    • {name_field}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        recommendations = []
        
        if form['dict_reuse'] < 70:
            recommendations.append("Add unmatched fields to dictionary with appropriate aliases")
            recommendations.append("Review field naming patterns and add fuzzy matching rules")
        
        if form['unmatched_fields']:
            recommendations.append(f"Investigate {len(form['unmatched_fields'])} unmatched fields and determine if they should be captured")
        
        if form['missing_patterns']['dates']:
            recommendations.append("Improve date field detection patterns")
        
        if form['missing_patterns']['signatures']:
            recommendations.append("Enhance signature field extraction")
        
        if form['missing_patterns']['names']:
            recommendations.append("Add name field detection for patient/guardian/responsible party")
        
        if not recommendations:
            recommendations.append("✓ Form has good parity - maintain current quality")
        
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
        
        # Add separator between forms
        if idx < len(forms_data):
            print(f"\n{'-'*100}\n")
    
    # Final summary
    print(f"\n{'='*100}")
    print("SUMMARY & NEXT STEPS")
    print(f"{'='*100}")
    
    avg_reuse = sum(f['dict_reuse'] for f in forms_data) / len(forms_data)
    forms_below_70 = [f for f in forms_data if f['dict_reuse'] < 70]
    forms_below_50 = [f for f in forms_data if f['dict_reuse'] < 50]
    
    print(f"\n📈 OVERALL STATISTICS:")
    print(f"  • Total forms: {len(forms_data)}")
    print(f"  • Average dictionary reuse: {avg_reuse:.1f}%")
    print(f"  • Forms needing improvement (<70%): {len(forms_below_70)}")
    print(f"  • Forms with poor parity (<50%): {len(forms_below_50)}")
    
    print(f"\n🎯 TOP PRIORITY FORMS (Lowest Dictionary Reuse):")
    for form in forms_data[:10]:
        print(f"  • {form['name']}: {form['dict_reuse']:.0f}% ({len(form['unmatched_fields'])} unmatched)")
    
    print(f"\n🔧 ACTION ITEMS FOR 100% PARITY:")
    print(f"  1. Focus on the {len(forms_below_50)} forms with <50% dictionary reuse")
    print(f"  2. Add unmatched field patterns to dictionary")
    print(f"  3. Improve detection of dates, signatures, and name fields")
    print(f"  4. Test with expanded dictionary and measure improvement")
    print(f"  5. Iterate until all forms achieve ≥90% dictionary reuse")
    
    print(f"\n{'='*100}\n")


if __name__ == '__main__':
    generate_detailed_report()
