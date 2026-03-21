"""Debug classification for a specific time range."""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "planner"))
from windowmon_summary import load_windowmon, classify_entry, build_activity_blocks

entries = load_windowmon("2026-03-15")
# Filter 10:15 - 11:35
filtered = [e for e in entries if e["_ts"] >= datetime(2026,3,15,10,15) and e["_ts"] <= datetime(2026,3,15,11,35)]

print("=== RAW CLASSIFICATION (entry by entry) ===")
print(f"{'TIME':>8}  {'ACCOUNT':6} {'ACTIVITY':50} {'PROCESS':20} {'TITLE'}")
print("-" * 130)
for e in filtered:
    if e.get("type"):
        print(f"{e['_ts'].strftime('%H:%M:%S'):>8}  {'---':6} {'[' + e['type'] + ']':50}")
        continue
    account, activity = classify_entry(e)
    ts = e["_ts"].strftime("%H:%M:%S")
    proc = e.get("process", "")[:20]
    title = e.get("title", "")[:60]
    print(f"{ts:>8}  {account:6} {activity:50} {proc:20} {title}")

print("\n\n=== ACTIVITY BLOCKS (after build_activity_blocks) ===")
# Only non-marker entries
window_entries = [e for e in filtered if not e.get("type")]
blocks = build_activity_blocks(filtered)

for b in blocks:
    start = b["start"].strftime("%H:%M:%S")
    end = b["end"].strftime("%H:%M:%S")
    dur = b.get("duration_s", 0) / 60
    print(f"  {start} - {end}  ({dur:5.1f}m)  [{b['account']:6}] {b['activity']}")
