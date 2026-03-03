import csv
import json
import os
import re
from collections import defaultdict

# --- Configuration ---
# Note: Using raw strings (r"...") for Windows paths
CSV_PATH = r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Planungsaktivitaeten.csv"
JSONL_PATH = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\tasks_csv.jsonl"
SCRIPT_PATH = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\parsers\parse_csv.py"
CONTROL_PREFIXES = ("Wait", "Start list", "Stop list", "Restart list", "Wait until top of hour")
ENCODING = 'cp1252' # Windows-1252 is common for German legacy files

# --- Setup Directories ---
os.makedirs(os.path.dirname(SCRIPT_PATH), exist_ok=True)
os.makedirs(os.path.dirname(JSONL_PATH), exist_ok=True)

def extract_name_and_code(activity_str):
    # Regex to find a 6-character alphanumeric code at the end, possibly preceded by space(s)
    match = re.search(r'\s+([A-Z0-9]{6})\s*$', activity_str.strip())
    code = None
    name = activity_str.strip()
    
    if match:
        code = match.group(1)
        # Remove the code and any preceding space from the name
        name = activity_str[:match.start()].strip()
    
    return name, code

def parse_and_deduplicate():
    # Key is (name, code). Value is the collected data dictionary + variant count.
    tasks_map = {}
    control_skipped_count = 0
    total_rows_processed = 0

    try:
        with open(CSV_PATH, mode='r', encoding=ENCODING, newline='') as csvfile:
            # Assuming semicolon delimiter based on description
            reader = csv.reader(csvfile, delimiter=';')
            
            # Skip header row
            try:
                header = next(reader)
            except StopIteration:
                print("Error: CSV file is empty or header is missing.")
                return 0

            for row in reader:
                total_rows_processed += 1
                if not row:
                    continue

                # Row mapping based on header: Activity;Minutes;List;Priority;Weekdays;Starting time;Dependencies;Preceding_Activity
                # We expect at least 7 fields based on the header structure provided.
                if len(row) < 7: 
                    continue
                    
                activity_raw = row[0].strip()

                # 1. Skip control flow rows
                if activity_raw.startswith(CONTROL_PREFIXES):
                    control_skipped_count += 1
                    continue

                # 2. Extract name and code
                name, code = extract_name_and_code(activity_raw)
                
                # 3. Extract other fields
                list_name = row[2].strip() if len(row) > 2 else ""
                priority_raw = row[3].strip() if len(row) > 3 else "0"
                weekdays = row[4].strip() if len(row) > 4 else ""
                starting_time = row[5].strip() if len(row) > 5 else ""
                dependencies = row[6].strip() if len(row) > 6 else ""

                # 4. Transform priority (comma -> dot)
                try:
                    priority = float(priority_raw.replace(',', '.'))
                except ValueError:
                    priority = 0.0 # Default if conversion fails

                key = (name, code if code else "") # Use empty string for code if none found
                
                if key not in tasks_map:
                    # First time seeing this (name, code) pair
                    tasks_map[key] = {
                        "name": name,
                        "code": code if code else "",
                        "list": list_name,
                        "priority": priority,
                        "fixed_time": starting_time,
                        "weekdays": weekdays,
                        "dependencies": dependencies,
                        "source": "csv",
                        "status": "active",
                        "variants": 1
                    }
                else:
                    # Deduplication: Increment variants count
                    tasks_map[key]["variants"] += 1
                    # Note: If priority/time differs, this keeps the first one encountered, 
                    # which satisfies "keep one entry" while tracking frequency via variants.
                    
    except FileNotFoundError:
        print(f"Error: Source CSV file not found at {CSV_PATH}")
        return -1
    except Exception as e:
        print(f"An error occurred during parsing: {e}")
        return -2

    # --- Write JSONL Output ---
    try:
        with open(JSONL_PATH, 'w', encoding='utf-8') as jsonl_file:
            for task_data in tasks_map.values():
                # Ensure 'code' is present, even if None in map key
                if 'code' not in task_data:
                    task_data['code'] = ""
                jsonl_file.write(json.dumps(task_data) + '\\n')
        
        unique_count = len(tasks_map)
        print(f"Successfully wrote {{unique_count}} unique tasks to {{JSONL_PATH}}")
        print(f"Total control flow rows skipped: {{control_skipped_count}}")
        print(f"Total rows processed (including header/skipped): {{total_rows_processed}}")
        print(f"FINAL_UNIQUE_COUNT: {{unique_count}}")
        return unique_count
        
    except Exception as e:
        print(f"An error occurred during JSONL writing: {{e}}")
        return -3

if __name__ == "__main__":
    parse_and_deduplicate()
