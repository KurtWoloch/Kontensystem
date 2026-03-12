"""Check which AutoDetect activity names have matching task codes."""
import json
import re
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Extract all unique AutoDetect activity names from rules
with open(os.path.join(BASE, "windowmon_summary.py"), "r", encoding="utf-8") as f:
    content = f.read()

# Find activity names in rule tuples
activities = set()
for m in re.finditer(r"""['"]([A-Z_]{2,})['"],\s*['"]([^'"]+)['"]\)""", content):
    acct, name = m.groups()
    if acct not in ('IDLE', '_PLANNER_OFFPC', '_WINLOGGER'):
        activities.add((acct, name))

# Load master task list codes
code_map = {}
with open(os.path.join(BASE, "data", "master_task_list_v4.jsonl"), "r", encoding="utf-8") as f:
    for line in f:
        task = json.loads(line.strip())
        if task.get("code"):
            code_map[task["name"].lower()] = (task["code"], task["name"])

# Check matches
print("AutoDetect-Aktivitäten und ihre Task-Code-Matches:")
print("=" * 80)
matched = 0
unmatched = 0
for acct, name in sorted(activities):
    name_lower = name.lower()
    match = code_map.get(name_lower)
    if match:
        print(f"  ✓ {acct:4s} {name:45s} → {match[0]} ({match[1]})")
        matched += 1
        continue
    # Try partial match
    found = None
    for task_name, (code, orig_name) in code_map.items():
        if name_lower in task_name or task_name in name_lower:
            found = f"{code} (partial: {orig_name})"
            break
    if found:
        print(f"  ≈ {acct:4s} {name:45s} → {found}")
        matched += 1
    else:
        print(f"  ✗ {acct:4s} {name:45s}   -- KEIN MATCH --")
        unmatched += 1

print(f"\n{matched} mit Match, {unmatched} ohne Match")
