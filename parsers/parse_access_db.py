"""Parse exported Access DB CSV files for unique activity/task names."""
import json
import os
import csv
import io

DATA_DIR = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data"
OUTPUT_FILE = os.path.join(DATA_DIR, "tasks_access_db.jsonl")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")

def read_csv(filename):
    """Read semicolon-delimited CSV, trying Windows-1252 then UTF-8."""
    path = os.path.join(DATA_DIR, filename)
    for enc in ['windows-1252', 'utf-8']:
        try:
            with open(path, 'r', encoding=enc) as f:
                reader = csv.DictReader(f, delimiter=';')
                return list(reader)
        except (UnicodeDecodeError, KeyError):
            continue
    return []

def parse_all():
    # 1. Parse Tab_Konten — account number → code/name mapping
    konten = {}
    for row in read_csv("access_Tab_Konten.csv"):
        nr = row.get('Kontennummer', '').strip()
        code = row.get('Kontenkürzel', '').strip()
        name = row.get('Kontenname', '').strip()
        if nr:
            konten[nr] = {'code': code, 'name': name}
    
    print(f"Tab_Konten: {len(konten)} accounts loaded")
    
    # Save accounts as reference
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(konten, f, ensure_ascii=False, indent=2)
    print(f"  -> saved to {ACCOUNTS_FILE}")

    tasks = {}  # (name, source_table) → task info, for dedup within each table
    
    # 2. Parse Tab_Aktionen — activity names with account numbers
    for row in read_csv("access_Tab_Aktionen.csv"):
        name = row.get('Aktionsname', '').strip()
        konto_nr = row.get('Durchführendes Konto', '').strip()
        acct = konten.get(konto_nr, {})
        if name:
            key = (name, 'Tab_Aktionen')
            if key not in tasks:
                tasks[key] = {
                    'name': name,
                    'code': '',
                    'account_prefix': acct.get('code', ''),
                    'account_name': acct.get('name', ''),
                    'source': 'access_Tab_Aktionen',
                    'status': 'active',
                    'notes': ''
                }
    
    aktionen_count = sum(1 for k in tasks if k[1] == 'Tab_Aktionen')
    print(f"Tab_Aktionen: {aktionen_count} unique activity names")

    # 3. Parse Tab_Aufwandserfassung — time entries with activity text
    for row in read_csv("access_Tab_Aufwandserfassung.csv"):
        name = row.get('Aktionstext', '').strip()
        konto_nr = row.get('Bedarfsträgerkonto', row.get('Bedarfsträgerkonto', '')).strip()
        acct = konten.get(konto_nr, {})
        if name:
            key = (name, 'Tab_Aufwandserfassung')
            if key not in tasks:
                tasks[key] = {
                    'name': name,
                    'code': '',
                    'account_prefix': acct.get('code', ''),
                    'account_name': acct.get('name', ''),
                    'source': 'access_Tab_Aufwandserfassung',
                    'status': 'active',
                    'notes': ''
                }
    
    ae_count = sum(1 for k in tasks if k[1] == 'Tab_Aufwandserfassung')
    print(f"Tab_Aufwandserfassung: {ae_count} unique activity names (from {18970} rows)")

    # 4. Parse Tab_Gewinnaktionen — profitable/planned activities
    for row in read_csv("access_Tab_Gewinnaktionen.csv"):
        name = row.get('AKtionsname', row.get('Aktionsname', '')).strip()
        acct_code = row.get('Kontokürzel', row.get('Kontokürzel', '')).strip()
        if name:
            key = (name, 'Tab_Gewinnaktionen')
            if key not in tasks:
                when = row.get('wann_moeglich', '').strip()
                can_offer = row.get('Angebot_moeglich', '').strip()
                tasks[key] = {
                    'name': name,
                    'code': '',
                    'account_prefix': acct_code,
                    'source': 'access_Tab_Gewinnaktionen',
                    'status': 'active',
                    'notes': f"when={when}, offerable={can_offer}" if when else ''
                }
    
    gw_count = sum(1 for k in tasks if k[1] == 'Tab_Gewinnaktionen')
    print(f"Tab_Gewinnaktionen: {gw_count} unique activities")

    # 5. Parse Tab_Wuensche — wishes/requests
    for row in read_csv("access_Tab_Wuensche.csv"):
        name = row.get('Gegenstand', '').strip()
        wisher = row.get('Name_Wuenscher', row.get('Name_Wünscher', '')).strip()
        status = row.get('Status', '').strip()
        if name:
            key = (name, 'Tab_Wuensche')
            if key not in tasks:
                tasks[key] = {
                    'name': name,
                    'code': '',
                    'account_prefix': '',
                    'source': 'access_Tab_Wuensche',
                    'status': 'needs_review' if status in ('', 'wartet') else 'retired',
                    'notes': f"wisher={wisher}, status={status}"
                }
    
    wu_count = sum(1 for k in tasks if k[1] == 'Tab_Wuensche')
    print(f"Tab_Wuensche: {wu_count} wishes/requests")

    # Write combined output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for task in tasks.values():
            f.write(json.dumps(task, ensure_ascii=False) + '\n')
    
    print(f"\nTotal: {len(tasks)} unique entries -> {OUTPUT_FILE}")

if __name__ == '__main__':
    parse_all()
