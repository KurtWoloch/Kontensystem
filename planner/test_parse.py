"""Quick parse test — run from kontensystem/ directory."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from csv_parser import parse_csv, CSV_PATH
from day_context import DayContext
from engine import PlannerEngine

print("=== CSV Parsing ===")
raw = parse_csv(CSV_PATH)
print(f"Lists found: {len(raw)}")
for name, rows in list(raw.items())[:12]:
    print(f"  {name}: {len(rows)} rows")

print("\n=== Day Context ===")
ctx_tue = DayContext(1)
print(f"Tuesday: {ctx_tue.describe()}")
ctx_mon = DayContext(0)
print(f"Monday:  {ctx_mon.describe()}")
ctx_sat = DayContext(5)
print(f"Saturday: {ctx_sat.describe()}")

print("\n=== Weekday matching (Tuesday) ===")
for wd in ["Teleworking", "nicht Wochenende", "Montag, Dienstag", "Wochenende", "Bürotag", "Putztag", ""]:
    print(f"  {wd!r:30} -> {ctx_tue.matches_weekdays(wd)}")

print("\n=== Dependency eval (Tuesday) ===")
for dep in ["Planungsvariablen.Teleworking", "!Planungsvariablen.BRZ_geplant", "Planungsvariablen.BRZ_geplant", ""]:
    print(f"  {dep!r:45} -> {ctx_tue.eval_dependency(dep)}")

print("\n=== Engine (Tuesday) ===")
eng = PlannerEngine(raw, ctx_tue)
active = eng.get_active_lists()
print(f"Active lists: {[ls.name for ls in active]}")
best = eng.get_best_candidate()
if best:
    ls, row = best
    print(f"Best candidate: {row.activity!r} ({ls.name}, p={row.priority})")

cands = eng.get_all_candidates()
print(f"All candidates: {len(cands)}")
for ls, row in cands[:10]:
    print(f"  [{ls.name}] {row.activity[:50]} p={row.priority}")
