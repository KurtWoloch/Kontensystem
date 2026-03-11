#!/usr/bin/env python3
"""Flag master task list entries that appear in the planner CSV."""

import csv
import json
import re
import unicodedata
from pathlib import Path
from collections import defaultdict

# --- Paths ---
CSV_PATH = Path(r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Planungsaktivitaeten.csv")
MASTER_V3 = Path(r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\master_task_list_v3.jsonl")
MASTER_V4 = Path(r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\master_task_list_v4.jsonl")
REPORT_PATH = Path(r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\planner_coverage_report.txt")

# --- Parse CSV ---
CODE_RE = re.compile(r'\b([A-Z]{6})\s*$')

def normalize(s):
    """Normalize string for fuzzy name matching."""
    s = s.strip().lower()
    # Replace umlauts
    s = s.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    # Remove trailing 6-char code
    s = re.sub(r'\s+[A-Z]{6}\s*$', '', s).strip()
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s)
    return s

csv_rows = []  # list of dicts with 'activity', 'code', 'list', 'priority'
with open(CSV_PATH, encoding='cp1252', newline='') as f:
    reader = csv.reader(f, delimiter=';')
    headers = next(reader)
    print(f"CSV headers: {headers}")
    for row in reader:
        if not row or not row[0].strip():
            continue
        activity_full = row[0].strip()
        code_match = CODE_RE.search(activity_full)
        code = code_match.group(1) if code_match else ''
        # Strip code from activity name for display
        activity_name = re.sub(r'\s+[A-Z]{6}\s*$', '', activity_full).strip()
        csv_rows.append({
            'activity_full': activity_full,
            'activity_name': activity_name,
            'code': code,
            'list': row[2].strip() if len(row) > 2 else '',
            'priority': row[3].strip() if len(row) > 3 else '',
            'norm': normalize(activity_full),
        })

print(f"CSV rows: {len(csv_rows)}")
print(f"CSV rows with 6-char code: {sum(1 for r in csv_rows if r['code'])}")

# Build lookup structures
csv_by_code = {}  # code -> row
csv_by_norm = {}  # normalized_name -> row

for row in csv_rows:
    if row['code']:
        csv_by_code[row['code']] = row
    norm = row['norm']
    if norm not in csv_by_norm:
        csv_by_norm[norm] = row

print(f"Unique codes in CSV: {len(csv_by_code)}")
print(f"Unique normalized names in CSV: {len(csv_by_norm)}")

# --- Load master task list ---
master_tasks = []
with open(MASTER_V3, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            master_tasks.append(json.loads(line))

print(f"Master tasks: {len(master_tasks)}")

# --- Match ---
matched = 0
code_matched = 0
name_matched = 0

# Track which CSV entries have been matched by a master task
csv_matched_codes = set()
csv_matched_norms = set()

v4_tasks = []
for task in master_tasks:
    task_code = task.get('code', '').strip()
    task_name = task.get('name', '').strip()
    task_norm = normalize(task_name)

    in_csv = False
    match_method = ''
    planner_activity = ''

    # Strategy 1: Code match
    if task_code and len(task_code) == 6 and task_code in csv_by_code:
        in_csv = True
        match_method = 'code'
        csv_row = csv_by_code[task_code]
        planner_activity = csv_row['activity_name']
        csv_matched_codes.add(task_code)
        csv_matched_norms.add(csv_row['norm'])

    # Strategy 2: Name match (only if no code match)
    if not in_csv and task_norm and task_norm in csv_by_norm:
        in_csv = True
        match_method = 'name'
        csv_row = csv_by_norm[task_norm]
        planner_activity = csv_row['activity_name']
        csv_matched_norms.add(csv_row['norm'])

    # Strategy 3: Partial name match — CSV name contains or is contained in task name
    # (generous but not sloppy: require at least 20 chars or full match of shorter string)
    if not in_csv and len(task_norm) >= 10:
        for norm_key, csv_row in csv_by_norm.items():
            # task norm is contained in CSV norm, or CSV norm contained in task norm
            if (task_norm in norm_key or norm_key in task_norm) and abs(len(task_norm) - len(norm_key)) <= 30:
                in_csv = True
                match_method = 'name'
                planner_activity = csv_row['activity_name']
                csv_matched_norms.add(norm_key)
                break

    if in_csv:
        matched += 1
        if match_method == 'code':
            code_matched += 1
        else:
            name_matched += 1

    # Build v4 entry — preserve all existing fields, add new ones
    v4_entry = dict(task)
    v4_entry['in_planner_csv'] = in_csv
    v4_entry['planner_match_method'] = match_method
    v4_entry['planner_activity'] = planner_activity
    v4_tasks.append(v4_entry)

# --- Write v4 ---
with open(MASTER_V4, 'w', encoding='utf-8') as f:
    for entry in v4_tasks:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

print(f"\nWritten {len(v4_tasks)} entries to {MASTER_V4}")

# --- Find CSV orphans (CSV activities with no master task match) ---
orphan_rows = []
for row in csv_rows:
    code_matched_flag = row['code'] and row['code'] in csv_matched_codes
    norm_matched_flag = row['norm'] in csv_matched_norms
    if not code_matched_flag and not norm_matched_flag:
        orphan_rows.append(row)

# --- Build report ---
total = len(v4_tasks)
match_rate = matched / total * 100 if total else 0

# By status
status_stats = defaultdict(lambda: {'total': 0, 'matched': 0})
for t in v4_tasks:
    s = t.get('status', 'unknown')
    status_stats[s]['total'] += 1
    if t['in_planner_csv']:
        status_stats[s]['matched'] += 1

# By tier
tier_stats = defaultdict(lambda: {'total': 0, 'matched': 0})
for t in v4_tasks:
    tier = t.get('tier', 'unknown')
    tier_stats[tier]['total'] += 1
    if t['in_planner_csv']:
        tier_stats[tier]['matched'] += 1

# Matched tasks grouped by list
matched_by_list = defaultdict(list)
for t in v4_tasks:
    if t['in_planner_csv']:
        lst = t.get('list', '') or '(no list)'
        matched_by_list[lst].append(t)

lines = []
lines.append("=" * 70)
lines.append("PLANNER CSV COVERAGE REPORT")
lines.append("=" * 70)
lines.append("")
lines.append(f"Total master tasks:     {total}")
lines.append(f"Matched in planner CSV: {matched}  ({match_rate:.1f}%)")
lines.append(f"  - by code:            {code_matched}")
lines.append(f"  - by name:            {name_matched}")
lines.append(f"Not matched:            {total - matched}")
lines.append("")
lines.append("-" * 70)
lines.append("BREAKDOWN BY STATUS")
lines.append("-" * 70)
for status in sorted(status_stats.keys()):
    s = status_stats[status]
    pct = s['matched'] / s['total'] * 100 if s['total'] else 0
    lines.append(f"  {status:<20s}  {s['matched']:>4d} / {s['total']:>4d}  ({pct:.1f}%)")

lines.append("")
lines.append("-" * 70)
lines.append("BREAKDOWN BY TIER")
lines.append("-" * 70)
for tier in sorted(tier_stats.keys(), key=lambda x: str(x)):
    s = tier_stats[tier]
    pct = s['matched'] / s['total'] * 100 if s['total'] else 0
    lines.append(f"  Tier {str(tier):<5s}  {s['matched']:>4d} / {s['total']:>4d}  ({pct:.1f}%)")

lines.append("")
lines.append("-" * 70)
lines.append("MATCHED TASKS BY LIST ASSIGNMENT")
lines.append("-" * 70)
for lst in sorted(matched_by_list.keys()):
    tasks_in_list = matched_by_list[lst]
    lines.append(f"\n  [{lst}]  ({len(tasks_in_list)} tasks)")
    for t in sorted(tasks_in_list, key=lambda x: x.get('name', '')):
        code_str = f" [{t['code']}]" if t.get('code') else ''
        lines.append(f"    {t['name']}{code_str}  (method: {t['planner_match_method']}, csv: {t['planner_activity']})")

lines.append("")
lines.append("-" * 70)
lines.append(f"PLANNER CSV ORPHANS ({len(orphan_rows)} activities with no master task match)")
lines.append("-" * 70)
lines.append("  These CSV activities are not found in the master task list:")
lines.append("")
for row in sorted(orphan_rows, key=lambda r: r['list'] + '|' + r['activity_name']):
    code_str = f" [{row['code']}]" if row['code'] else ''
    lines.append(f"  [{row['list']}]  {row['activity_name']}{code_str}")

lines.append("")
lines.append("=" * 70)
lines.append(f"Report generated for master_task_list_v4.jsonl")
lines.append("=" * 70)

report_text = '\n'.join(lines)
with open(REPORT_PATH, 'w', encoding='utf-8') as f:
    f.write(report_text)

print(f"\nReport written to {REPORT_PATH}")
print(f"\n=== SUMMARY ===")
print(f"Total: {total}, Matched: {matched} ({match_rate:.1f}%), Orphan CSV activities: {len(orphan_rows)}")
print(f"Code matches: {code_matched}, Name matches: {name_matched}")
