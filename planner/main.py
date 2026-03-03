"""
main.py — Entry point for the reactive planner.
"""
import tkinter as tk
import sys
import os
from datetime import datetime

from startup_dialog import show_startup_dialog
from day_context import DayContext
from engine import PlannerEngine
from gui import PlannerGUI
from csv_parser import parse_csv

ENGINE_DIR = os.path.dirname(__file__)


def main():
    # --- 1. Setup Context ---
    ctx = show_startup_dialog()
    if not ctx:
        sys.exit(0)

    # --- 2. Load CSV and Initialize Engine ---
    raw_lists = parse_csv()
    engine = PlannerEngine(raw_lists, ctx)

    # --- 3. Load today's log to restore state ---
    today_log = os.path.join(ENGINE_DIR, "..", "logs",
                             f"planner-log-{datetime.now().strftime('%Y-%m-%d')}.json")
    done, skipped = engine.load_log(today_log)
    if done or skipped:
        print(f"[Planer] Restored from log: {done} done, {skipped} skipped.")

    active = [ls.name for ls in engine.get_active_lists()]
    print(f"[Planer] Active lists: {active}")

    best = engine.get_best_candidate()
    if best:
        print(f"[Planer] Next task: '{best[1].activity}' ({best[0].name})")

    # --- 4. Start GUI ---
    # Note: Log is saved manually via the "Save Log" button.
    # Closing the window does NOT auto-save to prevent data loss.
    root = tk.Tk()
    app = PlannerGUI(root, engine)
    root.mainloop()


if __name__ == "__main__":
    main()
