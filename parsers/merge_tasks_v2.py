"""Merge v2: Collapse Ablauf and Aufwandserfassung annotation variants to base tasks.

Strategy:
- For ablauf_planned, ablauf_unplanned, access_Tab_Aufwandserfassung, access_Tab_Aktionen:
  Strip parenthetical annotations to get base task name, merge variants under it.
  Track variant count for reference.
- For csv, old_cs, kurtdoku: Keep parenthetical qualifiers as-is (intentional planning distinctions)
- For taskliste, window_logger_vb5, yaml_exceptions, windowlog_corrector, 
  access_Tab_Gewinnaktionen, access_Tab_Wuensche: Keep as-is
- Special handling: "AE / Abr. <date>", "Aufwandserfassung <date>", "Abrechnung <date>" 
  → collapse to "Aufwandserfassung / Abrechnung"
"""
import json
import os
import re

DATA_DIR = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data"
OUTPUT_FILE = os.path.join(DATA_DIR, "master_task_list_v2.jsonl")
STATS_FILE = os.path.join(DATA_DIR, "merge_stats_v2.txt")
ANNOTATIONS_FILE = os.path.join(DATA_DIR, "annotation_index.jsonl")

# Sources where parenthetical content is annotation (collapse it)
COLLAPSE_SOURCES = {
    'ablauf_planned', 'ablauf_unplanned', 
    'access_Tab_Aufwandserfassung', 'access_Tab_Aktionen'
}

# Sources where parenthetical content is intentional (keep it)
KEEP_SOURCES = {
    'csv', 'old_cs', 'kurtdoku',
    'taskliste', 'window_logger_vb5', 'yaml_exceptions', 'windowlog_corrector',
    'access_Tab_Gewinnaktionen', 'access_Tab_Wuensche'
}

# Patterns for AE/Abrechnung date variants
AE_ABR_PATTERNS = [
    re.compile(r'^AE\s*/\s*Abr\.\s+\d', re.IGNORECASE),
    re.compile(r'^Aufwandserfassung\s+\d', re.IGNORECASE),
    re.compile(r'^Abrechnung\s+\d', re.IGNORECASE),
    re.compile(r'^AE\s+\d', re.IGNORECASE),
]

CODE_RE = re.compile(r'\s([A-Z][A-Z0-9]{5})\s*$')

def strip_parenthetical(name):
    """Remove parenthetical annotation from task name.
    
    'Bearb. Essensplan (Bauerngugelhupf + Chai Tee)' -> 'Bearb. Essensplan'
    'Ansehen Youtube-Videos (some video title)' -> 'Ansehen Youtube-Videos'
    
    But be careful with names that ARE parenthetical:
    'Bearb. Essensplan (gegessen, zu essen)' in CSV should NOT be stripped.
    That's handled by only stripping for COLLAPSE_SOURCES.
    """
    # Find first opening paren
    idx = name.find('(')
    if idx > 0:
        base = name[:idx].strip()
        if base:  # Don't return empty string
            return base
    return name.strip()

def is_ae_abr(name):
    """Check if this is an AE/Abrechnung date variant."""
    for pat in AE_ABR_PATTERNS:
        if pat.match(name):
            return True
    return False

def normalize(name):
    """Basic normalization: collapse whitespace, trim."""
    s = name.strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def normalize_key(name):
    return normalize(name).lower()

def extract_code(name):
    """Extract 6-char code from end of name."""
    m = CODE_RE.search(name)
    return m.group(1) if m else ''

def strip_code(name):
    """Remove trailing 6-char code from name."""
    code = extract_code(name)
    if code:
        return name[:name.rfind(code)].strip()
    return name

def extract_prefix(name):
    """Extract prefix before first parenthetical."""
    m = re.match(r'^([^(]+)', name)
    return m.group(1).strip() if m else name.strip()

