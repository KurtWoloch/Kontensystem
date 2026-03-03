"""
gui.py — tkinter GUI for the reactive planner.

Layout:
  ┌─────────────────────────────────────────────┐
  │  CLOCK               Day-type info           │
  ├──────────────────────────┬──────────────────┤
  │                          │  QUEUE            │
  │  CURRENT TASK (large)    │  (upcoming items) │
  │  list • priority • mins  │                   │
  │                          │                   │
  ├──────────────────────────┴──────────────────┤
  │  [✓ Done]   [⏭ Skip]   [⏸ Pause]           │
  ├─────────────────────────────────────────────┤
  │  STATUS BAR: items done, active lists, waits │
  └─────────────────────────────────────────────┘
"""
import tkinter as tk
from tkinter import ttk, font, messagebox
from datetime import datetime
from typing import Optional, Tuple

from models import CsvRow, ListState
from engine import PlannerEngine


REFRESH_MS = 15_000   # refresh display every 15 seconds
TICK_MS = 10_000      # engine tick every 10 seconds (check Wait timers)

COLOR_BG = "#1e1e2e"
COLOR_FG = "#cdd6f4"
COLOR_ACCENT = "#89b4fa"
COLOR_DONE = "#a6e3a1"
COLOR_SKIP = "#f38ba8"
COLOR_PAUSE = "#fab387"
COLOR_WAIT = "#f9e2af"
COLOR_PANEL = "#181825"
COLOR_LIST = "#313244"
COLOR_HEADER = "#89dceb"
COLOR_BTN = "#45475a"


