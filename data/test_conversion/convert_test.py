#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test .doc -> .txt conversion via win32com (Word COM automation)."""

import os
import sys

INPUT_DOC = r"I:\Daten\Wohnungsverwaltung\Dokumentation zur Papiersortierung November 2007.doc"
OUTPUT_TXT = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\test_conversion\Dokumentation zur Papiersortierung November 2007.txt"
RESULT_LOG = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\test_conversion\conversion_result.txt"

def log(msg):
    print(msg)

def try_win32com():
    """Attempt conversion using win32com Word automation."""
    log("=== Attempting win32com Word COM automation ===")
    try:
        import win32com.client
        log("win32com.client imported successfully")
    except ImportError as e:
        log(f"FAILED: win32com not available: {e}")
        log("Trying: pip install pywin32 ...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pywin32"],
            capture_output=True, text=True
        )
        log(result.stdout)
        log(result.stderr)
        try:
            import win32com.client
            log("win32com now available after install")
        except ImportError as e2:
            log(f"STILL FAILED after install: {e2}")
            return False, str(e2)

    word = None
    try:
        log("Dispatching Word.Application ...")
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        log(f"Word version: {word.Version}")
        
        log(f"Opening: {INPUT_DOC}")
        doc = word.Documents.Open(INPUT_DOC)
        
        log(f"Saving as TXT to: {OUTPUT_TXT}")
        # wdFormatText = 2
        doc.SaveAs(OUTPUT_TXT, FileFormat=2)
        doc.Close(False)
        log("Document closed.")
        
        # Verify output
        if os.path.exists(OUTPUT_TXT):
            size = os.path.getsize(OUTPUT_TXT)
            log(f"SUCCESS! Output file: {OUTPUT_TXT} ({size} bytes)")
            # Show first 500 chars
            with open(OUTPUT_TXT, "r", encoding="cp1252", errors="replace") as f:
                preview = f.read(500)
            log(f"\n--- PREVIEW (first 500 chars) ---\n{preview}\n---")
            return True, f"OK - {size} bytes"
        else:
            log("ERROR: Output file not created!")
            return False, "Output file not created"
            
    except Exception as e:
        log(f"ERROR during Word automation: {type(e).__name__}: {e}")
        return False, str(e)
    finally:
        if word:
            try:
                word.Quit()
                log("Word.Quit() called.")
            except:
                pass

def main():
    log(f"Python: {sys.version}")
    log(f"Input: {INPUT_DOC}")
    log(f"Output: {OUTPUT_TXT}")
    log(f"Input exists: {os.path.exists(INPUT_DOC)}")
    log("")
    
    success, msg = try_win32com()
    
    # Write result log
    status = "SUCCESS" if success else "FAILED"
    with open(RESULT_LOG, "w", encoding="utf-8") as f:
        f.write(f"Conversion test result: {status}\n")
        f.write(f"Input: {INPUT_DOC}\n")
        f.write(f"Output: {OUTPUT_TXT}\n")
        f.write(f"Message: {msg}\n")
    
    log(f"\n=== RESULT: {status} ===")
    log(f"Details: {msg}")

if __name__ == "__main__":
    main()
