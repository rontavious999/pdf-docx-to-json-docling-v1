#!/usr/bin/env python3
"""
multi_model_extract.py - Multi-Model Document Extraction with Intelligent Heuristics

Supports 6 extraction models from the bakeoff:
1. unstructured - High-accuracy ML-based layout detection (default)
2. doctr - Document OCR with transformer models
3. tesseract - Traditional OCR engine
4. pdfplumber - PDF text extraction (digital PDFs)
5. ocrmypdf - OCR for scanned PDFs
6. easyocr - Deep learning OCR

Features:
- Individual model selection or automatic best-model selection
- Quality scoring and heuristics for choosing the best extraction
- Comparative analysis mode for side-by-side comparison
- Fallback mechanism for graceful degradation

USAGE:
    # Use specific model
    python3 multi_model_extract.py --model unstructured --in documents --out output
    
    # Auto-select best model (tries multiple and picks best)
    python3 multi_model_extract.py --model auto --in documents --out output
    
    # Run all models for comparison
    python3 multi_model_extract.py --model all --in documents --out output
    
    # Use heuristics to recommend model for a file
    python3 multi_model_extract.py --recommend documents/file.pdf

REQUIREMENTS:
    pip install unstructured[all-docs] doctr pdfplumber ocrmypdf easyocr pytesseract pillow
"""

import os
import sys
import argparse
import traceback
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import Counter

# Model imports with fallback handling
try:
    from unstructured.partition.auto import partition as unstructured_partition
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    print("⚠️  unstructured not available. Install with: pip install unstructured[all-docs]")

try:
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    DOCTR_AVAILABLE = True
except ImportError:
    DOCTR_AVAILABLE = False
    print("⚠️  doctr not available. Install with: pip install python-doctr")

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("⚠️  pytesseract not available. Install with: pip install pytesseract pillow")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("⚠️  pdfplumber not available. Install with: pip install pdfplumber")

try:
    import ocrmypdf
    OCRMYPDF_AVAILABLE = True
except ImportError:
    OCRMYPDF_AVAILABLE = False
    print("⚠️  ocrmypdf not available. Install with: pip install ocrmypdf")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠️  easyocr not available. Install with: pip install easyocr")


@dataclass
class ExtractionResult:
    """Result from a document extraction attempt"""
    model: str
    text: str
    success: bool
    error: Optional[str] = None
    quality_score: float = 0.0
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class QualityMetrics:
    """Quality metrics for extracted text"""
    char_count: int
    word_count: int
    line_count: int
    avg_word_length: float
    alphanumeric_ratio: float
    whitespace_ratio: float
    punctuation_ratio: float
    digit_ratio: float
    uppercase_ratio: float
    has_structured_content: bool
    confidence_score: float
    
    def to_dict(self):
        return asdict(self)