class PlannerGUI:

    def __init__(self, root: tk.Tk, engine: PlannerEngine):
        self.root = root
        self.engine = engine
        self._current: Optional[Tuple[ListState, CsvRow]] = None

        self._build_ui()
        self._tick()
        self._refresh()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        self.root.title("Tagesplanung — Reaktiver Planer")
        self.root.configure(bg=COLOR_BG)
        self.root.minsize(640, 480)
        self.root.geometry("900x580")

        # ── Top bar: clock + day info ──────────────────────────────────
        top_bar = tk.Frame(self.root, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=10, pady=(8, 0))

        self.lbl_clock = tk.Label(
            top_bar, text="00:00", font=("Consolas", 28, "bold"),
            bg=COLOR_BG, fg=COLOR_ACCENT
        )
        self.lbl_clock.pack(side=tk.LEFT)

        self.lbl_daytype = tk.Label(
            top_bar, text="", font=("Segoe UI", 10),
            bg=COLOR_BG, fg=COLOR_FG
        )
        self.lbl_daytype.pack(side=tk.RIGHT, pady=8)
        self.lbl_daytype.config(text=self.engine.ctx.describe())

        # ── Main area: current task + queue ───────────────────────────
        main_frame = tk.Frame(self.root, bg=COLOR_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        # Left: current task panel
        task_panel = tk.Frame(main_frame, bg=COLOR_PANEL, relief=tk.FLAT, bd=1)
        task_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.lbl_task_name = tk.Label(
            task_panel, text="—", font=("Segoe UI", 16, "bold"),
            bg=COLOR_PANEL, fg=COLOR_FG, wraplength=480,
            justify=tk.LEFT, anchor="nw", padx=14, pady=10
        )
        self.lbl_task_name.pack(fill=tk.BOTH, expand=True)

        meta_row = tk.Frame(task_panel, bg=COLOR_PANEL)
        meta_row.pack(fill=tk.X, padx=14, pady=(0, 8))

        self.lbl_list_name = tk.Label(
            meta_row, text="", font=("Segoe UI", 10),
            bg=COLOR_PANEL, fg=COLOR_HEADER
        )
        self.lbl_list_name.pack(side=tk.LEFT)

        self.lbl_meta = tk.Label(
            meta_row, text="", font=("Segoe UI", 10),
            bg=COLOR_PANEL, fg=COLOR_FG
        )
        self.lbl_meta.pack(side=tk.LEFT, padx=(12, 0))

        self.lbl_start_time = tk.Label(
            meta_row, text="", font=("Segoe UI", 10),
            bg=COLOR_PANEL, fg=COLOR_WAIT
        )
        self.lbl_start_time.pack(side=tk.RIGHT, padx=(0, 4))

        # Right: queue panel
        queue_panel = tk.Frame(main_frame, bg=COLOR_PANEL, relief=tk.FLAT, bd=1)
        queue_panel.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        tk.Label(
            queue_panel, text="Warteschlange", font=("Segoe UI", 9, "bold"),
            bg=COLOR_PANEL, fg=COLOR_HEADER, anchor="w", padx=8, pady=4
        ).pack(fill=tk.X)

        self.queue_listbox = tk.Listbox(
            queue_panel, bg=COLOR_LIST, fg=COLOR_FG,
            font=("Consolas", 9), selectbackground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, activestyle="none",
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(queue_panel, orient=tk.VERTICAL,
                                  command=self.queue_listbox.yview)
        self.queue_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.queue_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ── Button row ────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, padx=10, pady=6)

        btn_cfg = dict(font=("Segoe UI", 12, "bold"), relief=tk.FLAT,
                       bd=0, padx=20, pady=8, cursor="hand2")

        self.btn_done = tk.Button(
            btn_frame, text="✓  Erledigt", bg=COLOR_DONE, fg="#1e1e2e",
            command=self._on_done, **btn_cfg
        )
        self.btn_done.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_skip = tk.Button(
            btn_frame, text="⏭  Überspringen", bg=COLOR_SKIP, fg="#1e1e2e",
            command=self._on_skip, **btn_cfg
        )
        self.btn_skip.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_adhoc = tk.Button(
            btn_frame, text="📝  Ungeplant", bg=COLOR_PAUSE, fg="#1e1e2e",
            command=self._on_adhoc, **btn_cfg
        )
        self.btn_adhoc.pack(side=tk.LEFT)

        self.btn_save = tk.Button(
            btn_frame, text="💾  Log speichern", bg=COLOR_LIST, fg=COLOR_FG,
            command=self._on_save_log, **btn_cfg
        )
        self.btn_save.pack(side=tk.RIGHT)

        # ── Status bar ────────────────────────────────────────────────
        self.status_bar = tk.Label(
            self.root, text="", font=("Segoe UI", 9),
            bg=COLOR_PANEL, fg=COLOR_FG, anchor="w", padx=8, pady=3
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------ #
    #  Timer callbacks                                                     #
    # ------------------------------------------------------------------ #

    def _tick(self):
        """Engine tick — unblocks waiting lists."""
        self.engine.tick()
        self.root.after(TICK_MS, self._tick)

    def _refresh(self):
        """Redraw the UI with current engine state."""
        self._update_clock()
        self._update_current()
        self._update_queue()
        self._update_status()
        self.root.after(REFRESH_MS, self._refresh)

    # ------------------------------------------------------------------ #
    #  Display updaters                                                    #
    # ------------------------------------------------------------------ #

    def _update_clock(self):
        now = datetime.now()
        self.lbl_clock.config(text=now.strftime("%H:%M"))

    def _update_current(self):
        best = self.engine.get_best_candidate()
        self._current = best

        if best is None:
            # Check if there are waiting lists
            waits = self.engine.get_wait_status()
            if waits:
                name, until = waits[0]
                remaining = int((until - datetime.now()).total_seconds() / 60) + 1
                self.lbl_task_name.config(
                    text=f"⏳ Warte … ({name})", fg=COLOR_WAIT
                )
                self.lbl_list_name.config(text=f"noch ca. {remaining} Min.")
                self.lbl_meta.config(text="")
            elif not self.engine.get_active_lists():
                self.lbl_task_name.config(text="Keine aktiven Listen.", fg=COLOR_FG)
                self.lbl_list_name.config(text="")
                self.lbl_meta.config(text="")
            else:
                self.lbl_task_name.config(text="Alle Listen erledigt ✓", fg=COLOR_DONE)
                self.lbl_list_name.config(text="")
                self.lbl_meta.config(text="")
            self.lbl_start_time.config(text="")
            return

        ls, row = best
        # Strip 6-char task code at end for display
        display_name = _strip_task_code(row.activity)

        self.lbl_task_name.config(text=display_name, fg=COLOR_FG)
        self.lbl_list_name.config(text=ls.name)
        self.lbl_meta.config(
            text=f"Prio {row.priority:.3f}  •  {row.minutes} Min."
        )
        if row.starting_time:
            self.lbl_start_time.config(
                text=f"⏰ ab {row.starting_time.strftime('%H:%M')}"
            )
        else:
            self.lbl_start_time.config(text="")

    def _update_queue(self):
        self.queue_listbox.delete(0, tk.END)
        candidates = self.engine.get_all_candidates()

        # Also show waiting lists
        waits = {name: until for name, until in self.engine.get_wait_status()}

        for ls, row in candidates:
            tag = "  ⏰" if row.starting_time else ""
            entry = (
                f"[{ls.name[:18]:<18}] "
                f"{_strip_task_code(row.activity)[:35]:<35}"
                f"  {row.minutes:>3}' p{row.priority:.2f}{tag}"
            )
            self.queue_listbox.insert(tk.END, entry)

        if waits:
            self.queue_listbox.insert(tk.END, "")
            self.queue_listbox.insert(tk.END, "── Wartend ──")
            for name, until in waits.items():
                remaining = int((until - datetime.now()).total_seconds() / 60) + 1
                self.queue_listbox.insert(
                    tk.END, f"  {name}: noch ~{remaining} Min."
                )

    def _update_status(self):
        done = self.engine.items_done_today()
        skipped = self.engine.items_skipped_today()
        active = len(self.engine.get_active_lists())
        waits = len(self.engine.get_wait_status())
        self.status_bar.config(
            text=(
                f"  Erledigt: {done}  |  Übersprungen: {skipped}  "
                f"|  Aktive Listen: {active}  |  Wartend: {waits}"
            )
        )

    # ------------------------------------------------------------------ #
    #  Button handlers                                                     #
    # ------------------------------------------------------------------ #

    def _on_done(self):
        self.engine.tick()
        best = self.engine.get_best_candidate()
        if best:
            ls, row = best
            self._show_done_dialog(ls, row)

    def _on_skip(self):
        self.engine.tick()
        best = self.engine.get_best_candidate()
        if best:
            ls, row = best
            self.engine.mark_skip(ls, row)
            self._refresh()

    def _on_adhoc(self):
        """Log an unplanned activity without advancing the current item."""
        self._show_adhoc_dialog()

    def _show_adhoc_dialog(self):
        """Log an unplanned activity without advancing the current item."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Ungeplante Aktivität erfassen")
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        # Activity text
        tk.Label(
            dlg, text="Bezeichnung:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(10, 2))

        txt_var = tk.StringVar(value="")
        txt_entry = tk.Entry(
            dlg, textvariable=txt_var, font=("Segoe UI", 11),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=60
        )
        txt_entry.pack(padx=12, pady=(0, 8))
        txt_entry.focus_set()

        now = datetime.now()
        last_end = self.engine.last_completed_at()
        default_start = last_end if last_end else now

        # ── Start time row ────────────────────────────────────────────
        start_frame = tk.Frame(dlg, bg=COLOR_BG)
        start_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

        tk.Label(
            start_frame, text="Begonnen um:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        start_h_var = tk.StringVar(value=f"{default_start.hour:02d}")
        start_m_var = tk.StringVar(value=f"{default_start.minute:02d}")

        tk.Spinbox(
            start_frame, from_=0, to=23, width=3, format="%02.0f",
            textvariable=start_h_var, font=("Consolas", 11),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(
            start_frame, text=":", font=("Consolas", 11),
            bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        tk.Spinbox(
            start_frame, from_=0, to=59, width=3, format="%02.0f",
            textvariable=start_m_var, font=("Consolas", 11),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
        ).pack(side=tk.LEFT)

        tk.Label(
            start_frame, text="(Vorgabe: Ende vorh. Aufgabe)",
            font=("Segoe UI", 8, "italic"), bg=COLOR_BG, fg="#6c7086"
        ).pack(side=tk.LEFT, padx=(10, 0))

        # ── End time row ──────────────────────────────────────────────
        end_frame = tk.Frame(dlg, bg=COLOR_BG)
        end_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(
            end_frame, text="Erledigt um:  ",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        end_h_var = tk.StringVar(value=f"{now.hour:02d}")
        end_m_var = tk.StringVar(value=f"{now.minute:02d}")

        tk.Spinbox(
            end_frame, from_=0, to=23, width=3, format="%02.0f",
            textvariable=end_h_var, font=("Consolas", 11),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(
            end_frame, text=":", font=("Consolas", 11),
            bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        tk.Spinbox(
            end_frame, from_=0, to=59, width=3, format="%02.0f",
            textvariable=end_m_var, font=("Consolas", 11),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
        ).pack(side=tk.LEFT)

        tk.Label(
            end_frame, text="(Vorgabe: jetzt)",
            font=("Segoe UI", 8, "italic"), bg=COLOR_BG, fg="#6c7086"
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Validation message
        lbl_error = tk.Label(
            dlg, text="", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BG, fg=COLOR_SKIP
        )
        lbl_error.pack(padx=12)

        # Buttons
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=(4, 12))

        def on_confirm():
            activity = txt_var.get().strip()
            if not activity:
                lbl_error.config(text="⚠ Bezeichnung darf nicht leer sein!")
                return

            try:
                sh = int(start_h_var.get())
                sm = int(start_m_var.get())
                start_time = now.replace(hour=sh, minute=sm,
                                         second=0, microsecond=0)
            except ValueError:
                start_time = default_start

            try:
                eh = int(end_h_var.get())
                em = int(end_m_var.get())
                end_time = now.replace(hour=eh, minute=em,
                                       second=0, microsecond=0)
            except ValueError:
                end_time = now

            if end_time < start_time:
                lbl_error.config(
                    text="⚠ Ende darf nicht vor dem Beginn liegen!")
                return

            dlg.destroy()
            self.engine.log_adhoc(activity, start_time, end_time)
            self._refresh()

        def on_cancel():
            dlg.destroy()

        tk.Button(
            btn_frame, text="  ✓ Erfassen  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_DONE, fg="#1e1e2e", relief=tk.FLAT,
            cursor="hand2", command=on_confirm
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="  Abbrechen  ",
            font=("Segoe UI", 11),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            cursor="hand2", command=on_cancel
        ).pack(side=tk.LEFT, padx=4)

        dlg.bind("<Return>", lambda e: on_confirm())
        dlg.bind("<Escape>", lambda e: on_cancel())

        # Center on parent
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def _on_save_log(self):
        path = self.engine.save_log()
        messagebox.showinfo("Log gespeichert", f"Log gespeichert:\n{path}")


    def _show_done_dialog(self, ls: ListState, row: CsvRow):
        """Show a dialog to edit text, set start time and completion time."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Aufgabe erledigt")
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        # Activity text (editable)
        tk.Label(
            dlg, text="Bezeichnung (bearbeiten falls nötig):",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(10, 2))

        txt_var = tk.StringVar(value=row.activity)
        txt_entry = tk.Entry(
            dlg, textvariable=txt_var, font=("Segoe UI", 11),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=60
        )
        txt_entry.pack(padx=12, pady=(0, 8))
        txt_entry.select_range(0, tk.END)
        txt_entry.focus_set()

        now = datetime.now()

        # Default start time = last item's end time, or now
        last_end = self.engine.last_completed_at()
        default_start = last_end if last_end else now

        # ── Start time row ────────────────────────────────────────────
        start_frame = tk.Frame(dlg, bg=COLOR_BG)
        start_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

        tk.Label(
            start_frame, text="Begonnen um:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        start_h_var = tk.StringVar(value=f"{default_start.hour:02d}")
        start_m_var = tk.StringVar(value=f"{default_start.minute:02d}")

        tk.Spinbox(
            start_frame, from_=0, to=23, width=3, format="%02.0f",
            textvariable=start_h_var, font=("Consolas", 11),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(
            start_frame, text=":", font=("Consolas", 11),
            bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        tk.Spinbox(
            start_frame, from_=0, to=59, width=3, format="%02.0f",
            textvariable=start_m_var, font=("Consolas", 11),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
        ).pack(side=tk.LEFT)

        tk.Label(
            start_frame, text=f"(Vorgabe: Ende vorh. Aufgabe)",
            font=("Segoe UI", 8, "italic"), bg=COLOR_BG, fg="#6c7086"
        ).pack(side=tk.LEFT, padx=(10, 0))

        # ── End time row ──────────────────────────────────────────────
        end_frame = tk.Frame(dlg, bg=COLOR_BG)
        end_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(
            end_frame, text="Erledigt um:  ",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        end_h_var = tk.StringVar(value=f"{now.hour:02d}")
        end_m_var = tk.StringVar(value=f"{now.minute:02d}")

        tk.Spinbox(
            end_frame, from_=0, to=23, width=3, format="%02.0f",
            textvariable=end_h_var, font=("Consolas", 11),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(
            end_frame, text=":", font=("Consolas", 11),
            bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        tk.Spinbox(
            end_frame, from_=0, to=59, width=3, format="%02.0f",
            textvariable=end_m_var, font=("Consolas", 11),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
        ).pack(side=tk.LEFT)

        tk.Label(
            end_frame, text="(Vorgabe: jetzt)",
            font=("Segoe UI", 8, "italic"), bg=COLOR_BG, fg="#6c7086"
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Validation message label
        lbl_error = tk.Label(
            dlg, text="", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BG, fg=COLOR_SKIP
        )
        lbl_error.pack(padx=12)

        # Buttons
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=(4, 12))

        def on_confirm():
            try:
                sh = int(start_h_var.get())
                sm = int(start_m_var.get())
                start_time = now.replace(hour=sh, minute=sm,
                                         second=0, microsecond=0)
            except ValueError:
                start_time = default_start

            try:
                eh = int(end_h_var.get())
                em = int(end_m_var.get())
                done_time = now.replace(hour=eh, minute=em,
                                        second=0, microsecond=0)
            except ValueError:
                done_time = now

            # Validate: end must be >= start
            if done_time < start_time:
                lbl_error.config(
                    text="⚠ Ende darf nicht vor dem Beginn liegen!")
                return

            edited_text = txt_var.get().strip()
            custom_text = edited_text if edited_text != row.activity else None

            dlg.destroy()
            self.engine.mark_done(ls, row, custom_time=done_time,
                                  custom_text=custom_text,
                                  start_time=start_time)
            self._refresh()

        def on_cancel():
            dlg.destroy()  # don't mark anything

        tk.Button(
            btn_frame, text="  ✓ Bestätigen  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_DONE, fg="#1e1e2e", relief=tk.FLAT,
            cursor="hand2", command=on_confirm
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="  Abbrechen  ",
            font=("Segoe UI", 11),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            cursor="hand2", command=on_cancel
        ).pack(side=tk.LEFT, padx=4)

        # Enter key confirms
        dlg.bind("<Return>", lambda e: on_confirm())
        dlg.bind("<Escape>", lambda e: on_cancel())

        # Center on parent
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")


# ------------------------------------------------------------------ #
#  Utilities                                                           #
# ------------------------------------------------------------------ #

def _strip_task_code(name: str) -> str:
    """Remove trailing 6-char task code if present (e.g. ' LEMTAU')."""
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and len(parts[1]) == 6 and parts[1].isupper():
        return parts[0]
    return name
