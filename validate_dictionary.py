#!/usr/bin/env python3
"""
validate_dictionary.py

Validate the dental_form_dictionary.json file for consistency and correctness.

Priority 7.1: Template Dictionary Versioning and Validation
- Validates JSON schema compliance
- Checks for required fields
- Validates field types and structures
- Enforces option format consistency
- Validates "if" clause references

USAGE:
  python3 validate_dictionary.py
  python3 validate_dictionary.py --dict path/to/dictionary.json
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Any


class DictionaryValidator:
    """Validates dental form dictionary structure and content."""
    
    def __init__(self, dict_path: Path):
        self.dict_path = dict_path
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.data: Dict[str, Any] = {}
        self.all_keys: Set[str] = set()
    
    def validate(self) -> bool:
        """Run all validations. Returns True if valid, False otherwise."""
        print(f"Validating {self.dict_path.name}...")
        
        # Load and parse JSON
        if not self._load_json():
            return False
        
        # Run validations
        self._validate_metadata()
        self._validate_structure()
        self._collect_all_keys()
        self._validate_fields()
        self._validate_if_clauses()
        
        # Report results
        self._print_results()
        
        return len(self.errors) == 0
    
    def _load_json(self) -> bool:
        """Load and parse the JSON file."""
        try:
            self.data = json.loads(self.dict_path.read_text(encoding='utf-8'))
            return True
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False
    
    def _validate_metadata(self):
        """Validate _meta section."""
        if '_meta' not in self.data:
            self.warnings.append("Missing _meta section")
            return
        
        meta = self.data['_meta']
        required_meta_fields = ['name', 'version']
        for field in required_meta_fields:
            if field not in meta:
                self.errors.append(f"Missing required _meta field: {field}")
        
        if 'version' in meta:
            version = meta['version']
            # Version should be semantic versioning format: X.Y.Z
            parts = str(version).split('.')
            if len(parts) != 3 or not all(p.isdigit() for p in parts):
                self.warnings.append(f"Version '{version}' should follow semantic versioning (X.Y.Z)")
    
    def _validate_structure(self):
        """Validate overall dictionary structure."""
        if not self.data:
            self.errors.append("Dictionary is empty")
            return
        
        # Check for at least one category besides _meta and aliases
        categories = [k for k in self.data.keys() if not k.startswith('_') and k != 'aliases']
        if not categories:
            self.errors.append("No field categories found (besides _meta and aliases)")
        
        # Each category should be a list (except 'aliases' which is a dict)
        for category, fields in self.data.items():
            if category.startswith('_') or category == 'aliases':
                continue  # Skip metadata and aliases
            if not isinstance(fields, list):
                self.errors.append(f"Category '{category}' should be a list, got {type(fields).__name__}")
    
    def _collect_all_keys(self):
        """Collect all field keys for reference validation."""
        for category, fields in self.data.items():
            if category.startswith('_') or category == 'aliases' or not isinstance(fields, list):
                continue
            for field in fields:
                if isinstance(field, dict) and 'key' in field:
                    self.all_keys.add(field['key'])
    
    def _validate_fields(self):
        """Validate individual field definitions."""
        for category, fields in self.data.items():
            if category.startswith('_') or category == 'aliases' or not isinstance(fields, list):
                continue
            
            for idx, field in enumerate(fields):
                if not isinstance(field, dict):
                    self.errors.append(f"Field at {category}[{idx}] is not a dict")
                    continue
                
                # Required fields
                if 'key' not in field:
                    self.errors.append(f"Field at {category}[{idx}] missing 'key'")
                    continue
                
                key = field['key']
                
                if 'type' not in field:
                    self.errors.append(f"Field '{key}' missing 'type'")
                
                # Validate type
                valid_types = ['input', 'radio', 'checkbox', 'dropdown', 'date', 'states', 
                              'block_signature', 'block_text', 'photo', 'text', 'multiradio', 'terms']
                if 'type' in field and field['type'] not in valid_types:
                    self.warnings.append(f"Field '{key}' has unusual type: {field['type']}")
                
                # Validate control structure
                if 'control' in field:
                    self._validate_control(key, field['control'])
                
                # Validate options for choice fields
                if field.get('type') in ['radio', 'checkbox', 'dropdown']:
                    if 'control' in field and 'options' in field['control']:
                        self._validate_options(key, field['control']['options'])
    
    def _validate_control(self, key: str, control: dict):
        """Validate control structure."""
        if not isinstance(control, dict):
            self.errors.append(f"Field '{key}' control is not a dict")
            return
        
        # Check for common control properties
        if 'input_type' in control:
            valid_input_types = ['text', 'email', 'phone', 'ssn', 'name', 'date', 'past', 'future', 'zip']
            if control['input_type'] not in valid_input_types:
                self.warnings.append(f"Field '{key}' has unusual input_type: {control['input_type']}")
    
    def _validate_options(self, key: str, options: list):
        """Validate options array format."""
        if not isinstance(options, list):
            self.errors.append(f"Field '{key}' options is not a list")
            return
        
        for idx, option in enumerate(options):
            if not isinstance(option, dict):
                self.errors.append(f"Field '{key}' option[{idx}] is not a dict")
                continue
            
            if 'name' not in option:
                self.errors.append(f"Field '{key}' option[{idx}] missing 'name'")
            
            if 'value' not in option:
                self.warnings.append(f"Field '{key}' option[{idx}] missing 'value'")
    
    def _validate_if_clauses(self):
        """Validate 'if' clause references."""
        for category, fields in self.data.items():
            if category.startswith('_') or category == 'aliases' or not isinstance(fields, list):
                continue
            
            for field in fields:
                if not isinstance(field, dict):
                    continue
                
                key = field.get('key')
                if not key:
                    continue
                
                # Check if field has 'if' clause
                if 'if' in field:
                    if_clause = field['if']
                    if not isinstance(if_clause, list):
                        self.errors.append(f"Field '{key}' 'if' clause is not a list")
                        continue
                    
                    for condition in if_clause:
                        if isinstance(condition, dict) and 'key' in condition:
                            ref_key = condition['key']
                            if ref_key not in self.all_keys:
                                self.warnings.append(
                                    f"Field '{key}' 'if' clause references unknown key: {ref_key}"
                                )
    
    def _print_results(self):
        """Print validation results."""
        print()
        
        if self.errors:
            print(f"❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
            print()
        
        if self.warnings:
            print(f"⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
            print()
        
        if not self.errors and not self.warnings:
            print("✅ Dictionary is valid!")
        elif not self.errors:
            print(f"✅ Dictionary is valid (with {len(self.warnings)} warnings)")
        else:
            print(f"❌ Dictionary validation failed with {len(self.errors)} errors")
        
        # Print summary statistics
        categories = [k for k in self.data.keys() if not k.startswith('_') and k != 'aliases']
        total_fields = sum(len(v) for k, v in self.data.items() 
                          if not k.startswith('_') and k != 'aliases' and isinstance(v, list))
        
        print()
        print(f"📊 Statistics:")
        print(f"  • Version: {self.data.get('_meta', {}).get('version', 'unknown')}")
        print(f"  • Categories: {len(categories)}")
        print(f"  • Total fields: {total_fields}")
        print(f"  • Unique keys: {len(self.all_keys)}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate dental_form_dictionary.json structure and content"
    )
    parser.add_argument(
        '--dict',
        type=Path,
        default=Path('dental_form_dictionary.json'),
        help='Path to dictionary file (default: dental_form_dictionary.json)'
    )
    args = parser.parse_args()
    
    dict_path = args.dict
    if not dict_path.exists():
        print(f"Error: Dictionary file not found: {dict_path}", file=sys.stderr)
        sys.exit(1)
    
    validator = DictionaryValidator(dict_path)
    is_valid = validator.validate()
    
    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