class DocumentExtractor:
    """Multi-model document extraction with intelligent heuristics"""
    
    MODELS = ['unstructured', 'doctr', 'tesseract', 'pdfplumber', 'ocrmypdf', 'easyocr']
    
    def __init__(self):
        self.doctr_model = None
        self.easyocr_reader = None
    
    def validate_file(self, file_path: str) -> bool:
        """Check if file exists and is valid PDF/DOCX"""
        if not os.path.exists(file_path):
            return False
        return file_path.lower().endswith(('.pdf', '.docx'))
    
    def is_scanned_pdf(self, file_path: str) -> Tuple[bool, str]:
        """
        Heuristic to detect if PDF is scanned (image-based) or digital (text-based).
        Returns: (is_scanned, reason)
        """
        if not file_path.lower().endswith('.pdf'):
            return False, "Not a PDF"
        
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                if len(pdf.pages) == 0:
                    return True, "Empty PDF"
                
                # Check first 3 pages for text
                text_chars = 0
                pages_checked = min(3, len(pdf.pages))
                
                for i in range(pages_checked):
                    page = pdf.pages[i]
                    text = page.extract_text() or ""
                    text_chars += len(text.strip())
                
                # If very little text found, likely scanned
                if text_chars < 50:
                    return True, f"Minimal text found ({text_chars} chars in {pages_checked} pages)"
                else:
                    return False, f"Digital PDF with {text_chars} chars"
        except Exception as e:
            return True, f"Error checking PDF: {str(e)}"
    
    def recommend_model(self, file_path: str) -> str:
        """
        Heuristic to recommend best extraction model for a file.
        
        Decision tree:
        1. Check file type (.pdf vs .docx)
        2. For PDFs, check if scanned or digital
        3. Recommend based on characteristics
        """
        ext = file_path.lower().split('.')[-1]
        
        if ext == 'docx':
            # For Word docs, unstructured works best
            return "unstructured", "Word documents: unstructured has best layout detection"
        
        elif ext == 'pdf':
            is_scanned, reason = self.is_scanned_pdf(file_path)
            
            if is_scanned:
                # For scanned PDFs, OCR models work better
                if EASYOCR_AVAILABLE:
                    return "easyocr", f"Scanned PDF ({reason}): easyocr has high accuracy"
                elif DOCTR_AVAILABLE:
                    return "doctr", f"Scanned PDF ({reason}): doctr is a good alternative"
                elif OCRMYPDF_AVAILABLE:
                    return "ocrmypdf", f"Scanned PDF ({reason}): ocrmypdf is reliable"
                else:
                    return "tesseract", f"Scanned PDF ({reason}): tesseract is the fallback"
            else:
                # For digital PDFs, text extraction is faster and more accurate
                if PDFPLUMBER_AVAILABLE:
                    return "pdfplumber", f"Digital PDF ({reason}): pdfplumber is fast and accurate"
                elif UNSTRUCTURED_AVAILABLE:
                    return "unstructured", f"Digital PDF ({reason}): unstructured has good layout detection"
                else:
                    return "auto", "No optimal model available, use auto"
        
        return "unstructured", "Default: unstructured is most versatile"
    
    def calculate_quality_metrics(self, text: str) -> QualityMetrics:
        """Calculate quality metrics for extracted text"""
        if not text:
            return QualityMetrics(
                char_count=0, word_count=0, line_count=0,
                avg_word_length=0.0, alphanumeric_ratio=0.0,
                whitespace_ratio=0.0, punctuation_ratio=0.0,
                digit_ratio=0.0, uppercase_ratio=0.0,
                has_structured_content=False, confidence_score=0.0
            )
        
        char_count = len(text)
        words = text.split()
        word_count = len(words)
        line_count = len(text.split('\n'))
        
        # Calculate ratios
        alphanumeric_count = sum(c.isalnum() for c in text)
        whitespace_count = sum(c.isspace() for c in text)
        punctuation_count = sum(c in '.,;:!?"\'()[]{}' for c in text)
        digit_count = sum(c.isdigit() for c in text)
        uppercase_count = sum(c.isupper() for c in text)
        
        alphanumeric_ratio = alphanumeric_count / char_count if char_count > 0 else 0
        whitespace_ratio = whitespace_count / char_count if char_count > 0 else 0
        punctuation_ratio = punctuation_count / char_count if char_count > 0 else 0
        digit_ratio = digit_count / char_count if char_count > 0 else 0
        uppercase_ratio = uppercase_count / alphanumeric_count if alphanumeric_count > 0 else 0
        
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0
        
        # Detect structured content (forms, fields, etc.)
        has_structured_content = (
            any(pattern in text for pattern in ['___', '___', '[ ]', '[X]', '☐', '☑']) or
            bool(re.search(r':\s*_+', text)) or
            bool(re.search(r'Date|Name|Address|Phone|Email', text, re.IGNORECASE))
        )
        
        # Calculate confidence score (higher is better)
        # Good text has:
        # - High alphanumeric ratio (0.6-0.9)
        # - Moderate whitespace (0.1-0.3)
        # - Reasonable word length (3-8 chars)
        # - Some punctuation (0.01-0.1)
        confidence_score = 0.0
        
        if 0.6 <= alphanumeric_ratio <= 0.9:
            confidence_score += 30
        if 0.1 <= whitespace_ratio <= 0.3:
            confidence_score += 20
        if 3 <= avg_word_length <= 8:
            confidence_score += 25
        if 0.01 <= punctuation_ratio <= 0.1:
            confidence_score += 15
        if has_structured_content:
            confidence_score += 10
        
        return QualityMetrics(
            char_count=char_count,
            word_count=word_count,
            line_count=line_count,
            avg_word_length=avg_word_length,
            alphanumeric_ratio=alphanumeric_ratio,
            whitespace_ratio=whitespace_ratio,
            punctuation_ratio=punctuation_ratio,
            digit_ratio=digit_ratio,
            uppercase_ratio=uppercase_ratio,
            has_structured_content=has_structured_content,
            confidence_score=confidence_score
        )
    
    def extract_unstructured(self, file_path: str) -> ExtractionResult:
        """Extract using unstructured library"""
        if not UNSTRUCTURED_AVAILABLE:
            return ExtractionResult(
                model='unstructured',
                text='',
                success=False,
                error='unstructured library not available'
            )
        
        try:
            elements = unstructured_partition(filename=str(file_path))
            
            parts = []
            for e in elements:
                text = getattr(e, "text", None) or str(e)
                if text and text.strip():
                    parts.append(text.strip())
            
            text = "\n\n".join(parts)
            metrics = self.calculate_quality_metrics(text)
            
            return ExtractionResult(
                model='unstructured',
                text=text,
                success=True,
                quality_score=metrics.confidence_score,
                metadata={'metrics': metrics.to_dict()}
            )
        except Exception as e:
            return ExtractionResult(
                model='unstructured',
                text='',
                success=False,
                error=str(e)
            )
    
    def extract_doctr(self, file_path: str) -> ExtractionResult:
        """Extract using doctr library"""
        if not DOCTR_AVAILABLE:
            return ExtractionResult(
                model='doctr',
                text='',
                success=False,
                error='doctr library not available'
            )
        
        try:
            if self.doctr_model is None:
                self.doctr_model = ocr_predictor(pretrained=True)
            
            doc = DocumentFile.from_pdf(file_path) if file_path.endswith('.pdf') else DocumentFile.from_images([file_path])
            result = self.doctr_model(doc)
            
            # Extract text from result
            text_parts = []
            for page in result.pages:
                for block in page.blocks:
                    for line in block.lines:
                        line_text = ' '.join(word.value for word in line.words)
                        if line_text.strip():
                            text_parts.append(line_text.strip())
            
            text = '\n'.join(text_parts)
            metrics = self.calculate_quality_metrics(text)
            
            return ExtractionResult(
                model='doctr',
                text=text,
                success=True,
                quality_score=metrics.confidence_score,
                metadata={'metrics': metrics.to_dict()}
            )
        except Exception as e:
            return ExtractionResult(
                model='doctr',
                text='',
                success=False,
                error=str(e)
            )
    
    def extract_tesseract(self, file_path: str) -> ExtractionResult:
        """Extract using tesseract OCR"""
        if not TESSERACT_AVAILABLE:
            return ExtractionResult(
                model='tesseract',
                text='',
                success=False,
                error='tesseract not available'
            )
        
        try:
            if file_path.endswith('.pdf'):
                # Convert PDF to images first
                from pdf2image import convert_from_path
                images = convert_from_path(file_path)
                text_parts = []
                for img in images:
                    page_text = pytesseract.image_to_string(img)
                    if page_text.strip():
                        text_parts.append(page_text.strip())
                text = '\n\n'.join(text_parts)
            else:
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image)
            
            metrics = self.calculate_quality_metrics(text)
            
            return ExtractionResult(
                model='tesseract',
                text=text,
                success=True,
                quality_score=metrics.confidence_score,
                metadata={'metrics': metrics.to_dict()}
            )
        except Exception as e:
            return ExtractionResult(
                model='tesseract',
                text='',
                success=False,
                error=str(e)
            )
    
    def extract_pdfplumber(self, file_path: str) -> ExtractionResult:
        """Extract using pdfplumber (for digital PDFs)"""
        if not PDFPLUMBER_AVAILABLE:
            return ExtractionResult(
                model='pdfplumber',
                text='',
                success=False,
                error='pdfplumber not available'
            )
        
        if not file_path.endswith('.pdf'):
            return ExtractionResult(
                model='pdfplumber',
                text='',
                success=False,
                error='pdfplumber only works with PDF files'
            )
        
        try:
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(page_text.strip())
            
            text = '\n\n'.join(text_parts)
            metrics = self.calculate_quality_metrics(text)
            
            return ExtractionResult(
                model='pdfplumber',
                text=text,
                success=True,
                quality_score=metrics.confidence_score,
                metadata={'metrics': metrics.to_dict()}
            )
        except Exception as e:
            return ExtractionResult(
                model='pdfplumber',
                text='',
                success=False,
                error=str(e)
            )
    
    def extract_ocrmypdf(self, file_path: str) -> ExtractionResult:
        """Extract using ocrmypdf (OCR for scanned PDFs)"""
        if not OCRMYPDF_AVAILABLE:
            return ExtractionResult(
                model='ocrmypdf',
                text='',
                success=False,
                error='ocrmypdf not available'
            )
        
        if not file_path.endswith('.pdf'):
            return ExtractionResult(
                model='ocrmypdf',
                text='',
                success=False,
                error='ocrmypdf only works with PDF files'
            )
        
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp_path = tmp.name
            
            # Run OCR and save to temp file
            ocrmypdf.ocr(file_path, tmp_path, skip_text=False, force_ocr=False)
            
            # Extract text from OCR'd PDF
            with pdfplumber.open(tmp_path) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(page_text.strip())
            
            text = '\n\n'.join(text_parts)
            metrics = self.calculate_quality_metrics(text)
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            return ExtractionResult(
                model='ocrmypdf',
                text=text,
                success=True,
                quality_score=metrics.confidence_score,
                metadata={'metrics': metrics.to_dict()}
            )
        except Exception as e:
            return ExtractionResult(
                model='ocrmypdf',
                text='',
                success=False,
                error=str(e)
            )
    
    def extract_easyocr(self, file_path: str) -> ExtractionResult:
        """Extract using easyocr (deep learning OCR)"""
        if not EASYOCR_AVAILABLE:
            return ExtractionResult(
                model='easyocr',
                text='',
                success=False,
                error='easyocr not available'
            )
        
        try:
            if self.easyocr_reader is None:
                self.easyocr_reader = easyocr.Reader(['en'])
            
            if file_path.endswith('.pdf'):
                # Convert PDF to images
                from pdf2image import convert_from_path
                images = convert_from_path(file_path)
                text_parts = []
                for img in images:
                    result = self.easyocr_reader.readtext(img, detail=0)
                    page_text = '\n'.join(result)
                    if page_text.strip():
                        text_parts.append(page_text.strip())
                text = '\n\n'.join(text_parts)
            else:
                result = self.easyocr_reader.readtext(file_path, detail=0)
                text = '\n'.join(result)
            
            metrics = self.calculate_quality_metrics(text)
            
            return ExtractionResult(
                model='easyocr',
                text=text,
                success=True,
                quality_score=metrics.confidence_score,
                metadata={'metrics': metrics.to_dict()}
            )
        except Exception as e:
            return ExtractionResult(
                model='easyocr',
                text='',
                success=False,
                error=str(e)
            )
    
    def extract_with_model(self, file_path: str, model: str) -> ExtractionResult:
        """Extract text using specified model"""
        extractors = {
            'unstructured': self.extract_unstructured,
            'doctr': self.extract_doctr,
            'tesseract': self.extract_tesseract,
            'pdfplumber': self.extract_pdfplumber,
            'ocrmypdf': self.extract_ocrmypdf,
            'easyocr': self.extract_easyocr
        }
        
        if model not in extractors:
            return ExtractionResult(
                model=model,
                text='',
                success=False,
                error=f'Unknown model: {model}'
            )
        
        return extractors[model](file_path)
    
    def extract_auto(self, file_path: str) -> ExtractionResult:
        """
        Automatically select and use the best model for the file.
        Tries multiple models and picks the one with highest quality score.
        """
        # Get recommendation
        recommended_model, reason = self.recommend_model(file_path)
        print(f"  💡 Recommendation: {recommended_model} ({reason})")
        
        # Try recommended model first
        result = self.extract_with_model(file_path, recommended_model)
        
        if result.success and result.quality_score >= 70:
            # Good enough, use it
            print(f"  ✅ {recommended_model} produced good quality (score: {result.quality_score:.1f})")
            return result
        
        # Try fallback models
        print(f"  ⚠️  {recommended_model} quality suboptimal (score: {result.quality_score:.1f}), trying alternatives...")
        
        # Fallback order based on general reliability
        fallback_order = ['unstructured', 'easyocr', 'pdfplumber', 'doctr', 'tesseract', 'ocrmypdf']
        fallback_order = [m for m in fallback_order if m != recommended_model]  # Remove already tried
        
        results = [result]
        for model in fallback_order:
            fb_result = self.extract_with_model(file_path, model)
            if fb_result.success:
                results.append(fb_result)
                print(f"  📊 {model}: quality score = {fb_result.quality_score:.1f}")
                
                # If we find a much better result, use it
                if fb_result.quality_score >= 80:
                    break
        
        # Pick the best result
        best_result = max([r for r in results if r.success], key=lambda r: r.quality_score, default=result)
        print(f"  🏆 Selected: {best_result.model} (score: {best_result.quality_score:.1f})")
        
        return best_result
    
    def extract_all(self, file_path: str) -> List[ExtractionResult]:
        """Extract using all available models for comparison"""
        results = []
        for model in self.MODELS:
            print(f"  🔄 Trying {model}...")
            result = self.extract_with_model(file_path, model)
            results.append(result)
            
            if result.success:
                print(f"    ✅ Success: {len(result.text)} chars, quality: {result.quality_score:.1f}")
            else:
                print(f"    ❌ Failed: {result.error}")
        
        return results
    
    def process_file(self, file_path: str, output_dir: str, model: str = 'unstructured') -> bool:
        """Process a single file and save results"""
        if not self.validate_file(file_path):
            print(f"⚠️  Unsupported file: {file_path}")
            return False
        
        file_path = Path(file_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📄 Processing: {file_path.name}")
        
        if model == 'auto':
            result = self.extract_auto(str(file_path))
            if result.success:
                out_path = output_dir / f"{file_path.stem}.txt"
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(result.text)
                print(f"✅ Saved: {out_path} (model: {result.model})")
                return True
            else:
                print(f"❌ All models failed for {file_path.name}")
                return False
        
        elif model == 'all':
            results = self.extract_all(str(file_path))
            
            # Save each result
            for result in results:
                suffix = f"_{result.model}"
                out_path = output_dir / f"{file_path.stem}{suffix}.txt"
                
                if result.success:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(result.text)
                    print(f"✅ Saved: {out_path}")
                else:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(f"Extraction failed: {result.error}")
                    print(f"⚠️  Failed: {out_path}")
            
            # Generate comparison report
            self.generate_comparison_report(file_path, results, output_dir)
            return True
        
        else:
            result = self.extract_with_model(str(file_path), model)
            if result.success:
                out_path = output_dir / f"{file_path.stem}.txt"
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(result.text)
                print(f"✅ Saved: {out_path}")
                return True
            else:
                print(f"❌ Extraction failed: {result.error}")
                return False
    
    def generate_comparison_report(self, file_path: Path, results: List[ExtractionResult], output_dir: Path):
        """Generate a comparison report for multi-model extraction"""
        report_path = output_dir / f"{file_path.stem}_comparison_report.md"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# Multi-Model Extraction Comparison\n\n")
            f.write(f"**File:** {file_path.name}\n\n")
            f.write(f"## Summary\n\n")
            f.write("| Model | Success | Quality Score | Char Count | Word Count |\n")
            f.write("|-------|---------|---------------|------------|------------|\n")
            
            for result in results:
                status = "✅" if result.success else "❌"
                metrics = result.metadata.get('metrics', {}) if result.metadata else {}
                char_count = metrics.get('char_count', 0)
                word_count = metrics.get('word_count', 0)
                
                f.write(f"| {result.model} | {status} | {result.quality_score:.1f} | {char_count} | {word_count} |\n")
            
            # Recommendation
            successful = [r for r in results if r.success]
            if successful:
                best = max(successful, key=lambda r: r.quality_score)
                f.write(f"\n**Recommended:** {best.model} (quality score: {best.quality_score:.1f})\n\n")
            
            # Detailed metrics
            f.write(f"## Detailed Metrics\n\n")
            for result in results:
                if not result.success:
                    continue
                
                f.write(f"### {result.model}\n\n")
                metrics = result.metadata.get('metrics', {}) if result.metadata else {}
                
                if metrics:
                    f.write(f"- **Characters:** {metrics.get('char_count', 0)}\n")
                    f.write(f"- **Words:** {metrics.get('word_count', 0)}\n")
                    f.write(f"- **Lines:** {metrics.get('line_count', 0)}\n")
                    f.write(f"- **Avg Word Length:** {metrics.get('avg_word_length', 0):.2f}\n")
                    f.write(f"- **Alphanumeric Ratio:** {metrics.get('alphanumeric_ratio', 0):.2%}\n")
                    f.write(f"- **Has Structured Content:** {metrics.get('has_structured_content', False)}\n")
                    f.write(f"- **Confidence Score:** {metrics.get('confidence_score', 0):.1f}/100\n\n")
        
        print(f"📊 Comparison report: {report_path}")
    
    def process_folder(self, input_dir: str, output_dir: str, model: str = 'unstructured'):
        """Process all supported files in directory"""
        input_dir = Path(input_dir)
        success_count = 0
        total_count = 0
        
        for root, _, files in os.walk(input_dir):
            for file in files:
                file_path = Path(root) / file
                if self.validate_file(str(file_path)):
                    total_count += 1
                    if self.process_file(str(file_path), output_dir, model):
                        success_count += 1
        
        print(f"\n📊 Summary: {success_count}/{total_count} files processed successfully")


def main():
    parser = argparse.ArgumentParser(
        description='Multi-Model Document Extraction with Intelligent Heuristics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract with specific model
  %(prog)s --model unstructured --in documents --out output
  
  # Auto-select best model
  %(prog)s --model auto --in documents --out output
  
  # Compare all models
  %(prog)s --model all --in documents --out output_comparison
  
  # Get model recommendation
  %(prog)s --recommend documents/form.pdf
        """
    )
    
    parser.add_argument('--in', dest='input_dir', default='documents',
                       help='Input directory (default: documents)')
    parser.add_argument('--out', dest='output_dir', default='output',
                       help='Output directory (default: output)')
    parser.add_argument('--model', 
                       choices=['unstructured', 'doctr', 'tesseract', 'pdfplumber', 
                               'ocrmypdf', 'easyocr', 'auto', 'all'],
                       default='unstructured',
                       help='Extraction model to use (default: unstructured)')
    parser.add_argument('--recommend', metavar='FILE',
                       help='Get model recommendation for a specific file')
    
    args = parser.parse_args()
    
    extractor = DocumentExtractor()
    
    # Handle recommendation mode
    if args.recommend:
        if not extractor.validate_file(args.recommend):
            print(f"❌ Invalid file: {args.recommend}")
            sys.exit(1)
        
        model, reason = extractor.recommend_model(args.recommend)
        print(f"\n📄 File: {args.recommend}")
        print(f"💡 Recommended model: {model}")
        print(f"📝 Reason: {reason}\n")
        sys.exit(0)
    
    # Normal extraction mode
    print(f"🚀 Starting extraction")
    print(f"   Input: {args.input_dir}")
    print(f"   Output: {args.output_dir}")
    print(f"   Model: {args.model}\n")
    
    extractor.process_folder(args.input_dir, args.output_dir, args.model)
    
    print("\n✅ Extraction complete!")


if __name__ == "__main__":
    main()
