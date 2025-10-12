#!/usr/bin/env python3
"""
run_all.py — Orchestrate Document Extraction ➜ Modento JSON

1) Runs docling_extract.py (same folder; local extraction using PyMuPDF and python-docx)
2) Then runs docling_text_to_modento.py --in output --out JSONs

Usage:
  python3 run_all.py
"""

from __future__ import annotations
import sys
import subprocess
from pathlib import Path

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    extractor = script_dir / "docling_extract.py"
    converter = script_dir / "docling_text_to_modento.py"

    if not extractor.exists():
        print(f"ERROR: {extractor.name} not found next to this script.", file=sys.stderr)
        sys.exit(2)
    if not converter.exists():
        print(f"ERROR: {converter.name} not found next to this script.", file=sys.stderr)
        sys.exit(2)

    # Step 1: Run document extraction (streams stdout/stderr)
    print(f"[1/2] Running {extractor.name} …")
    subprocess.run([sys.executable, str(extractor)], cwd=script_dir, check=True)

    # Step 2: Convert text ➜ Modento JSON
    print(f"[2/2] Running {converter.name} …")
    subprocess.run(
        [sys.executable, str(converter), "--in", "output", "--out", "JSONs", "--debug"],
        cwd=script_dir,
        check=True,
    )

    print("✅ Done.")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ A step failed (exit code {e.returncode}). See logs above.", file=sys.stderr)
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
