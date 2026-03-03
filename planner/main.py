"""
main.py — Entry point for the reactive daily planner.

Usage:
  py planner/main.py

The tool:
  1. Shows a startup dialog to confirm day type (auto-detected).
  2. Parses Planungsaktivitaeten.csv with correct encoding.
  3. Initialises the reactive engine with Liste_Morgentoilette active.
  4. Opens the main planner window.
"""
import sys
import os
import tkinter as tk
from tkinter import messagebox

# Make sure we can import sibling modules regardless of cwd
sys.path.insert(0, os.path.dirname(__file__))

from csv_parser import parse_csv, CSV_PATH
from engine import PlannerEngine
from gui import PlannerGUI
from startup_dialog import show_startup_dialog
from day_context import DayContext


def main():
    # ── 1. Startup dialog ──────────────────────────────────────────────
    ctx = show_startup_dialog()
    if ctx is None:
        # User cancelled
        sys.exit(0)

    # ── 2. Parse CSV ───────────────────────────────────────────────────
    try:
        raw_lists = parse_csv(CSV_PATH)
    except FileNotFoundError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "CSV nicht gefunden",
            f"Planungsaktivitaeten.csv wurde nicht gefunden:\n{CSV_PATH}"
        )
        sys.exit(1)
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Fehler beim Lesen der CSV", str(exc))
        sys.exit(1)

    total_rows = sum(len(v) for v in raw_lists.values())
    print(
        f"[Planer] CSV geladen: {len(raw_lists)} Listen, "
        f"{total_rows} Zeilen. Tagestyp: {ctx.describe()}"
    )

    # ── 3. Initialise engine ──────────────────────────────────────────
    engine = PlannerEngine(raw_lists, ctx)

    active = engine.get_active_lists()
    print(f"[Planer] Aktive Listen beim Start: {[ls.name for ls in active]}")
    best = engine.get_best_candidate()
    if best:
        ls, row = best
        print(f"[Planer] Erste Aufgabe: {row.activity!r} ({ls.name})")

    # ── 4. Main window ────────────────────────────────────────────────
    root = tk.Tk()
    root.configure(bg="#1e1e2e")

    # Set a reasonable initial size and let user resize
    root.geometry("920x580")
    root.minsize(640, 460)

    # Handle close: save log before exit
    def on_close():
        try:
            path = engine.save_log()
            print(f"[Planer] Log gespeichert: {path}")
        except Exception as e:
            print(f"[Planer] Warnung: Log konnte nicht gespeichert werden: {e}")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    PlannerGUI(root, engine)
    root.mainloop()


if __name__ == "__main__":
    main()
