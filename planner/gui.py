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
import os
import tkinter as tk
from tkinter import ttk, font, messagebox
from datetime import datetime
from typing import Optional, Tuple

from models import CsvRow, ListState
from engine import PlannerEngine
from code_suggest import CodeSuggestor


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
        # Maps queue listbox index → projection item dict (for click-to-log)
        self._queue_index_map: dict = {}

        # Code suggestion engine
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        self._code_suggestor = CodeSuggestor(data_dir)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
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

        # ── Current task panel (compact, full width) ─────────────────
        task_panel = tk.Frame(self.root, bg=COLOR_PANEL, relief=tk.FLAT, bd=1)
        task_panel.pack(fill=tk.X, padx=10, pady=(6, 0))

        self.lbl_task_name = tk.Label(
            task_panel, text="—", font=("Segoe UI", 16, "bold"),
            bg=COLOR_PANEL, fg=COLOR_FG, wraplength=860,
            justify=tk.LEFT, anchor="w"
        )
        self.lbl_task_name.pack(fill=tk.X, padx=14, pady=(8, 2))

        meta_row = tk.Frame(task_panel, bg=COLOR_PANEL)
        meta_row.pack(fill=tk.X, padx=14, pady=(0, 6))

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

        # ── Queue panel (full width, below current task) ──────────────
        queue_panel = tk.Frame(self.root, bg=COLOR_PANEL, relief=tk.FLAT, bd=1)
        queue_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 6))

        tk.Label(
            queue_panel, text="Tagesplan", font=("Segoe UI", 9, "bold"),
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

        # Double-click on queue item → log it directly
        self.queue_listbox.bind("<Double-1>", self._on_queue_double_click)
        # Right-click on queue item → skip it
        self.queue_listbox.bind("<Button-3>", self._on_queue_right_click)

        # ── Button rows ───────────────────────────────────────────────
        btn_frame_top = tk.Frame(self.root, bg=COLOR_BG)
        btn_frame_top.pack(fill=tk.X, padx=10, pady=(6, 2))

        btn_cfg = dict(font=("Segoe UI", 11, "bold"), relief=tk.FLAT,
                       bd=0, padx=14, pady=6, cursor="hand2")

        self.btn_done = tk.Button(
            btn_frame_top, text="✓ Erledigt", bg=COLOR_DONE, fg="#1e1e2e",
            command=self._on_done, **btn_cfg
        )
        self.btn_done.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_skip = tk.Button(
            btn_frame_top, text="⏭ Überspringen", bg=COLOR_SKIP, fg="#1e1e2e",
            command=self._on_skip, **btn_cfg
        )
        self.btn_skip.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_interrupt = tk.Button(
            btn_frame_top, text="⏸ Unterbrechen", bg=COLOR_WAIT, fg="#1e1e2e",
            command=self._on_interrupt, **btn_cfg
        )
        self.btn_interrupt.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_adhoc = tk.Button(
            btn_frame_top, text="📝 Ungeplant", bg=COLOR_PAUSE, fg="#1e1e2e",
            command=self._on_adhoc, **btn_cfg
        )
        self.btn_adhoc.pack(side=tk.LEFT)

        btn_frame_bot = tk.Frame(self.root, bg=COLOR_BG)
        btn_frame_bot.pack(fill=tk.X, padx=10, pady=(0, 6))

        self.btn_save = tk.Button(
            btn_frame_bot, text="💾 Log speichern", bg=COLOR_LIST, fg=COLOR_FG,
            command=self._on_save_log, **btn_cfg
        )
        self.btn_save.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_report = tk.Button(
            btn_frame_bot, text="📊 Tagesbericht", bg=COLOR_LIST, fg=COLOR_FG,
            command=self._on_report, **btn_cfg
        )
        self.btn_report.pack(side=tk.LEFT)

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
        if ls.continuation_count > 0:
            display_name += "  (Fs.)"

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
        # Preserve scroll position across redraws
        scroll_pos = self.queue_listbox.yview()
        self.queue_listbox.delete(0, tk.END)
        self._queue_index_map = {}

        projection = self.engine.get_day_projection()
        if not projection:
            self.queue_listbox.insert(tk.END, "  (keine weiteren Einträge)")
            return

        # Build set of currently actionable candidates for visual hint
        candidates = self.engine.get_all_candidates()
        candidate_keys = set()
        for ls, row in candidates:
            candidate_keys.add((ls.name, row.activity))

        # Projection is already in chronological order (interleaved)
        prev_list = None
        for item in projection:
            state = item['state']
            est = item.get('est_start')
            time_col = est.strftime('%H:%M') if isinstance(est, datetime) else '     '
            end = item.get('est_end')
            end_col = end.strftime('%H:%M') if isinstance(end, datetime) else '     '

            name = _strip_task_code(item['activity'])
            mins = item['minutes']
            ln = item['list_name']

            # Check if this item is a current candidate (actionable)
            is_candidate = (ln, item['activity']) in candidate_keys

            # Show list name tag when switching lists
            list_tag = ""
            if ln != prev_list:
                list_tag = f"[{ln}]"
                prev_list = ln

            # Show list tag on a separate subtle line if list changed
            if list_tag:
                self.queue_listbox.insert(tk.END, f"  {list_tag}")
                self.queue_listbox.itemconfig(
                    tk.END, fg=COLOR_HEADER, selectforeground=COLOR_HEADER)
                # Tag line has no projection data — don't add to map

            prefix = "▶ " if state == "current" else "  "
            fixed = "⏰" if item.get('fixed_time') else "  "
            # Mark actionable candidates with a click hint
            click_hint = " 🖱" if is_candidate and state != "current" else ""

            entry = (f"{prefix}{time_col}–{end_col}  {fixed} "
                     f"{name}  ({mins}'){click_hint}")
            self.queue_listbox.insert(tk.END, entry)

            # Store mapping for this index
            idx = self.queue_listbox.size() - 1
            self._queue_index_map[idx] = item

            # Color by state
            if state == 'current':
                self.queue_listbox.itemconfig(
                    idx, fg=COLOR_ACCENT,
                    selectforeground=COLOR_ACCENT)
            elif is_candidate:
                # Ready candidates get a distinct color
                self.queue_listbox.itemconfig(
                    idx, fg=COLOR_DONE,
                    selectforeground=COLOR_DONE)
            elif state == 'scheduled':
                self.queue_listbox.itemconfig(
                    idx, fg=COLOR_WAIT,
                    selectforeground=COLOR_WAIT)

        # Restore scroll position
        self.queue_listbox.yview_moveto(scroll_pos[0])

    def _update_status(self):
        done = self.engine.items_done_today()
        skipped = self.engine.items_skipped_today()
        active = len(self.engine.get_active_lists())
        waits = len(self.engine.get_wait_status())
        # Count remaining activities in projection
        projection = self.engine.get_day_projection()
        remaining = sum(1 for p in projection
                        if not p.get('is_control') and p['state'] != 'current')
        self.status_bar.config(
            text=(
                f"  Erledigt: {done}  |  Übersprungen: {skipped}  "
                f"|  Offen: {remaining}  "
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
            self._show_skip_dialog(ls, row)

    def _show_skip_dialog(self, ls, row):
        """Dialog to enter a reason before skipping."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Aufgabe überspringen")
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        display = _strip_task_code(row.activity)
        if ls.continuation_count > 0:
            display += " (Fs.)"
        tk.Label(
            dlg, text=f"Überspringen: {display}",
            font=("Segoe UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_SKIP,
            wraplength=500, justify=tk.LEFT
        ).pack(anchor="w", padx=12, pady=(10, 6))

        tk.Label(
            dlg, text="Begründung (optional):",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(4, 2))

        comment_var = tk.StringVar(value="")
        comment_entry = tk.Entry(
            dlg, textvariable=comment_var, font=("Segoe UI", 11),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=50
        )
        comment_entry.pack(padx=12, pady=(0, 8))
        comment_entry.focus_set()

        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=(4, 12))

        def on_confirm():
            dlg.destroy()
            self.engine.mark_skip(ls, row,
                                  comment=comment_var.get().strip())
            self._refresh()

        def on_cancel():
            dlg.destroy()

        tk.Button(
            btn_frame, text="  ⏭ Überspringen  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_SKIP, fg="#1e1e2e", relief=tk.FLAT,
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

        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def _on_interrupt(self):
        """Interrupt the current task with another activity."""
        self.engine.tick()
        best = self.engine.get_best_candidate()
        if best:
            ls, row = best
            self._show_interrupt_dialog(ls, row)

    def _on_adhoc(self):
        """Log an unplanned activity without advancing the current item."""
        self._show_adhoc_dialog()

    def _show_adhoc_dialog(self, prefill_activity: str = ""):
        """Log an unplanned activity without advancing the current item.

        Args:
            prefill_activity: If set, pre-fills the activity name
                (e.g. when double-clicking a future queue item).
        """
        dlg = tk.Toplevel(self.root)
        title = ("Vorgezogene Aktivität erfassen" if prefill_activity
                 else "Ungeplante Aktivität erfassen")
        dlg.title(title)
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        # Hint when logging a future item out of order
        if prefill_activity:
            tk.Label(
                dlg,
                text="Diese Aktivität wird vorgezogen. "
                     "Beim regulären Erreichen bitte überspringen.",
                font=("Segoe UI", 8, "italic"),
                bg=COLOR_BG, fg=COLOR_WAIT, wraplength=450,
                justify=tk.LEFT
            ).pack(anchor="w", padx=12, pady=(10, 2))

        # Activity text
        tk.Label(
            dlg, text="Bezeichnung:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(10 if not prefill_activity else 2, 2))

        txt_var = tk.StringVar(value=prefill_activity)
        txt_entry = tk.Entry(
            dlg, textvariable=txt_var, font=("Segoe UI", 11),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=60
        )
        txt_entry.pack(padx=12, pady=(0, 2))
        txt_entry.focus_set()

        # ── Code suggestion row ───────────────────────────────────────
        suggest_frame = tk.Frame(dlg, bg=COLOR_BG)
        suggest_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        lbl_suggest = tk.Label(
            suggest_frame, text="",
            font=("Segoe UI", 8), bg=COLOR_BG, fg="#a6e3a1",
            anchor="w"
        )
        lbl_suggest.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_apply_code = tk.Button(
            suggest_frame, text="  Code anfügen  ",
            font=("Segoe UI", 8), bg="#45475a", fg=COLOR_FG,
            relief=tk.FLAT, cursor="hand2"
        )
        # Initially hidden
        btn_apply_code.pack_forget()

        def _update_suggestion(*_args):
            """Update code suggestion as user types."""
            activity = txt_var.get().strip()
            suggestions = self._code_suggestor.suggest(activity)
            if not suggestions:
                lbl_suggest.config(text="")
                btn_apply_code.pack_forget()
                return

            code, match_type, matched_name = suggestions[0]
            if match_type == "existing":
                lbl_suggest.config(
                    text=f"✓ Code {code} erkannt",
                    fg="#a6e3a1"
                )
                btn_apply_code.pack_forget()
            else:
                # Show suggestion with match quality
                quality = {"exact": "✓", "prefix": "≈", "alias": "✓", "contains": "?"}.get(match_type, "?")
                short_name = matched_name[:50] + "…" if len(matched_name) > 50 else matched_name
                lbl_suggest.config(
                    text=f"{quality} Vorschlag: {code} ({short_name})",
                    fg="#a6e3a1" if match_type in ("exact", "alias") else "#f9e2af"
                )
                # Show "apply" button
                btn_apply_code.config(
                    command=lambda c=code: _apply_code(c)
                )
                btn_apply_code.pack(side=tk.RIGHT)

        def _apply_code(code: str):
            """Append the suggested code to the activity name."""
            current = txt_var.get().strip()
            # Don't append if already ends with a 6-char code
            parts = current.rsplit(None, 1)
            if len(parts) == 2 and len(parts[1]) == 6 and parts[1].isupper():
                # Replace existing code
                txt_var.set(f"{parts[0]} {code}")
            else:
                txt_var.set(f"{current} {code}")
            txt_entry.icursor(tk.END)

        txt_var.trace_add("write", _update_suggestion)
        # Trigger initial suggestion if prefilled
        if prefill_activity:
            _update_suggestion()

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

        # Comment field
        tk.Label(
            dlg, text="Kommentar (optional):",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(4, 2))

        adhoc_comment_var = tk.StringVar(value="")
        tk.Entry(
            dlg, textvariable=adhoc_comment_var, font=("Segoe UI", 10),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=60
        ).pack(padx=12, pady=(0, 8))

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
            self.engine.log_adhoc(activity, start_time, end_time,
                                  comment=adhoc_comment_var.get().strip())
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

    def _show_interrupt_dialog(self, ls, row):
        """Dialog to record an interruption of the current task."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Aufgabe unterbrechen")
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        # Show what's being interrupted
        display = _strip_task_code(row.activity)
        if ls.continuation_count > 0:
            display += " (Fs.)"
        tk.Label(
            dlg, text=f"Unterbreche: {display}",
            font=("Segoe UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_ACCENT,
            wraplength=500, justify=tk.LEFT
        ).pack(anchor="w", padx=12, pady=(10, 6))

        # Interrupting activity name
        tk.Label(
            dlg, text="Unterbrechung durch:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(4, 2))

        txt_var = tk.StringVar(value="")
        txt_entry = tk.Entry(
            dlg, textvariable=txt_var, font=("Segoe UI", 11),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=50
        )
        txt_entry.pack(padx=12, pady=(0, 8))
        txt_entry.focus_set()

        now = datetime.now()

        # ── Interrupt start time ──────────────────────────────────────
        start_frame = tk.Frame(dlg, bg=COLOR_BG)
        start_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

        tk.Label(
            start_frame, text="Unterbrochen um:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        start_h_var = tk.StringVar(value=f"{now.hour:02d}")
        start_m_var = tk.StringVar(value=f"{now.minute:02d}")

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

        # ── Interrupt end / resume time ───────────────────────────────
        end_frame = tk.Frame(dlg, bg=COLOR_BG)
        end_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(
            end_frame, text="Fortgesetzt um:  ",
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

        # Comment field
        tk.Label(
            dlg, text="Kommentar (optional):",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(4, 2))

        int_comment_var = tk.StringVar(value="")
        tk.Entry(
            dlg, textvariable=int_comment_var, font=("Segoe UI", 10),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=50
        ).pack(padx=12, pady=(0, 8))

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
                int_start = now.replace(hour=sh, minute=sm,
                                        second=0, microsecond=0)
            except ValueError:
                int_start = now

            try:
                eh = int(end_h_var.get())
                em = int(end_m_var.get())
                int_end = now.replace(hour=eh, minute=em,
                                      second=0, microsecond=0)
            except ValueError:
                int_end = now

            if int_end < int_start:
                lbl_error.config(
                    text="⚠ Fortgesetzt darf nicht vor Unterbrochen liegen!")
                return

            dlg.destroy()
            self.engine.interrupt_current(
                ls, row, activity, int_start, int_end,
                comment=int_comment_var.get().strip())
            self._refresh()

        def on_cancel():
            dlg.destroy()

        tk.Button(
            btn_frame, text="  ✓ Erfassen  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_WAIT, fg="#1e1e2e", relief=tk.FLAT,
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

    # ------------------------------------------------------------------ #
    #  Queue click handlers                                                #
    # ------------------------------------------------------------------ #

    def _find_candidate_for_item(self, proj_item):
        """Match a projection item to a current engine candidate.

        Returns (ListState, CsvRow) or None.
        """
        candidates = self.engine.get_all_candidates()
        target_list = proj_item['list_name']
        target_activity = proj_item['activity']

        for ls, row in candidates:
            if ls.name == target_list and row.activity == target_activity:
                return ls, row
            # Also match continuations: projection shows "X (Fs.)"
            # but the candidate row.activity is just "X"
            if (ls.name == target_list
                    and target_activity == f"{row.activity} (Fs.)"):
                return ls, row
        return None

    def _on_queue_double_click(self, event):
        """Double-click a queue item to log it.

        - Current candidates → normal "done" dialog (advances list).
        - Future items → ad-hoc dialog with name pre-filled.
          The item will need to be skipped when the list reaches it.
        """
        sel = self.queue_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        proj_item = self._queue_index_map.get(idx)
        if proj_item is None:
            return  # clicked a list header line

        match = self._find_candidate_for_item(proj_item)
        if match is not None:
            # Current candidate — normal done dialog
            ls, row = match
            self._show_done_dialog(ls, row)
        else:
            # Future item — open ad-hoc dialog with name pre-filled
            self._show_adhoc_dialog(
                prefill_activity=proj_item['activity']
            )

    def _on_queue_right_click(self, event):
        """Right-click a queue item to skip it (candidates only)."""
        idx = self.queue_listbox.nearest(event.y)
        if idx < 0:
            return
        self.queue_listbox.selection_clear(0, tk.END)
        self.queue_listbox.selection_set(idx)

        proj_item = self._queue_index_map.get(idx)
        if proj_item is None:
            return

        match = self._find_candidate_for_item(proj_item)
        if match is None:
            act_name = _strip_task_code(proj_item['activity'])
            list_name = proj_item['list_name']
            messagebox.showinfo(
                "Nicht verfügbar",
                f"{act_name}\n"
                f"ist noch nicht an der Reihe in {list_name}.\n\n"
                "Rechtsklick-Überspringen geht nur bei "
                "aktuellen Kandidaten.\n"
                "Doppelklick zum Vorziehen ist möglich."
            )
            return

        ls, row = match
        self._show_skip_dialog(ls, row)

    def _on_close(self):
        """Handle window close — prompt to save if there are unsaved changes."""
        if self.engine.unsaved_changes:
            answer = messagebox.askyesnocancel(
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Log-Einträge.\n\n"
                "Möchten Sie das Log vor dem Beenden speichern?",
                icon="warning"
            )
            if answer is None:
                return  # Cancel — don't close
            if answer:
                path = self.engine.save_log()
                print(f"[Planer] Log gespeichert: {path}")
        self.root.destroy()

    def _on_save_log(self):
        path = self.engine.save_log()
        messagebox.showinfo("Log gespeichert", f"Log gespeichert:\n{path}")

    def _on_report(self):
        """Ask which date to report on, then generate and display."""
        # Save current log first to ensure today's data is up to date
        self.engine.save_log()

        self._show_report_date_dialog()

    def _show_report_date_dialog(self):
        """Let user pick a date for the report (default: today)."""
        import os
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")

        dlg = tk.Toplevel(self.root)
        dlg.title("Tagesbericht erstellen")
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(
            dlg, text="Datum für den Tagesbericht:",
            font=("Segoe UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_ACCENT
        ).pack(anchor="w", padx=12, pady=(10, 6))

        # Scan available dates (from log files)
        available = []
        if os.path.isdir(log_dir):
            for fname in sorted(os.listdir(log_dir), reverse=True):
                if fname.startswith("planner-log-") and fname.endswith(".json"):
                    d = fname[len("planner-log-"):-len(".json")]
                    # Skip backup files (contain underscores)
                    if "_" not in d:
                        available.append(d)

        today_str = datetime.now().strftime("%Y-%m-%d")

        # Show available dates as a listbox
        if available:
            tk.Label(
                dlg, text="Verfügbare Tage (Doppelklick oder auswählen):",
                font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
            ).pack(anchor="w", padx=12, pady=(4, 2))

            list_frame = tk.Frame(dlg, bg=COLOR_BG)
            list_frame.pack(fill=tk.BOTH, padx=12, pady=(0, 8))

            date_listbox = tk.Listbox(
                list_frame, bg=COLOR_LIST, fg=COLOR_FG,
                font=("Consolas", 11), selectbackground=COLOR_ACCENT,
                relief=tk.FLAT, height=min(len(available), 8),
                highlightthickness=0
            )
            for d in available:
                # Check if projection also exists
                has_proj = os.path.exists(
                    os.path.join(log_dir, f"projection-{d}.json"))
                marker = "  ✓" if has_proj else "  (keine Projektion)"
                date_listbox.insert(tk.END, f"  {d}{marker}")
            date_listbox.pack(fill=tk.X)

            # Pre-select today if available
            for i, d in enumerate(available):
                if d == today_str:
                    date_listbox.selection_set(i)
                    date_listbox.see(i)
                    break
            else:
                date_listbox.selection_set(0)

        # Validation message
        lbl_error = tk.Label(
            dlg, text="", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BG, fg=COLOR_SKIP
        )
        lbl_error.pack(padx=12)

        # Buttons
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=(4, 12))

        def on_generate():
            if not available:
                lbl_error.config(text="Keine Log-Dateien vorhanden!")
                return
            sel = date_listbox.curselection()
            if not sel:
                lbl_error.config(text="Bitte ein Datum auswählen!")
                return
            date_str = available[sel[0]]
            dlg.destroy()
            self._generate_and_show_report(date_str)

        def on_cancel():
            dlg.destroy()

        tk.Button(
            btn_frame, text="  📊 Erstellen  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_ACCENT, fg="#1e1e2e", relief=tk.FLAT,
            cursor="hand2", command=on_generate
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="  Abbrechen  ",
            font=("Segoe UI", 11),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            cursor="hand2", command=on_cancel
        ).pack(side=tk.LEFT, padx=4)

        # Double-click on date generates immediately
        if available:
            date_listbox.bind("<Double-1>", lambda e: on_generate())

        dlg.bind("<Return>", lambda e: on_generate())
        dlg.bind("<Escape>", lambda e: on_cancel())

        # Center on parent
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def _generate_and_show_report(self, date_str):
        """Generate a report for the given date and show it."""
        import os
        from day_report import generate_report

        report = generate_report(date_str)

        if report is None:
            messagebox.showerror(
                "Fehler",
                f"Tagesbericht für {date_str} konnte nicht erstellt werden.\n"
                "Projection- oder Log-Datei fehlt.")
            return

        # Save report file
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        report_path = os.path.join(log_dir, f"report-{date_str}.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        # Show in a scrollable dialog
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Tagesbericht — {date_str}")
        dlg.configure(bg=COLOR_BG)
        dlg.geometry("750x600")

        txt = tk.Text(
            dlg, bg=COLOR_LIST, fg=COLOR_FG,
            font=("Consolas", 9), wrap=tk.NONE,
            relief=tk.FLAT, padx=10, pady=10
        )
        scroll_y = ttk.Scrollbar(dlg, orient=tk.VERTICAL, command=txt.yview)
        scroll_x = ttk.Scrollbar(dlg, orient=tk.HORIZONTAL, command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set,
                      xscrollcommand=scroll_x.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(fill=tk.BOTH, expand=True)

        txt.insert(tk.END, report)
        txt.config(state=tk.DISABLED)

        tk.Label(
            dlg, text=f"Gespeichert: {report_path}",
            font=("Segoe UI", 8), bg=COLOR_BG, fg="#6c7086"
        ).pack(pady=4)


    def _show_done_dialog(self, ls: ListState, row: CsvRow):
        """Show a dialog to edit text, set start time and completion time."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Aufgabe erledigt")
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        # Activity text (editable) — add "(Fs.)" suffix if continuation
        display_activity = row.activity
        if ls.continuation_count > 0:
            display_activity = f"{row.activity} (Fs.)"

        tk.Label(
            dlg, text="Bezeichnung (bearbeiten falls nötig):",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(10, 2))

        txt_var = tk.StringVar(value=display_activity)
        txt_entry = tk.Entry(
            dlg, textvariable=txt_var, font=("Segoe UI", 11),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=60
        )
        txt_entry.pack(padx=12, pady=(0, 2))
        txt_entry.select_range(0, tk.END)
        txt_entry.focus_set()

        # ── Code suggestion row ───────────────────────────────────────
        done_suggest_frame = tk.Frame(dlg, bg=COLOR_BG)
        done_suggest_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        done_lbl_suggest = tk.Label(
            done_suggest_frame, text="",
            font=("Segoe UI", 8), bg=COLOR_BG, fg="#a6e3a1",
            anchor="w"
        )
        done_lbl_suggest.pack(side=tk.LEFT, fill=tk.X, expand=True)

        done_btn_apply = tk.Button(
            done_suggest_frame, text="  Code anfügen  ",
            font=("Segoe UI", 8), bg="#45475a", fg=COLOR_FG,
            relief=tk.FLAT, cursor="hand2"
        )
        done_btn_apply.pack_forget()

        def _update_done_suggestion(*_args):
            activity = txt_var.get().strip()
            suggestions = self._code_suggestor.suggest(activity)
            if not suggestions:
                done_lbl_suggest.config(text="")
                done_btn_apply.pack_forget()
                return
            code, match_type, matched_name = suggestions[0]
            if match_type == "existing":
                done_lbl_suggest.config(
                    text=f"✓ Code {code} erkannt", fg="#a6e3a1")
                done_btn_apply.pack_forget()
            else:
                quality = {"exact": "✓", "prefix": "≈", "alias": "✓", "contains": "?"}.get(match_type, "?")
                short_name = matched_name[:50] + "…" if len(matched_name) > 50 else matched_name
                done_lbl_suggest.config(
                    text=f"{quality} Vorschlag: {code} ({short_name})",
                    fg="#a6e3a1" if match_type in ("exact", "alias") else "#f9e2af")
                done_btn_apply.config(
                    command=lambda c=code: _apply_done_code(c))
                done_btn_apply.pack(side=tk.RIGHT)

        def _apply_done_code(code: str):
            current = txt_var.get().strip()
            parts = current.rsplit(None, 1)
            if len(parts) == 2 and len(parts[1]) == 6 and parts[1].isupper():
                txt_var.set(f"{parts[0]} {code}")
            else:
                txt_var.set(f"{current} {code}")
            txt_entry.icursor(tk.END)

        txt_var.trace_add("write", _update_done_suggestion)
        _update_done_suggestion()  # check initial value

        now = datetime.now()

        # Use pending_start from interruption, else last completed time
        if ls.pending_start:
            default_start = ls.pending_start
            start_hint = "(Vorgabe: nach Unterbrechung)"
        else:
            last_end = self.engine.last_completed_at()
            default_start = last_end if last_end else now
            start_hint = "(Vorgabe: Ende vorh. Aufgabe)"

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
            start_frame, text=start_hint,
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

        # Comment field
        tk.Label(
            dlg, text="Kommentar (optional):",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(4, 2))

        comment_var = tk.StringVar(value="")
        comment_entry = tk.Entry(
            dlg, textvariable=comment_var, font=("Segoe UI", 10),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=60
        )
        comment_entry.pack(padx=12, pady=(0, 8))

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
                                  start_time=start_time,
                                  comment=comment_var.get().strip())
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
