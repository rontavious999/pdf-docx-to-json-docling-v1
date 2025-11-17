#!/usr/bin/env python3
"""
Tests for multi_model_extract.py

Tests the multi-model extraction functionality, quality scoring,
and heuristics system.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from multi_model_extract import (
    DocumentExtractor,
    ExtractionResult,
    QualityMetrics,
    PDFPLUMBER_AVAILABLE
)


class TestQualityMetrics:
    """Test quality metric calculation"""
    
    def test_empty_text_metrics(self):
        """Test metrics for empty text"""
        extractor = DocumentExtractor()
        metrics = extractor.calculate_quality_metrics("")
        
        assert metrics.char_count == 0
        assert metrics.word_count == 0
        assert metrics.line_count == 0
        assert metrics.confidence_score == 0.0
    
    def test_good_quality_text_metrics(self):
        """Test metrics for high-quality text"""
        text = """Patient Information Form
        
        Name: John Doe
        Date of Birth: 01/15/1980
        Phone: (555) 123-4567
        Email: john.doe@example.com
        
        Medical History:
        [ ] Diabetes
        [ ] High Blood Pressure
        [X] Allergies
        """
        
        extractor = DocumentExtractor()
        metrics = extractor.calculate_quality_metrics(text)
        
        assert metrics.char_count > 0
        assert metrics.word_count > 10
        assert metrics.alphanumeric_ratio > 0.5
        assert metrics.has_structured_content is True
        assert metrics.confidence_score >= 50  # Should be decent quality (>= instead of >)
    
    def test_noisy_text_metrics(self):
        """Test metrics for low-quality/noisy text"""
        text = "###!!!   %%%   $$$$$ @@@@"
        
        extractor = DocumentExtractor()
        metrics = extractor.calculate_quality_metrics(text)
        
        assert metrics.char_count > 0
        assert metrics.alphanumeric_ratio < 0.3  # Mostly non-alphanumeric
        assert metrics.confidence_score < 50  # Poor quality
    
    def test_structured_content_detection(self):
        """Test detection of form fields and structured content"""
        extractor = DocumentExtractor()
        
        # Test with form fields
        form_text = "Name: ___________  Date: ___________"
        metrics = extractor.calculate_quality_metrics(form_text)
        assert metrics.has_structured_content is True
        
        # Test with checkboxes
        checkbox_text = "Options: [ ] Yes [ ] No"
        metrics = extractor.calculate_quality_metrics(checkbox_text)
        assert metrics.has_structured_content is True
        
        # Test without structure
        plain_text = "This is just a simple paragraph without any form fields."
        metrics = extractor.calculate_quality_metrics(plain_text)
        assert metrics.has_structured_content is False


class TestDocumentTypeDetection:
    """Test heuristics for document type detection"""
    
    def test_validate_file(self):
        """Test file validation"""
        extractor = DocumentExtractor()
        
        # Create temporary files for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_file = Path(tmpdir) / "test.pdf"
            docx_file = Path(tmpdir) / "test.docx"
            txt_file = Path(tmpdir) / "test.txt"
            
            pdf_file.touch()
            docx_file.touch()
            txt_file.touch()
            
            assert extractor.validate_file(str(pdf_file)) is True
            assert extractor.validate_file(str(docx_file)) is True
            assert extractor.validate_file(str(txt_file)) is False
        
        # Test non-existent file
        assert extractor.validate_file("nonexistent.pdf") is False
    
    @pytest.mark.skipif(not PDFPLUMBER_AVAILABLE, reason="pdfplumber not installed")
    @patch('pdfplumber.open')
    def test_scanned_pdf_detection_with_text(self, mock_pdfplumber):
        """Test detection of digital PDF (has text)"""
        # Mock a PDF with text content
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is a digital PDF with plenty of text content."
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber.return_value = mock_pdf
        
        extractor = DocumentExtractor()
        is_scanned, reason = extractor.is_scanned_pdf("test.pdf")
        
        assert is_scanned is False
        assert "Digital PDF" in reason
    
    @pytest.mark.skipif(not PDFPLUMBER_AVAILABLE, reason="pdfplumber not installed")
    @patch('pdfplumber.open')
    def test_scanned_pdf_detection_no_text(self, mock_pdfplumber):
        """Test detection of scanned PDF (no text)"""
        # Mock a PDF without text content
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page, mock_page, mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber.return_value = mock_pdf
        
        extractor = DocumentExtractor()
        is_scanned, reason = extractor.is_scanned_pdf("test.pdf")
        
        assert is_scanned is True
        assert "Minimal text found" in reason
    
    def test_recommend_model_for_docx(self):
        """Test model recommendation for DOCX files"""
        extractor = DocumentExtractor()
        model, reason = extractor.recommend_model("test.docx")
        
        assert model == "unstructured"
        assert "Word" in reason
    
    @patch.object(DocumentExtractor, 'is_scanned_pdf')
    def test_recommend_model_for_digital_pdf(self, mock_is_scanned):
        """Test model recommendation for digital PDF"""
        mock_is_scanned.return_value = (False, "Digital PDF with 500 chars")
        
        extractor = DocumentExtractor()
        model, reason = extractor.recommend_model("test.pdf")
        
        # Should recommend pdfplumber or unstructured for digital PDFs
        assert model in ["pdfplumber", "unstructured"]
        assert "Digital PDF" in reason
    
    @patch.object(DocumentExtractor, 'is_scanned_pdf')
    def test_recommend_model_for_scanned_pdf(self, mock_is_scanned):
        """Test model recommendation for scanned PDF"""
        mock_is_scanned.return_value = (True, "Minimal text found (5 chars)")
        
        extractor = DocumentExtractor()
        model, reason = extractor.recommend_model("test.pdf")
        
        # Should recommend an OCR model for scanned PDFs
        assert model in ["easyocr", "doctr", "ocrmypdf", "tesseract"]
        assert "Scanned PDF" in reason


class TestExtractionResult:
    """Test ExtractionResult dataclass"""
    
    def test_extraction_result_creation(self):
        """Test creating extraction result"""
        result = ExtractionResult(
            model="unstructured",
            text="Sample text",
            success=True,
            quality_score=85.5
        )
        
        assert result.model == "unstructured"
        assert result.text == "Sample text"
        assert result.success is True
        assert result.quality_score == 85.5
        assert result.error is None
        assert result.metadata == {}
    
    def test_extraction_result_with_error(self):
        """Test extraction result with error"""
        result = ExtractionResult(
            model="doctr",
            text="",
            success=False,
            error="Model not available"
        )
        
        assert result.success is False
        assert result.error == "Model not available"
        assert result.text == ""


class TestModelExtraction:
    """Test individual model extraction methods"""
    
    def test_extract_with_unavailable_model(self):
        """Test extraction when model is not available"""
        extractor = DocumentExtractor()
        
        # Test with model that doesn't exist
        result = extractor.extract_with_model("test.pdf", "nonexistent_model")
        
        assert result.success is False
        assert "Unknown model" in result.error
    
    @patch('multi_model_extract.UNSTRUCTURED_AVAILABLE', False)
    def test_extract_unstructured_unavailable(self):
        """Test unstructured extraction when library not available"""
        extractor = DocumentExtractor()
        result = extractor.extract_unstructured("test.pdf")
        
        assert result.success is False
        assert result.model == "unstructured"
        assert "not available" in result.error
    
    @patch('multi_model_extract.PDFPLUMBER_AVAILABLE', False)
    def test_extract_pdfplumber_unavailable(self):
        """Test pdfplumber extraction when library not available"""
        extractor = DocumentExtractor()
        result = extractor.extract_pdfplumber("test.pdf")
        
        assert result.success is False
        assert result.model == "pdfplumber"
    
    def test_extract_pdfplumber_with_docx(self):
        """Test pdfplumber with DOCX file (should fail)"""
        extractor = DocumentExtractor()
        result = extractor.extract_pdfplumber("test.docx")
        
        assert result.success is False
        # Error message depends on whether pdfplumber is available
        assert "not available" in result.error or "only works with PDF" in result.error


class TestAutoSelection:
    """Test automatic model selection"""
    
    @patch.object(DocumentExtractor, 'recommend_model')
    @patch.object(DocumentExtractor, 'extract_with_model')
    def test_auto_selection_with_good_result(self, mock_extract, mock_recommend):
        """Test auto selection when recommended model works well"""
        mock_recommend.return_value = ("unstructured", "Best for this file")
        
        # Mock a good extraction result
        mock_extract.return_value = ExtractionResult(
            model="unstructured",
            text="High quality extracted text",
            success=True,
            quality_score=85.0
        )
        
        extractor = DocumentExtractor()
        result = extractor.extract_auto("test.pdf")
        
        assert result.success is True
        assert result.quality_score >= 70
    
    @patch.object(DocumentExtractor, 'recommend_model')
    @patch.object(DocumentExtractor, 'extract_with_model')
    def test_auto_selection_with_fallback(self, mock_extract, mock_recommend):
        """Test auto selection with fallback to better model"""
        mock_recommend.return_value = ("pdfplumber", "Fast extraction")
        
        # Mock poor result from first model, better from fallback
        def extract_side_effect(file_path, model):
            if model == "pdfplumber":
                return ExtractionResult(
                    model="pdfplumber",
                    text="Poor quality",
                    success=True,
                    quality_score=40.0
                )
            elif model == "unstructured":
                return ExtractionResult(
                    model="unstructured",
                    text="Much better quality text",
                    success=True,
                    quality_score=85.0
                )
            else:
                return ExtractionResult(
                    model=model,
                    text="",
                    success=False,
                    error="Not available"
                )
        
        mock_extract.side_effect = extract_side_effect
        
        extractor = DocumentExtractor()
        result = extractor.extract_auto("test.pdf")
        
        # Should have tried fallback and selected better model
        assert result.success is True
        assert result.quality_score > 70


class TestComparisonReporting:
    """Test comparison report generation"""
    
    def test_generate_comparison_report(self):
        """Test generating comparison report"""
        extractor = DocumentExtractor()
        
        results = [
            ExtractionResult(
                model="unstructured",
                text="Sample text from unstructured",
                success=True,
                quality_score=85.0,
                metadata={
                    'metrics': {
                        'char_count': 100,
                        'word_count': 20,
                        'line_count': 5,
                        'confidence_score': 85.0,
                        'has_structured_content': True
                    }
                }
            ),
            ExtractionResult(
                model="pdfplumber",
                text="",
                success=False,
                error="Library not available"
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.pdf"
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            
            extractor.generate_comparison_report(file_path, results, output_dir)
            
            report_path = output_dir / "test_comparison_report.md"
            assert report_path.exists()
            
            content = report_path.read_text()
            assert "Multi-Model Extraction Comparison" in content
            assert "unstructured" in content
            assert "pdfplumber" in content
            assert "85.0" in content  # Quality score


class TestProcessing:
    """Test file and folder processing"""
    
    @patch.object(DocumentExtractor, 'validate_file')
    def test_process_file_invalid(self, mock_validate):
        """Test processing invalid file"""
        mock_validate.return_value = False
        
        extractor = DocumentExtractor()
        result = extractor.process_file("invalid.txt", "output", "unstructured")
        
        assert result is False
    
    @patch.object(DocumentExtractor, 'extract_with_model')
    @patch.object(DocumentExtractor, 'validate_file')
    def test_process_file_success(self, mock_validate, mock_extract):
        """Test successful file processing"""
        mock_validate.return_value = True
        mock_extract.return_value = ExtractionResult(
            model="unstructured",
            text="Extracted text",
            success=True,
            quality_score=85.0
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.pdf"
            file_path.touch()  # Create empty file
            output_dir = Path(tmpdir) / "output"
            
            extractor = DocumentExtractor()
            result = extractor.process_file(str(file_path), str(output_dir), "unstructured")
            
            assert result is True
            assert (output_dir / "test.txt").exists()
    
    @patch.object(DocumentExtractor, 'recommend_model')
    @patch.object(DocumentExtractor, 'extract_with_model')
    @patch.object(DocumentExtractor, 'validate_file')
    def test_process_file_recommend_mode(self, mock_validate, mock_extract, mock_recommend):
        """Test processing file with recommend mode"""
        mock_validate.return_value = True
        mock_recommend.return_value = ("pdfplumber", "Digital PDF: pdfplumber is fast")
        mock_extract.return_value = ExtractionResult(
            model="pdfplumber",
            text="Extracted text from pdfplumber",
            success=True,
            quality_score=88.0
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.pdf"
            file_path.touch()  # Create empty file
            output_dir = Path(tmpdir) / "output"
            
            extractor = DocumentExtractor()
            result = extractor.process_file(str(file_path), str(output_dir), "recommend")
            
            assert result is True
            assert (output_dir / "test.txt").exists()
            # Verify recommend_model was called
            mock_recommend.assert_called_once()
            # Verify extract_with_model was called with the recommended model
            mock_extract.assert_called_once_with(str(file_path), "pdfplumber")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
