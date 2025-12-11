#!/usr/bin/env python3
"""
Simple check to ensure no '[presence-debug]' or 'presence-debug' debug prints remain in the codebase.
Usage: python scripts/check_no_debug_prints.py
Exit codes: 0 = OK, 1 = found forbidden debug prints
"""
import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = [r"\[presence-debug\]", r"presence-debug", r"logger.debug\(f?\"\[presence-debug\]", r"logger.debug\(f?\'\[presence-debug\]\'"]
EXCLUDED_DIRS = {".venv", "venv", "node_modules", ".git", "scripts/archive"}
ALLOWED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css"}
EXCLUDED_FILES = {"check_no_debug_prints.py"}

def find_matches():
    matches = []
    for f in ROOT.rglob("*.*"):
        # Skip excluded directories
        if any(part in EXCLUDED_DIRS for part in f.parts):
            continue
        # Only scan common source file types (avoid matching docs or logs)
        if f.suffix not in ALLOWED_EXTENSIONS:
            continue
        # Exclude this helper file (it contains pattern literals) or other excluded files
        if f.name in EXCLUDED_FILES:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for pattern in PATTERNS:
            if re.search(pattern, text):
                matches.append((f.relative_to(ROOT), pattern))
                break
    return matches

def main():
    matches = find_matches()
    if matches:
        print("Found debug prints or presence-debug markers in repository:")
        for path, pattern in matches:
            print(f" - {path} (matched: {pattern})")
        print("\nPlease remove or archive these entries (scripts/archive/) before committing.")
        return 1
    else:
        print("No presence-debug markers found. Good job!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
