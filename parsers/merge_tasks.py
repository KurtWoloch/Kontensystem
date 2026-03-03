"""Merge all task JSONL files into a unified master task list.

Strategy:
- Normalize whitespace/punctuation for matching, but preserve original names
- Exact match after normalization = same task, merge sources
- Group by prefix (before first parenthetical) for review, but DON'T auto-merge
- Tasks with different parenthetical qualifiers stay separate
- Track which sources each task appears in
- Assign best available code, priority, list, account
"""
import json
import os
import re
import unicodedata

DATA_DIR = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data"
OUTPUT_FILE = os.path.join(DATA_DIR, "master_task_list.jsonl")
STATS_FILE = os.path.join(DATA_DIR, "merge_stats.txt")

def normalize(name):
    """Normalize a task name for matching purposes.
    
    - Strip leading/trailing whitespace
    - Collapse multiple spaces to one
    - Normalize common punctuation variations (. vs no dot after Bearb)
    - Lowercase for comparison only
    """
    s = name.strip()
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s)
    # Remove spaces before/after parentheses and slashes for comparison
    s = re.sub(r'\s*\(\s*', ' (', s)
    s = re.sub(r'\s*\)\s*', ') ', s)
    s = re.sub(r'\s*\/\s*', ' / ', s)
    s = s.strip()
    return s

def normalize_key(name):
    """Create a matching key: normalized + lowercased."""
    return normalize(name).lower()

def extract_prefix(name):
    """Extract prefix before first parenthetical, for grouping."""
    m = re.match(r'^([^(]+)', name)
    if m:
        return m.group(1).strip()
    return name.strip()

def merge_all():
    # Load all JSONL files
    jsonl_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith('tasks_') and f.endswith('.jsonl')])
    
    print(f"Loading {len(jsonl_files)} source files...")
    
    # Master dict: normalized_key -> merged task record
    master = {}
    raw_count = 0
    
    for filename in jsonl_files:
        filepath = os.path.join(DATA_DIR, filename)
        file_count = 0
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                name = entry.get('name', '').strip()
                if not name:
                    continue
                
                raw_count += 1
                file_count += 1
                key = normalize_key(name)
                source = entry.get('source', filename)
                code = entry.get('code', '')
                priority = entry.get('priority', 0)
                acct = entry.get('account_prefix', '')
                status = entry.get('status', '')
                lst = entry.get('list', '')
                parent = entry.get('parent', '')
                notes = entry.get('notes', '')
                fixed_time = entry.get('fixed_time', '')
                
                if key not in master:
                    master[key] = {
                        'name': normalize(name),  # Use normalized but original-case version
                        'code': code,
                        'account_prefix': acct,
                        'parent': parent,
                        'list': lst,
                        'priority': priority if isinstance(priority, (int, float)) else 0,
                        'fixed_time': fixed_time,
                        'status': status,
                        'sources': [source],
                        'source_count': 1,
                        'notes': notes,
                        'prefix': extract_prefix(normalize(name))
                    }
                else:
                    rec = master[key]
                    # Merge: take best available info
                    if source not in rec['sources']:
                        rec['sources'].append(source)
                        rec['source_count'] += 1
                    if code and not rec['code']:
                        rec['code'] = code
                    if acct and not rec['account_prefix']:
                        rec['account_prefix'] = acct
                    if priority and (not rec['priority'] or priority > rec['priority']):
                        rec['priority'] = priority
                    if lst and not rec['list']:
                        rec['list'] = lst
                    if parent and not rec['parent']:
                        rec['parent'] = parent
                    if fixed_time and not rec['fixed_time']:
                        rec['fixed_time'] = fixed_time
                    # Status: prefer 'active' over anything else
                    if status == 'active':
                        rec['status'] = 'active'
                    elif not rec['status']:
                        rec['status'] = status
        
        print(f"  {filename}: {file_count} entries")
    
    print(f"\nRaw entries: {raw_count}")
    print(f"After dedup: {len(master)}")
    
    # Sort by prefix then name for readability
    sorted_tasks = sorted(master.values(), key=lambda t: (t['prefix'].lower(), t['name'].lower()))
    
    # Write master list
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for task in sorted_tasks:
            # Convert sources list to comma-separated string
            task['sources'] = ', '.join(task['sources'])
            f.write(json.dumps(task, ensure_ascii=False) + '\n')
    
    print(f"Master list: {len(sorted_tasks)} entries -> {OUTPUT_FILE}")
    
    # Generate stats
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Master Task List - Merge Statistics\n")
        f.write(f"{'='*50}\n\n")
        f.write(f"Raw entries across all sources: {raw_count}\n")
        f.write(f"After deduplication: {len(master)}\n")
        f.write(f"Dedup ratio: {raw_count/len(master):.1f}x\n\n")
        
        # Source coverage
        f.write(f"Source Coverage:\n")
        source_counts = {}
        for task in master.values():
            for s in (task['sources'] if isinstance(task['sources'], list) else task['sources'].split(', ')):
                source_counts[s] = source_counts.get(s, 0) + 1
        for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
            f.write(f"  {src}: {cnt} unique tasks\n")
        
        f.write(f"\nMulti-source tasks (appear in 3+ sources):\n")
        multi = [(t['name'], t['source_count'], t['sources']) 
                 for t in sorted_tasks if t['source_count'] >= 3]
        multi.sort(key=lambda x: -x[1])
        for name, cnt, sources in multi[:50]:
            f.write(f"  [{cnt}] {name}\n")
            f.write(f"       Sources: {sources}\n")
        if len(multi) > 50:
            f.write(f"  ... and {len(multi)-50} more\n")
        
        f.write(f"\nTotal multi-source tasks (3+): {len(multi)}\n")
        
        # Tasks with codes
        with_code = sum(1 for t in master.values() if t['code'])
        f.write(f"\nTasks with 6-char codes: {with_code}\n")
        without_code = len(master) - with_code
        f.write(f"Tasks without codes: {without_code}\n")
        
        # Prefix groups (families)
        prefixes = {}
        for task in sorted_tasks:
            p = task['prefix']
            if p not in prefixes:
                prefixes[p] = []
            prefixes[p].append(task['name'])
        
        large_families = [(p, names) for p, names in prefixes.items() if len(names) >= 3]
        large_families.sort(key=lambda x: -len(x[1]))
        f.write(f"\nLarge task families (3+ variants):\n")
        for prefix, names in large_families[:30]:
            f.write(f"\n  '{prefix}' ({len(names)} variants):\n")
            for n in names[:8]:
                f.write(f"    - {n}\n")
            if len(names) > 8:
                f.write(f"    ... and {len(names)-8} more\n")
    
    print(f"Stats: {STATS_FILE}")

if __name__ == '__main__':
    merge_all()
