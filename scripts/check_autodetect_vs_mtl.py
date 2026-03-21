"""Compare AutoDetect rule outputs against Master Task List."""
import json
import re
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load master task list
mtl = []
with open(os.path.join(BASE, 'data', 'master_task_list_v4.jsonl'), 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            mtl.append(json.loads(line))

mtl_codes = {}
mtl_by_name_lower = {}
for t in mtl:
    name = t.get('name', '')
    code = t.get('code', '')
    mtl_by_name_lower[name.lower()] = t
    if code:
        mtl_codes[code] = t

print(f'Master Task List: {len(mtl)} tasks, {len(mtl_codes)} with codes\n')

# Extract AutoDetect activity names from source
with open(os.path.join(BASE, 'planner', 'windowmon_summary.py'), 'r', encoding='utf-8') as f:
    src = f.read()

# Parse AUTODETECT_RULES: find all (account, activity) pairs
# Pattern: lines ending with  'ACCOUNT', 'Activity name'),
activities = set()
for m in re.finditer(r"""["']([A-Z_]{2,})["'],\s*["'](.+?)["']\s*\)""", src):
    account = m.group(1)
    activity = m.group(2)
    # Skip special markers and empty activities
    if account.startswith('_') or not activity:
        continue
    activities.add((account, activity))

# Also collect activities from yesterday's autodetect corrections
corrections_file = os.path.join(BASE, 'logs', 'autodetect-corrections-2026-03-14.json')
correction_activities = set()
if os.path.exists(corrections_file):
    with open(corrections_file, 'r', encoding='utf-8') as f:
        corrections = json.load(f)
    for c in corrections:
        orig = c.get('original', '')
        corr = c.get('corrected', '')
        if orig:
            correction_activities.add(('ORIG', orig))
        if corr:
            correction_activities.add(('CORR', corr))

# Also check yesterday's planner log for windowmon_import entries
planner_log = os.path.join(BASE, 'logs', 'planner-log-2026-03-14.json')
wm_import_activities = set()
if os.path.exists(planner_log):
    with open(planner_log, 'r', encoding='utf-8') as f:
        log = json.load(f)
    for entry in log:
        if entry.get('list') == 'windowmon_import':
            wm_import_activities.add(entry['activity'])

def check_mtl(activity):
    """Check if an activity exists in MTL. Returns (found, info)."""
    # Extract task code
    code_match = re.search(r'\s([A-Z]{6})(?:\s*\(Fs\.\))?\s*$', activity)
    code = code_match.group(1) if code_match else ''
    
    # By code
    if code and code in mtl_codes:
        t = mtl_codes[code]
        return True, f'CODE {code} → {t["name"][:60]}'
    
    # Exact name
    if activity.lower() in mtl_by_name_lower:
        t = mtl_by_name_lower[activity.lower()]
        return True, f'EXACT → code={t.get("code", "(none)")}'
    
    # Prefix match (first 25 chars)
    prefix = activity[:25].lower()
    for name_lower, t in mtl_by_name_lower.items():
        if name_lower.startswith(prefix):
            return True, f'PREFIX → {t["name"][:50]} code={t.get("code", "(none)")}'
    
    return False, ''

# === AutoDetect hardcoded rules ===
print('=' * 90)
print('AUTODETECT HARDCODED RULES vs MTL')
print('=' * 90)

in_mtl = []
not_in_mtl = []
for account, activity in sorted(activities, key=lambda x: x[1]):
    found, info = check_mtl(activity)
    if found:
        in_mtl.append((account, activity, info))
    else:
        not_in_mtl.append((account, activity))

print(f'\nIN MTL ({len(in_mtl)}):')
for account, activity, info in in_mtl:
    print(f'  [{account:2}] {activity}')
    print(f'        {info}')

print(f'\nNOT in MTL ({len(not_in_mtl)}):')
for account, activity in not_in_mtl:
    print(f'  [{account:2}] {activity}')

# === Yesterday's windowmon_import entries ===
print(f'\n{"=" * 90}')
print(f"YESTERDAY'S IMPORTED WINDOWMON ACTIVITIES vs MTL")
print(f'{"=" * 90}')

in_mtl2 = []
not_in_mtl2 = []
for activity in sorted(wm_import_activities):
    found, info = check_mtl(activity)
    if found:
        in_mtl2.append((activity, info))
    else:
        not_in_mtl2.append(activity)

print(f'\nIN MTL ({len(in_mtl2)}):')
for activity, info in in_mtl2:
    print(f'  {activity}')
    print(f'        {info}')

print(f'\nNOT in MTL ({len(not_in_mtl2)}):')
for activity in not_in_mtl2:
    print(f'  {activity}')

# === Summary of correction patterns ===
print(f'\n{"=" * 90}')
print(f'CORRECTION PATTERNS (original → corrected)')
print(f'{"=" * 90}')
if os.path.exists(corrections_file):
    with open(corrections_file, 'r', encoding='utf-8') as f:
        corrections = json.load(f)
    
    # Unique corrections
    seen = set()
    for c in corrections:
        orig = c.get('original', '')
        corr = c.get('corrected', '')
        key = (orig, corr)
        if key not in seen:
            seen.add(key)
            orig_found, _ = check_mtl(orig)
            corr_found, corr_info = check_mtl(corr)
            orig_mark = '✓' if orig_found else '✗'
            corr_mark = '✓' if corr_found else '✗'
            print(f'  {orig_mark} {orig}')
            print(f'    → {corr_mark} {corr}')
            if corr_found:
                print(f'      ({corr_info})')
            print()
