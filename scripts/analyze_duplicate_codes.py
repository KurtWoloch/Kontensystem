"""Analyze duplicate task codes in MTL and learned_codes."""
import json, os
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# === Load MTL ===
mtl = []
with open(os.path.join(BASE, 'data', 'master_task_list_v4.jsonl'), 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line.strip())
        mtl.append(t)

# === Load learned_codes ===
learned = []  # list of (code, name) — preserving all entries
with open(os.path.join(BASE, 'data', 'learned_codes.csv'), 'r', encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split(';', 1)
        if len(parts) == 2 and len(parts[0]) == 6 and parts[0].isupper():
            learned.append((parts[0], parts[1]))

# === Part 1: Codes used by multiple DIFFERENT task names in MTL ===
mtl_code_to_names = defaultdict(set)
for t in mtl:
    code = t.get('code', '')
    name = t.get('name', '')
    if code and name:
        mtl_code_to_names[code].add(name)

mtl_multi = {code: names for code, names in mtl_code_to_names.items() if len(names) > 1}

print("=" * 90)
print(f"PART 1: CODES WITH MULTIPLE TASK NAMES IN MTL  ({len(mtl_multi)} codes)")
print("=" * 90)
for code in sorted(mtl_multi.keys()):
    names = sorted(mtl_multi[code])
    print(f"\n  {code} ({len(names)} names):")
    for name in names:
        print(f"    - {name}")

# === Part 2: Same for learned_codes ===
learned_code_to_names = defaultdict(set)
for code, name in learned:
    learned_code_to_names[code].add(name)

learned_multi = {code: names for code, names in learned_code_to_names.items() if len(names) > 1}

print(f"\n\n{'=' * 90}")
print(f"PART 2: CODES WITH MULTIPLE NAMES IN LEARNED_CODES  ({len(learned_multi)} codes)")
print("=" * 90)
for code in sorted(learned_multi.keys()):
    names = sorted(learned_multi[code])
    print(f"\n  {code} ({len(names)} names):")
    for name in names:
        print(f"    - {name}")

# === Part 3: Task names that appear with MULTIPLE DIFFERENT codes in MTL ===
# Normalize names for comparison
from collections import Counter
import re

def norm(s):
    return re.sub(r'\s+', ' ', s.lower().strip())

mtl_name_to_codes = defaultdict(set)
for t in mtl:
    code = t.get('code', '')
    name = t.get('name', '')
    if code and name:
        mtl_name_to_codes[norm(name)].add(code)

name_multi_codes = {name: codes for name, codes in mtl_name_to_codes.items() if len(codes) > 1}

print(f"\n\n{'=' * 90}")
print(f"PART 3: TASK NAMES WITH MULTIPLE CODES IN MTL  ({len(name_multi_codes)} names)")
print("=" * 90)
for name in sorted(name_multi_codes.keys()):
    codes = sorted(name_multi_codes[name])
    # Find original-cased name
    for t in mtl:
        if norm(t.get('name', '')) == name:
            orig_name = t['name']
            break
    print(f"\n  \"{orig_name}\" -> {', '.join(codes)}")

# === Part 4: Cross-reference — names from Part 1 that also appear in Part 3 ===
print(f"\n\n{'=' * 90}")
print(f"PART 4: SUMMARY STATISTICS")
print("=" * 90)
print(f"  Total MTL tasks: {len(mtl)}")
print(f"  Tasks with codes: {sum(1 for t in mtl if t.get('code'))}")
print(f"  Unique codes in MTL: {len(mtl_code_to_names)}")
print(f"  Codes with multiple names (MTL): {len(mtl_multi)}")
print(f"  Names with multiple codes (MTL): {len(name_multi_codes)}")
print(f"  Unique codes in learned_codes: {len(learned_code_to_names)}")
print(f"  Codes with multiple names (learned): {len(learned_multi)}")
print(f"  Total learned entries: {len(learned)}")

# Top offenders by name count
print(f"\n  Top 10 most-overloaded codes (MTL):")
for code, names in sorted(mtl_multi.items(), key=lambda x: -len(x[1]))[:10]:
    print(f"    {code}: {len(names)} different names")
