"""Export duplicate codes as CSV for manual review."""
import json, os, csv
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load MTL
mtl_code_to_names = defaultdict(list)
with open(os.path.join(BASE, 'data', 'master_task_list_v4.jsonl'), 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line.strip())
        code = t.get('code', '')
        name = t.get('name', '')
        if code and name:
            mtl_code_to_names[code].append(('MTL', name))

# Load learned_codes (deduplicate per code+name)
learned_seen = set()
with open(os.path.join(BASE, 'data', 'learned_codes.csv'), 'r', encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split(';', 1)
        if len(parts) == 2 and len(parts[0]) == 6 and parts[0].isupper():
            code, name = parts[0], parts[1]
            key = (code, name)
            if key not in learned_seen:
                learned_seen.add(key)
                mtl_code_to_names[code].append(('Learned', name))

# Filter to codes with multiple distinct names
multi = {}
for code, entries in mtl_code_to_names.items():
    names = set(name for _, name in entries)
    if len(names) > 1:
        multi[code] = entries

# Write CSV
out_path = os.path.join(BASE, 'data', 'duplicate_codes_review.csv')
with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow(['Code', 'Quelle', 'Aktivitätsname', 'Vorschlag_Code', 'Kommentar'])
    
    for code in sorted(multi.keys()):
        entries = multi[code]
        # Deduplicate and sort: MTL first, then Learned, alphabetical within
        seen = set()
        sorted_entries = []
        for source, name in sorted(entries, key=lambda x: (0 if x[0] == 'MTL' else 1, x[1])):
            if name not in seen:
                seen.add(name)
                sorted_entries.append((source, name))
        
        for source, name in sorted_entries:
            writer.writerow([code, source, name, '', ''])
        # Empty separator row between codes
        writer.writerow(['', '', '', '', ''])

print(f"Exportiert: {out_path}")
print(f"  {len(multi)} Codes mit {sum(len(set(n for _, n in e)) for e in multi.values())} Aktivitätsvarianten")
