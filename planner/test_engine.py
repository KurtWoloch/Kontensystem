"""Deeper engine test — simulate a morning session."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from csv_parser import parse_csv, CSV_PATH
from day_context import DayContext
from engine import PlannerEngine
from models import RowType

raw = parse_csv(CSV_PATH)
print(f"All lists: {list(raw.keys())}")

print("\n=== Morning simulation (Tuesday / Teleworking) ===")
ctx = DayContext(1)  # Tuesday
eng = PlannerEngine(raw, ctx)

# Simulate 20 done/skip actions
for i in range(25):
    best = eng.get_best_candidate()
    if not best:
        print(f"  [{i:02d}] No candidate (waiting or done)")
        # Show wait status
        waits = eng.get_wait_status()
        for name, until in waits:
            print(f"       Wait: {name} until {until.strftime('%H:%M:%S')}")
        break
    ls, row = best
    action = "DONE" if i % 4 != 3 else "SKIP"
    print(f"  [{i:02d}] {action} [{ls.name}] {row.activity[:55]}")
    if action == "DONE":
        eng.mark_done(ls, row)
    else:
        eng.mark_skip(ls, row)

print(f"\nDone: {eng.items_done_today()}, Skipped: {eng.items_skipped_today()}")
print(f"Active lists: {[ls.name for ls in eng.get_active_lists()]}")

# Test log saving
path = eng.save_log()
print(f"Log saved: {path}")
