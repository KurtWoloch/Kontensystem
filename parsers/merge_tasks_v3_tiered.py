"""Merge v3: Produce tiered master task list.

Tier 1 - Core: Appears in 2+ sources (recurring, plannable)
Tier 2 - Defined: Single-source but from structured/planning sources (CSV, old_cs, kurtdoku, etc.)
Tier 3 - Logged: Single-source, only in Ablauf or Aufwandserfassung (one-off, reference only)

Output:
- master_task_list_v3.jsonl  (Tier 1 + 2, the reviewable list)
- master_task_list_v3.csv    (same, human-readable spreadsheet format)
- logged_activities.jsonl    (Tier 3, reference/annotation index)
- merge_report_v3.txt        (summary stats)
"""
import json
import os
import csv as csvmod

DATA_DIR = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data"
INPUT_FILE = os.path.join(DATA_DIR, "master_task_list_v2.jsonl")

OUTPUT_MASTER_JSONL = os.path.join(DATA_DIR, "master_task_list_v3.jsonl")
OUTPUT_MASTER_CSV = os.path.join(DATA_DIR, "master_task_list_v3.csv")
OUTPUT_LOGGED = os.path.join(DATA_DIR, "logged_activities.jsonl")
OUTPUT_REPORT = os.path.join(DATA_DIR, "merge_report_v3.txt")

# Structured/planning sources (Tier 2 if single-source)
STRUCTURED_SOURCES = {
    'csv', 'old_cs', 'kurtdoku',
    'taskliste', 'window_logger_vb5', 'yaml_exceptions', 'windowlog_corrector',
    'access_Tab_Gewinnaktionen', 'access_Tab_Wuensche'
}

# Logged-only sources (Tier 3 if single-source)
LOGGED_SOURCES = {
    'ablauf_planned', 'ablauf_unplanned',
    'access_Tab_Aufwandserfassung', 'access_Tab_Aktionen'
}

def load_tasks():
    tasks = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    return tasks

def classify(task):
    """Assign tier based on source count and source types."""
    sources = [s.strip() for s in task['sources'].split(',')]
    
    if len(sources) >= 2:
        return 1  # Core: multi-source
    
    source = sources[0]
    if source in STRUCTURED_SOURCES:
        return 2  # Defined: single structured source
    
    return 3  # Logged: single logged source

def run():
    tasks = load_tasks()
    print(f"Loaded {len(tasks)} tasks from v2 merge")
    
    # Classify
    tiers = {1: [], 2: [], 3: []}
    for task in tasks:
        tier = classify(task)
        task['tier'] = tier
        tiers[tier].append(task)
    
    print(f"Tier 1 (Core - multi-source):     {len(tiers[1])}")
    print(f"Tier 2 (Defined - structured):     {len(tiers[2])}")
    print(f"Tier 3 (Logged - one-off):         {len(tiers[3])}")
    print(f"Reviewable (Tier 1+2):             {len(tiers[1]) + len(tiers[2])}")
    
    # Sort: Tier 1 first, then Tier 2, within each sort by name
    reviewable = sorted(tiers[1], key=lambda t: t['name'].lower()) + \
                 sorted(tiers[2], key=lambda t: t['name'].lower())
    logged = sorted(tiers[3], key=lambda t: t['name'].lower())
    
    # Write JSONL (reviewable)
    with open(OUTPUT_MASTER_JSONL, 'w', encoding='utf-8') as f:
        for task in reviewable:
            f.write(json.dumps(task, ensure_ascii=False) + '\n')
    
    # Write CSV (reviewable, human-friendly)
    csv_fields = ['tier', 'name', 'code', 'account_prefix', 'parent', 'list', 
                  'priority', 'fixed_time', 'status', 'sources', 'source_count', 
                  'variant_count', 'notes']
    with open(OUTPUT_MASTER_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csvmod.DictWriter(f, fieldnames=csv_fields, delimiter=';',
                                    extrasaction='ignore')
        writer.writeheader()
        for task in reviewable:
            writer.writerow(task)
    
    # Write logged activities
    with open(OUTPUT_LOGGED, 'w', encoding='utf-8') as f:
        for task in logged:
            f.write(json.dumps(task, ensure_ascii=False) + '\n')
    
    # Write report
    with open(OUTPUT_REPORT, 'w', encoding='utf-8') as f:
        f.write("Master Task List v3 - Tiered Merge Report\n")
        f.write("=" * 55 + "\n\n")
        f.write(f"Total from v2 merge: {len(tasks)}\n\n")
        f.write(f"Tier 1 (Core - appears in 2+ sources): {len(tiers[1])}\n")
        f.write(f"Tier 2 (Defined - single structured source): {len(tiers[2])}\n")
        f.write(f"Tier 3 (Logged - one-off, reference only): {len(tiers[3])}\n")
        f.write(f"\nReviewable list (Tier 1+2): {len(reviewable)}\n")
        f.write(f"Reference list (Tier 3): {len(logged)}\n\n")
        
        # Account prefix distribution in reviewable
        f.write("Account distribution (reviewable tasks with account prefix):\n")
        acct_counts = {}
        for t in reviewable:
            a = t.get('account_prefix', '') or '??'
            acct_counts[a] = acct_counts.get(a, 0) + 1
        for acct, cnt in sorted(acct_counts.items(), key=lambda x: -x[1]):
            f.write(f"  {acct}: {cnt}\n")
        
        # Tasks with codes vs without
        with_code = sum(1 for t in reviewable if t.get('code'))
        f.write(f"\nWith 6-char code: {with_code}\n")
        f.write(f"Without code: {len(reviewable) - with_code}\n\n")
        
        # Tier 1 breakdown
        f.write("=" * 55 + "\n")
        f.write(f"TIER 1 - Core Tasks ({len(tiers[1])})\n")
        f.write("=" * 55 + "\n\n")
        for t in sorted(tiers[1], key=lambda x: (-x['source_count'], x['name'].lower())):
            code_str = f" [{t['code']}]" if t['code'] else ""
            acct_str = f" ({t['account_prefix']})" if t.get('account_prefix') else ""
            var_str = f" ~{t['variant_count']} variants" if t.get('variant_count', 0) > 1 else ""
            f.write(f"  [{t['source_count']} src] {t['name']}{code_str}{acct_str}{var_str}\n")
        
        f.write("\n" + "=" * 55 + "\n")
        f.write(f"TIER 2 - Defined Tasks ({len(tiers[2])})\n")
        f.write("=" * 55 + "\n\n")
        for t in sorted(tiers[2], key=lambda x: x['name'].lower()):
            code_str = f" [{t['code']}]" if t['code'] else ""
            src = t['sources']
            f.write(f"  {t['name']}{code_str} (from: {src})\n")
    
    print(f"\nOutput:")
    print(f"  Reviewable: {OUTPUT_MASTER_JSONL}")
    print(f"  Reviewable CSV: {OUTPUT_MASTER_CSV}")
    print(f"  Logged ref: {OUTPUT_LOGGED}")
    print(f"  Report: {OUTPUT_REPORT}")

if __name__ == '__main__':
    run()
