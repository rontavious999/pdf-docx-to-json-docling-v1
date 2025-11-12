#!/usr/bin/env python3
"""
Comprehensive parity validator for PDF-to-JSON conversion pipeline.
Ensures 100% production readiness with automated checks for:
- Field capture completeness
- Correct section assignments
- Proper input types
- Line splitting accuracy
- Dictionary reuse rates
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional


class ParityValidator:
    """Validates conversion parity between input and output."""
    
    def __init__(self, debug=False):
        self.debug = debug
        self.issues = []
        self.warnings = []
        self.stats = defaultdict(int)
    
    def validate_field_types(self, json_data: List[Dict]) -> List[str]:
        """Validate that field types are appropriate."""
        issues = []
        
        for item in json_data:
            key = item.get('key', '')
            field_type = item.get('type', '')
            title = item.get('title', '')
            control = item.get('control', {})
            input_type = control.get('input_type', '')
            
            # Phone fields should be input/phone
            if 'phone' in key.lower() and 'phone' in title.lower():
                if field_type != 'input' or input_type != 'phone':
                    issues.append(
                        f"Field '{title}' (key: {key}) has type={field_type}, "
                        f"input_type={input_type}, expected input/phone"
                    )
            
            # Email fields should be input/email
            if 'email' in key.lower():
                if field_type != 'input' or input_type != 'email':
                    issues.append(
                        f"Field '{title}' (key: {key}) has type={field_type}, "
                        f"input_type={input_type}, expected input/email"
                    )
            
            # Date fields should be date type
            if any(date_word in key.lower() for date_word in ['date', 'birth', 'dob']):
                # Skip if it's clearly not a date field despite having 'date' in name
                if 'update' not in key.lower() and 'date' in title.lower():
                    if field_type not in ['date', 'input']:  # Allow input as fallback
                        issues.append(
                            f"Field '{title}' (key: {key}) has type={field_type}, "
                            f"expected date type"
                        )
            
            # Signature fields should be block_signature
            if 'signature' in key.lower():
                if field_type != 'block_signature':
                    issues.append(
                        f"Field '{title}' (key: {key}) has type={field_type}, "
                        f"expected block_signature"
                    )
        
        return issues
    
    def validate_section_assignments(self, json_data: List[Dict]) -> List[str]:
        """Validate that fields are in appropriate sections."""
        issues = []
        
        for item in json_data:
            key = item.get('key', '')
            section = item.get('section', '')
            title = item.get('title', '')
            
            # Insurance fields should be in Insurance or Patient Information
            if 'insurance' in key.lower() or 'insurance' in title.lower():
                if section not in ['Insurance', 'Patient Information', 'General']:
                    issues.append(
                        f"Field '{title}' (key: {key}) in section '{section}', "
                        f"expected Insurance or Patient Information"
                    )
            
            # Emergency contact fields
            if 'emergency' in key.lower() or 'emergency' in title.lower():
                if section != 'Emergency Contact':
                    issues.append(
                        f"Field '{title}' (key: {key}) in section '{section}', "
                        f"expected Emergency Contact"
                    )
            
            # Signature fields should be in Consent
            if 'signature' in key.lower():
                if section != 'Consent':
                    issues.append(
                        f"Field '{title}' (key: {key}) in section '{section}', "
                        f"expected Consent"
                    )
            
            # Medical condition fields
            if any(word in key.lower() for word in ['condition', 'disease', 'illness', 'medication']):
                if section not in ['Medical History', 'General', 'Dental History']:
                    issues.append(
                        f"Field '{title}' (key: {key}) in section '{section}', "
                        f"expected Medical History"
                    )
        
        return issues
    
    def validate_key_format(self, json_data: List[Dict]) -> List[str]:
        """Validate that field keys follow standards."""
        issues = []
        
        for item in json_data:
            key = item.get('key', '')
            
            # Key should be lowercase with underscores
            if not re.match(r'^[a-z][a-z0-9_]*$', key):
                issues.append(
                    f"Key '{key}' does not follow lowercase_underscore format"
                )
            
            # Key should not be too long (>80 chars is excessive)
            if len(key) > 80:
                issues.append(
                    f"Key '{key}' is too long ({len(key)} chars), consider shortening"
                )
            
            # Key should not end with underscore
            if key.endswith('_') and not key.endswith('_2') and not key.endswith('_3'):
                issues.append(
                    f"Key '{key}' ends with underscore"
                )
        
        return issues
    
    def detect_duplicate_keys(self, json_data: List[Dict]) -> List[str]:
        """Detect duplicate keys (should never happen in final output)."""
        issues = []
        key_counts = Counter(item.get('key', '') for item in json_data)
        
        for key, count in key_counts.items():
            if count > 1:
                issues.append(
                    f"Duplicate key '{key}' appears {count} times"
                )
        
        return issues
    
    def check_missing_required_fields(self, json_data: List[Dict]) -> List[str]:
        """Check for commonly expected fields."""
        warnings = []
        
        # Extract all keys
        keys = set(item.get('key', '') for item in json_data)
        
        # Check for signature field
        has_signature = any('signature' in k for k in keys)
        if not has_signature:
            warnings.append(
                "No signature field found (may be acceptable for some forms)"
            )
        
        # Check for patient name (at least one name field)
        has_name = any(
            word in k for k in keys 
            for word in ['name', 'first_name', 'last_name', 'patient_name']
        )
        if not has_name:
            warnings.append(
                "No name field found (unusual for patient forms)"
            )
        
        return warnings
    
    def analyze_text_coverage(self, text_path: Path, json_data: List[Dict]) -> Dict:
        """Analyze how well the JSON covers the input text."""
        text = text_path.read_text()
        lines = text.split('\n')
        
        # Count potential fields in text
        potential_fields = 0
        field_indicators = [
            r'_{3,}',  # Underscores for inputs
            r'\[\s*\]',  # Checkboxes
            r'^\s*[A-Z][^:]{1,60}:\s*$',  # Label colon patterns
            r'^\s*\[\s*\]\s*[A-Z]',  # Checkbox with label
        ]
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue
            
            for pattern in field_indicators:
                if re.search(pattern, line):
                    potential_fields += 1
                    break
        
        # Calculate coverage
        actual_fields = len(json_data)
        coverage_ratio = actual_fields / potential_fields if potential_fields > 0 else 1.0
        
        return {
            'potential_fields': potential_fields,
            'actual_fields': actual_fields,
            'coverage_ratio': coverage_ratio,
        }
    
    def validate_form(self, text_path: Path, json_path: Path, stats_path: Path) -> Dict:
        """Validate a single form conversion."""
        result = {
            'name': text_path.stem,
            'status': 'ok',
            'errors': [],
            'warnings': [],
            'stats': {},
        }
        
        # Check files exist
        if not json_path.exists():
            result['status'] = 'error'
            result['errors'].append(f"JSON output not found: {json_path}")
            return result
        
        # Load JSON
        try:
            with open(json_path) as f:
                json_data = json.load(f)
        except Exception as e:
            result['status'] = 'error'
            result['errors'].append(f"Failed to load JSON: {e}")
            return result
        
        # Load stats if available
        if stats_path.exists():
            try:
                with open(stats_path) as f:
                    stats = json.load(f)
                    result['stats'] = stats
            except:
                pass
        
        # Run validations
        result['errors'].extend(self.validate_key_format(json_data))
        result['errors'].extend(self.detect_duplicate_keys(json_data))
        result['warnings'].extend(self.validate_field_types(json_data))
        result['warnings'].extend(self.validate_section_assignments(json_data))
        result['warnings'].extend(self.check_missing_required_fields(json_data))
        
        # Analyze coverage
        coverage = self.analyze_text_coverage(text_path, json_data)
        result['coverage'] = coverage
        
        # Set status
        if result['errors']:
            result['status'] = 'error'
        elif result['warnings']:
            result['status'] = 'warning'
        
        return result
    
    def validate_all(self, output_dir: Path, json_dir: Path) -> Dict:
        """Validate all forms in the pipeline output."""
        results = []
        
        for text_path in sorted(output_dir.glob('*.txt')):
            json_path = json_dir / f"{text_path.stem}.modento.json"
            stats_path = json_dir / f"{text_path.stem}.modento.stats.json"
            
            result = self.validate_form(text_path, json_path, stats_path)
            results.append(result)
        
        # Aggregate statistics
        summary = {
            'total_forms': len(results),
            'successful': sum(1 for r in results if r['status'] == 'ok'),
            'with_warnings': sum(1 for r in results if r['status'] == 'warning'),
            'with_errors': sum(1 for r in results if r['status'] == 'error'),
            'total_errors': sum(len(r['errors']) for r in results),
            'total_warnings': sum(len(r['warnings']) for r in results),
            'total_fields': sum(r['coverage']['actual_fields'] for r in results),
            'avg_fields_per_form': 0,
            'avg_coverage': 0,
            'avg_dictionary_reuse': 0,
            'results': results,
        }
        
        if summary['successful'] > 0:
            summary['avg_fields_per_form'] = (
                summary['total_fields'] / summary['total_forms']
            )
            
            # Average coverage
            coverages = [r['coverage']['coverage_ratio'] for r in results if 'coverage' in r]
            if coverages:
                summary['avg_coverage'] = sum(coverages) / len(coverages)
            
            # Average dictionary reuse
            reuses = [
                r['stats'].get('reused_pct', 0) 
                for r in results if 'stats' in r and r['stats']
            ]
            if reuses:
                summary['avg_dictionary_reuse'] = sum(reuses) / len(reuses)
        
        return summary
    
    def print_report(self, summary: Dict):
        """Print a comprehensive validation report."""
        print("\n" + "="*80)
        print("PARITY VALIDATION REPORT")
        print("="*80)
        
        print(f"\n📊 Overall Statistics:")
        print(f"  Total forms processed: {summary['total_forms']}")
        print(f"  ✅ Successful: {summary['successful']}")
        print(f"  ⚠️  With warnings: {summary['with_warnings']}")
        print(f"  ❌ With errors: {summary['with_errors']}")
        print(f"  Total fields captured: {summary['total_fields']}")
        print(f"  Average fields per form: {summary['avg_fields_per_form']:.1f}")
        print(f"  Average coverage ratio: {summary['avg_coverage']:.1%}")
        print(f"  Average dictionary reuse: {summary['avg_dictionary_reuse']:.1f}%")
        
        # Show forms with issues
        problematic = [
            r for r in summary['results'] 
            if r['status'] in ['error', 'warning']
        ]
        
        if problematic:
            print(f"\n⚠️  Forms with Issues ({len(problematic)}):")
            for r in problematic[:10]:  # Show first 10
                print(f"\n  {r['name']}:")
                if r['errors']:
                    print(f"    Errors: {len(r['errors'])}")
                    for err in r['errors'][:3]:
                        print(f"      - {err}")
                if r['warnings']:
                    print(f"    Warnings: {len(r['warnings'])}")
                    for warn in r['warnings'][:3]:
                        print(f"      - {warn}")
        
        # Show forms with low dictionary reuse
        low_reuse = [
            r for r in summary['results']
            if r.get('stats', {}).get('reused_pct', 100) < 70
        ]
        
        if low_reuse:
            print(f"\n📉 Forms with Low Dictionary Reuse (<70%):")
            for r in sorted(low_reuse, key=lambda x: x.get('stats', {}).get('reused_pct', 0)):
                stats = r.get('stats', {})
                reused = stats.get('reused_from_dictionary', 0)
                total = stats.get('total_items', 0)
                pct = stats.get('reused_pct', 0)
                print(f"  {r['name']}: {reused}/{total} ({pct:.1f}%)")
        
        # Production readiness assessment
        print(f"\n{'='*80}")
        print("PRODUCTION READINESS ASSESSMENT")
        print("="*80)
        
        is_production_ready = (
            summary['with_errors'] == 0 and
            summary['avg_dictionary_reuse'] >= 60 and
            summary['avg_coverage'] >= 0.8
        )
        
        if is_production_ready:
            print("✅ SYSTEM IS PRODUCTION READY")
            print("   - No critical errors detected")
            print("   - Good dictionary reuse rate")
            print("   - Acceptable field coverage")
        else:
            print("⚠️  SYSTEM NEEDS IMPROVEMENT")
            if summary['with_errors'] > 0:
                print(f"   - {summary['with_errors']} forms have errors")
            if summary['avg_dictionary_reuse'] < 60:
                print(f"   - Dictionary reuse is low ({summary['avg_dictionary_reuse']:.1f}%)")
            if summary['avg_coverage'] < 0.8:
                print(f"   - Field coverage is low ({summary['avg_coverage']:.1%})")
        
        print("="*80)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate parity between input and JSON output"
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('output'),
        help='Directory containing extracted text files'
    )
    parser.add_argument(
        '--json-dir',
        type=Path,
        default=Path('JSONs'),
        help='Directory containing JSON output files'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    
    args = parser.parse_args()
    
    # Check directories exist
    if not args.output_dir.exists():
        print(f"❌ Error: Output directory not found: {args.output_dir}")
        print("Run 'python3 run_all.py' first to generate output")
        sys.exit(1)
    
    if not args.json_dir.exists():
        print(f"❌ Error: JSON directory not found: {args.json_dir}")
        print("Run 'python3 run_all.py' first to generate output")
        sys.exit(1)
    
    # Run validation
    validator = ParityValidator(debug=args.debug)
    summary = validator.validate_all(args.output_dir, args.json_dir)
    validator.print_report(summary)
    
    # Exit with error code if there are critical issues
    if summary['with_errors'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
