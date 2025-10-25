#!/usr/bin/env python3
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
    """Safely get text from Unstructured elements or fallback to str(e)."""
    try:
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='High‑accuracy Document Text Extractor (Unstructured)')
    parser.add_argument('input', help='Input folder path')
    parser.add_argument('output', help='Output folder path')
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
    args = parser.parse_args()

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
