#!/usr/bin/env python3
"""
unstructured_extract.py

Batch-convert .pdf and .docx files in ./documents to text using Unstructured library,
saving .txt files to ./output.

This uses the Unstructured library for high-accuracy document text extraction with:
- Hi-res strategy for model-based layout detection
- Table structure inference for preserving grids
- Multi-language support
- Automatic fallback and retry mechanisms

USAGE:
  python3 unstructured_extract.py
  python3 unstructured_extract.py --in documents --out output
  python3 unstructured_extract.py --in documents --out output --strategy hi_res
  python3 unstructured_extract.py --in documents --out output --retry

REQUIREMENTS:
  pip install unstructured
"""

import os
import sys
import argparse
import traceback
from pathlib import Path
from unstructured.partition.auto import partition

def validate_file(file_path):
    """Check if file exists and is valid PDF/DOCX"""
    if not os.path.exists(file_path):
        return False
    return file_path.lower().endswith(('.pdf', '.docx'))

def element_to_text(e):
    """Safely get text from Unstructured elements.
    
    For tables, try to preserve row structure by parsing HTML if available.
    This helps maintain field separation in multi-column layouts.
    """
    import re
    
    try:
        # For table elements, try to use HTML to preserve row structure
        if type(e).__name__ == 'Table':
            # Try to get HTML representation
            if hasattr(e, 'metadata') and hasattr(e.metadata, 'text_as_html') and e.metadata.text_as_html:
                html = e.metadata.text_as_html
                # Split by table rows
                rows = html.split('</tr>')
                row_texts = []
                for row in rows:
                    # Remove HTML tags and clean up
                    row_text = re.sub(r'<[^>]+>', ' ', row).strip()
                    if row_text:
                        # Normalize whitespace
                        row_text = re.sub(r'\s+', ' ', row_text)
                        row_texts.append(row_text)
                # Join rows with double newline to preserve separation
                if row_texts:
                    return '\n\n'.join(row_texts)
        
        # Default: get text attribute or fallback to str()
        t = getattr(e, "text", None)
        if t is None and hasattr(e, "get"):
            t = e.get("text")
        return (t if isinstance(t, str) else str(e)) or ""
    except Exception:
        return str(e) if e is not None else ""

def _lang_list(languages):
    return [s.strip() for s in (languages.split(',') if isinstance(languages, str) else languages) if s and s.strip()]

def extract_text(file_path,
                 strategy="hi_res",
                 languages="eng",
                 infer_table_structure=True,
                 include_page_breaks=False,
                 hi_res_model_name=None):
    """High‑accuracy extractor: favors layout fidelity over speed.
    - strategy: default 'hi_res' for model‑based layout
    - languages: ISO‑639‑3 codes (e.g., 'eng')
    - infer_table_structure: preserve tables/grids
    - include_page_breaks: usually False for cleaner downstream parsing
    - hi_res_model_name: 'yolox' or 'detectron2_onnx' (optional)
    """
    try:
        langs = _lang_list(languages)
        # Build kwargs for the 'auto' partition; it forwards to pdf/docx handlers.
        kw = dict(
            filename=str(file_path),
            strategy=strategy,
            languages=langs,
            infer_table_structure=bool(infer_table_structure),
            include_page_breaks=bool(include_page_breaks),
        )
        # Only pass hi_res_model_name when using hi_res and a name is provided.
        if (strategy == "hi_res") and hi_res_model_name:
            kw["hi_res_model_name"] = hi_res_model_name

        try:
            elements = partition(**kw)
        except TypeError:
            # Fallback for older unstructured versions: drop unknown args, then try ocr_languages if needed.
            for bad in ("hi_res_model_name", "include_page_breaks", "infer_table_structure"):
                kw.pop(bad, None)
            try:
                elements = partition(**kw)
            except TypeError:
                kw.pop("languages", None)
                kw["ocr_languages"] = langs
                elements = partition(**kw)

        parts = []
        for e in elements:
            t = element_to_text(e)
            if t and t.strip():
                parts.append(t.strip())
        return "\n\n".join(parts)

    except Exception as e:
        print(f"❌ Extraction failed for {file_path}: {str(e)}")
        return ""

def process_one(file_path,
                out_dir,
                strategy="hi_res",
                use_ocr=False,
                auto_ocr=True,
                languages="eng",
                infer_table_structure=True,
                include_page_breaks=False,
                hi_res_model_name=None):
    """Process a single file and save extracted text to output directory.
    
    Args:
        file_path: Path to the file to process
        out_dir: Output directory for the extracted text
        strategy: Extraction strategy ('hi_res', 'fast', 'auto', 'ocr_only')
        use_ocr: Force OCR for all pages (deprecated, use strategy='ocr_only')
        auto_ocr: Automatically detect and use OCR for scanned PDFs
        languages: Language codes for OCR
        infer_table_structure: Preserve table structures
        include_page_breaks: Include page break markers
        hi_res_model_name: Specific model for hi_res strategy
    
    Returns:
        Path to the output text file, or None if extraction failed
    """
    from pathlib import Path
    
    file_path = Path(file_path)
    out_dir = Path(out_dir)
    
    if not validate_file(str(file_path)):
        print(f"⚠️ File not supported: {file_path}")
        return None
    
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{file_path.stem}.txt"
    out_path = out_dir / out_name
    
    try:
        # Handle deprecated use_ocr parameter
        if use_ocr and strategy != "ocr_only":
            strategy = "ocr_only"
        
        text = extract_text(file_path,
                           strategy=strategy,
                           languages=languages,
                           infer_table_structure=infer_table_structure,
                           include_page_breaks=include_page_breaks,
                           hi_res_model_name=hi_res_model_name)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text or "")
        
        print(f"✅ Processed: {file_path}")
        return out_path
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {str(e)}")
        # Write error message to file for debugging
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(f"Extraction error: {str(e)}")
        return None


