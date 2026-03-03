"""Parse all Ablauf files for unique activity names.

Two line formats:
1. Planned: "HH:MM -> HH:MM Activity Name CODE (Dauer: X', Prio: Y)"
   or just: "HH:MM Activity Name CODE (Dauer: X', Prio: Y)"
2. Unplanned: "*HH:MM Activity Name"

We extract unique activity names from both, marking planned vs unplanned.
"""
import json
import os
import re
import glob

ABLAUF_DIR = r"C:\Users\kurt_\Betrieb\Kontenverwaltung"
OUTPUT_FILE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\tasks_ablauf.jsonl"

# Match planned line: optional "HH:MM -> " prefix, then "HH:MM Activity (Dauer...)"
PLANNED_RE = re.compile(
    r'^(?:\d{1,2}:\d{2}\s*->\s*)?(\d{1,2}:\d{2})\s+(.+?)\s*\(Dauer:.*$'
)

# Match unplanned line: "*HH:MM Activity"
UNPLANNED_RE = re.compile(
    r'^\*(\d{1,2}:\d{2})\s+(.+)$'
)

# Extract 6-char code from end of activity name
CODE_RE = re.compile(r'\s([A-Z][A-Z0-9]{5})\s*$')

def clean_activity_name(name):
    """Remove trailing code and clean up."""
    name = name.strip()
    # Remove trailing (Dauer...) if present
    name = re.sub(r'\s*\(Dauer:.*$', '', name)
    return name

def parse_all_ablauf():
    files = glob.glob(os.path.join(ABLAUF_DIR, "Ablauf *.txt"))
    print(f"Found {len(files)} Ablauf files")
    
    planned_activities = {}   # name -> {code, count}
    unplanned_activities = {} # name -> count
    
    files_parsed = 0
    lines_total = 0
    
    for filepath in files:
        # Try encodings
        content = None
        for enc in ['utf-8-sig', 'utf-8', 'windows-1252', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            continue
        
        files_parsed += 1
        
        for line in content:
            line = line.rstrip('\n').rstrip('\r')
            lines_total += 1
            
            # Try unplanned first (starts with *)
            m = UNPLANNED_RE.match(line)
            if m:
                name = clean_activity_name(m.group(2))
                if name:
                    unplanned_activities[name] = unplanned_activities.get(name, 0) + 1
                continue
            
            # Try planned
            m = PLANNED_RE.match(line)
            if m:
                name = clean_activity_name(m.group(2))
                if name:
                    code_m = CODE_RE.search(name)
                    code = code_m.group(1) if code_m else ''
                    if code:
                        name_clean = name[:name.rfind(code)].strip()
                    else:
                        name_clean = name
                    
                    if name_clean not in planned_activities:
                        planned_activities[name_clean] = {'code': code, 'count': 0}
                    planned_activities[name_clean]['count'] += 1
                continue
    
    print(f"Parsed {files_parsed} files, {lines_total} lines")
    print(f"Planned activities: {len(planned_activities)} unique")
    print(f"Unplanned activities: {len(unplanned_activities)} unique")
    
    # Write output
    count = 0
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # Planned activities
        for name, info in sorted(planned_activities.items()):
            entry = {
                'name': name,
                'code': info['code'],
                'source': 'ablauf_planned',
                'status': 'active',
                'notes': f"seen {info['count']}x across Ablauf files"
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            count += 1
        
        # Unplanned activities
        for name, cnt in sorted(unplanned_activities.items()):
            # Check if it already exists as planned (skip if so)
            if name in planned_activities:
                continue
            entry = {
                'name': name,
                'code': '',
                'source': 'ablauf_unplanned',
                'status': 'active',
                'notes': f"unplanned, seen {cnt}x across Ablauf files"
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            count += 1
    
    print(f"\nTotal: {count} unique entries -> {OUTPUT_FILE}")

if __name__ == '__main__':
    parse_all_ablauf()
