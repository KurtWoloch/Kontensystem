"""
main.py — Entry point for the reactive planner.
"""
import json
import tkinter as tk
import sys
import os
from datetime import datetime
from typing import Optional

from startup_dialog import show_startup_dialog
from day_context import DayContext
from engine import PlannerEngine
from gui import PlannerGUI
from csv_parser import parse_csv

ENGINE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(ENGINE_DIR, "..", "logs")


def _earliest_start_from_log(log_path: str) -> 'Optional[datetime]':
    """
    Read a planner log JSON and return the earliest started_at time.
    Returns None if the log doesn't exist or has no entries.
    """
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not log_data:
        return None

    earliest = None
    today = datetime.now().date()
    for entry in log_data:
        raw = entry.get("started_at", "")
        try:
            t = datetime.strptime(raw, "%H:%M:%S")
            # Anchor to today; skip after-midnight times (< 05:00)
            # as they belong to the tail end of the previous day
            if t.hour < 5:
                continue
            dt = t.replace(year=today.year, month=today.month, day=today.day)
            if earliest is None or dt < earliest:
                earliest = dt
        except ValueError:
            continue
    return earliest


def save_initial_projection(engine: PlannerEngine):
    """
    Snapshot the day's ideal projection before any work is done.

    This captures what the engine *would* schedule if every item took
    exactly its planned duration and nothing unplanned happened —
    the equivalent of the old Planung file.  Saved once per day;
    if the file already exists (restart), it is not overwritten.

    On restart (log already exists but no projection), uses the
    earliest logged start time so the projection reflects the real
    start of the day, not the restart time.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    day_str = engine.session_date.strftime("%Y-%m-%d")
    path = os.path.join(LOG_DIR, f"projection-{day_str}.json")

    if os.path.exists(path):
        print(f"[Planer] Projection already saved: {path}")
        return path

    # Check if a log already exists — if so, derive start time from it
    log_path = os.path.join(LOG_DIR, f"planner-log-{day_str}.json")
    start_time = _earliest_start_from_log(log_path)
    if start_time:
        print(f"[Planer] Log exists — projecting from earliest logged "
              f"start: {start_time.strftime('%H:%M')}")

    projection = engine.get_day_projection(start_time=start_time)
    data = []
    for item in projection:
        est_start = item.get('est_start')
        est_end = item.get('est_end')
        data.append({
            "activity": item['activity'],
            "list_name": item['list_name'],
            "minutes": item['minutes'],
            "priority": item['priority'],
            "fixed_time": (item['fixed_time'].strftime('%H:%M')
                           if item.get('fixed_time') else None),
            "est_start": (est_start.strftime('%H:%M')
                          if est_start else None),
            "est_end": (est_end.strftime('%H:%M')
                        if est_end else None),
            "state": item['state'],
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[Planer] Initial projection saved: {path} "
          f"({len(data)} items)")
    return path


def main():
    # --- 1. Setup Context ---
    startup_result = show_startup_dialog()
    if not startup_result:
        sys.exit(0)
    ctx, yaml_overrides = startup_result

    # --- 2. Load CSV and Initialize Engine ---
    raw_lists = parse_csv()
    early_hours = yaml_overrides.get("earlyWorkStart")
    engine = PlannerEngine(raw_lists, ctx, session_date=datetime.now(),
                           early_work_hours=early_hours,
                           yaml_overrides=yaml_overrides)

    # --- 3. Save initial projection (before loading log) ---
    save_initial_projection(engine)

    # --- 4. Load today's log to restore state ---
    today_log = os.path.join(LOG_DIR,
                             f"planner-log-{engine.session_date.strftime('%Y-%m-%d')}.json")
    done, skipped = engine.load_log(today_log)
    if done or skipped:
        print(f"[Planer] Restored from log: {done} done, {skipped} skipped.")

    active = [ls.name for ls in engine.get_active_lists()]
    print(f"[Planer] Active lists: {active}")

    best = engine.get_best_candidate()
    if best:
        print(f"[Planer] Next task: '{best[1].activity}' ({best[0].name})")

    # --- 5. Start GUI ---
    # Note: Log is saved manually via the "Save Log" button.
    # Closing the window does NOT auto-save to prevent data loss.
    root = tk.Tk()
    app = PlannerGUI(root, engine)
    root.mainloop()


if __name__ == "__main__":
    main()