def process_folder(input_dir,
                   output_dir,
                   strategy="hi_res",
                   retry=False,
                   languages="eng",
                   infer_table_structure=True,
                   include_page_breaks=False,
                   hi_res_model_name=None):
    """Process all supported files in directory tree"""
    for root, _, files in os.walk(input_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if not validate_file(file_path):
                continue

            rel_path = os.path.relpath(root, input_dir)
            out_folder = os.path.join(output_dir, rel_path)
            Path(out_folder).mkdir(parents=True, exist_ok=True)

            out_name = f"{Path(file).stem}.txt"
            out_path = os.path.join(out_folder, out_name)

            try:
                text = extract_text(file_path,
                                    strategy=strategy,
                                    languages=languages,
                                    infer_table_structure=infer_table_structure,
                                    include_page_breaks=include_page_breaks,
                                    hi_res_model_name=hi_res_model_name)
                if not text.strip() and retry:
                    print(f"⚠️ Empty result. Retrying with hi_res: {file_path}")
                    text = extract_text(file_path,
                                        strategy="hi_res",
                                        languages=languages,
                                        infer_table_structure=infer_table_structure,
                                        include_page_breaks=include_page_breaks,
                                        hi_res_model_name=hi_res_model_name)

                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(text or "")
                print(f"✅ Processed: {file_path}")
            except Exception as e:
                print(f"🔥 Critical error processing {file_path}:")
                traceback.print_exc()
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(f"Extraction error: {str(e)}")

def validate_dependencies():
    """
    Parity Improvement #15: Validate that required system dependencies are installed.
    
    Checks for:
    - poppler-utils (for PDF processing with hi_res strategy)
    - tesseract-ocr (for OCR capabilities)
    
    Returns warnings but doesn't fail - allows graceful degradation to 'fast' strategy.
    """
    import subprocess
    import shutil
    
    warnings = []
    
    # Check for poppler-utils (pdfinfo command)
    if not shutil.which('pdfinfo'):
        warnings.append("⚠️  poppler-utils not found. Hi-res PDF extraction may fail.")
        warnings.append("   Install: apt-get install poppler-utils (or brew install poppler on Mac)")
    
    # Check for tesseract
    if not shutil.which('tesseract'):
        warnings.append("⚠️  tesseract-ocr not found. OCR capabilities limited.")
        warnings.append("   Install: apt-get install tesseract-ocr (or brew install tesseract on Mac)")
    
    if warnings:
        print("=" * 70)
        for warning in warnings:
            print(warning)
        print("=" * 70)
        print()
    
    return len(warnings) == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='High‑accuracy Document Text Extractor (Unstructured)')
    parser.add_argument('--in', dest='input', default='documents', help='Input folder path (default: documents)')
    parser.add_argument('--out', dest='output', default='output', help='Output folder path (default: output)')
    # Default to hi_res for maximum accuracy (speed not a concern for the user)
    parser.add_argument('--strategy', choices=['auto', 'fast', 'hi_res', 'ocr_only'],
                        default='hi_res', help='Extraction strategy (default: hi_res)')
    parser.add_argument('--retry', action='store_true',
                        help='Retry with hi_res if extraction returns empty text')
    parser.add_argument('--languages', default='eng',
                        help='Comma-separated languages, e.g. "eng,spa"')
    parser.add_argument('--infer-table-structure', dest='infer_table_structure',
                        action='store_true', default=True,
                        help='Enable table/grid inference (default: on)')
    parser.add_argument('--no-infer-tables', dest='infer_table_structure',
                        action='store_false',
                        help='Disable table/grid inference')
    parser.add_argument('--include-page-breaks', dest='include_page_breaks',
                        action='store_true', default=False,
                        help='Include page break markers in output (default: off)')
    parser.add_argument('--hi-res-model-name', default=None,
                        choices=[None, 'yolox', 'detectron2_onnx'],
                        help='Optional hi_res layout model override (yolox or detectron2_onnx)')
    parser.add_argument('--skip-dependency-check', action='store_true',
                        help='Skip dependency validation check')
    args = parser.parse_args()

    # Parity Improvement #15: Validate dependencies
    if not args.skip_dependency_check:
        validate_dependencies()

    print(f"🚀 Starting extraction from {args.input} to {args.output}")
    print(f"🔧 Strategy: {args.strategy}, Retry: {args.retry}, Languages: {args.languages}, Tables: {args.infer_table_structure}, PageBreaks: {args.include_page_breaks}, hi_res_model: {args.hi_res_model_name}")
    process_folder(args.input,
                   args.output,
                   strategy=args.strategy,
                   retry=args.retry,
                   languages=args.languages,
                   infer_table_structure=args.infer_table_structure,
                   include_page_breaks=args.include_page_breaks,
                   hi_res_model_name=args.hi_res_model_name)
    print("✅ Extraction complete!")
