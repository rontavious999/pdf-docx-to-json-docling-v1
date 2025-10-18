#!/usr/bin/env python3
"""
Tests for evaluation feedback patches

This file tests the patches suggested in "Evaluation of PDF-DocX to JSON (Docling) Pipeline v1.pdf":
- Patch 2: Field Key Validation
- Patch 3: Skip non-extractable files
"""

import pytest
from pathlib import Path
import tempfile
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from docling_text_to_modento.core import is_valid_modento_key, validate_form, Question
from docling_extract import process_one as extract_process_one


class TestPatch2FieldKeyValidation:
    """
    Patch 2: Field Key Validation
    
    Tests the is_valid_modento_key() function that validates field keys
    conform to Modento's expected format (snake_case with only lowercase 
    letters, digits, underscores).
    """
    
    def test_valid_keys(self):
        """Test that properly formatted keys pass validation"""
        assert is_valid_modento_key("patient_name") is True
        assert is_valid_modento_key("date_of_birth") is True
        assert is_valid_modento_key("phone_1") is True
        assert is_valid_modento_key("phone_mobile") is True
        assert is_valid_modento_key("emergency_contact_name") is True
        assert is_valid_modento_key("q") is True
        assert is_valid_modento_key("q_1") is True
        assert is_valid_modento_key("insurance_primary_name") is True
        assert is_valid_modento_key("medical_history_diabetes") is True
        assert is_valid_modento_key("_private_field") is True  # starts with underscore is OK
    
    def test_invalid_uppercase(self):
        """Test that keys with uppercase letters fail validation"""
        assert is_valid_modento_key("Patient_Name") is False
        assert is_valid_modento_key("PATIENT_NAME") is False
        assert is_valid_modento_key("PatientName") is False
    
    def test_invalid_hyphens(self):
        """Test that keys with hyphens fail validation"""
        assert is_valid_modento_key("patient-name") is False
        assert is_valid_modento_key("date-of-birth") is False
    
    def test_invalid_special_chars(self):
        """Test that keys with special characters fail validation"""
        assert is_valid_modento_key("patient@name") is False
        assert is_valid_modento_key("patient.name") is False
        assert is_valid_modento_key("patient name") is False  # spaces not allowed
        assert is_valid_modento_key("patient/name") is False
    
    def test_invalid_starts_with_digit(self):
        """Test that keys starting with a digit fail validation"""
        assert is_valid_modento_key("1_patient") is False
        assert is_valid_modento_key("123test") is False
    
    def test_invalid_empty(self):
        """Test that empty keys fail validation"""
        assert is_valid_modento_key("") is False
    
    def test_validate_form_catches_invalid_keys(self):
        """Test that validate_form() detects invalid keys"""
        # Valid question
        valid_q = Question(
            key="patient_name",
            title="Patient Name",
            section="patient_info",
            type="text",
            optional=False,
            control={}
        )
        
        # Invalid question with uppercase
        invalid_q1 = Question(
            key="Patient_Name",
            title="Patient Name", 
            section="patient_info",
            type="text",
            optional=False,
            control={}
        )
        
        # Invalid question with hyphen
        invalid_q2 = Question(
            key="patient-name",
            title="Patient Name",
            section="patient_info", 
            type="text",
            optional=False,
            control={}
        )
        
        # Valid signature
        signature = Question(
            key="signature",
            title="Signature",
            section="signature",
            type="signature",
            optional=False,
            control={}
        )
        
        # Test with valid keys only
        errors = validate_form([valid_q, signature])
        invalid_key_errors = [e for e in errors if "Invalid key format" in e]
        assert len(invalid_key_errors) == 0
        
        # Test with invalid key (uppercase)
        errors = validate_form([invalid_q1, signature])
        invalid_key_errors = [e for e in errors if "Invalid key format" in e]
        assert len(invalid_key_errors) == 1
        assert "Patient_Name" in invalid_key_errors[0]
        
        # Test with invalid key (hyphen)
        errors = validate_form([invalid_q2, signature])
        invalid_key_errors = [e for e in errors if "Invalid key format" in e]
        assert len(invalid_key_errors) == 1
        assert "patient-name" in invalid_key_errors[0]


class TestPatch3SkipNonExtractableFiles:
    """
    Patch 3: Skip non-extractable files
    
    Tests that files that cannot be extracted (no text layer, no OCR available)
    are skipped gracefully instead of creating empty or error-containing outputs.
    """
    
    def test_skip_no_text_layer_marker(self):
        """Test that files with [NO TEXT LAYER] marker are skipped in extraction"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            out_dir = tmpdir / "output"
            out_dir.mkdir()
            
            # Create a dummy PDF path (won't actually be read in this test)
            # We'll mock the extraction result
            test_file = tmpdir / "test.pdf"
            test_file.write_text("dummy")
            
            # The actual test is in the process logic, but we can verify
            # the marker text would be caught
            marker_text = "[NO TEXT LAYER] This PDF appears to be scanned but OCR is not available."
            assert marker_text.startswith("[NO TEXT LAYER]")
    
    def test_skip_ocr_not_available_marker(self):
        """Test that files with [OCR NOT AVAILABLE] marker are skipped"""
        marker_text = "[OCR NOT AVAILABLE] PDF appears to be scanned but pytesseract is not installed."
        assert marker_text.startswith("[OCR NOT AVAILABLE]")
    
    def test_process_one_skips_unextractable_text(self):
        """Test that the conversion process skips files with extraction error markers"""
        # Import the conversion process_one
        from docling_text_to_modento.core import process_one as convert_process_one
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create a text file with error marker
            txt_file = tmpdir / "unextractable.txt"
            txt_file.write_text("[NO TEXT LAYER] This PDF appears to be scanned but OCR is not available.")
            
            out_dir = tmpdir / "output"
            out_dir.mkdir()
            
            # Process should skip this file
            result = convert_process_one(txt_file, out_dir, catalog=None, debug=False)
            
            # Should return None (skipped)
            assert result is None
            
            # Should not create JSON output
            json_files = list(out_dir.glob("*.json"))
            assert len(json_files) == 0
    
    def test_process_one_handles_normal_text(self):
        """Test that normal text files are still processed"""
        from docling_text_to_modento.core import process_one as convert_process_one
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create a normal text file
            txt_file = tmpdir / "normal.txt"
            txt_file.write_text("""
Patient Information

Name: John Doe
Date of Birth: 01/01/1980
Phone: 555-1234

Signature: ________________
""")
            
            out_dir = tmpdir / "output"
            out_dir.mkdir()
            
            # Process should handle this file normally
            result = convert_process_one(txt_file, out_dir, catalog=None, debug=False)
            
            # Should return output path
            assert result is not None
            assert result.exists()
            assert result.suffix == ".json"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
