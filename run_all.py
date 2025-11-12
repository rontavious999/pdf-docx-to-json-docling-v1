#!/usr/bin/env python3
"""
run_all.py — Orchestrate Document Extraction ➜ Modento JSON

1) Clears old output (output/ and JSONs/ directories)
2) Runs unstructured_extract.py (same folder; local extraction using Unstructured library)
3) Then runs text_to_modento.py --in output --out JSONs

Usage:
  python3 run_all.py
"""

from __future__ import annotations
import sys
import subprocess
import shutil
from pathlib import Path

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    extractor = script_dir / "unstructured_extract.py"
    converter = script_dir / "text_to_modento.py"
    
    output_dir = script_dir / "output"
    jsons_dir = script_dir / "JSONs"

    if not extractor.exists():
        print(f"ERROR: {extractor.name} not found next to this script.", file=sys.stderr)
        sys.exit(2)
    if not converter.exists():
        print(f"ERROR: {converter.name} not found next to this script.", file=sys.stderr)
        sys.exit(2)

    # Step 0: Clear old output directories
    print("[0/3] Clearing old output...")
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
    print(f"[1/3] Running {extractor.name} …")
    subprocess.run([sys.executable, str(extractor)], cwd=script_dir, check=True)

    # Step 2: Convert text ➜ Modento JSON
    print(f"[2/3] Running {converter.name} …")
    subprocess.run(
        [sys.executable, str(converter), "--in", "output", "--out", "JSONs", "--debug"],
        cwd=script_dir,
        check=True,
    )

    print("[3/3] ✅ Done.")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ A step failed (exit code {e.returncode}). See logs above.", file=sys.stderr)
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
