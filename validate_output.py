#!/usr/bin/env python3
"""
validate_output.py - Comprehensive validation of JSON output quality

This script validates the generated Modento JSON files for:
1. Completeness - Are all fields from the form captured?
2. Accuracy - Are field types, keys, and values correct?
3. Consistency - Are fields consistently formatted?
4. Quality - Are there any issues or warnings?

Usage:
    python validate_output.py --json JSONs/output.modento.json --txt output/input.txt
    python validate_output.py --dir JSONs/
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import Counter, defaultdict


class ValidationResult:
    """Container for validation results"""
    def __init__(self, filename: str):
        self.filename = filename
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.metrics: Dict = {}
    
    def add_error(self, msg: str):
        self.errors.append(msg)
    
    def add_warning(self, msg: str):
        self.warnings.append(msg)
    
    def add_info(self, msg: str):
        self.info.append(msg)
    
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def print_summary(self):
        print(f"\n{'='*80}")
        print(f"Validation Report: {self.filename}")
        print(f"{'='*80}")
        
        if self.metrics:
            print("\nMetrics:")
            for key, value in self.metrics.items():
                print(f"  {key}: {value}")
        
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for err in self.errors:
                print(f"  - {err}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warn in self.warnings:
                print(f"  - {warn}")
        
        if self.info:
            print(f"\n💡 Info ({len(self.info)}):")
            for inf in self.info:
                print(f"  - {inf}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All checks passed!")
        
        print(f"{'='*80}\n")


def validate_json_structure(data: List[dict], result: ValidationResult):
    """Validate basic JSON structure and required fields"""
    required_fields = ['key', 'title', 'section', 'type']
    
    for i, item in enumerate(data):
        # Check required fields
        for field in required_fields:
            if field not in item:
                result.add_error(f"Field {i+1} missing required field: {field}")
        
        # Validate key format (should be lowercase with underscores)
        if 'key' in item:
            key = item['key']
            if not re.match(r'^[a-z0-9_]+$', key):
                result.add_warning(f"Field '{key}' has non-standard key format")
        
        # Validate type
        valid_types = ['input', 'date', 'radio', 'dropdown', 'checkbox', 
                      'states', 'terms', 'block_signature', 'textarea']
        if 'type' in item and item['type'] not in valid_types:
            result.add_error(f"Field '{item.get('key', 'unknown')}' has invalid type: {item['type']}")
        
        # Validate control structure
        if 'control' not in item:
            result.add_warning(f"Field '{item.get('key', 'unknown')}' missing control structure")
        elif item.get('type') in ['radio', 'dropdown']:
            if 'options' not in item['control']:
                result.add_error(f"Field '{item.get('key', 'unknown')}' of type {item['type']} missing options")


def check_duplicate_keys(data: List[dict], result: ValidationResult):
    """Check for duplicate keys"""
    keys = [item.get('key', '') for item in data]
    duplicates = [k for k, count in Counter(keys).items() if count > 1 and k]
    
    if duplicates:
        for dup in duplicates:
            result.add_error(f"Duplicate key found: '{dup}'")


def check_field_completeness(data: List[dict], txt_content: str, result: ValidationResult):
    """Check if major form elements are captured"""
    
    # Count potential fields in source text
    # Look for patterns like "Label:" or "Label: _____"
    label_pattern = r'^[\s•\-\*]*([A-Z][^:\n]{2,50}):\s*(?:_+|\[\s*\])?'
    potential_labels = set(re.findall(label_pattern, txt_content, re.MULTILINE))
    
    # Captured titles
    captured_titles = set(item.get('title', '').strip() for item in data)
    
    result.metrics['potential_labels_found'] = len(potential_labels)
    result.metrics['fields_captured'] = len(data)
    
    # Estimate coverage (rough)
    if potential_labels:
        # Check how many potential labels are captured
        matched = 0
        for label in potential_labels:
            # Fuzzy match - check if captured title is similar
            label_lower = label.lower()
            for title in captured_titles:
                if label_lower in title.lower() or title.lower() in label_lower:
                    matched += 1
                    break
        
        coverage = (matched / len(potential_labels)) * 100
        result.metrics['estimated_coverage'] = f"{coverage:.1f}%"
        
        if coverage < 80:
            result.add_warning(f"Estimated field coverage is {coverage:.1f}% - may be missing fields")
        elif coverage >= 95:
            result.add_info(f"Excellent field coverage: {coverage:.1f}%")


def check_section_distribution(data: List[dict], result: ValidationResult):
    """Check section distribution"""
    sections = Counter(item.get('section', 'Unknown') for item in data)
    
    result.metrics['sections'] = dict(sections)
    
    # Check for fields in "General" section (often catch-all)
    general_count = sections.get('General', 0)
    total_count = len(data)
    
    if total_count > 0 and general_count / total_count > 0.5:
        result.add_warning(f"More than 50% of fields in 'General' section - may need better section inference")


def check_option_quality(data: List[dict], result: ValidationResult):
    """Check quality of options in radio/dropdown fields"""
    for item in data:
        if item.get('type') in ['radio', 'dropdown']:
            options = item.get('control', {}).get('options', [])
            
            if not options:
                result.add_warning(f"Field '{item.get('key')}' has no options")
                continue
            
            # Check for duplicate options
            option_names = [opt.get('name', '') for opt in options]
            duplicates = [name for name, count in Counter(option_names).items() if count > 1 and name]
            if duplicates:
                result.add_warning(f"Field '{item.get('key')}' has duplicate options: {duplicates}")
            
            # Check option format
            for opt in options:
                if 'name' not in opt or 'value' not in opt:
                    result.add_error(f"Field '{item.get('key')}' has malformed option: {opt}")


def check_field_types(data: List[dict], result: ValidationResult):
    """Verify field types are appropriate"""
    type_counts = Counter(item.get('type', 'unknown') for item in data)
    result.metrics['field_types'] = dict(type_counts)
    
    # Check for suspicious patterns
    for item in data:
        key = item.get('key', '')
        title = item.get('title', '').lower()
        ftype = item.get('type', '')
        
        # Date fields should have type 'date'
        if any(word in title for word in ['date', 'birth', 'dob']) and ftype != 'date':
            result.add_warning(f"Field '{key}' appears to be a date but has type '{ftype}'")
        
        # State fields should have type 'states'
        if 'state' in title and ftype not in ['states', 'input']:
            result.add_warning(f"Field '{key}' appears to be a state field but has type '{ftype}'")
        
        # Email/phone fields should be type 'input'
        if any(word in key for word in ['email', 'phone']) and ftype not in ['input']:
            result.add_warning(f"Field '{key}' appears to be contact info but has type '{ftype}'")


def validate_file(json_path: Path, txt_path: Path = None) -> ValidationResult:
    """Validate a single JSON file"""
    result = ValidationResult(json_path.name)
    
    try:
        # Load JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            result.add_error("JSON root must be an array")
            return result
        
        result.metrics['total_fields'] = len(data)
        
        # Run validations
        validate_json_structure(data, result)
        check_duplicate_keys(data, result)
        check_section_distribution(data, result)
        check_option_quality(data, result)
        check_field_types(data, result)
        
        # If text file provided, check completeness
        if txt_path and txt_path.exists():
            with open(txt_path, 'r', encoding='utf-8') as f:
                txt_content = f.read()
            check_field_completeness(data, txt_content, result)
        
    except json.JSONDecodeError as e:
        result.add_error(f"Invalid JSON: {e}")
    except Exception as e:
        result.add_error(f"Validation failed: {e}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate Modento JSON output quality")
    parser.add_argument('--json', type=Path, help="Path to JSON file to validate")
    parser.add_argument('--txt', type=Path, help="Path to corresponding text file (optional)")
    parser.add_argument('--dir', type=Path, help="Directory containing JSON files to validate")
    parser.add_argument('--summary', action='store_true', help="Show summary only")
    
    args = parser.parse_args()
    
    if not args.json and not args.dir:
        parser.error("Must specify either --json or --dir")
    
    results = []
    
    if args.json:
        # Validate single file
        result = validate_file(args.json, args.txt)
        results.append(result)
        if not args.summary:
            result.print_summary()
    
    if args.dir:
        # Validate all JSON files in directory
        json_files = sorted(args.dir.glob("*.modento.json"))
        print(f"\nValidating {len(json_files)} files in {args.dir}/")
        
        for json_path in json_files:
            # Try to find corresponding text file
            txt_name = json_path.stem.replace('.modento', '.txt')
            txt_path = Path('output') / txt_name
            
            result = validate_file(json_path, txt_path if txt_path.exists() else None)
            results.append(result)
            
            if not args.summary:
                result.print_summary()
    
    # Overall summary
    if len(results) > 1:
        print(f"\n{'='*80}")
        print(f"OVERALL SUMMARY ({len(results)} files)")
        print(f"{'='*80}")
        
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)
        valid_count = sum(1 for r in results if r.is_valid())
        
        print(f"\n✅ Valid files: {valid_count}/{len(results)}")
        print(f"❌ Total errors: {total_errors}")
        print(f"⚠️  Total warnings: {total_warnings}")
        
        if total_errors == 0:
            print("\n🎉 All files passed validation!")
        
        print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
