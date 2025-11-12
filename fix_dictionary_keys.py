#!/usr/bin/env python3
"""
Fix invalid keys in the dental_form_dictionary.json file.
Keys must start with a lowercase letter and contain only lowercase letters, numbers, and underscores.
"""

import json
import re
from pathlib import Path


def fix_key(key: str) -> str:
    """
    Fix an invalid key to make it valid.
    
    Rules:
    - Must start with lowercase letter
    - Can contain lowercase letters, numbers, underscores
    - If starts with digit, prepend 'q_'
    - If starts with uppercase, convert to lowercase
    - Remove any other invalid characters
    """
    if not key:
        return 'field'
    
    # Convert to lowercase
    key = key.lower()
    
    # Remove any characters that aren't alphanumeric or underscore
    key = re.sub(r'[^\w]', '_', key)
    
    # Remove consecutive underscores
    key = re.sub(r'_+', '_', key)
    
    # Remove leading/trailing underscores
    key = key.strip('_')
    
    # If starts with digit, prepend 'q_'
    if key and key[0].isdigit():
        key = 'q_' + key
    
    # If empty after cleaning, use default
    if not key:
        key = 'field'
    
    return key


def fix_keys_in_dict(obj, key_mapping=None):
    """
    Recursively fix all invalid keys in the dictionary structure.
    Returns (fixed_obj, key_mapping)
    """
    if key_mapping is None:
        key_mapping = {}
    
    if isinstance(obj, dict):
        fixed_dict = {}
        for k, v in obj.items():
            # If this dict has a 'key' property, fix it
            if k == 'key' and isinstance(v, str):
                if v and not re.match(r'^[a-z][a-z0-9_]*$', v):
                    fixed_key = fix_key(v)
                    key_mapping[v] = fixed_key
                    fixed_dict[k] = fixed_key
                else:
                    fixed_dict[k] = v
            else:
                fixed_dict[k], key_mapping = fix_keys_in_dict(v, key_mapping)
        return fixed_dict, key_mapping
    
    elif isinstance(obj, list):
        return [fix_keys_in_dict(item, key_mapping)[0] for item in obj], key_mapping
    
    elif isinstance(obj, str):
        # Check if this string is a reference to a key that was fixed
        if obj in key_mapping:
            return key_mapping[obj], key_mapping
        return obj, key_mapping
    
    else:
        return obj, key_mapping


def main():
    """Main function to fix dictionary keys."""
    dict_path = Path('dental_form_dictionary.json')
    backup_path = Path('dental_form_dictionary.json.backup_before_fix')
    
    print("="*80)
    print("FIXING INVALID KEYS IN DENTAL FORM DICTIONARY")
    print("="*80)
    
    # Load dictionary
    print(f"\n📖 Loading dictionary from {dict_path}")
    with open(dict_path) as f:
        dictionary = json.load(f)
    
    # Find invalid keys
    print(f"\n🔍 Scanning for invalid keys...")
    
    def count_invalid_keys(obj):
        """Count invalid keys in structure."""
        count = 0
        if isinstance(obj, dict):
            if 'key' in obj and isinstance(obj['key'], str):
                key_val = obj['key']
                if key_val and not re.match(r'^[a-z][a-z0-9_]*$', key_val):
                    count += 1
            for v in obj.values():
                count += count_invalid_keys(v)
        elif isinstance(obj, list):
            for item in obj:
                count += count_invalid_keys(item)
        return count
    
    invalid_count = count_invalid_keys(dictionary)
    print(f"   Found {invalid_count} invalid keys")
    
    if invalid_count == 0:
        print("\n✅ No invalid keys found. Dictionary is already valid.")
        return
    
    # Create backup
    print(f"\n💾 Creating backup at {backup_path}")
    with open(backup_path, 'w') as f:
        json.dump(dictionary, f, indent=2)
    
    # Fix keys
    print(f"\n🔧 Fixing invalid keys...")
    fixed_dict, key_mapping = fix_keys_in_dict(dictionary)
    
    # Show mappings
    if key_mapping:
        print(f"\n📋 Key mappings ({len(key_mapping)} keys fixed):")
        for old_key, new_key in sorted(key_mapping.items())[:20]:
            print(f"   {old_key} -> {new_key}")
        if len(key_mapping) > 20:
            print(f"   ... and {len(key_mapping) - 20} more")
    
    # Verify no invalid keys remain
    remaining_invalid = count_invalid_keys(fixed_dict)
    if remaining_invalid > 0:
        print(f"\n⚠️  WARNING: {remaining_invalid} invalid keys still remain!")
        return
    
    # Save fixed dictionary
    print(f"\n💾 Saving fixed dictionary to {dict_path}")
    with open(dict_path, 'w') as f:
        json.dump(fixed_dict, f, indent=2)
    
    print(f"\n✅ Dictionary fixed successfully!")
    print(f"   - Fixed {len(key_mapping)} invalid keys")
    print(f"   - Backup saved to {backup_path}")
    print(f"   - Original dictionary updated")
    
    print(f"\n{'='*80}")


if __name__ == '__main__':
    main()
