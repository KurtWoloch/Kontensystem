"""
Bulk convert .doc files to .txt using Word COM automation.
Opens Word ONCE, processes all files, then quits.
"""
import win32com.client
import os
import json
import re
import time

WORKSPACE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem"
INDEX_PATH = os.path.join(WORKSPACE, "data", "documentation_index.jsonl")
OUT_DIR = os.path.join(WORKSPACE, "data", "docs_txt")

os.makedirs(OUT_DIR, exist_ok=True)

def sanitize_filename(s):
    """Replace characters not safe for Windows filenames with underscores."""
    return re.sub(r'[:\?\*"<>\|/\\]', '_', s)

# Load all entries
entries = []
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            entries.append(json.loads(line))

# Filter: only .doc files
doc_entries = [e for e in entries if e.get("format") == "doc"]
skip_entries = [e for e in entries if e.get("format") != "doc"]

print(f"Total entries: {len(entries)}")
print(f"  .doc files to convert: {len(doc_entries)}")
print(f"  Non-.doc entries (skipped): {len(skip_entries)}")
print()

# Track results
successes = {}  # doc_id -> txt_path
failures = {}   # doc_id -> error message

# Open Word ONCE
print("Starting Word Application...")
word = win32com.client.Dispatch("Word.Application")
word.Visible = False
print("Word started.\n")

for i, entry in enumerate(doc_entries):
    doc_id = entry["doc_id"]
    title = entry["title"]
    src_path = entry["path"]
    
    safe_title = sanitize_filename(title)
    out_filename = f"{doc_id}_{safe_title}.txt"
    out_path = os.path.join(OUT_DIR, out_filename)
    
    print(f"[{i+1}/{len(doc_entries)}] {doc_id}: {title}")
    print(f"  Source: {src_path}")
    print(f"  Output: {out_filename}")
    
    if not os.path.exists(src_path):
        msg = f"File not found: {src_path}"
        print(f"  ERROR: {msg}")
        failures[doc_id] = msg
        print()
        continue
    
    try:
        doc = word.Documents.Open(src_path, ReadOnly=True)
        
        # Try UTF-8 encoding first (65001), fall back to default
        try:
            doc.SaveAs(out_path, FileFormat=2, Encoding=65001)
            print(f"  OK (UTF-8)")
        except Exception as enc_err:
            print(f"  UTF-8 failed ({enc_err}), trying default encoding...")
            try:
                # Try without encoding parameter
                doc.SaveAs(out_path, FileFormat=2)
                print(f"  OK (default encoding)")
            except Exception as e2:
                raise e2
        
        doc.Close(SaveChanges=False)
        successes[doc_id] = out_path
        
    except Exception as e:
        err_msg = str(e)
        print(f"  ERROR: {err_msg}")
        failures[doc_id] = err_msg
        # Try to close any open document
        try:
            word.Documents.Close(SaveChanges=False)
        except:
            pass
    
    print()

# Quit Word
print("Quitting Word...")
try:
    word.Quit()
    print("Word closed.\n")
except Exception as e:
    print(f"Warning closing Word: {e}\n")

# Update the JSONL index with txt_path
print("Updating documentation_index.jsonl with txt_path fields...")
updated_entries = []
for entry in entries:
    doc_id = entry["doc_id"]
    if doc_id in successes:
        entry["txt_path"] = successes[doc_id]
    updated_entries.append(entry)

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    for entry in updated_entries:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

print("Index updated.\n")

# Summary
print("=" * 60)
print("CONVERSION SUMMARY")
print("=" * 60)
print(f"Total .doc files:     {len(doc_entries)}")
print(f"Successful:           {len(successes)}")
print(f"Failed:               {len(failures)}")
print()

if successes:
    print(f"SUCCEEDED ({len(successes)}):")
    for doc_id, path in successes.items():
        print(f"  {doc_id} -> {os.path.basename(path)}")
    print()

if failures:
    print(f"FAILED ({len(failures)}):")
    for doc_id, err in failures.items():
        print(f"  {doc_id}: {err}")
    print()

print("Done.")
