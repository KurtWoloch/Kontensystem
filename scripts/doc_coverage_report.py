#!/usr/bin/env python3
"""
Cross-reference March 4 planner log against documentation coverage.
Generates data/daily_doc_coverage_2026-03-04.txt
"""
import json
import re
import os
from datetime import datetime, date
from collections import defaultdict

BASE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem"

# ── Load data ─────────────────────────────────────────────────────────────────

with open(os.path.join(BASE, "logs", "planner-log-2026-03-04.json"), encoding="utf-8") as f:
    log = json.load(f)

task_by_code = {}   # code → task entry
task_by_name = {}   # lower-stripped name → task entry

with open(os.path.join(BASE, "data", "master_task_list_v4.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        t = json.loads(line)
        if t.get("code"):
            task_by_code[t["code"]] = t
        # also index by first 20 chars of name (lowered) for fuzzy name matching
        key = t["name"].lower().strip()
        if key not in task_by_name:
            task_by_name[key] = t

doc_index = {}  # doc_id → doc entry
with open(os.path.join(BASE, "data", "documentation_index.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        doc_index[d["doc_id"]] = d

TODAY = date(2026, 3, 5)   # report generation date

def doc_age_years(doc):
    """Return age in years from last_modified string (YYYY-MM-DD or similar)."""
    lm = doc.get("last_modified", "")
    if not lm:
        return None
    # Try YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y"):
        try:
            d = datetime.strptime(lm[:10], fmt[:len(lm[:10])]).date()
            return round((TODAY - d).days / 365.25, 1)
        except Exception:
            pass
    # Try numeric year embedded in title like "7.5.29" → 2007 or 2029?
    # last_modified field should be a proper date; if unparseable, return None
    return None

# ── Extract 6-char code from activity string ──────────────────────────────────

def extract_code(activity: str):
    """Return the last 6-char uppercase alphanum token if it looks like a code."""
    m = re.search(r'\b([A-Z]{2,6}[A-Z0-9]{0,4})\s*(?:\([^)]*\))?\s*$', activity)
    if m:
        cand = m.group(1)
        if len(cand) == 6:
            return cand
    return None

# ── Match log entry to master task ────────────────────────────────────────────

def match_task(entry):
    """Return (task_entry_or_None, match_method)"""
    activity = entry["activity"]
    code = extract_code(activity)
    if code and code in task_by_code:
        return task_by_code[code], "code"
    # Try original_activity code
    orig = entry.get("original_activity", "")
    if orig:
        code2 = extract_code(orig)
        if code2 and code2 in task_by_code:
            return task_by_code[code2], "orig_code"
    # Try name match (strip code suffix, lowercase)
    name_clean = re.sub(r'\s+[A-Z]{6}\s*(\([^)]*\))?\s*$', '', activity).strip().lower()
    if name_clean in task_by_name:
        return task_by_name[name_clean], "name_exact"
    # Try prefix match (first 30 chars)
    for key, t in task_by_name.items():
        if len(name_clean) >= 10 and name_clean[:20] == key[:20]:
            return t, "name_prefix"
    return None, None

# ── Process log entries ────────────────────────────────────────────────────────

def actual_minutes(entry):
    """Compute actual minutes from started_at / completed_at."""
    try:
        s = datetime.strptime(entry["started_at"], "%H:%M:%S")
        c = datetime.strptime(entry["completed_at"], "%H:%M:%S")
        diff = (c - s).seconds // 60
        if diff < 0:
            diff += 24 * 60
        return diff
    except Exception:
        return entry.get("minutes", 0)

records = []
for entry in log:
    if entry.get("skipped"):
        continue
    mins = actual_minutes(entry)
    task, method = match_task(entry)
    code = extract_code(entry["activity"]) or (extract_code(entry.get("original_activity", "")) or "")
    
    if task:
        doc_status = task.get("doc_status", "undocumented")
        doc_refs = task.get("doc_refs", [])
        account_prefix = task.get("account_prefix", "")
    else:
        doc_status = "unmatched"
        doc_refs = []
        account_prefix = ""

    # Build doc details
    doc_details = []
    for ref in doc_refs:
        did = ref["doc_id"]
        doc = doc_index.get(did)
        if doc:
            age = doc_age_years(doc)
            doc_details.append({
                "doc_id": did,
                "title": doc.get("title", did),
                "last_modified": doc.get("last_modified", "?"),
                "age_years": age,
                "match_type": ref.get("match_type", ""),
            })

    records.append({
        "activity": entry["activity"],
        "code": code,
        "list": entry.get("list", ""),
        "minutes": mins,
        "started_at": entry["started_at"],
        "completed_at": entry["completed_at"],
        "doc_status": doc_status,
        "match_method": method,
        "account_prefix": account_prefix,
        "doc_details": doc_details,
        "task_name": task["name"] if task else "",
    })

# ── Aggregate: group by canonical activity (code or stripped name) ─────────────

def canonical_key(rec):
    if rec["code"]:
        return rec["code"]
    return re.sub(r'\s+[A-Z]{6}\s*(\([^)]*\))?\s*$', '', rec["activity"]).strip()

aggregated = defaultdict(lambda: {
    "activities": [], "minutes": 0, "doc_status": "unmatched",
    "code": "", "account_prefix": "", "doc_details": [], "task_name": ""
})

for rec in records:
    key = canonical_key(rec)
    agg = aggregated[key]
    agg["activities"].append(rec["activity"])
    agg["minutes"] += rec["minutes"]
    # Keep the most informative doc_status
    status_rank = {"documented": 3, "mentioned": 2, "undocumented": 1, "unmatched": 0}
    if status_rank.get(rec["doc_status"], 0) > status_rank.get(agg["doc_status"], 0):
        agg["doc_status"] = rec["doc_status"]
        agg["account_prefix"] = rec["account_prefix"]
        agg["task_name"] = rec["task_name"]
    if not agg["code"] and rec["code"]:
        agg["code"] = rec["code"]
    # Merge doc_details (deduplicate by doc_id)
    existing_ids = {d["doc_id"] for d in agg["doc_details"]}
    for d in rec["doc_details"]:
        if d["doc_id"] not in existing_ids:
            agg["doc_details"].append(d)
            existing_ids.add(d["doc_id"])

# Convert to list, sort by minutes desc
items = []
for key, agg in aggregated.items():
    # Get representative activity name
    activity = agg["activities"][0]
    # Clean display name
    display = re.sub(r'\s+[A-Z]{6}\s*(\([^)]*\))?\s*$', '', activity).strip()
    if not display:
        display = activity
    items.append({
        "key": key,
        "display": display,
        "code": agg["code"],
        "minutes": agg["minutes"],
        "doc_status": agg["doc_status"],
        "account_prefix": agg["account_prefix"],
        "task_name": agg["task_name"],
        "doc_details": agg["doc_details"],
        "occurrences": len(agg["activities"]),
    })

items.sort(key=lambda x: x["minutes"], reverse=True)

# ── Statistics ─────────────────────────────────────────────────────────────────

total_mins = sum(r["minutes"] for r in records)
by_status = defaultdict(int)
for r in records:
    by_status[r["doc_status"]] += r["minutes"]

documented_mins = by_status["documented"]
mentioned_mins = by_status["mentioned"]
undocumented_mins = by_status["undocumented"]
unmatched_mins = by_status["unmatched"]

def pct(n):
    if total_mins == 0:
        return 0.0
    return round(100 * n / total_mins, 1)

# ── Oldest documented activities ───────────────────────────────────────────────

# Collect all doc_details with ages across items
all_doc_refs_used = []
for item in items:
    if item["doc_details"]:
        for dd in item["doc_details"]:
            if dd["age_years"] is not None:
                all_doc_refs_used.append({
                    "activity": item["display"],
                    "code": item["code"],
                    "doc_id": dd["doc_id"],
                    "title": dd["title"],
                    "last_modified": dd["last_modified"],
                    "age_years": dd["age_years"],
                    "match_type": dd["match_type"],
                    "activity_mins": item["minutes"],
                })
all_doc_refs_used.sort(key=lambda x: x["age_years"], reverse=True)
# Deduplicate by doc_id, keep highest age
seen_docs = {}
for d in all_doc_refs_used:
    if d["doc_id"] not in seen_docs:
        seen_docs[d["doc_id"]] = d
oldest_docs = sorted(seen_docs.values(), key=lambda x: x["age_years"], reverse=True)[:10]

# Biggest undocumented/unmatched time sinks
undoc_items = [i for i in items if i["doc_status"] in ("undocumented", "unmatched") and i["minutes"] > 0]
undoc_items.sort(key=lambda x: x["minutes"], reverse=True)

# ── Format report ──────────────────────────────────────────────────────────────

STATUS_ICON = {
    "documented": "✅",
    "mentioned": "⚠️ ",
    "undocumented": "❌",
    "unmatched": "🔍",
}
STATUS_LABEL = {
    "documented": "DOCUMENTED",
    "mentioned":  "MENTIONED ",
    "undocumented": "UNDOC     ",
    "unmatched":    "UNMATCHED ",
}

lines = []
lines.append("=" * 80)
lines.append("DAILY DOCUMENTATION COVERAGE REPORT — March 4, 2026")
lines.append("=" * 80)
lines.append(f"Generated: {TODAY.isoformat()}")
lines.append("")

lines.append("━" * 80)
lines.append("SUMMARY STATISTICS")
lines.append("━" * 80)
lines.append(f"  Total minutes logged        : {total_mins:>4} min")
lines.append(f"  ✅ Documented               : {documented_mins:>4} min  ({pct(documented_mins):>5.1f}%)")
lines.append(f"  ⚠️  Mentioned               : {mentioned_mins:>4} min  ({pct(mentioned_mins):>5.1f}%)")
lines.append(f"  ❌ Undocumented             : {undocumented_mins:>4} min  ({pct(undocumented_mins):>5.1f}%)")
lines.append(f"  🔍 Unmatched to task list   : {unmatched_mins:>4} min  ({pct(unmatched_mins):>5.1f}%)")
lines.append(f"  Coverage (doc+mentioned)    :       {pct(documented_mins + mentioned_mins):>5.1f}%")
lines.append("")

lines.append("━" * 80)
lines.append("FULL ACTIVITY LIST  (sorted by time spent, most first)")
lines.append("━" * 80)
lines.append(f"  {'ACTIVITY':<45} {'CODE':<6}  {'MIN':>4}  STATUS      DOCUMENTATION")
lines.append(f"  {'-'*44} {'-'*6}  {'-'*4}  {'-'*10}  {'-'*30}")

for item in items:
    icon = STATUS_ICON.get(item["doc_status"], "?")
    label = STATUS_LABEL.get(item["doc_status"], item["doc_status"])
    display = item["display"]
    if len(display) > 44:
        display = display[:43] + "…"
    code_str = item["code"] or "      "
    
    if item["doc_details"]:
        # Find the "best" doc (named match > account; lowest age is most relevant)
        named = [d for d in item["doc_details"] if d["match_type"] == "named"]
        best_docs = named if named else item["doc_details"]
        # Deduplicate by title
        seen_titles = {}
        for d in best_docs:
            if d["title"] not in seen_titles:
                seen_titles[d["title"]] = d
        best_docs = list(seen_titles.values())[:3]  # max 3
        
        first = True
        for d in best_docs:
            age_str = f"{d['age_years']:.1f}y" if d["age_years"] is not None else "?y"
            title_short = d["title"]
            if len(title_short) > 35:
                title_short = title_short[:34] + "…"
            if first:
                lines.append(f"  {display:<45} {code_str:<6}  {item['minutes']:>4}  {icon} {label}  [{d['doc_id']}] {title_short} ({age_str})")
                first = False
            else:
                lines.append(f"  {'':45} {'':6}  {'':4}  {'':13} [{d['doc_id']}] {title_short} ({age_str})")
    else:
        # No docs
        note = ""
        if item["doc_status"] == "unmatched":
            note = "→ not in task list"
            if item["code"]:
                note = f"→ code {item['code']} not in task list"
        elif item["doc_status"] == "undocumented":
            note = f"→ acct: {item['account_prefix']}" if item["account_prefix"] else "→ no account"
        lines.append(f"  {display:<45} {code_str:<6}  {item['minutes']:>4}  {icon} {label}  {note}")

lines.append("")

lines.append("━" * 80)
lines.append("BIGGEST UNDOCUMENTED / UNMATCHED TIME SINKS  (top 15)")
lines.append("━" * 80)
for i, item in enumerate(undoc_items[:15], 1):
    display = item["display"]
    if len(display) > 50:
        display = display[:49] + "…"
    code_str = f"[{item['code']}]" if item["code"] else "[------]"
    status = item["doc_status"].upper()
    acct = f"acct={item['account_prefix']}" if item["account_prefix"] else "no acct"
    lines.append(f"  {i:>2}. {display:<50} {code_str}  {item['minutes']:>4} min  {status}  {acct}")
lines.append("")

lines.append("━" * 80)
lines.append("OLDEST DOCUMENTATION REFERENCED TODAY  (top 10 by age)")
lines.append("━" * 80)
if oldest_docs:
    for d in oldest_docs:
        title_short = d["title"]
        if len(title_short) > 50:
            title_short = title_short[:49] + "…"
        match_lbl = f"[{d['match_type']}]"
        lines.append(f"  [{d['doc_id']}] {title_short}")
        lines.append(f"       Last modified: {d['last_modified']}  (age: {d['age_years']:.1f} years)  {match_lbl}")
        lines.append(f"       Referenced by: {d['activity']} ({d['activity_mins']} min)")
        lines.append("")
else:
    lines.append("  (No dated documentation found)")
lines.append("")

lines.append("━" * 80)
lines.append("NOTES")
lines.append("━" * 80)
lines.append("  Status definitions:")
lines.append("    ✅ DOCUMENTED  — task has a named or direct doc reference in master task list")
lines.append("    ⚠️  MENTIONED   — task is mentioned in docs for its account but not specifically described")
lines.append("    ❌ UNDOCUMENTED — task has no doc references at all")
lines.append("    🔍 UNMATCHED   — activity could not be matched to any task in master_task_list_v4")
lines.append("")
lines.append("  'Mentioned' docs are typically account-level documents that cover the area")
lines.append("  broadly (e.g. Dokumentation Lebenserhaltung) but don't describe this specific")
lines.append("  task. They count as weak coverage.")
lines.append("")

report_path = os.path.join(BASE, "data", "daily_doc_coverage_2026-03-04.txt")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Report written: {report_path}")
print()
print("=== QUICK SUMMARY ===")
print(f"Total minutes logged : {total_mins}")
print(f"✅ Documented        : {documented_mins} min ({pct(documented_mins):.1f}%)")
print(f"⚠️  Mentioned         : {mentioned_mins} min ({pct(mentioned_mins):.1f}%)")
print(f"❌ Undocumented      : {undocumented_mins} min ({pct(undocumented_mins):.1f}%)")
print(f"🔍 Unmatched         : {unmatched_mins} min ({pct(unmatched_mins):.1f}%)")
print(f"Coverage (doc+ment.) : {pct(documented_mins + mentioned_mins):.1f}%")
print()
print(f"Top 5 undocumented time sinks:")
for item in undoc_items[:5]:
    print(f"  {item['minutes']:>4} min  [{item['code'] or '------'}]  {item['display'][:55]}")
