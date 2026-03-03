"""Parse schedule_exceptions.yaml for unique event/task names not in CSV."""
import json
import os
import sys

# PyYAML may not be installed, handle gracefully
try:
    import yaml
except ImportError:
    print("PyYAML not available, parsing manually", file=sys.stderr)
    yaml = None

INPUT_FILE = r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\schedule_exceptions.yaml"
OUTPUT_FILE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data\tasks_yaml.jsonl"

def parse_yaml():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    unique_events = {}  # name -> {date, startTime, duration, priority}
    
    exceptions = data.get('exceptions', [])
    for exc in exceptions:
        date = exc.get('date', '')
        # Extract from addEvents
        for event in exc.get('addEvents', []):
            name = event.get('name', '').strip()
            if name and name not in unique_events:
                unique_events[name] = {
                    'date': date,
                    'startTime': event.get('startTime', ''),
                    'duration': event.get('durationMinutes', ''),
                    'priority': event.get('priority', '')
                }
        # Extract from removeActivities (these reference existing tasks)
        for act in exc.get('removeActivities', []):
            act = act.strip()
            if act and act not in unique_events:
                unique_events[act] = {
                    'date': date,
                    'notes': 'removed_activity'
                }
    
    count = 0
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        for name, info in sorted(unique_events.items()):
            entry = {
                'name': name,
                'code': '',
                'source': 'yaml_exceptions',
                'status': 'needs_review',
                'notes': f"first seen {info.get('date','')}, " + 
                         (f"removed" if info.get('notes') == 'removed_activity' 
                          else f"start={info.get('startTime','')}, dur={info.get('duration','')}min, prio={info.get('priority','')}")
            }
            out.write(json.dumps(entry, ensure_ascii=False) + '\n')
            count += 1
    
    print(f"Parsed {count} unique events from YAML exceptions")
    return count

if __name__ == '__main__':
    parse_yaml()
