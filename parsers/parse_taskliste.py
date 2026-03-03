import json
import re
import os
import sys

# --- Configuration ---
INPUT_FILE = r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Taskliste.txt"
OUTPUT_FILE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\tasks_taskliste.jsonl"
ENCODING = "windows-1252"

# Define categories based on headers (must be lowercase for comparison)
CATEGORIES = {
    "normalerweise periodische tätigkeiten": "periodic_normal",
    "kurzfristig": "kurzfristig",
    "mittelfristig": "mittelfristig",
    "offene dokumentationen": "offene_dokumentationen",
    "aus liste offener punkte": "offene_punkte",
    "aus ideenliste": "ideenliste",
    "aus wunschliste": "wunschliste",
    "aus planung": "planung",
    "laufende tätigkeiten": "laufende_taetigkeiten",
    "überfällige termine": "ueberfaellige_termine",
    "termine": "termine",
}

# Regex to find task line: XX - Task description (optional date in "Termine" section)
# Captures: 1: Account Prefix (2 letters), 2: Description, 3: Date (YYYY-MM-DD) if found
TASK_LINE_PATTERN = re.compile(r"^([A-Z]{2})\s*-\s*(.*?)(?:\s*\(([\d]{4}-[\d]{2}-[\d]{2})\))?$")

def parse_taskliste():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file not found at {INPUT_FILE}", file=sys.stderr)
        return 0

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    tasks = []
    current_category_key = "uncategorized"
    
    try:
        # Use 'ignore' error handling for Windows-1252 to skip unmappable characters if any
        with open(INPUT_FILE, 'r', encoding=ENCODING, errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {INPUT_FILE}: {e}", file=sys.stderr)
        return 0

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Check for category header
        found_category = False
        for header, key in CATEGORIES.items():
            if line.lower().startswith(header):
                current_category_key = key
                found_category = True
                break
        
        if found_category:
            continue

        # Attempt to match task line
        match = TASK_LINE_PATTERN.match(line)
        if match:
            account_prefix, description, date = match.groups()
            
            task_name = description.strip()
            account_code = "" # Per prompt example
            
            task_data = {
                "name": task_name,
                "code": account_code,
                "account_prefix": account_prefix,
                "category": current_category_key,
                "source": "taskliste",
                "status": "needs_review",
                "date": date if date else "",
                "notes": ""
            }
            tasks.append(task_data)
            
    count = len(tasks)
    
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
            for task in tasks:
                out_f.write(json.dumps(task) + '\n')
    except Exception as e:
        print(f"Error writing to {OUTPUT_FILE}: {e}", file=sys.stderr)
        return 0
            
    print(f"Script 1 Complete. Parsed {count} tasks from Taskliste.txt into {OUTPUT_FILE}")
    return count

if __name__ == "__main__":
    result = parse_taskliste()
    # Exit with a unique code or just print the summary required for the main agent
    print(f"TASKLISTE_COUNT:{result}")