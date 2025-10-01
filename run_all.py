#!/usr/bin/env python3
"""
run_all.py — Orchestrate LLMWhisperer ➜ Modento JSON

1) Runs llmwhisperer.py (same folder; uses your defaults: mode=form, output_mode=layout_preserving)
2) Then runs llm_text_to_modento.py --in output --out JSONs

Usage:
  python3 run_all.py
"""

from __future__ import annotations
import sys
import subprocess
from pathlib import Path

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    whisper = script_dir / "llmwhisperer.py"
    converter = script_dir / "llm_text_to_modento.py"

    if not whisper.exists():
        print(f"ERROR: {whisper.name} not found next to this script.", file=sys.stderr)
        sys.exit(2)
    if not converter.exists():
        print(f"ERROR: {converter.name} not found next to this script.", file=sys.stderr)
        sys.exit(2)

    # Step 1: Run LLMWhisperer (streams stdout/stderr)
    print(f"[1/2] Running {whisper.name} …")
    subprocess.run([sys.executable, str(whisper)], cwd=script_dir, check=True)

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
