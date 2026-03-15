"""Debug code suggestions for various inputs."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'planner'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from code_suggest import CodeSuggestor

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
cs = CodeSuggestor(DATA_DIR)

# Check what's registered for "ansehen youtube-videos"
norm = cs._normalize("Ansehen YouTube-Videos")
print(f"Normalized: '{norm}'")
print(f"In _name_to_code: {cs._name_to_code.get(norm, 'NOT FOUND')}")
print(f"Code RAYTYT in _code_names: {cs._code_names.get('RAYTYT', 'NOT FOUND')}")
print(f"Code RWMPAR in _code_names: {cs._code_names.get('RWMPAR', 'NOT FOUND')}")
print()

# Count RAYTYT entries in learned_codes
import json
learned_raytyt = 0
with open(os.path.join(DATA_DIR, 'learned_codes.csv'), 'r', encoding='utf-8') as f:
    for line in f:
        if line.startswith('RAYTYT;'):
            learned_raytyt += 1
print(f"RAYTYT entries in learned_codes.csv: {learned_raytyt}")
print()

# Trace suggestions for each input stage
inputs = ["An", "Ans", "Ansehen Y", "Ansehen Youtube", "Ansehen Youtube-Videos"]
for text in inputs:
    results = cs.suggest(text)
    print(f"Input: '{text}'")
    for code, match_type, name in results[:3]:
        print(f"  [{match_type:8}] {code} — {name[:60]}")
    if not results:
        print(f"  (no suggestions)")
    print()

# Check: what does MTL say about "Ansehen YouTube-Videos"?
print("=== MTL entries with 'ansehen' in name ===")
mtl_path = os.path.join(DATA_DIR, 'master_task_list_v4.jsonl')
with open(mtl_path, 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line.strip())
        if 'ansehen' in t['name'].lower() and t.get('code'):
            print(f"  {t['code']} — {t['name']}")
