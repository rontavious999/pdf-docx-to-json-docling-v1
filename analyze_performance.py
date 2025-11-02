#!/usr/bin/env python3
"""
analyze_performance.py - Analyze pipeline performance and create comprehensive spreadsheet

This script:
1. Analyzes all generated JSON files
2. Compares actual fields vs expected fields from dictionary
3. Calculates accuracy metrics
4. Generates performance statistics
5. Creates a CSV spreadsheet with the results
"""

import json
import csv
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

def load_dictionary(dict_path: str) -> Dict:
    """Load the dental form dictionary and count available fields"""
    with open(dict_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Count fields
    total_fields = 0
    sections = {}
    all_keys = set()
    
    for section_name, items in data.items():
        if section_name == '_meta':
            continue
        if isinstance(items, list):
            field_count = len(items)
            total_fields += field_count
            sections[section_name] = field_count
            for item in items:
                if isinstance(item, dict) and 'key' in item:
                    all_keys.add(item['key'])
    
    return {
        'data': data,
        'total_fields': total_fields,
        'sections': sections,
        'unique_keys': all_keys,
        'section_count': len(sections)
    }

def analyze_stats_file(stats_path: str) -> Dict:
    """Analyze a single stats file and extract metrics"""
    with open(stats_path, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    
    filename = stats.get('file', '').replace('.modento.json', '')
    
    metrics = {
        'filename': filename,
        'total_items': stats.get('total_items', 0),
        'reused_from_dictionary': stats.get('reused_from_dictionary', 0),
        'reused_pct': stats.get('reused_pct', 0),
        'unmatched_count': len(stats.get('unmatched_fields', [])),
        'near_misses': len(stats.get('near_misses', [])),
        'raw_questions_parsed': stats.get('parsing', {}).get('raw_questions_parsed', 0),
        'sections_detected': stats.get('parsing', {}).get('sections_detected', 0),
        'file_size_bytes': stats.get('extraction', {}).get('file_size_bytes', 0),
        'character_count': stats.get('extraction', {}).get('character_count', 0),
        'line_count': stats.get('extraction', {}).get('line_count', 0),
    }
    
    # Calculate accuracy
    if metrics['total_items'] > 0:
        metrics['match_accuracy'] = (metrics['reused_from_dictionary'] / metrics['total_items']) * 100
    else:
        metrics['match_accuracy'] = 0
    
    # Get section and type breakdowns
    sections = stats.get('counts_by_section', {})
    types = stats.get('counts_by_type', {})
    
    metrics['sections'] = ', '.join([f"{k}:{v}" for k, v in sections.items()])
    metrics['types'] = ', '.join([f"{k}:{v}" for k, v in types.items()])
    
    # Get unmatched field details
    unmatched = stats.get('unmatched_fields', [])
    metrics['unmatched_fields'] = '; '.join([f['title'][:50] for f in unmatched[:5]])  # First 5, truncated
    
    return metrics

def analyze_json_file(json_path: str) -> Dict:
    """Analyze a JSON output file"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        return {'field_count': 0, 'has_signature': False}
    
    field_count = len(data)
    has_signature = any(item.get('type') in ['signature', 'block_signature'] for item in data)
    
    # Count field types
    field_types = defaultdict(int)
    sections = defaultdict(int)
    
    for item in data:
        field_types[item.get('type', 'unknown')] += 1
        sections[item.get('section', 'unknown')] += 1
    
    return {
        'field_count': field_count,
        'has_signature': has_signature,
        'field_types': dict(field_types),
        'sections': dict(sections)
    }

def calculate_overall_stats(all_metrics: List[Dict]) -> Dict:
    """Calculate overall statistics across all documents"""
    total_docs = len(all_metrics)
    
    if total_docs == 0:
        return {}
    
    total_items = sum(m['total_items'] for m in all_metrics)
    total_matched = sum(m['reused_from_dictionary'] for m in all_metrics)
    total_unmatched = sum(m['unmatched_count'] for m in all_metrics)
    
    avg_accuracy = sum(m['match_accuracy'] for m in all_metrics) / total_docs
    avg_items_per_doc = total_items / total_docs
    avg_sections = sum(m['sections_detected'] for m in all_metrics) / total_docs
    
    total_size = sum(m['file_size_bytes'] for m in all_metrics)
    total_chars = sum(m['character_count'] for m in all_metrics)
    total_lines = sum(m['line_count'] for m in all_metrics)
    
    return {
        'total_documents': total_docs,
        'total_items': total_items,
        'total_matched': total_matched,
        'total_unmatched': total_unmatched,
        'overall_match_rate': (total_matched / total_items * 100) if total_items > 0 else 0,
        'avg_accuracy': avg_accuracy,
        'avg_items_per_doc': avg_items_per_doc,
        'avg_sections_per_doc': avg_sections,
        'total_size_kb': total_size / 1024,
        'total_characters': total_chars,
        'total_lines': total_lines,
        'avg_size_kb': total_size / 1024 / total_docs,
        'avg_chars_per_doc': total_chars / total_docs,
        'avg_lines_per_doc': total_lines / total_docs,
    }

def create_detailed_spreadsheet(all_metrics: List[Dict], overall_stats: Dict, output_path: str, dict_info: Dict = None):
    """Create a detailed CSV spreadsheet with all metrics"""
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header section
        writer.writerow(['PERFORMANCE ANALYSIS REPORT'])
        writer.writerow(['Generated:', Path().absolute()])
        writer.writerow([])
        
        # Write dictionary comparison if available
        if dict_info:
            writer.writerow(['DICTIONARY VS OUTPUT COMPARISON'])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Available Fields in Dictionary', dict_info.get('total_fields', 0)])
            writer.writerow(['Total Dictionary Sections', dict_info.get('section_count', 0)])
            writer.writerow(['Total Unique Keys in Dictionary', len(dict_info.get('unique_keys', set()))])
            writer.writerow([])
            writer.writerow(['Total Fields Extracted from Documents', overall_stats.get('total_items', 0)])
            writer.writerow(['Fields Matched to Dictionary', overall_stats.get('total_matched', 0)])
            writer.writerow(['Fields NOT in Dictionary (new/unique)', overall_stats.get('total_unmatched', 0)])
            writer.writerow([])
            dict_usage = (overall_stats.get('total_matched', 0) / dict_info.get('total_fields', 1)) * 100
            writer.writerow(['Dictionary Coverage (% of dictionary used)', f"{dict_usage:.2f}%"])
            writer.writerow(['Dictionary Match Rate (% of extracted fields matched)', f"{overall_stats.get('overall_match_rate', 0):.2f}%"])
            writer.writerow([])
        
        # Write overall statistics
        writer.writerow(['OVERALL STATISTICS'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Documents Processed', overall_stats.get('total_documents', 0)])
        writer.writerow(['Total Fields Extracted', overall_stats.get('total_items', 0)])
        writer.writerow(['Total Fields Matched to Dictionary', overall_stats.get('total_matched', 0)])
        writer.writerow(['Total Unmatched Fields', overall_stats.get('total_unmatched', 0)])
        writer.writerow(['Overall Match Rate (%)', f"{overall_stats.get('overall_match_rate', 0):.2f}"])
        writer.writerow(['Average Accuracy per Document (%)', f"{overall_stats.get('avg_accuracy', 0):.2f}"])
        writer.writerow(['Average Fields per Document', f"{overall_stats.get('avg_items_per_doc', 0):.2f}"])
        writer.writerow(['Average Sections per Document', f"{overall_stats.get('avg_sections_per_doc', 0):.2f}"])
        writer.writerow(['Total Content Size (KB)', f"{overall_stats.get('total_size_kb', 0):.2f}"])
        writer.writerow(['Average Document Size (KB)', f"{overall_stats.get('avg_size_kb', 0):.2f}"])
        writer.writerow(['Total Characters', overall_stats.get('total_characters', 0)])
        writer.writerow(['Average Characters per Document', f"{overall_stats.get('avg_chars_per_doc', 0):.2f}"])
        writer.writerow(['Total Lines', overall_stats.get('total_lines', 0)])
        writer.writerow(['Average Lines per Document', f"{overall_stats.get('avg_lines_per_doc', 0):.2f}"])
        writer.writerow([])
        
        # Write accuracy distribution
        writer.writerow(['ACCURACY DISTRIBUTION'])
        accuracy_buckets = {'90-100%': 0, '80-90%': 0, '70-80%': 0, '60-70%': 0, '50-60%': 0, 'Below 50%': 0}
        for m in all_metrics:
            acc = m['match_accuracy']
            if acc >= 90:
                accuracy_buckets['90-100%'] += 1
            elif acc >= 80:
                accuracy_buckets['80-90%'] += 1
            elif acc >= 70:
                accuracy_buckets['70-80%'] += 1
            elif acc >= 60:
                accuracy_buckets['60-70%'] += 1
            elif acc >= 50:
                accuracy_buckets['50-60%'] += 1
            else:
                accuracy_buckets['Below 50%'] += 1
        
        writer.writerow(['Range', 'Count', 'Percentage'])
        for bucket, count in accuracy_buckets.items():
            pct = (count / overall_stats.get('total_documents', 1)) * 100
            writer.writerow([bucket, count, f"{pct:.1f}%"])
        writer.writerow([])
        
        # Write detailed per-document metrics
        writer.writerow(['DETAILED PER-DOCUMENT METRICS'])
        writer.writerow([
            'Filename',
            'Total Fields',
            'Matched Fields',
            'Unmatched Fields',
            'Match Accuracy (%)',
            'Raw Questions',
            'Sections',
            'File Size (bytes)',
            'Characters',
            'Lines',
            'Section Breakdown',
            'Type Breakdown',
            'Sample Unmatched Fields'
        ])
        
        # Sort by accuracy descending
        sorted_metrics = sorted(all_metrics, key=lambda x: x['match_accuracy'], reverse=True)
        
        for m in sorted_metrics:
            writer.writerow([
                m['filename'],
                m['total_items'],
                m['reused_from_dictionary'],
                m['unmatched_count'],
                f"{m['match_accuracy']:.2f}",
                m['raw_questions_parsed'],
                m['sections_detected'],
                m['file_size_bytes'],
                m['character_count'],
                m['line_count'],
                m['sections'],
                m['types'],
                m.get('unmatched_fields', '')[:100]  # Truncate to 100 chars
            ])
        
        writer.writerow([])
        
        # Write top performers and bottom performers
        writer.writerow(['TOP 5 PERFORMERS (by accuracy)'])
        writer.writerow(['Filename', 'Accuracy (%)', 'Total Fields', 'Matched Fields'])
        for m in sorted_metrics[:5]:
            writer.writerow([m['filename'], f"{m['match_accuracy']:.2f}", m['total_items'], m['reused_from_dictionary']])
        
        writer.writerow([])
        
        writer.writerow(['BOTTOM 5 PERFORMERS (by accuracy)'])
        writer.writerow(['Filename', 'Accuracy (%)', 'Total Fields', 'Matched Fields'])
        for m in sorted_metrics[-5:]:
            writer.writerow([m['filename'], f"{m['match_accuracy']:.2f}", m['total_items'], m['reused_from_dictionary']])
        
        writer.writerow([])
        
        # Write field type analysis
        writer.writerow(['FIELD TYPE ANALYSIS'])
        type_counts = defaultdict(int)
        for m in all_metrics:
            types_str = m['types']
            if types_str:
                for type_item in types_str.split(', '):
                    if ':' in type_item:
                        type_name, count = type_item.split(':')
                        type_counts[type_name] += int(count)
        
        writer.writerow(['Field Type', 'Total Count', 'Percentage'])
        total_type_count = sum(type_counts.values())
        for type_name, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_type_count * 100) if total_type_count > 0 else 0
            writer.writerow([type_name, count, f"{pct:.2f}%"])
        
        writer.writerow([])
        
        # Write section analysis
        writer.writerow(['SECTION ANALYSIS'])
        section_counts = defaultdict(int)
        for m in all_metrics:
            sections_str = m['sections']
            if sections_str:
                for section_item in sections_str.split(', '):
                    if ':' in section_item:
                        section_name, count = section_item.split(':')
                        section_counts[section_name] += int(count)
        
        writer.writerow(['Section Name', 'Total Count', 'Percentage'])
        total_section_count = sum(section_counts.values())
        for section_name, count in sorted(section_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_section_count * 100) if total_section_count > 0 else 0
            writer.writerow([section_name, count, f"{pct:.2f}%"])

def main():
    """Main analysis function"""
    base_dir = Path(__file__).parent
    jsons_dir = base_dir / 'JSONs'
    dict_path = base_dir / 'dental_form_dictionary.json'
    
    print("🔍 Analyzing pipeline performance...")
    print(f"📂 JSONs directory: {jsons_dir}")
    
    # Load dictionary
    dict_info = None
    if dict_path.exists():
        print(f"📖 Loading dictionary: {dict_path}")
        dict_info = load_dictionary(str(dict_path))
        print(f"   ✓ {dict_info['total_fields']} fields in {dict_info['section_count']} sections")
    
    # Find all stats files
    stats_files = list(jsons_dir.glob('*.stats.json'))
    print(f"📊 Found {len(stats_files)} stats files")
    
    if not stats_files:
        print("❌ No stats files found. Run the pipeline first.")
        return
    
    # Analyze all stats files
    all_metrics = []
    for stats_file in stats_files:
        try:
            metrics = analyze_stats_file(str(stats_file))
            all_metrics.append(metrics)
        except Exception as e:
            print(f"⚠️  Error analyzing {stats_file.name}: {e}")
    
    print(f"✅ Analyzed {len(all_metrics)} documents")
    
    # Calculate overall statistics
    overall_stats = calculate_overall_stats(all_metrics)
    
    # Create output spreadsheet
    output_path = base_dir / 'performance_analysis.csv'
    create_detailed_spreadsheet(all_metrics, overall_stats, str(output_path), dict_info)
    
    print(f"\n✅ Spreadsheet created: {output_path}")
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    
    if dict_info:
        print(f"\n📖 Dictionary Information:")
        print(f"   Available Fields: {dict_info['total_fields']}")
        print(f"   Available Sections: {dict_info['section_count']}")
        print(f"   Unique Keys: {len(dict_info['unique_keys'])}")
        dict_usage = (overall_stats.get('total_matched', 0) / dict_info['total_fields']) * 100
        print(f"   Dictionary Coverage: {dict_usage:.2f}%")
    
    print(f"\n📊 Processing Results:")
    print(f"   Total Documents: {overall_stats.get('total_documents', 0)}")
    print(f"   Total Fields Extracted: {overall_stats.get('total_items', 0)}")
    print(f"   Matched to Dictionary: {overall_stats.get('total_matched', 0)}")
    print(f"   Unmatched (new/unique): {overall_stats.get('total_unmatched', 0)}")
    print(f"   Overall Match Rate: {overall_stats.get('overall_match_rate', 0):.2f}%")
    print(f"   Average Accuracy per Doc: {overall_stats.get('avg_accuracy', 0):.2f}%")
    
    print(f"\n📈 Performance Metrics:")
    print(f"   Average Fields per Document: {overall_stats.get('avg_items_per_doc', 0):.2f}")
    print(f"   Average Sections per Document: {overall_stats.get('avg_sections_per_doc', 0):.2f}")
    print(f"   Average Document Size: {overall_stats.get('avg_size_kb', 0):.2f} KB")
    print(f"   Processing Efficiency: {overall_stats.get('avg_chars_per_doc', 0):.0f} chars/doc")
    print("="*60)

if __name__ == '__main__':
    main()
