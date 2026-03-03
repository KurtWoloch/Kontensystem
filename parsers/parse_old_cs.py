"""Parse Tagesplanung_Global_Old.cs for hardcoded task definitions.

Extracts Planungsaktivitaet_hinzufuegen() calls, including commented-out ones.
"""
import re
import json
import os

INPUT_FILE = r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Tagesplanung\Tagesplanung_Global_Old.cs"
OUTPUT_FILE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\tasks_old_cs.jsonl"

# Map constant names to readable list names
LIST_MAP = {
    'Liste_Morgentoilette': 'Liste_Morgentoilette',
    'Liste_untertags': 'Liste_untertags',
    'Liste_mittags': 'Liste_mittags',
    'Liste_nachmittags': 'Liste_nachmittags',
    'Liste_Abendzeremonie': 'Liste_Abendzeremonie',
}

# Extract 6-char code from end of task name (pattern: space + 6 uppercase/digit chars at end)
CODE_RE = re.compile(r'\s([A-Z][A-Z0-9]{5})\s*$')

def parse_old_cs():
    for enc in ['utf-8-sig', 'utf-8', 'windows-1252']:
        try:
            with open(INPUT_FILE, 'r', encoding=enc) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue

    tasks = {}  # (name, code) -> task_data, for dedup
    
    for line in lines:
        stripped = line.strip()
        
        # Check if commented out
        is_retired = stripped.startswith('//')
        if is_retired:
            stripped = stripped.lstrip('/').strip()
        
        # Match the function call - flexible pattern
        if 'Planungsaktivitaet_hinzufuegen' not in stripped:
            continue
        
        # Extract the string argument (task name) - first quoted string
        name_match = re.search(r'"([^"]+)"', stripped)
        if not name_match:
            continue
        full_name = name_match.group(1)
        
        # Extract duration - first number after the name string
        after_name = stripped[name_match.end():]
        dur_match = re.search(r',\s*(\d+)', after_name)
        duration = int(dur_match.group(1)) if dur_match else 0
        
        # Extract list constant
        list_name = ''
        for const_name, readable in LIST_MAP.items():
            if const_name in after_name:
                list_name = readable
                break
        
        # Extract priority if explicitly passed (look for decimal number like 1.81)
        prio_match = re.search(r',\s*([\d]+\.[\d]+)\s*\)', after_name)
        priority = float(prio_match.group(1)) if prio_match else 0
        
        # Extract time string if present (like "7:30" or "10:41")
        time_match = re.search(r'"(\d{1,2}:\d{2})"', after_name)
        fixed_time = time_match.group(1) if time_match else ''
        
        # Extract 6-char code from name
        code_match = CODE_RE.search(full_name)
        code = code_match.group(1) if code_match else ''
        
        # Clean name (remove trailing code)
        clean_name = full_name
        if code:
            clean_name = full_name[:full_name.rfind(code)].strip()
        
        key = (clean_name, code)
        if key not in tasks:
            tasks[key] = {
                'name': clean_name,
                'code': code,
                'parent': '',
                'list': list_name,
                'priority': priority,
                'fixed_time': fixed_time,
                'source': 'old_cs',
                'status': 'retired' if is_retired else 'active',
                'notes': f'duration={duration}min'
            }
        else:
            # Update: if we have a non-retired version, prefer it
            if not is_retired and tasks[key]['status'] == 'retired':
                tasks[key]['status'] = 'active'
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for task in tasks.values():
            f.write(json.dumps(task, ensure_ascii=False) + '\n')
    
    active = sum(1 for t in tasks.values() if t['status'] == 'active')
    retired = sum(1 for t in tasks.values() if t['status'] == 'retired')
    print(f"Parsed {len(tasks)} unique tasks ({active} active, {retired} retired) from old C# code")

if __name__ == '__main__':
    parse_old_cs()
