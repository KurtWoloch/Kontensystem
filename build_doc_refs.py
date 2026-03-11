"""
build_doc_refs.py
Match master task list entries to documentation files.
Adds doc_refs and doc_status fields to each task.
"""
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

WORKSPACE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem"
DATA = os.path.join(WORKSPACE, "data")

print("Loading master task list...", flush=True)
tasks = []
with open(os.path.join(DATA, "master_task_list_v4.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            tasks.append(json.loads(line))
print(f"  {len(tasks)} tasks loaded", flush=True)

print("Loading documentation index...", flush=True)
docs = []
with open(os.path.join(DATA, "documentation_index.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            docs.append(json.loads(line))
print(f"  {len(docs)} docs loaded", flush=True)


def get_txt_content(doc):
    """Return text content of a doc, or None if unavailable."""
    txt_path = doc.get("txt_path")
    if txt_path and os.path.exists(txt_path):
        try:
            with open(txt_path, encoding="cp1252", errors="replace") as f:
                return f.read()
        except Exception as e:
            print(f"    Error reading {txt_path}: {e}", flush=True)
            return None

    # For plain .txt or direct path docs (e.g. DOC107 KURTDOKU)
    fmt = doc.get("format", "")
    if fmt == "txt":
        direct_path = doc.get("path", "")
        if direct_path and os.path.exists(direct_path):
            try:
                with open(direct_path, encoding="cp1252", errors="replace") as f:
                    return f.read()
            except Exception as e:
                print(f"    Error reading {direct_path}: {e}", flush=True)
    return None


# Pre-build task lookup structures
print("Building task lookup tables...", flush=True)
# (task_idx, name_lower, name_original)
task_names = []
# (task_idx, code_str)
task_codes = []
# account_prefix -> list of task_idx
task_account_map = defaultdict(list)
# account prefix sizes
account_sizes = defaultdict(int)

for i, task in enumerate(tasks):
    name = task.get("name", "")
    code = task.get("code", "")
    account = task.get("account_prefix", "")

    # Named matching: only if name is >= 8 chars
    if len(name) >= 8:
        task_names.append((i, name.lower(), name))

    # Code matching: only 6-char codes
    if code and len(code) == 6:
        task_codes.append((i, code))

    if account:
        task_account_map[account].append(i)
        account_sizes[account] += 1

print(f"  {len(task_names)} tasks with names >=8 chars", flush=True)
print(f"  {len(task_codes)} tasks with 6-char codes", flush=True)

# Initialize doc_refs and doc_status on all tasks
for task in tasks:
    task["doc_refs"] = []
    task["doc_status"] = "undocumented"

# Track which (task_idx, doc_id) pairs are already matched (to avoid duplicates)
matched_pairs = set()  # (task_idx, doc_id) -> match_type already recorded

def add_ref(task_idx, doc_id, match_type, context):
    key = (task_idx, doc_id, match_type)
    if key not in matched_pairs:
        matched_pairs.add(key)
        tasks[task_idx]["doc_refs"].append({
            "doc_id": doc_id,
            "match_type": match_type,
            "context": context
        })


def extract_context(content, pos, term_len, window=50, max_len=120):
    start = max(0, pos - window)
    end = min(len(content), pos + term_len + window)
    snippet = content[start:end].strip()
    snippet = snippet.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    # Collapse multiple spaces
    import re
    snippet = re.sub(r' +', ' ', snippet)
    if len(snippet) > max_len:
        snippet = snippet[:max_len] + "..."
    return snippet


print(f"\nProcessing {len(docs)} documentation files...", flush=True)

docs_processed = 0
docs_skipped = 0

for doc in docs:
    doc_id = doc["doc_id"]
    doc_account = doc.get("account_prefix", "")
    doc_title = doc.get("title", "")

    content = get_txt_content(doc)
    if content is None:
        docs_skipped += 1
        continue

    docs_processed += 1
    content_lower = content.lower()

    named_found = set()
    coded_found = set()

    # --- Named matching ---
    for (task_idx, name_lower, name_original) in task_names:
        pos = content_lower.find(name_lower)
        if pos >= 0:
            context = extract_context(content, pos, len(name_lower))
            add_ref(task_idx, doc_id, "named", context)
            named_found.add(task_idx)

    # --- Code matching ---
    for (task_idx, code) in task_codes:
        if task_idx in named_found:
            continue  # already have a stronger match for this doc
        # Codes are uppercase 6-char strings; check both in original and lower
        # (they might appear as-is in text)
        pos = content.find(code)
        if pos < 0:
            # also try lowercase? Unlikely for codes but let's check
            pos = content_lower.find(code.lower())
        if pos >= 0:
            context = extract_context(content, pos, len(code))
            add_ref(task_idx, doc_id, "coded", context)
            coded_found.add(task_idx)

    # --- Account matching (weak) ---
    # Only for documents with a specific account prefix AND small account (<=50 tasks)
    # AND only for tasks not already matched via name/code in this doc
    if doc_account and doc_account in task_account_map:
        if account_sizes[doc_account] <= 50:
            for task_idx in task_account_map[doc_account]:
                if task_idx not in named_found and task_idx not in coded_found:
                    context = f"[Account {doc_account} coverage: {doc_title[:60]}]"
                    add_ref(task_idx, doc_id, "account", context)

    if docs_processed % 20 == 0:
        print(f"  Processed {docs_processed} docs...", flush=True)

print(f"  Done. Processed={docs_processed}, Skipped={docs_skipped}", flush=True)

# --- Set doc_status ---
print("\nSetting doc_status for all tasks...", flush=True)
for task in tasks:
    refs = task.get("doc_refs", [])
    if not refs:
        task["doc_status"] = "undocumented"
    else:
        match_types = {r["match_type"] for r in refs}
        if "named" in match_types or "coded" in match_types:
            task["doc_status"] = "documented"
        else:
            task["doc_status"] = "mentioned"  # account-level only

total = len(tasks)
documented = sum(1 for t in tasks if t["doc_status"] == "documented")
mentioned = sum(1 for t in tasks if t["doc_status"] == "mentioned")
undocumented = sum(1 for t in tasks if t["doc_status"] == "undocumented")
print(f"  documented={documented}, mentioned={mentioned}, undocumented={undocumented}", flush=True)

# --- Write updated master task list ---
output_path = os.path.join(DATA, "master_task_list_v4.jsonl")
print(f"\nWriting updated master task list to {output_path}...", flush=True)
with open(output_path, "w", encoding="utf-8") as f:
    for task in tasks:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")
print(f"  Written {len(tasks)} tasks.", flush=True)

# --- Build report data ---
print("\nGenerating report...", flush=True)

# Breakdown by account prefix
account_stats = defaultdict(lambda: {"documented": 0, "mentioned": 0, "undocumented": 0, "total": 0})
for task in tasks:
    acc = task.get("account_prefix") or "(none)"
    account_stats[acc]["total"] += 1
    account_stats[acc][task["doc_status"]] += 1

# Document -> task references (named/coded only)
doc_named_coded = defaultdict(list)  # doc_id -> [(task_name, code, match_type)]
doc_account_refs = defaultdict(list) # doc_id -> [(task_name, code)]

for task in tasks:
    for ref in task.get("doc_refs", []):
        doc_id = ref["doc_id"]
        mt = ref["match_type"]
        if mt in ("named", "coded"):
            doc_named_coded[doc_id].append((task.get("name", ""), task.get("code", ""), mt))
        elif mt == "account":
            doc_account_refs[doc_id].append((task.get("name", ""), task.get("code", "")))

# Sort by most-referenced
doc_title_map = {d["doc_id"]: d["title"] for d in docs}
doc_ranking = sorted(
    doc_named_coded.keys(),
    key=lambda did: -len(doc_named_coded[did])
)

# --- Write report ---
report_path = os.path.join(DATA, "doc_ref_report.txt")
with open(report_path, "w", encoding="utf-8") as f:

    f.write("=" * 72 + "\n")
    f.write("DOC REF REPORT — Kontensystem Task Documentation Links\n")
    f.write("=" * 72 + "\n\n")

    f.write("SUMMARY\n")
    f.write("-" * 40 + "\n")
    f.write(f"Total tasks:              {total}\n")
    f.write(f"Documented (named/coded): {documented} ({100*documented//total if total else 0}%)\n")
    f.write(f"Mentioned (account only): {mentioned} ({100*mentioned//total if total else 0}%)\n")
    f.write(f"Undocumented:             {undocumented} ({100*undocumented//total if total else 0}%)\n\n")
    f.write(f"Docs processed: {docs_processed}\n")
    f.write(f"Docs skipped (no txt):    {docs_skipped}\n\n")

    f.write("\nBREAKDOWN BY ACCOUNT PREFIX\n")
    f.write("-" * 60 + "\n")
    f.write(f"  {'Prefix':8s} {'Total':>6}  {'Documented':>10}  {'Mentioned':>9}  {'Undocumented':>12}\n")
    f.write(f"  {'-'*8} {'-'*6}  {'-'*10}  {'-'*9}  {'-'*12}\n")
    for acc in sorted(account_stats.keys()):
        s = account_stats[acc]
        f.write(f"  {acc:8s} {s['total']:>6}  {s['documented']:>10}  {s['mentioned']:>9}  {s['undocumented']:>12}\n")

    f.write("\n\nTOP 30 DOCUMENTS BY TASK REFERENCES (named + coded)\n")
    f.write("-" * 60 + "\n")
    f.write(f"  {'DocID':7s} {'Refs':>5}  {'Title'}\n")
    f.write(f"  {'-'*7} {'-'*5}  {'-'*50}\n")
    for doc_id in doc_ranking[:30]:
        refs = doc_named_coded[doc_id]
        named_count = sum(1 for r in refs if r[2] == "named")
        coded_count = sum(1 for r in refs if r[2] == "coded")
        title = doc_title_map.get(doc_id, "?")
        f.write(f"  {doc_id:7s} {len(refs):>5}  {title[:55]}  (named={named_count}, coded={coded_count})\n")

    f.write("\n\nDOCUMENTED TASKS BY DOCUMENT (named/coded matches)\n")
    f.write("=" * 72 + "\n")
    for doc_id in doc_ranking:
        title = doc_title_map.get(doc_id, "?")
        refs = doc_named_coded[doc_id]
        named_c = sum(1 for r in refs if r[2] == "named")
        coded_c = sum(1 for r in refs if r[2] == "coded")
        f.write(f"\n{doc_id}: {title}\n")
        f.write(f"  ({len(refs)} refs: named={named_c}, coded={coded_c})\n")
        for task_name, task_code, mt in sorted(refs, key=lambda x: x[0]):
            f.write(f"    [{mt:5s}]  {task_code:6s}  {task_name}\n")

    f.write("\n\nUNDOCUMENTED TASKS\n")
    f.write("=" * 72 + "\n")
    undoc_tasks = [t for t in tasks if t["doc_status"] == "undocumented"]
    undoc_tasks.sort(key=lambda t: (not t.get("in_planner_csv", False), t.get("account_prefix") or "", t.get("name", "")))
    f.write(f"Total undocumented: {len(undoc_tasks)}\n\n")

    f.write("-- IN PLANNER (active, in_planner_csv=True) --\n")
    in_planner_undoc = [t for t in undoc_tasks if t.get("in_planner_csv")]
    for t in in_planner_undoc:
        f.write(f"  {t.get('code', ''):6s}  {t.get('account_prefix', ''):4s}  {t['name']}\n")
    f.write(f"  ({len(in_planner_undoc)} tasks)\n\n")

    f.write("-- NOT IN PLANNER --\n")
    not_planner_undoc = [t for t in undoc_tasks if not t.get("in_planner_csv")]
    for t in not_planner_undoc:
        f.write(f"  {t.get('code', ''):6s}  {t.get('account_prefix', ''):4s}  {t['name']}\n")
    f.write(f"  ({len(not_planner_undoc)} tasks)\n")

print(f"Report written to {report_path}", flush=True)

print("\n" + "=" * 60)
print("FINAL SUMMARY")
print("=" * 60)
print(f"Total tasks:              {total}")
print(f"Documented (named/coded): {documented} ({100*documented//total if total else 0}%)")
print(f"Mentioned (account only): {mentioned} ({100*mentioned//total if total else 0}%)")
print(f"Undocumented:             {undocumented} ({100*undocumented//total if total else 0}%)")
print(f"\nDocs processed: {docs_processed}, Skipped: {docs_skipped}")
print(f"\nTop 5 most-referenced docs:")
for doc_id in doc_ranking[:5]:
    refs = doc_named_coded[doc_id]
    print(f"  {doc_id}: {len(refs)} refs — {doc_title_map.get(doc_id, '?')[:50]}")