def merge_all():
    jsonl_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith('tasks_') and f.endswith('.jsonl')])
    
    print(f"Loading {len(jsonl_files)} source files...")
    
    master = {}  # normalized_key -> task record
    annotations = []  # full annotation variants for reference
    raw_count = 0
    collapsed_count = 0
    
    for filename in jsonl_files:
        filepath = os.path.join(DATA_DIR, filename)
        file_count = 0
        file_collapsed = 0
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                name = normalize(entry.get('name', ''))
                if not name:
                    continue
                
                raw_count += 1
                file_count += 1
                source = entry.get('source', filename.replace('tasks_', '').replace('.jsonl', ''))
                code = entry.get('code', '')
                priority = entry.get('priority', 0)
                acct = entry.get('account_prefix', '')
                status = entry.get('status', '')
                lst = entry.get('list', '')
                parent = entry.get('parent', '')
                notes = entry.get('notes', '')
                fixed_time = entry.get('fixed_time', '')
                
                # Decide whether to collapse
                display_name = name
                was_collapsed = False
                
                if source in COLLAPSE_SOURCES:
                    # Special: AE/Abrechnung date variants
                    if is_ae_abr(name):
                        display_name = "Aufwandserfassung / Abrechnung"
                        was_collapsed = True
                    else:
                        stripped = strip_parenthetical(name)
                        if stripped != name:
                            # Save annotation variant
                            annotations.append({
                                'base_task': stripped,
                                'full_name': name,
                                'source': source
                            })
                            display_name = stripped
                            was_collapsed = True
                
                if was_collapsed:
                    file_collapsed += 1
                    collapsed_count += 1
                
                # Strip code from display name for cleaner matching
                code_from_name = extract_code(display_name)
                if code_from_name:
                    if not code:
                        code = code_from_name
                    display_name = strip_code(display_name)
                
                key = normalize_key(display_name)
                
                if key not in master:
                    master[key] = {
                        'name': display_name,
                        'code': code,
                        'account_prefix': acct,
                        'parent': parent,
                        'list': lst,
                        'priority': priority if isinstance(priority, (int, float)) else 0,
                        'fixed_time': fixed_time,
                        'status': status,
                        'sources': [source],
                        'source_count': 1,
                        'variant_count': 1 if was_collapsed else 0,
                        'notes': notes if not was_collapsed else '',
                        'prefix': extract_prefix(display_name)
                    }
                else:
                    rec = master[key]
                    if source not in rec['sources']:
                        rec['sources'].append(source)
                        rec['source_count'] += 1
                    if was_collapsed:
                        rec['variant_count'] = rec.get('variant_count', 0) + 1
                    if code and not rec['code']:
                        rec['code'] = code
                    if acct and not rec['account_prefix']:
                        rec['account_prefix'] = acct
                    if priority and isinstance(priority, (int, float)) and (not rec['priority'] or priority > rec['priority']):
                        rec['priority'] = priority
                    if lst and not rec['list']:
                        rec['list'] = lst
                    if parent and not rec['parent']:
                        rec['parent'] = parent
                    if fixed_time and not rec['fixed_time']:
                        rec['fixed_time'] = fixed_time
                    if status == 'active':
                        rec['status'] = 'active'
                    elif not rec['status']:
                        rec['status'] = status
        
        print(f"  {filename}: {file_count} entries ({file_collapsed} collapsed)")
    
    print(f"\nRaw: {raw_count}, Collapsed annotations: {collapsed_count}")
    print(f"Master list: {len(master)} unique base tasks")
    
    # Sort by prefix then name
    sorted_tasks = sorted(master.values(), key=lambda t: (t['prefix'].lower(), t['name'].lower()))
    
    # Write master list
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for task in sorted_tasks:
            task['sources'] = ', '.join(task['sources'])
            f.write(json.dumps(task, ensure_ascii=False) + '\n')
    
    # Write annotation index
    with open(ANNOTATIONS_FILE, 'w', encoding='utf-8') as f:
        for ann in sorted(annotations, key=lambda a: (a['base_task'].lower(), a['full_name'].lower())):
            f.write(json.dumps(ann, ensure_ascii=False) + '\n')
    
    print(f"Master list: {OUTPUT_FILE}")
    print(f"Annotation index: {len(annotations)} variants -> {ANNOTATIONS_FILE}")
    
    # Stats
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        f.write("Master Task List v2 - Merge Statistics\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Raw entries: {raw_count}\n")
        f.write(f"Annotation variants collapsed: {collapsed_count}\n")
        f.write(f"Final unique base tasks: {len(master)}\n")
        f.write(f"Compression ratio: {raw_count/len(master):.1f}x\n\n")
        
        # Tasks with most variants (interesting for activity mapping later)
        f.write("Top tasks by annotation variant count:\n")
        by_variants = sorted(master.values(), key=lambda t: -t.get('variant_count', 0))
        for t in by_variants[:30]:
            vc = t.get('variant_count', 0)
            if vc < 2:
                break
            f.write(f"  [{vc:4d} variants] {t['name']}\n")
        
        f.write(f"\nSource coverage:\n")
        source_counts = {}
        for task in master.values():
            for s in (task['sources'] if isinstance(task['sources'], list) else task['sources'].split(', ')):
                source_counts[s] = source_counts.get(s, 0) + 1
        for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
            f.write(f"  {src}: {cnt}\n")
        
        f.write(f"\nWith 6-char code: {sum(1 for t in master.values() if t['code'])}\n")
        f.write(f"Without code: {sum(1 for t in master.values() if not t['code'])}\n")
        
        # Multi-source tasks
        multi = [t for t in sorted_tasks if t['source_count'] >= 3]
        f.write(f"\nMulti-source tasks (3+): {len(multi)}\n")
        for t in sorted(multi, key=lambda x: -x['source_count'])[:30]:
            f.write(f"  [{t['source_count']}] {t['name']} ({t['sources']})\n")

if __name__ == '__main__':
    merge_all()
