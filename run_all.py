#!/usr/bin/env python3
"""
run_all.py — Orchestrate Document Extraction ➜ Modento JSON

1) Clears old output (output/ and JSONs/ directories)
2) Runs multi_model_extract.py or unstructured_extract.py for text extraction
3) Then runs text_to_modento.py --in output --out JSONs
4) Validates parity and produces comprehensive report

Usage:
  python3 run_all.py                                    # Use default (unstructured)
  python3 run_all.py --model recommend                 # Get recommendation per file, use that model
  python3 run_all.py --model auto                      # Auto-select best model (tries multiple)
  python3 run_all.py --model pdfplumber                # Use specific model
  python3 run_all.py --skip-validation                 # Skip parity validation
  python3 run_all.py --extractor legacy                # Use old unstructured_extract.py
"""

from __future__ import annotations
import sys
import subprocess
import shutil
import argparse
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete PDF-to-JSON conversion pipeline with validation"
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip parity validation after conversion'
    )
    parser.add_argument(
        '--model',
        choices=['unstructured', 'doctr', 'tesseract', 'pdfplumber', 'ocrmypdf', 'easyocr', 'recommend', 'auto', 'all'],
        default='unstructured',
        help='Extraction model to use (default: unstructured). Use "recommend" for per-file recommendation.'
    )
    parser.add_argument(
        '--extractor',
        choices=['multi', 'legacy'],
        default='multi',
        help='Use multi_model_extract.py (multi) or unstructured_extract.py (legacy)'
    )
    args = parser.parse_args()
    
    script_dir = Path(__file__).resolve().parent
    
    # Select extractor based on argument
    if args.extractor == 'multi':
        extractor = script_dir / "multi_model_extract.py"
    else:
        extractor = script_dir / "unstructured_extract.py"
    
    converter = script_dir / "text_to_modento.py"
    validator = script_dir / "parity_validator.py"
    
    output_dir = script_dir / "output"
    jsons_dir = script_dir / "JSONs"

    if not extractor.exists():
        print(f"ERROR: {extractor.name} not found next to this script.", file=sys.stderr)
        sys.exit(2)
    if not converter.exists():
        print(f"ERROR: {converter.name} not found next to this script.", file=sys.stderr)
        sys.exit(2)

    # Step 0: Clear old output directories
    print("[0/4] Clearing old output...")
    for directory in [output_dir, jsons_dir]:
        if directory.exists():
            try:
                shutil.rmtree(directory)
                print(f"  ✓ Removed old {directory.name}/")
            except Exception as e:
                print(f"  ⚠️  Could not remove {directory.name}/: {e}", file=sys.stderr)
        # Recreate empty directory
        directory.mkdir(exist_ok=True)
        print(f"  ✓ Created fresh {directory.name}/")

    # Step 1: Run document extraction (streams stdout/stderr)
    print(f"[1/4] Running {extractor.name} with model={args.model} …")
    
    if args.extractor == 'multi':
        # Use multi-model extractor with specified model
        subprocess.run([sys.executable, str(extractor), 
                       "--in", "documents", 
                       "--out", "output",
                       "--model", args.model], 
                      cwd=script_dir, check=True)
    else:
        # Use legacy unstructured extractor
        subprocess.run([sys.executable, str(extractor)], cwd=script_dir, check=True)

    # Step 2: Convert text ➜ Modento JSON
    print(f"[2/4] Running {converter.name} …")
    subprocess.run(
        [sys.executable, str(converter), "--in", "output", "--out", "JSONs", "--debug"],
        cwd=script_dir,
        check=True,
    )

    # Step 3: Validate parity (unless skipped)
    if not args.skip_validation:
        if validator.exists():
            print(f"[3/4] Running parity validation …")
            result = subprocess.run(
                [sys.executable, str(validator)],
                cwd=script_dir,
                capture_output=False
            )
            if result.returncode != 0:
                print(f"\n⚠️  Parity validation completed with warnings/errors.")
                print(f"    Review the report above for details.")
        else:
            print(f"[3/4] Skipping validation (validator not found)")
    else:
        print(f"[3/4] Skipping validation (--skip-validation flag)")

    print("[4/4] ✅ Done.")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ A step failed (exit code {e.returncode}). See logs above.", file=sys.stderr)
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
