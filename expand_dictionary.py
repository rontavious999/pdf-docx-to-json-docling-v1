#!/usr/bin/env python3
"""
expand_dictionary.py

Parity Improvement #4 & #6: Expand dictionary with common unmatched fields
and add medical conditions template.

Usage:
    python3 expand_dictionary.py
"""

import json
from pathlib import Path

# Common medical conditions for "Do you have or have you had any of the following?" grids
MEDICAL_CONDITIONS = [
    "Heart Disease", "High Blood Pressure", "Low Blood Pressure",
    "Stroke", "Heart Attack", "Angina", "Heart Murmur",
    "Rheumatic Fever", "Artificial Heart Valve", "Pacemaker",
    "Diabetes", "Hypoglycemia", "Thyroid Disease",
    "Cancer", "Chemotherapy", "Radiation Therapy",
    "Anemia", "Blood Disorder", "Bleeding Disorder",
    "Hepatitis", "Liver Disease", "Kidney Disease",
    "Asthma", "Emphysema", "Tuberculosis", "COPD",
    "Arthritis", "Rheumatism", "Joint Replacement",
    "Osteoporosis", "Bone Disease",
    "HIV/AIDS", "Sexually Transmitted Disease",
    "Seizures", "Epilepsy", "Neurological Disorder",
    "Mental Health Disorder", "Depression", "Anxiety",
    "Glaucoma", "Vision Problems",
    "Stomach/Intestinal Disease", "Ulcers",
    "Pregnancy", "Nursing",
]

def expand_dictionary():
    """
    Expand the dental_form_dictionary.json with:
    1. Medical conditions template (Improvement #6)
    2. Common unmatched fields from analysis (Improvement #4)
    """
    dict_path = Path('dental_form_dictionary.json')
    
    if not dict_path.exists():
        print(f"ERROR: {dict_path} not found")
        return
    
    # Load dictionary
    with open(dict_path, 'r', encoding='utf-8') as f:
        dictionary = json.load(f)
    
    # Add medical conditions template
    if 'medical_conditions' not in dictionary:
        print("Adding medical_conditions template...")
        dictionary['medical_conditions'] = [{
            "key": "medical_conditions",
            "type": "conditions",
            "title": "Do you have or have you had any of the following?",
            "section": "Medical History",
            "optional": False,
            "control": {
                "options": [
                    {"name": condition, "value": condition.lower().replace(" ", "_").replace("/", "_")}
                    for condition in MEDICAL_CONDITIONS
                ]
            }
        }]
    
    # Add common unmatched fields to aliases
    if 'aliases' in dictionary and isinstance(dictionary['aliases'], dict):
        print("Adding common field aliases...")
        
        # Common variations for existing fields
        new_aliases = {
            "are_you_under_a_physicians_care_now": "1.under_care",
            "are_you_under_physician_care": "1.under_care",
            "under_doctors_care": "1.under_care",
            "have_you_ever_been_hospitalized": "hospitalized",
            "have_you_had_surgery": "hospitalized",
            "have_you_ever_had_major_surgery": "hospitalized",
            "are_you_taking_any_medications": "taking_medication",
            "taking_any_medicine": "taking_medication",
            "current_medications": "taking_medication",
            "do_you_have_allergies": "allergies",
            "allergic_to_any_medications": "allergies",
            "medical_conditions": "medical_conditions",
            "medical_history": "medical_conditions",
            "health_conditions": "medical_conditions",
        }
        
        for alias_key, target_key in new_aliases.items():
            if alias_key not in dictionary['aliases']:
                dictionary['aliases'][alias_key] = target_key
    
    # Update version
    if '_meta' in dictionary:
        meta = dictionary['_meta']
        current_version = meta.get('version', '1.2.0')
        major, minor, patch = current_version.split('.')
        new_version = f"{major}.{int(minor)+1}.0"
        meta['version'] = new_version
        meta['notes'] = (meta.get('notes', '') + 
                        f" v{new_version} adds medical_conditions template and common field aliases (Parity Improvements #4 & #6).")
    
    # Save dictionary
    backup_path = dict_path.with_suffix('.json.backup2')
    print(f"Creating backup: {backup_path}")
    dict_path.rename(backup_path)
    
    with open(dict_path, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Dictionary expanded successfully!")
    print(f"   - Added medical_conditions template with {len(MEDICAL_CONDITIONS)} conditions")
    print(f"   - Added {len(new_aliases)} field aliases")
    print(f"   - Version updated to {dictionary['_meta']['version']}")

if __name__ == '__main__':
    expand_dictionary()
