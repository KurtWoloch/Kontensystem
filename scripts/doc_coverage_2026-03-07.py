#!/usr/bin/env python3
"""Doc coverage analysis for March 7, 2026 planner log."""
import json, re, os
from datetime import datetime
from collections import defaultdict

BASE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem"

with open(os.path.join(BASE, "logs", "planner-log-2026-03-07.json"), encoding="utf-8") as f:
    log = json.load(f)

task_by_code = {}
with open(os.path.join(BASE, "data", "master_task_list_v4.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        t = json.loads(line)
        if t.get("code"):
            task_by_code[t["code"]] = t

def extract_code(activity):
    m = re.search(r'\b([A-Z]{2,6}[A-Z0-9]{0,4})\s*(?:\([^)]*\))?\s*$', activity)
    if m and len(m.group(1)) == 6:
        return m.group(1)
    return None

def actual_minutes(entry):
    try:
        s = datetime.strptime(entry["started_at"], "%H:%M:%S")
        c = datetime.strptime(entry["completed_at"], "%H:%M:%S")
        return max((c - s).seconds // 60, 0)
    except:
        return entry.get("minutes", 0)

undoc_time = defaultdict(lambda: {"minutes": 0, "activities": [], "code": "", "task_name": "", "account": ""})
total_mins = 0
status_mins = defaultdict(int)

for entry in log:
    if entry.get("skipped"):
        continue
    mins = actual_minutes(entry)
    total_mins += mins

    code = extract_code(entry["activity"])
    if not code:
        orig = entry.get("original_activity", "")
        if orig:
            code = extract_code(orig)

    if code and code in task_by_code:
        task = task_by_code[code]
        doc_status = task.get("doc_status", "undocumented")
        status_mins[doc_status] += mins

        if doc_status == "undocumented":
            key = code
            undoc_time[key]["minutes"] += mins
            undoc_time[key]["activities"].append(entry["activity"])
            undoc_time[key]["code"] = code
            undoc_time[key]["task_name"] = task.get("name", "")
            undoc_time[key]["account"] = task.get("account_prefix", "")
    elif code:
        status_mins["unknown_code"] += mins
    else:
        status_mins["no_code"] += mins

print("=" * 70)
print("DOKUMENTATIONS-ABDECKUNG - 7. Maerz 2026 (Samstag)")
print("=" * 70)
print()
print(f"Gesamtzeit (nicht-uebersprungen): {total_mins} min ({total_mins/60:.1f}h)")
print()
for st in ["documented", "mentioned", "undocumented", "unknown_code", "no_code"]:
    m = status_mins.get(st, 0)
    pct = 100 * m / total_mins if total_mins else 0
    labels = {
        "documented": "Dokumentiert",
        "mentioned": "Erwaehnt (Account-Level)",
        "undocumented": "Undokumentiert",
        "unknown_code": "Code nicht in Task-Liste",
        "no_code": "Kein Code",
    }
    print(f"  {labels[st]:<30s}: {m:>4} min  ({pct:>5.1f}%)")

print()
print("=" * 70)
print("UNDOKUMENTIERTE AKTIVITAETEN - sortiert nach Zeitaufwand")
print("=" * 70)
print()

items = sorted(undoc_time.values(), key=lambda x: -x["minutes"])
for item in items:
    print(f"  {item['minutes']:>4} min  [{item['code']}]  {item['task_name'][:60]}")
    print(f"           Account: {item['account']}")
    unique_acts = list(dict.fromkeys(item["activities"]))
    if len(unique_acts) > 1:
        for a in unique_acts:
            print(f"           > {a[:70]}")
    print()
