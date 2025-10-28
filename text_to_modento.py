#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_to_modento.py — v2.20

TXT (Unstructured) -> Modento-compliant JSON

What's new vs v2.19 (Archivev19 continued):
  • Archivev19 Fix 4: Never treat lines with question marks as section headings (captures "Question? If so, detail:" patterns)
  • Previous (v2.19/Archivev19 Fix 3): Inline checkbox field title extraction preserves labels on same line as options
  • Previous (v2.18/Archivev19 Fix 1-2): Single-word field labels, multi-line questions with mid-line checkboxes
  • Previous (v2.17/Archivev18): Date template artifacts, instructional text filtering, explain field titles
  • Previous (v2.16): Multi-sub-field label splitting, enhanced employer/insurance patterns
  • Previous (v2.15): OCR typo correction for "rregular" -> "Irregular"
  • Previous (v2.14): Enhanced category header detection, unique "Please explain" titles

IMPORTANT: This script has been modularized. The main logic now resides in the
text_to_modento package. This file serves as a backward-compatible wrapper
to maintain the existing CLI interface.
"""

# Import the main function from the core module in the package
from text_to_modento.core import main

if __name__ == "__main__":
    main()
