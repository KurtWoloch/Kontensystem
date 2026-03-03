"""Parse Window Logger VB5 combo box items and windowlog_corrector.py mappings."""
import re
import json
import os

VB5_FILE = r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Checklisten_Winlogger\Window logger.frm"
CORRECTOR_FILE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\windowlog_corrector.py"
OUTPUT_WL = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\tasks_window_logger.jsonl"
OUTPUT_WC = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\tasks_windowlog_corrector.jsonl"

def parse_vb5_combo_items():
    """Extract AddItem entries from Window Logger VB5 form."""
    tasks = []
    seen = set()
    
    with open(VB5_FILE, 'r', encoding='windows-1252', errors='replace') as f:
        for line in f:
            # Match .AddItem "XX - Description" (may be commented out with ')
            m = re.search(r'\.AddItem\s+"([^"]+)"', line)
            if m:
                full = m.group(1).strip()
                is_commented = line.strip().startswith("'")
                
                # Parse "XX - Description" format
                acct_match = re.match(r'^([A-Z]{2})\s*-\s*(.+)$', full)
                if acct_match:
                    acct = acct_match.group(1)
                    name = acct_match.group(2).strip()
                else:
                    acct = ''
                    name = full
                
                if name not in seen:
                    seen.add(name)
                    tasks.append({
                        'name': name,
                        'code': '',
                        'account_prefix': acct,
                        'parent': '',
                        'list': '',
                        'priority': 0,
                        'fixed_time': '',
                        'source': 'window_logger_vb5',
                        'status': 'retired' if is_commented else 'active',
                        'notes': f'combo box item, account={acct}'
                    })
    
    os.makedirs(os.path.dirname(OUTPUT_WL), exist_ok=True)
    with open(OUTPUT_WL, 'w', encoding='utf-8') as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')
    
    print(f"Window Logger VB5: {len(tasks)} combo box activities")
    return len(tasks)

def parse_corrector_mappings():
    """Extract activity mappings from windowlog_corrector.py."""
    tasks = []
    seen = set()
    
    with open(CORRECTOR_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract 'new_activity': 'Name' and 'new_account': 'XX' pairs
    # Also extract any "XX - Activity" patterns
    for m in re.finditer(r"'new_activity'\s*:\s*['\"]([^'\"]+)['\"]", content):
        name = m.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            tasks.append({
                'name': name,
                'code': '',
                'account_prefix': '',
                'parent': '',
                'list': '',
                'priority': 0,
                'fixed_time': '',
                'source': 'windowlog_corrector',
                'status': 'active',
                'notes': 'window-to-activity mapping rule'
            })
    
    os.makedirs(os.path.dirname(OUTPUT_WC), exist_ok=True)
    with open(OUTPUT_WC, 'w', encoding='utf-8') as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')
    
    print(f"Windowlog corrector: {len(tasks)} mapped activities")
    return len(tasks)

if __name__ == '__main__':
    parse_vb5_combo_items()
    parse_corrector_mappings()
