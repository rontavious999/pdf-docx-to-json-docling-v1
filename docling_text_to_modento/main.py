#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for docling_text_to_modento — v2.20

This is the new modular entry point that delegates to the core module.
"""

import sys
from pathlib import Path

# Import the main function from core
from .core import main

if __name__ == "__main__":
    main()
