#!/usr/bin/env python3
"""
whisper_batch_extract.py

Batch-convert .pdf and .docx files in ./documents to text via
Unstract LLMWhisperer v2, saving .txt files to ./output.

FORCED SETTINGS (always):
- processing mode: form
- output mode: text

USAGE:
  python3 whisper_batch_extract.py
  python3 whisper_batch_extract.py --in documents --out output

REQUIREMENTS:
  pip install requests

API KEY:
  EITHER set env var LLMWHISPERER_API_KEY="your_key"
  OR paste into UNSTRACT_API_KEY below where indicated.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# ===================== API CONFIG =====================
# Put your API key here (recommended to use env var instead).
UNSTRACT_API_KEY = os.getenv("LLMWHISPERER_API_KEY", "wG15LPsf2W5B30sslJIzc6KN38Hjpr9sJOigobcBrbI")  # <-- PUT YOUR API KEY HERE
BASE_URL = os.getenv(
    "LLMWHISPERER_BASE_URL_V2",
    "https://llmwhisperer-api.us-central.unstract.com/api/v2",
)

# Endpoints (v2)
WHISPER_URL = f"{BASE_URL}/whisper"            # POST (binary body)
STATUS_URL  = f"{BASE_URL}/whisper-status"     # GET  ?whisper_hash=...
RETR_URL    = f"{BASE_URL}/whisper-retrieve"   # GET  ?whisper_hash=...&text_only=true

# === Force accuracy-first defaults (always) ===
FORCED_MODE = "form"           # <-- always use 'form' processing mode
FORCED_OUTPUT_MODE = "layout_preserving"    # <-- always retrieve plain text


def ensure_output_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def looks_like_form(name: str) -> bool:
    # Unused now (auto-mode disabled), kept for reference.
    name_l = name.lower()
    keys = ("form", "consent", "intake", "hipaa", "checkbox", "radio", "questionnaire")
    return any(k in name_l for k in keys)


def choose_mode(filename: str, forced_mode: Optional[str], auto_mode: bool) -> str:
    # With forced_mode set, this always returns 'form'.
    if forced_mode:
        return forced_mode
    return "form"


def post_whisper(file_path: Path, mode: str, output_mode: str, session: requests.Session, tag: str) -> str:
    headers = {
        "unstract-key": UNSTRACT_API_KEY,
        "Content-Type": "application/octet-stream",
    }
    params = {
        "mode": mode,                  # <-- forced: "form"
        "output_mode": output_mode,    # <-- forced: "text"
        "file_name": file_path.name,
        "tag": tag,
    }

    with open(file_path, "rb") as f:
        r = session.post(WHISPER_URL, params=params, headers=headers, data=f, timeout=120)
    if r.status_code != 202:
        raise RuntimeError(f"Whisper submit failed ({r.status_code}): {r.text}")
    j = r.json()
    whisper_hash = j.get("whisper_hash") or ""
    if not whisper_hash:
        raise RuntimeError(f"No whisper_hash returned: {j}")
    return whisper_hash


def poll_status(whisper_hash: str, session: requests.Session, wait_timeout: int = 600) -> dict:
    """Poll until status=processed or timeout."""
    headers = {"unstract-key": UNSTRACT_API_KEY}
    params = {"whisper_hash": whisper_hash}

    start = time.time()
    delay = 1.5
    while True:
        r = session.get(STATUS_URL, headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Status failed ({r.status_code}): {r.text}")
        j = r.json()
        status = j.get("status", "")
        if status == "processed":
            return j
        if status == "error":
            raise RuntimeError(f"Extraction error: {json.dumps(j, ensure_ascii=False)}")

        if time.time() - start > wait_timeout:
            raise TimeoutError(f"Timed out waiting for processing; last status={status}")
        time.sleep(delay)
        if delay < 5.0:
            delay = min(5.0, delay + 0.5)


def retrieve_text(whisper_hash: str, session: requests.Session) -> str:
    """
    Retrieve extracted text (only once per job).
    We use text_only=true to get plain text directly.
    """
    headers = {"unstract-key": UNSTRACT_API_KEY}
    params = {"whisper_hash": whisper_hash, "text_only": "true"}
    r = session.get(RETR_URL, headers=headers, params=params, timeout=60)

    if r.status_code == 200:
        # When text_only=true, service returns plain text body
        return r.text

    try:
        j = r.json()
    except Exception:
        j = {"message": r.text}
    raise RuntimeError(f"Retrieve failed ({r.status_code}): {json.dumps(j, ensure_ascii=False)}")


def unique_txt_path(dst: Path) -> Path:
    if not dst.exists():
        return dst
    i = 1
    while True:
        cand = dst.with_name(f"{dst.stem}-{i}{dst.suffix}")
        if not cand.exists():
            return cand
        i += 1


def process_one(file_path: Path, out_dir: Path, session: requests.Session,
                forced_mode: Optional[str], auto_mode: bool, output_mode: str,
                wait_timeout: int) -> None:
    mode = choose_mode(file_path.name, forced_mode, auto_mode)
    tag = f"batch:{mode}"

    print(f"[+] {file_path.name}  -> mode={mode}, output_mode={output_mode}")

    whisper_hash = post_whisper(file_path, mode, output_mode, session, tag)
    poll_status(whisper_hash, session, wait_timeout=wait_timeout)
    text = retrieve_text(whisper_hash, session)

    out_path = unique_txt_path(out_dir / (file_path.stem + ".txt"))
    out_path.write_text(text, encoding="utf-8")
    print(f"[✓] Saved -> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", default="documents", help="Input folder (default: documents)")
    ap.add_argument("--out", dest="out_dir", default="output", help="Output folder (default: output)")
    ap.add_argument("--wait-timeout", type=int, default=600, help="Max seconds to wait per file (default: 600)")
    # Modes are hardcoded now: mode='form', output_mode='text'
    args = ap.parse_args()

    if not UNSTRACT_API_KEY or "PUT-YOUR-API-KEY-HERE" in UNSTRACT_API_KEY:
        print(
            "ERROR: No API key configured.\n"
            "Set env var LLMWHISPERER_API_KEY or edit UNSTRACT_API_KEY in this script.",
            file=sys.stderr,
        )
        sys.exit(2)

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    ensure_output_dir(out_dir)

    if not in_dir.exists():
        print(f"ERROR: Input folder does not exist: {in_dir}", file=sys.stderr)
        sys.exit(2)

    exts = {".pdf", ".docx"}
    files = sorted([p for p in in_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts])
    if not files:
        print(f"WARNING: No .pdf or .docx files found in {in_dir}")
        return

    session = requests.Session()

    print(f"Enforcing processing mode={FORCED_MODE} and output_mode={FORCED_OUTPUT_MODE}")
    for f in files:
        try:
            process_one(
                file_path=f,
                out_dir=out_dir,
                session=session,
                forced_mode=FORCED_MODE,       # <-- force 'form'
                auto_mode=False,               # <-- disable heuristics
                output_mode=FORCED_OUTPUT_MODE,# <-- force 'text'
                wait_timeout=args.wait_timeout,
            )
        except Exception as e:
            print(f"[x] Failed on {f.name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
