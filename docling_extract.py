#!/usr/bin/env python3
"""
docling_extract.py

Batch-convert .pdf and .docx files in ./documents to text using local extraction,
saving .txt files to ./output.

This replaces the LLMWhisperer API-based extraction with local extraction using:
- PyMuPDF (fitz) for PDF files
- python-docx for DOCX files

USAGE:
  python3 docling_extract.py
  python3 docling_extract.py --in documents --out output

REQUIREMENTS:
  pip install pymupdf python-docx
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(2)

try:
    from docx import Document
except ImportError:
    print("ERROR: python-docx not installed. Run: pip install python-docx", file=sys.stderr)
    sys.exit(2)


def ensure_output_dir(p: Path) -> None:
    """Create output directory if it doesn't exist."""
    p.mkdir(parents=True, exist_ok=True)


def extract_text_from_pdf(file_path: Path) -> str:
    """
    Extract text from a PDF file using PyMuPDF.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content
    """
    doc = fitz.open(file_path)
    text_parts = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Use "text" mode for simple text extraction
        text = page.get_text("text")
        if text.strip():
            text_parts.append(text)
    
    doc.close()
    return "\n".join(text_parts)


def extract_text_from_docx(file_path: Path) -> str:
    """
    Extract text from a DOCX file using python-docx.
    
    Args:
        file_path: Path to the DOCX file
        
    Returns:
        Extracted text content
    """
    doc = Document(file_path)
    text_parts = []
    
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)
    
    # Also extract text from tables
    for table in doc.tables:
        for row in table.rows:
            row_text = []
            for cell in row.cells:
                if cell.text.strip():
                    row_text.append(cell.text.strip())
            if row_text:
                text_parts.append(" | ".join(row_text))
    
    return "\n".join(text_parts)


def unique_txt_path(dst: Path) -> Path:
    """
    Generate a unique file path by appending a number if the file exists.
    
    Args:
        dst: Desired destination path
        
    Returns:
        Unique path that doesn't exist yet
    """
    if not dst.exists():
        return dst
    i = 1
    while True:
        cand = dst.with_name(f"{dst.stem}-{i}{dst.suffix}")
        if not cand.exists():
            return cand
        i += 1


def process_one(file_path: Path, out_dir: Path) -> None:
    """
    Process a single document file and extract text to output directory.
    
    Args:
        file_path: Path to the input document
        out_dir: Directory to save the extracted text
    """
    print(f"[+] {file_path.name}")
    
    try:
        # Extract text based on file type
        if file_path.suffix.lower() == ".pdf":
            text = extract_text_from_pdf(file_path)
        elif file_path.suffix.lower() == ".docx":
            text = extract_text_from_docx(file_path)
        else:
            print(f"[!] Unsupported file type: {file_path.suffix}", file=sys.stderr)
            return
        
        # Save to output file
        out_path = unique_txt_path(out_dir / (file_path.stem + ".txt"))
        out_path.write_text(text, encoding="utf-8")
        print(f"[✓] Saved -> {out_path}")
        
    except Exception as e:
        print(f"[x] Failed: {e}", file=sys.stderr)
        raise


def main():
    ap = argparse.ArgumentParser(
        description="Extract text from PDF and DOCX files using local extraction"
    )
    ap.add_argument(
        "--in", 
        dest="in_dir", 
        default="documents", 
        help="Input folder (default: documents)"
    )
    ap.add_argument(
        "--out", 
        dest="out_dir", 
        default="output", 
        help="Output folder (default: output)"
    )
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    ensure_output_dir(out_dir)

    if not in_dir.exists():
        print(f"ERROR: Input folder does not exist: {in_dir}", file=sys.stderr)
        sys.exit(2)

    # Find all PDF and DOCX files
    exts = {".pdf", ".docx"}
    files = sorted([p for p in in_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts])
    
    if not files:
        print(f"WARNING: No .pdf or .docx files found in {in_dir}")
        return

    print(f"Found {len(files)} file(s) to process")
    print(f"Using local extraction (PyMuPDF for PDF, python-docx for DOCX)")
    
    for f in files:
        try:
            process_one(file_path=f, out_dir=out_dir)
        except Exception as e:
            print(f"[x] Failed on {f.name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
