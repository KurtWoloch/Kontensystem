"""Verify that all AutoDetect codes exist in MTL or learned_codes."""
import json, re, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load MTL codes
mtl_codes = {}
with open(os.path.join(BASE, 'data', 'master_task_list_v4.jsonl'), 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line.strip())
        if t.get('code'):
            mtl_codes[t['code']] = t['name']

# Load learned codes (last entry per code wins)
learned = {}
with open(os.path.join(BASE, 'data', 'learned_codes.csv'), 'r', encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split(';', 1)
        if len(parts) == 2 and len(parts[0]) == 6:
            learned[parts[0]] = parts[1]

# Extract activities from AutoDetect rules
with open(os.path.join(BASE, 'planner', 'windowmon_summary.py'), 'r', encoding='utf-8') as f:
    src = f.read()

activities = set()
for m in re.finditer(r'''["']([A-Z_]{2,})["'],\s*["'](.+?)["']\s*\)''', src):
    account = m.group(1)
    activity = m.group(2)
    if account.startswith('_') or not activity:
        continue
    activities.add((account, activity))

print(f"MTL: {len(mtl_codes)} codes | Learned: {len(learned)} entries")
print(f"AutoDetect rules: {len(activities)} unique activities\n")

ok_count = 0
warn_count = 0
nocode_count = 0

for account, activity in sorted(activities, key=lambda x: x[1]):
    code_match = re.search(r'\s([A-Z]{6})$', activity)
    code = code_match.group(1) if code_match else ''

    if not code:
        print(f"  [--] [{account:4}] {activity}  (no code)")
        nocode_count += 1
        continue

    in_mtl = code in mtl_codes
    in_learned = code in learned

    if in_mtl:
        print(f"  [ok] [{account:4}] {activity}")
        print(f"         MTL: {mtl_codes[code][:55]}")
        ok_count += 1
    elif in_learned:
        print(f"  [lr] [{account:4}] {activity}")
        print(f"         Learned: {learned[code][:55]}")
        ok_count += 1
    else:
        print(f"  [!!] [{account:4}] {activity}  << CODE NOT FOUND")
        warn_count += 1

print(f"\nSummary: {ok_count} with known code, {nocode_count} without code, {warn_count} unknown codes")
