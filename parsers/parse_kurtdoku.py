"""Parse KURTDOKU.txt the way the VB5 Checklisten program does.

The VB5 program scans for lines matching:
  - "Checkliste bei <event>:" → event-triggered checklist
  - "Checkliste <name>:"     → named checklist (can be called as sub-checklist)

Then reads subsequent non-empty lines as items. Each item line starts with "- " 
(2 chars stripped via Mid(zeile, 3) in VB5). Empty line = end of checklist.

Special item types (handled by the VB5 runtime, we just extract them):
  - "Priorität=<n>"           → sets checklist priority
  - "Checkliste <name>"       → blocking sub-checklist call
  - "Start Checkliste <name>" → non-blocking sub-checklist spawn
  - "Wenn <cond>, <action>"   → conditional item
  - "Warten auf <time>"       → timer/wait item
"""

import json
import re
import os

SOURCE_PATH = r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Checklisten_Winlogger\KURTDOKU.txt"
OUTPUT_PATH = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\tasks_kurtdoku.jsonl"

def parse_kurtdoku():
    # Try encodings - the file is likely Windows-1252
    for enc in ['windows-1252', 'utf-8', 'latin-1']:
        try:
            with open(SOURCE_PATH, 'r', encoding=enc) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue
    
    checklists = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n').rstrip('\r')
        
        # Match "Checkliste ..." or "Checkliste bei ..." ending with ":"
        # But skip descriptive lines like "Checklisten zu 1.1.2 (Zahnarzt):"
        if re.match(r'^Checkliste\s+(bei\s+)?\S', line) and line.endswith(':'):
            checklist_name = line[:-1]  # strip trailing ':'
            
            # Determine type
            if 'bei ' in checklist_name and checklist_name.startswith('Checkliste bei '):
                cl_type = 'event'
            else:
                cl_type = 'named'
            
            # Read items until empty line or EOF
            items = []
            priority = None
            i += 1
            while i < len(lines):
                item_line = lines[i].rstrip('\n').rstrip('\r')
                if item_line == '':
                    break
                # Strip "- " prefix (VB5 does Mid(zeile, 3))
                if item_line.startswith('- '):
                    item_text = item_line[2:]
                else:
                    item_text = item_line
                
                # Check for priority setting
                if item_text.startswith('Priorität=') or item_text.startswith('Priorit\xe4t='):
                    try:
                        priority = float(item_text.split('=')[1].replace(',', '.'))
                    except ValueError:
                        pass
                else:
                    items.append(item_text)
                i += 1
            
            checklists.append({
                'cl_name': checklist_name,
                'cl_type': cl_type,
                'priority': priority,
                'cl_items': items
            })
        else:
            i += 1
    
    # Write JSONL output
    task_count = 0
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for cl in checklists:
            for item in cl['cl_items']:
                # Determine item type
                item_type = 'action'
                if item.startswith('Wenn '):
                    item_type = 'conditional'
                elif item.startswith('Warten auf '):
                    item_type = 'timer'
                elif item.startswith('Checkliste ') and not item.startswith('Checkliste bei '):
                    item_type = 'sub_checklist_blocking'
                elif item.startswith('Start Checkliste '):
                    item_type = 'sub_checklist_spawn'
                
                entry = {
                    'name': item,
                    'code': '',
                    'parent': cl['cl_name'],
                    'list': cl['cl_name'],
                    'priority': cl['priority'] if cl['priority'] else 0,
                    'fixed_time': '',
                    'source': 'kurtdoku',
                    'status': 'active',
                    'notes': f"type={cl['cl_type']}, item_type={item_type}"
                }
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                task_count += 1
    
    print(f"Found {len(checklists)} checklists with {task_count} total items")
    for cl in checklists:
        print(f"  {cl['cl_name']} (prio={cl['priority']}, {len(cl['cl_items'])} items)")

if __name__ == '__main__':
    parse_kurtdoku()
