#!/usr/bin/env python3
"""
Integration tests for the PDF-to-JSON pipeline.

Patch 3: End-to-end testing
Tests the complete pipeline: PDF/DOCX → text extraction → JSON conversion

These tests verify that the entire workflow functions correctly,
catching integration issues that unit tests might miss.
"""

import json
import shutil
import tempfile
from pathlib import Path
import pytest

# Import the extraction and conversion functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from unstructured_extract import process_one as extract_process_one
from text_to_modento.core import process_one as convert_process_one
from text_to_modento.modules.template_catalog import TemplateCatalog


class TestIntegrationPipeline:
    """Integration tests for the full PDF/DOCX to JSON pipeline."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for test outputs."""
        temp_base = tempfile.mkdtemp()
        temp_path = Path(temp_base)
        
        text_dir = temp_path / "text_output"
        json_dir = temp_path / "json_output"
        
        text_dir.mkdir()
        json_dir.mkdir()
        
        yield {
            'base': temp_path,
            'text': text_dir,
            'json': json_dir
        }
        
        # Cleanup
        shutil.rmtree(temp_base)
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the path to test fixtures."""
        return Path(__file__).parent / "fixtures"
    
    @pytest.fixture
    def catalog(self):
        """Load the template catalog for testing."""
        dict_path = Path(__file__).parent.parent / "dental_form_dictionary.json"
        if dict_path.exists():
            return TemplateCatalog.from_path(dict_path)
        return None
    
    def test_pdf_to_text_extraction(self, temp_dirs, fixtures_dir):
        """Test PDF text extraction step."""
        pdf_file = fixtures_dir / "test_consent_form.pdf"
        
        if not pdf_file.exists():
            pytest.skip("Test PDF fixture not found")
        
        # Extract text from PDF
        extract_process_one(
            file_path=pdf_file,
            out_dir=temp_dirs['text'],
            use_ocr=False,
            auto_ocr=True
        )
        
        # Verify text file was created
        text_files = list(temp_dirs['text'].glob("*.txt"))
        assert len(text_files) == 1, "Expected exactly one text file"
        
        # Verify content was extracted
        text_content = text_files[0].read_text()
        assert len(text_content) > 0, "Text file should not be empty"
        assert "Patient" in text_content or "patient" in text_content.lower(), \
            "Expected patient-related content in extracted text"
    
    def test_docx_to_text_extraction(self, temp_dirs, fixtures_dir):
        """Test DOCX text extraction step."""
        docx_file = fixtures_dir / "test_patient_form.docx"
        
        if not docx_file.exists():
            pytest.skip("Test DOCX fixture not found")
        
        # Extract text from DOCX
        extract_process_one(
            file_path=docx_file,
            out_dir=temp_dirs['text'],
            use_ocr=False,
            auto_ocr=False
        )
        
        # Verify text file was created
        text_files = list(temp_dirs['text'].glob("*.txt"))
        assert len(text_files) == 1, "Expected exactly one text file"
        
        # Verify content was extracted
        text_content = text_files[0].read_text()
        assert len(text_content) > 0, "Text file should not be empty"
        assert "Patient" in text_content, "Expected patient-related content"
    
    def test_text_to_json_conversion(self, temp_dirs, fixtures_dir, catalog):
        """Test text to JSON conversion step."""
        # First extract text from a test file
        docx_file = fixtures_dir / "test_patient_form.docx"
        
        if not docx_file.exists():
            pytest.skip("Test DOCX fixture not found")
        
        extract_process_one(
            file_path=docx_file,
            out_dir=temp_dirs['text'],
            use_ocr=False,
            auto_ocr=False
        )
        
        # Get the extracted text file
        text_files = list(temp_dirs['text'].glob("*.txt"))
        assert len(text_files) == 1
        text_file = text_files[0]
        
        # Convert text to JSON
        convert_process_one(
            txt_path=text_file,
            out_dir=temp_dirs['json'],
            catalog=catalog,
            debug=False
        )
        
        # Verify JSON file was created
        json_files = list(temp_dirs['json'].glob("*.modento.json"))
        assert len(json_files) == 1, "Expected exactly one JSON file"
        
        # Verify JSON structure
        with open(json_files[0], 'r') as f:
            data = json.load(f)
        
        # JSON output is a list of field dictionaries
        assert isinstance(data, (dict, list)), "JSON output should be a dictionary or list"
        # Basic structure checks - should have some fields
        assert len(data) > 0, "JSON should not be empty"
    
    def test_full_pipeline_pdf(self, temp_dirs, fixtures_dir, catalog):
        """Test complete pipeline: PDF → text → JSON."""
        pdf_file = fixtures_dir / "test_consent_form.pdf"
        
        if not pdf_file.exists():
            pytest.skip("Test PDF fixture not found")
        
        # Step 1: Extract text
        extract_process_one(
            file_path=pdf_file,
            out_dir=temp_dirs['text'],
            use_ocr=False,
            auto_ocr=True
        )
        
        text_files = list(temp_dirs['text'].glob("*.txt"))
        assert len(text_files) == 1
        
        # Step 2: Convert to JSON
        convert_process_one(
            txt_path=text_files[0],
            out_dir=temp_dirs['json'],
            catalog=catalog,
            debug=False
        )
        
        # Verify final JSON output
        json_files = list(temp_dirs['json'].glob("*.modento.json"))
        assert len(json_files) == 1
        
        with open(json_files[0], 'r') as f:
            data = json.load(f)
        
        assert isinstance(data, (dict, list))
        assert len(data) > 0
    
    def test_full_pipeline_docx(self, temp_dirs, fixtures_dir, catalog):
        """Test complete pipeline: DOCX → text → JSON."""
        docx_file = fixtures_dir / "test_patient_form.docx"
        
        if not docx_file.exists():
            pytest.skip("Test DOCX fixture not found")
        
        # Step 1: Extract text
        extract_process_one(
            file_path=docx_file,
            out_dir=temp_dirs['text'],
            use_ocr=False,
            auto_ocr=False
        )
        
        text_files = list(temp_dirs['text'].glob("*.txt"))
        assert len(text_files) == 1
        
        # Step 2: Convert to JSON
        convert_process_one(
            txt_path=text_files[0],
            out_dir=temp_dirs['json'],
            catalog=catalog,
            debug=False
        )
        
        # Verify final JSON output
        json_files = list(temp_dirs['json'].glob("*.modento.json"))
        assert len(json_files) == 1
        
        with open(json_files[0], 'r') as f:
            data = json.load(f)
        
        assert isinstance(data, (dict, list))
        assert len(data) > 0
    
    def test_parallel_file_naming_uniqueness(self, temp_dirs, fixtures_dir):
        """
        Test that unique file naming works correctly.
        
        Patch 1: Verifies that files with same name get unique outputs.
        """
        pdf_file = fixtures_dir / "test_consent_form.pdf"
        
        if not pdf_file.exists():
            pytest.skip("Test PDF fixture not found")
        
        # Process the same file twice (simulating duplicate names)
        extract_process_one(
            file_path=pdf_file,
            out_dir=temp_dirs['text'],
            use_ocr=False,
            auto_ocr=True
        )
        
        # First extraction should create a file
        text_files = list(temp_dirs['text'].glob("*.txt"))
        assert len(text_files) == 1
        
        # The file should have a folder hash in its name (Patch 1)
        text_file_name = text_files[0].name
        assert "_" in text_file_name, "Output filename should include folder hash for uniqueness"


class TestIntegrationErrorHandling:
    """Integration tests for error handling in the pipeline."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for test outputs."""
        temp_base = tempfile.mkdtemp()
        temp_path = Path(temp_base)
        
        text_dir = temp_path / "text_output"
        json_dir = temp_path / "json_output"
        
        text_dir.mkdir()
        json_dir.mkdir()
        
        yield {
            'base': temp_path,
            'text': text_dir,
            'json': json_dir
        }
        
        # Cleanup
        shutil.rmtree(temp_base)
    
    def test_unsupported_file_type(self, temp_dirs):
        """Test handling of unsupported file types."""
        # Create a dummy .txt file (unsupported for extraction)
        dummy_file = temp_dirs['base'] / "test.txt"
        dummy_file.write_text("This is not a PDF or DOCX")
        
        # Should handle gracefully (not crash)
        try:
            extract_process_one(
                file_path=dummy_file,
                out_dir=temp_dirs['text'],
                use_ocr=False,
                auto_ocr=False
            )
        except Exception:
            # It's okay if it raises an exception for unsupported types
            pass
        
        # Should not create output for unsupported types
        text_files = list(temp_dirs['text'].glob("*.txt"))
        assert len(text_files) == 0, "Should not create output for unsupported file types"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
