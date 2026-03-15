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
import json
import tkinter as tk
from tkinter import ttk, font, messagebox
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List

from models import CsvRow, ListState, RowType
from engine import PlannerEngine
from code_suggest import CodeSuggestor
from automations import load_automations, find_automation, run_automation
from automation_editor import open_editor as open_automation_editor
from window_monitor import WindowMonitor
from windowmon_import import open_import_dialog


REFRESH_MS = 15_000   # refresh display every 15 seconds
TICK_MS = 10_000      # engine tick every 10 seconds (check Wait timers)
WINMON_MS = 2_500     # window monitor GUI update every 2.5 seconds
IDLE_THRESHOLD_S = 30 # seconds without input → Off-PC mode
IDLE_BACKDATE_S = 20  # backdate idle start by this many seconds

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

# ── Dialog mode configuration ──────────────────────────────────────────── #
DIALOG_CONFIG = {
    "done": {
        "title": "Aufgabe erledigt",
        "header": None,
        "show_activity": True,
        "activity_label": "Bezeichnung (bearbeiten falls nötig):",
        "activity_width": 60,
        "show_code_suggest": True,
        "show_times": True,
        "time_labels": ("Begonnen um:", "Erledigt um:"),
        "show_comment": True,
        "comment_label": "Kommentar (optional):",
        "comment_font_size": 10,
        "comment_width": 60,
        "confirm": ("  ✓ Erledigt  ", COLOR_DONE),
    },
    "skip": {
        "title": "Aufgabe überspringen",
        "header": "skip",
        "show_activity": False,
        "show_code_suggest": False,
        "show_times": False,
        "show_comment": True,
        "comment_label": "Begründung (optional):",
        "comment_font_size": 11,
        "comment_width": 50,
        "confirm": ("  ⏭ Überspringen  ", COLOR_SKIP),
    },
    "adhoc": {
        "title": "Ungeplante Aktivität erfassen",
        "header": None,
        "show_activity": True,
        "activity_label": "Bezeichnung:",
        "activity_width": 60,
        "show_code_suggest": True,
        "show_times": True,
        "time_labels": ("Begonnen um:", "Erledigt um:"),
        "show_comment": True,
        "comment_label": "Kommentar (optional):",
        "comment_font_size": 10,
        "comment_width": 60,
        "confirm": ("  ✓ Erfassen  ", COLOR_DONE),
    },
    "interrupt": {
        "title": "Aufgabe unterbrechen",
        "header": "interrupt",
        "show_activity": True,
        "activity_label": "Unterbrechung durch:",
        "activity_width": 50,
        "show_code_suggest": True,
        "show_times": True,
        "time_labels": ("Unterbrochen um:", "Fortgesetzt um:"),
        "show_comment": True,
        "comment_label": "Kommentar (optional):",
        "comment_font_size": 10,
        "comment_width": 50,
        "confirm": ("  ⚡ Unterbrechen  ", COLOR_WAIT),
    },
}


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

        # Automations
        self._automations = load_automations()

        # Initial projection (for drift display)
        self._initial_projection = self._load_initial_projection()

        # ── Idle / Off-PC detection state ──────────────────────────────
        self._last_input_time: datetime = datetime.now()
        self._idle_active: bool = False
        self._idle_since: Optional[datetime] = None  # backdated start

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Bind user-input events for idle detection (on root → captures all)
        for event_seq in ("<Motion>", "<Key>", "<Button>", "<MouseWheel>"):
            self.root.bind_all(event_seq, self._on_user_input, add="+")

        # Window monitor — optional, failure-tolerant
        self._window_monitor: Optional[WindowMonitor] = None
        try:
            self._window_monitor = WindowMonitor(poll_interval=1.0)
            self._window_monitor.start()
        except Exception as e:
            print(f"[Planer] Window monitor failed to start: {e}")
            self._window_monitor = None

        self._tick()
        self._refresh()
        self._update_window_monitor()

    # ------------------------------------------------------------------ #
    #  Initial projection (drift display)                                  #
    # ------------------------------------------------------------------ #

    def _load_initial_projection(self) -> List[Dict]:
        """Load the initial day projection from the JSON file."""
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        day_str = self.engine.session_date.strftime("%Y-%m-%d")
        path = os.path.join(log_dir, f"projection-{day_str}.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _get_projected_start(self, list_name: str, activity: str
                             ) -> Optional[datetime]:
        """Find the est_start of an activity in the initial projection.

        Matches by list_name and activity text.  For continuations
        (activity ends with '(Fs.)'), also tries matching without
        the suffix.  Returns the first match.
        """
        for item in self._initial_projection:
            if item.get("list_name") != list_name:
                continue
            proj_act = item.get("activity", "")
            if proj_act == activity:
                est = item.get("est_start")
                if est:
                    try:
                        return datetime.strptime(est, "%H:%M")
                    except (ValueError, TypeError):
                        pass
                break
        # Try without (Fs.) suffix
        base_activity = activity.replace(" (Fs.)", "").strip()
        if base_activity != activity:
            for item in self._initial_projection:
                if item.get("list_name") != list_name:
                    continue
                proj_act = item.get("activity", "")
                if proj_act == base_activity:
                    est = item.get("est_start")
                    if est:
                        try:
                            return datetime.strptime(est, "%H:%M")
                        except (ValueError, TypeError):
                            pass
                    break
        return None

    def _update_drift(self, ls: ListState, row: CsvRow):
        """Calculate and display drift vs. initial projection."""
        if not self._initial_projection:
            self.lbl_drift.config(text="")
            return

        # Build activity name as it appears in the projection
        activity = row.activity
        if ls.continuation_count > 0:
            activity = f"{activity} (Fs.)"

        proj_start = self._get_projected_start(ls.name, activity)
        if proj_start is None:
            # Try without (Fs.) — the original item before split
            proj_start = self._get_projected_start(ls.name, row.activity)
        if proj_start is None:
            self.lbl_drift.config(text="")
            return

        # proj_start is a datetime with only H:M set (year=1900).
        # Combine with today's date for comparison.
        now = datetime.now()
        projected = now.replace(
            hour=proj_start.hour, minute=proj_start.minute,
            second=0, microsecond=0
        )
        drift = now - projected
        drift_minutes = int(drift.total_seconds() / 60)

        if abs(drift_minutes) < 5:
            # Within 5 minutes — on track
            self.lbl_drift.config(
                text=f"📍 Geplant: {proj_start.strftime('%H:%M')} — im Zeitplan",
                fg=COLOR_DONE
            )
        elif drift_minutes > 0:
            # Behind schedule
            hours = drift_minutes // 60
            mins = drift_minutes % 60
            if hours > 0:
                drift_str = f"+{hours}h {mins:02d}m"
            else:
                drift_str = f"+{mins}m"
            # Color intensity based on severity
            if drift_minutes > 120:
                color = "#f38ba8"  # red — severe
            elif drift_minutes > 60:
                color = "#fab387"  # orange — significant
            elif drift_minutes > 30:
                color = "#f9e2af"  # yellow — moderate
            else:
                color = COLOR_FG   # mild
            self.lbl_drift.config(
                text=f"📍 Geplant: {proj_start.strftime('%H:%M')} — "
                     f"Rückstand: {drift_str}",
                fg=color
            )
        else:
            # Ahead of schedule
            ahead = abs(drift_minutes)
            self.lbl_drift.config(
                text=f"📍 Geplant: {proj_start.strftime('%H:%M')} — "
                     f"{ahead}m voraus",
                fg=COLOR_DONE
            )

    # ------------------------------------------------------------------ #
    #  UI Construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        self.root.title("Tagesplanung — Reaktiver Planer")  # initial; updated dynamically
        self.root.configure(bg=COLOR_BG)
        self.root.minsize(640, 560)
        self.root.geometry("900x700")

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

        # ── Erledigt panel (completed items, above current task) ─────
        done_panel = tk.Frame(self.root, bg=COLOR_PANEL, relief=tk.FLAT, bd=1)
        done_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 0))

        tk.Label(
            done_panel, text="Erledigt", font=("Segoe UI", 9, "bold"),
            bg=COLOR_PANEL, fg="#a6adc8", anchor="w", padx=8, pady=2
        ).pack(fill=tk.X)

        self.done_listbox = tk.Listbox(
            done_panel, bg=COLOR_LIST, fg="#a6adc8",
            font=("Consolas", 9), selectbackground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, activestyle="none",
            highlightthickness=0
        )
        done_scrollbar = ttk.Scrollbar(done_panel, orient=tk.VERTICAL,
                                       command=self.done_listbox.yview)
        self.done_listbox.configure(yscrollcommand=done_scrollbar.set)
        done_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.done_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Log editing bindings
        self.done_listbox.bind("<Delete>", self._on_done_delete)
        self.done_listbox.bind("<BackSpace>", self._on_done_delete)
        self.done_listbox.bind("<Double-1>", self._on_done_double_click)

        # ── Current task panel (compact, full width) ─────────────────
        task_panel = tk.Frame(self.root, bg=COLOR_PANEL, relief=tk.FLAT, bd=1)
        task_panel.pack(fill=tk.X, padx=10, pady=(4, 0))

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

        # ── Drift indicator row ───────────────────────────────────────
        self.lbl_drift = tk.Label(
            task_panel, text="", font=("Segoe UI", 10, "bold"),
            bg=COLOR_PANEL, fg=COLOR_FG, anchor="w"
        )
        self.lbl_drift.pack(fill=tk.X, padx=14, pady=(0, 6))

        # Automation launch button (hidden by default, shown when task has one)
        self.btn_automation = tk.Button(
            meta_row, text="▶ Starten", font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1", fg="#1e1e2e", relief=tk.FLAT, bd=0,
            padx=8, pady=2, cursor="hand2",
            command=self._on_run_automation
        )
        self._current_automation = None  # currently matched automation dict

        # ── Preemption notification bar (hidden by default) ───────────
        self._preempt_frame = tk.Frame(self.root, bg="#f38ba8")
        # Not packed yet — shown/hidden dynamically

        self._preempt_label = tk.Label(
            self._preempt_frame, text="",
            font=("Segoe UI", 9, "bold"), bg="#f38ba8", fg="#1e1e2e",
            anchor="w", padx=8, pady=4
        )
        self._preempt_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._preempt_btn = tk.Button(
            self._preempt_frame, text="  ⏸ Unterbrechen  ",
            font=("Segoe UI", 9, "bold"), bg="#1e1e2e", fg="#f38ba8",
            relief=tk.FLAT, cursor="hand2",
            command=self._on_preempt_interrupt
        )
        self._preempt_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=2)

        self._preempt_dismiss_btn = tk.Button(
            self._preempt_frame, text="  Später  ",
            font=("Segoe UI", 9), bg="#45475a", fg=COLOR_FG,
            relief=tk.FLAT, cursor="hand2",
            command=self._on_preempt_dismiss
        )
        self._preempt_dismiss_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=2)

        self._preempt_candidate = None  # (ListState, CsvRow) of the preempting item
        self._preempt_dismissed = False  # True if user clicked "Später"

        # ── Queue panel (upcoming items, below current task) ──────────
        queue_panel = tk.Frame(self.root, bg=COLOR_PANEL, relief=tk.FLAT, bd=1)
        queue_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 6))

        tk.Label(
            queue_panel, text="Geplant", font=("Segoe UI", 9, "bold"),
            bg=COLOR_PANEL, fg=COLOR_HEADER, anchor="w", padx=8, pady=2
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

        # Condition (WENN) buttons — shown only when current task is CONDITION
        self.btn_ja = tk.Button(
            btn_frame_top, text="✓ Ja", bg=COLOR_DONE, fg="#1e1e2e",
            command=self._on_condition_ja, **btn_cfg
        )
        self.btn_nein = tk.Button(
            btn_frame_top, text="✗ Nein", bg=COLOR_SKIP, fg="#1e1e2e",
            command=self._on_condition_nein, **btn_cfg
        )
        # (not packed — shown/hidden dynamically via _set_condition_mode)
        self._condition_mode = False  # tracks current button layout

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
        self.btn_report.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_automations = tk.Button(
            btn_frame_bot, text="⚡ Automationen", bg=COLOR_LIST, fg=COLOR_FG,
            command=self._on_open_automations, **btn_cfg
        )
        self.btn_automations.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_import = tk.Button(
            btn_frame_bot, text="📥 Nacherfassung", bg=COLOR_LIST, fg=COLOR_FG,
            command=self._on_windowmon_import, **btn_cfg
        )
        self.btn_import.pack(side=tk.LEFT)

        # ── Status bar ────────────────────────────────────────────────
        self.status_bar = tk.Label(
            self.root, text="", font=("Segoe UI", 9),
            bg=COLOR_PANEL, fg=COLOR_FG, anchor="w", padx=8, pady=3
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # ── Window monitor bar (above status bar) ─────────────────────
        self.lbl_window_monitor = tk.Label(
            self.root, text="🖥️ …", font=("Consolas", 8),
            bg=COLOR_BG, fg="#6c7086", anchor="w", padx=10, pady=1
        )
        self.lbl_window_monitor.pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------ #
    #  Timer callbacks                                                     #
    # ------------------------------------------------------------------ #

    def _tick(self):
        """Engine tick — unblocks waiting lists."""
        self.engine.tick()
        self.root.after(TICK_MS, self._tick)

    def _refresh(self):
        """Redraw the UI with current engine state."""
        self._check_idle()
        self._update_clock()
        self._update_current()
        self._update_queue()
        self._update_status()
        self._update_window_title()
        self.root.after(REFRESH_MS, self._refresh)

    def _update_window_monitor(self):
        """Update the window monitor label with current active window."""
        if self._window_monitor is not None:
            try:
                info = self._window_monitor.get_current()
                if info and info.get("title"):
                    title = info["title"]
                    browser = info.get("browser", "")
                    # Truncate long titles
                    max_len = 90
                    if len(title) > max_len:
                        title = title[:max_len] + "…"
                    prefix = f"🖥️ {browser} — " if browser else "🖥️ "
                    self.lbl_window_monitor.config(
                        text=f"{prefix}{title}",
                        fg="#585b70"
                    )
                else:
                    self.lbl_window_monitor.config(
                        text="🖥️ (kein Fenster erkannt)",
                        fg="#45475a"
                    )
            except Exception:
                pass  # don't crash the GUI for monitor issues
        self.root.after(WINMON_MS, self._update_window_monitor)

    # ------------------------------------------------------------------ #
    #  Idle / Off-PC detection                                             #
    # ------------------------------------------------------------------ #

    def _on_user_input(self, event=None):
        """Called on any mouse/keyboard input — resets idle timer."""
        self._last_input_time = datetime.now()
        if self._idle_active:
            self._end_idle()

    def _check_idle(self):
        """Called from _refresh — activate idle if threshold exceeded."""
        if self._idle_active:
            return  # already idle
        elapsed = (datetime.now() - self._last_input_time).total_seconds()
        if elapsed >= IDLE_THRESHOLD_S:
            self._start_idle()

    def _start_idle(self):
        """Activate Off-PC mode."""
        self._idle_active = True
        # Backdate: the user actually left ~IDLE_BACKDATE_S ago
        self._idle_since = datetime.now() - timedelta(seconds=IDLE_BACKDATE_S)
        # Write marker to windowmon log
        self._write_idle_marker("idle_start", self._idle_since)
        # Visual feedback
        self._update_idle_display()
        self._update_window_title()

    def _end_idle(self):
        """Deactivate Off-PC mode on user return."""
        idle_start = self._idle_since
        self._idle_active = False
        idle_end = datetime.now()
        self._idle_since = None
        # Write marker to windowmon log
        self._write_idle_marker("idle_end", idle_end, idle_start)
        # Restore display
        self._update_idle_display()
        self._update_window_title()

    def _write_idle_marker(self, marker_type: str, ts: datetime,
                           idle_start: Optional[datetime] = None):
        """Write an idle marker event to the windowmon JSONL log."""
        if self._window_monitor is None:
            return
        try:
            entry = {
                "ts": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                "type": marker_type,
                "hwnd": 0,
                "title": "",
                "process": "planner_idle",
                "browser": "",
            }
            if marker_type == "idle_end" and idle_start is not None:
                duration_s = int((ts - idle_start).total_seconds())
                entry["idle_duration_s"] = duration_s
                entry["idle_start"] = idle_start.strftime(
                    "%Y-%m-%dT%H:%M:%S")
            # Use the monitor's log writer directly
            from window_monitor import WindowEvent, LOG_DIR
            import json as _json
            today = datetime.now().strftime("%Y-%m-%d")
            os.makedirs(LOG_DIR, exist_ok=True)
            path = os.path.join(LOG_DIR, f"windowmon-{today}.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Planer] Idle marker write error: {e}")

    def _update_idle_display(self):
        """Update the window monitor label to show idle state."""
        if self._idle_active and self._idle_since:
            since_str = self._idle_since.strftime("%H:%M")
            self.lbl_window_monitor.config(
                text=f"💤 Off-PC seit {since_str}",
                fg="#f9e2af"
            )
        # else: next _update_window_monitor() call will restore normal display

    def _get_current_activity_name(self) -> str:
        """Return the current activity name (with task code), or ''."""
        best = self.engine.get_best_candidate()
        if best is None:
            return ""
        _ls, row = best
        return row.activity

    def _update_window_title(self):
        """Update root window title with current mode + activity.

        Normal:  'Tagesplanung — Reaktiver Planer — [Aktivität]'
        Off-PC:  'Tagesplanung — Off-PC — [Aktivität]'

        The old VB5 Window Logger reads this title, so:
        - 'Off-PC' signals no phantom-KS accounting
        - The activity name lets the logger know what's being done
        """
        activity = self._get_current_activity_name()
        if self._idle_active:
            mode = "Off-PC"
        else:
            mode = "Reaktiver Planer"
        if activity:
            title = f"Tagesplanung — {mode} — {activity}"
        else:
            title = f"Tagesplanung — {mode}"
        self.root.title(title)

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
            self._set_condition_mode(False)
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
            self.lbl_drift.config(text="")
            self._current_automation = None
            self.btn_automation.pack_forget()
            return

        ls, row = best

        # ── CONDITION (WENN) row — show question + Ja/Nein UI ─────────
        if row.row_type == RowType.CONDITION:
            self._set_condition_mode(True)
            question = row.condition_question or row.activity
            action = row.condition_action
            self.lbl_task_name.config(
                text=f"❓ {question}", fg=COLOR_WAIT
            )
            self.lbl_list_name.config(text=ls.name)
            self.lbl_meta.config(
                text=f"Prio {row.priority:.3f}  •  Entscheidung"
                     + (f"  →  {action}" if action else "")
            )
            self.lbl_start_time.config(text="")
            self.lbl_drift.config(text="")
            self._current_automation = None
            self.btn_automation.pack_forget()
            self._preempt_frame.pack_forget()
            return

        # ── Normal activity row ────────────────────────────────────────
        self._set_condition_mode(False)

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

        # ── Drift indicator ────────────────────────────────────────────
        self._update_drift(ls, row)

        # Show/hide automation button
        auto = find_automation(row.activity, self._automations)
        self._current_automation = auto
        if auto:
            label = auto.get("label", "▶ Starten")
            self.btn_automation.config(text=f"▶ {label}")
            self.btn_automation.pack(side=tk.RIGHT, padx=(8, 0))
        else:
            self.btn_automation.pack_forget()

        # Check for preemption (higher-priority item waiting)
        preempt = self.engine.get_preemption_candidate()
        if preempt and not self._preempt_dismissed:
            p_ls, p_row = preempt
            p_name = _strip_task_code(p_row.activity)
            time_str = ""
            if p_row.starting_time:
                time_str = f" (⏰ {p_row.starting_time.strftime('%H:%M')})"
            self._preempt_label.config(
                text=f"⚠ {p_name}{time_str} — {p_ls.name} — "
                     f"Prio {p_row.priority:.3f} wartet"
            )
            self._preempt_candidate = preempt
            self._preempt_frame.pack(fill=tk.X, padx=10, pady=(2, 0),
                                     before=self._get_queue_panel())
        else:
            self._preempt_frame.pack_forget()
            if not preempt:
                # Reset dismiss when the preemption resolves
                self._preempt_dismissed = False
                self._preempt_candidate = None

    def _get_queue_panel(self):
        """Return the queue panel widget for pack ordering."""
        return self.queue_listbox.master

    def _update_queue(self):
        # ── Completed items panel (sorted by started_at) ──────────────
        completed = self.engine.get_completed_log()
        prev_done_count = self.done_listbox.size()
        new_done_count = len(completed) if completed else 0

        # Always rebuild so edits (Ändern) are reflected immediately
        done_sel = self.done_listbox.curselection()
        done_scroll = self.done_listbox.yview()
        self.done_listbox.delete(0, tk.END)
        if completed:
            for item in completed:
                start_col = item.started_at.strftime('%H:%M')
                end_col = item.completed_at.strftime('%H:%M')
                name = _strip_task_code(item.activity)
                mins = item.minutes
                skip_mark = " ⏭" if item.skipped else ""

                entry = f"  {start_col}–{end_col}  {name}  ({mins}'){skip_mark}"
                self.done_listbox.insert(tk.END, entry)
                idx = self.done_listbox.size() - 1

                if item.skipped:
                    self.done_listbox.itemconfig(
                        idx, fg="#7f849c", selectforeground="#7f849c")
                else:
                    self.done_listbox.itemconfig(
                        idx, fg="#a6adc8", selectforeground="#a6adc8")

            # Only auto-scroll when new items were added
            if new_done_count > prev_done_count:
                self.done_listbox.see(tk.END)
            else:
                self.done_listbox.yview_moveto(done_scroll[0])
        else:
            self.done_listbox.insert(tk.END, "  (noch keine Einträge)")
            self.done_listbox.itemconfig(
                tk.END, fg="#7f849c", selectforeground="#7f849c")

        # Restore done_listbox selection if still valid
        if done_sel and done_sel[0] < self.done_listbox.size():
            self.done_listbox.selection_set(done_sel[0])
            self.done_listbox.see(done_sel[0])

        # ── Projection panel (upcoming items) ─────────────────────────
        # Preserve scroll position across redraws
        queue_sel = self.queue_listbox.curselection()
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

        # Restore queue_listbox selection if still valid
        if queue_sel and queue_sel[0] < self.queue_listbox.size():
            self.queue_listbox.selection_set(queue_sel[0])
            self.queue_listbox.see(queue_sel[0])

    def _update_status(self):
        done = self.engine.items_done_today()
        skipped = self.engine.items_skipped_today()
        active = len(self.engine.get_active_lists())
        waits = len(self.engine.get_wait_status())
        # Count remaining activities in projection
        projection = self.engine.get_day_projection()
        remaining = sum(1 for p in projection
                        if not p.get('is_control') and p['state'] != 'current')

        # Last completed time + gap detection
        last_at = self.engine.last_completed_at()
        last_str = ""
        if last_at:
            last_str = f"  |  Letzter Eintrag: {last_at.strftime('%H:%M')}"
            now = datetime.now()
            gap_mins = int((now - last_at).total_seconds() / 60)
            if gap_mins >= 30:
                gap_h = gap_mins // 60
                gap_m = gap_mins % 60
                if gap_h > 0:
                    last_str += f"  ⚠ Lücke: {gap_h}h {gap_m:02d}m"
                else:
                    last_str += f"  ⚠ Lücke: {gap_m}m"

        self.status_bar.config(
            text=(
                f"  Erledigt: {done}  |  Übersprungen: {skipped}  "
                f"|  Offen: {remaining}  "
                f"|  Aktive Listen: {active}  |  Wartend: {waits}"
                f"{last_str}"
            )
        )

    # ------------------------------------------------------------------ #
    #  Button handlers                                                     #
    # ------------------------------------------------------------------ #

    def _on_windowmon_import(self):
        """Open the windowmon import dialog for Nacherfassung."""
        open_import_dialog(self.root, self.engine, self._code_suggestor)
        # Refresh after import (new log entries may exist)
        self._refresh()

    def _on_open_automations(self):
        """Open the automation editor and reload automations when it closes."""
        editor = open_automation_editor(self.root)
        editor_win = editor.win  # capture reference

        def _on_editor_closed(event):
            # Only fire when the editor top-level itself is destroyed,
            # not its child widgets
            if event.widget is not editor_win:
                return
            self._automations = load_automations()
            # Schedule refresh on next event loop tick (editor is fully gone)
            self.root.after(50, self._refresh)

        editor_win.bind("<Destroy>", _on_editor_closed)

    def _on_preempt_interrupt(self):
        """User chose to interrupt current task for the preempting item."""
        if self._current and self._preempt_candidate:
            ls, row = self._current
            _p_ls, p_row = self._preempt_candidate
            self._preempt_frame.pack_forget()
            self._preempt_dismissed = False
            self._preempt_candidate = None
            self._show_task_dialog("interrupt", ls, row,
                                   prefill_activity=p_row.activity)

    def _on_preempt_dismiss(self):
        """User chose 'Später' — hide the bar until the preemption changes."""
        self._preempt_dismissed = True
        self._preempt_frame.pack_forget()

    def _on_run_automation(self):
        """Launch the automation associated with the current task."""
        if self._current_automation:
            success = run_automation(self._current_automation)
            if not success:
                messagebox.showerror(
                    "Automation fehlgeschlagen",
                    f"Konnte Automation nicht starten:\n"
                    f"{self._current_automation.get('command', '')}"
                    f"{self._current_automation.get('url', '')}"
                )

    def _set_condition_mode(self, active: bool):
        """Switch the main button row between normal and condition (Ja/Nein) layout."""
        if active == self._condition_mode:
            return
        self._condition_mode = active
        # Unpack all mutable buttons, then repack in the right order
        for btn in (self.btn_done, self.btn_skip, self.btn_interrupt,
                    self.btn_ja, self.btn_nein, self.btn_adhoc):
            btn.pack_forget()
        if active:
            self.btn_ja.pack(side=tk.LEFT, padx=(0, 4))
            self.btn_nein.pack(side=tk.LEFT, padx=(0, 4))
            self.btn_adhoc.pack(side=tk.LEFT)
        else:
            self.btn_done.pack(side=tk.LEFT, padx=(0, 4))
            self.btn_skip.pack(side=tk.LEFT, padx=(0, 4))
            self.btn_interrupt.pack(side=tk.LEFT, padx=(0, 4))
            self.btn_adhoc.pack(side=tk.LEFT)

    def _on_condition_ja(self):
        """User answered 'Ja' to a WENN condition."""
        self._preempt_dismissed = False
        self.engine.tick()
        best = self.engine.get_best_candidate()
        if best:
            ls, row = best
            if row.row_type == RowType.CONDITION:
                self.engine.answer_condition(ls, row, True)
                self._refresh()

    def _on_condition_nein(self):
        """User answered 'Nein' to a WENN condition."""
        self._preempt_dismissed = False
        self.engine.tick()
        best = self.engine.get_best_candidate()
        if best:
            ls, row = best
            if row.row_type == RowType.CONDITION:
                self.engine.answer_condition(ls, row, False)
                self._refresh()

    def _on_done(self):
        self._preempt_dismissed = False
        self.engine.tick()
        best = self.engine.get_best_candidate()
        if best:
            ls, row = best
            self._show_task_dialog("done", ls, row)

    def _on_skip(self):
        self._preempt_dismissed = False
        self.engine.tick()
        best = self.engine.get_best_candidate()
        if best:
            ls, row = best
            self._show_task_dialog("skip", ls, row)

    def _show_task_dialog(self, mode: str, ls=None, row=None,
                          prefill_activity: str = ""):
        """Unified dialog for done/skip/adhoc/interrupt modes."""
        cfg = DIALOG_CONFIG[mode]
        dlg = tk.Toplevel(self.root)

        # Override title for adhoc with prefill
        title = ("Vorgezogene Aktivität erfassen"
                 if mode == "adhoc" and prefill_activity
                 else cfg["title"])
        dlg.title(title)
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.minsize(width=520, height=0)  # feste Mindestbreite

        # ── Header ────────────────────────────────────────────────────
        if cfg["header"] == "skip":
            display = _strip_task_code(row.activity)
            if ls and ls.continuation_count > 0:
                display += " (Fs.)"
            tk.Label(
                dlg, text=f"Überspringen: {display}",
                font=("Segoe UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_SKIP,
                wraplength=500, justify=tk.LEFT
            ).pack(anchor="w", padx=12, pady=(10, 6))
        elif cfg["header"] == "interrupt":
            display = _strip_task_code(row.activity)
            if ls and ls.continuation_count > 0:
                display += " (Fs.)"
            tk.Label(
                dlg, text=f"Unterbreche: {display}",
                font=("Segoe UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_ACCENT,
                wraplength=500, justify=tk.LEFT
            ).pack(anchor="w", padx=12, pady=(10, 6))

        # ── Adhoc prefill hint ─────────────────────────────────────────
        if mode == "adhoc" and prefill_activity:
            tk.Label(
                dlg,
                text="Diese Aktivität wird vorgezogen. "
                     "Beim regulären Erreichen bitte überspringen.",
                font=("Segoe UI", 8, "italic"),
                bg=COLOR_BG, fg=COLOR_WAIT, wraplength=450,
                justify=tk.LEFT
            ).pack(anchor="w", padx=12, pady=(10, 2))

        # ── Activity field ─────────────────────────────────────────────
        txt_var = None
        txt_entry = None
        if cfg["show_activity"]:
            # Determine top padding based on what preceded this widget
            if cfg["header"] is not None:
                act_top_pad = 4
            elif mode == "adhoc" and prefill_activity:
                act_top_pad = 2
            else:
                act_top_pad = 10

            tk.Label(
                dlg, text=cfg["activity_label"],
                font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
            ).pack(anchor="w", padx=12, pady=(act_top_pad, 2))

            # Determine initial text
            if mode == "done":
                initial_text = row.activity
                if ls and ls.continuation_count > 0:
                    initial_text = f"{row.activity} (Fs.)"
            else:
                initial_text = prefill_activity

            txt_var = tk.StringVar(value=initial_text)
            txt_entry = tk.Entry(
                dlg, textvariable=txt_var, font=("Segoe UI", 11),
                bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
                width=cfg["activity_width"]
            )
            txt_entry.pack(anchor="w", padx=12,
                           pady=(0, 2 if cfg["show_code_suggest"] else 8))
            if mode == "done":
                txt_entry.select_range(0, tk.END)
            txt_entry.focus_set()

            # ── Dynamic window title — shows activity for windowmon ────
            # When this dialog is left open during Off-PC, the Window
            # Logger captures the title. Including the activity text lets
            # AutoDetect classify what the user is actually doing.
            _base_title = title

            def _update_dialog_title(*_args):
                activity_text = txt_var.get().strip()
                if activity_text:
                    dlg.title(f"{_base_title} \u2014 {activity_text}")
                else:
                    dlg.title(_base_title)

            txt_var.trace_add("write", _update_dialog_title)
            _update_dialog_title()  # set initial title

        # ── Code suggestion row ────────────────────────────────────────
        if cfg["show_code_suggest"]:
            suggest_frame = tk.Frame(dlg, bg=COLOR_BG)
            suggest_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

            lbl_suggest = tk.Label(
                suggest_frame, text="",
                font=("Segoe UI", 8), bg=COLOR_BG, fg="#a6e3a1",
                anchor="w", wraplength=280
            )
            lbl_suggest.pack(side=tk.LEFT, fill=tk.X, expand=True)

            btn_apply_name = tk.Button(
                suggest_frame, text="  Name übernehmen  ",
                font=("Segoe UI", 8), bg="#89b4fa", fg="#1e1e2e",
                relief=tk.FLAT, cursor="hand2",
                highlightthickness=2, highlightcolor="#f9e2af",
                highlightbackground=COLOR_BG, takefocus=True
            )
            btn_apply_name.pack_forget()

            btn_apply_code = tk.Button(
                suggest_frame, text="  Code anfügen  ",
                font=("Segoe UI", 8), bg="#45475a", fg=COLOR_FG,
                relief=tk.FLAT, cursor="hand2",
                highlightthickness=2, highlightcolor="#f9e2af",
                highlightbackground=COLOR_BG, takefocus=True
            )
            btn_apply_code.pack_forget()

            def _update_suggestion(*_args):
                activity = txt_var.get().strip()
                suggestions = self._code_suggestor.suggest(activity)
                if not suggestions:
                    lbl_suggest.config(text="")
                    btn_apply_code.pack_forget()
                    btn_apply_name.pack_forget()
                    return
                code, match_type, matched_name = suggestions[0]
                if match_type == "existing":
                    lbl_suggest.config(
                        text=f"✓ Code {code} erkannt", fg="#a6e3a1"
                    )
                    btn_apply_code.pack_forget()
                    btn_apply_name.pack_forget()
                else:
                    quality = {
                        "exact": "✓", "prefix": "≈",
                        "alias": "✓", "contains": "?"
                    }.get(match_type, "?")
                    short_name = (matched_name[:50] + "…"
                                  if len(matched_name) > 50 else matched_name)
                    lbl_suggest.config(
                        text=f"{quality} Vorschlag: {code} ({short_name})",
                        fg="#a6e3a1" if match_type in ("exact", "alias")
                        else "#f9e2af"
                    )
                    btn_apply_name.config(
                        command=lambda c=code, n=matched_name:
                            _apply_full_name(n, c)
                    )
                    btn_apply_name.pack(side=tk.RIGHT, padx=(4, 0))
                    btn_apply_code.config(
                        command=lambda c=code: _apply_code(c)
                    )
                    btn_apply_code.pack(side=tk.RIGHT)

            def _apply_full_name(name: str, code: str):
                txt_var.set(f"{name} {code}")
                txt_entry.icursor(tk.END)

            def _apply_code(code: str):
                current = txt_var.get().strip()
                parts = current.rsplit(None, 1)
                if (len(parts) == 2 and len(parts[1]) == 6
                        and parts[1].isupper()):
                    txt_var.set(f"{parts[0]} {code}")
                else:
                    txt_var.set(f"{current} {code}")
                txt_entry.icursor(tk.END)

            txt_var.trace_add("write", _update_suggestion)
            # Trigger initial suggestion when there is already text
            if txt_var.get().strip():
                _update_suggestion()

        # ── Time fields ────────────────────────────────────────────────
        now = datetime.now()
        start_h_var = start_m_var = end_h_var = end_m_var = None
        default_start = now
        if cfg["show_times"]:
            start_label, end_label = cfg["time_labels"]

            # Determine default start time and hint text
            if mode == "done":
                if ls and ls.pending_start:
                    default_start = ls.pending_start
                    start_hint = "(Vorgabe: nach Unterbrechung)"
                else:
                    last_end = self.engine.last_completed_at()
                    default_start = last_end if last_end else now
                    start_hint = "(Vorgabe: Ende vorh. Aufgabe)"
            elif mode == "interrupt":
                default_start = now
                start_hint = ""
            else:  # adhoc
                last_end = self.engine.last_completed_at()
                default_start = last_end if last_end else now
                start_hint = "(Vorgabe: Ende vorh. Aufgabe)"

            # Start time row
            start_frame = tk.Frame(dlg, bg=COLOR_BG)
            start_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

            tk.Label(
                start_frame, text=start_label,
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

            if start_hint:
                tk.Label(
                    start_frame, text=start_hint,
                    font=("Segoe UI", 8, "italic"), bg=COLOR_BG, fg="#6c7086"
                ).pack(side=tk.LEFT, padx=(10, 0))

            # End time row
            end_frame = tk.Frame(dlg, bg=COLOR_BG)
            end_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

            tk.Label(
                end_frame, text=end_label + "  ",
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

        # ── Comment field ──────────────────────────────────────────────
        comment_var = tk.StringVar(value="")
        if cfg["show_comment"]:
            tk.Label(
                dlg, text=cfg["comment_label"],
                font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
            ).pack(anchor="w", padx=12, pady=(4, 2))

            comment_entry = tk.Entry(
                dlg, textvariable=comment_var,
                font=("Segoe UI", cfg["comment_font_size"]),
                bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
                width=cfg["comment_width"]
            )
            comment_entry.pack(padx=12, pady=(0, 8))
            if not cfg["show_activity"]:
                comment_entry.focus_set()

        # ── Validation label ───────────────────────────────────────────
        lbl_error = tk.Label(
            dlg, text="", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BG, fg=COLOR_SKIP
        )
        lbl_error.pack(padx=12)

        # ── Buttons ────────────────────────────────────────────────────
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=(4, 12))

        confirm_text, confirm_color = cfg["confirm"]

        def on_confirm():
            # Validate activity
            if cfg["show_activity"] and txt_var is not None:
                if not txt_var.get().strip():
                    lbl_error.config(
                        text="⚠ Bezeichnung darf nicht leer sein!")
                    return

            # Parse times
            start_time = end_time = None
            if cfg["show_times"]:
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
            comment = comment_var.get().strip()

            if mode == "done":
                edited_text = txt_var.get().strip()
                custom_text = (edited_text if edited_text != row.activity
                               else None)
                self.engine.mark_done(ls, row, custom_time=end_time,
                                      custom_text=custom_text,
                                      start_time=start_time,
                                      comment=comment)
                # Learn code from edited text (e.g. user added a code)
                self._code_suggestor.learn(edited_text)
            elif mode == "skip":
                self.engine.mark_skip(ls, row, comment=comment)
            elif mode == "adhoc":
                activity = txt_var.get().strip()
                self.engine.log_adhoc(activity, start_time, end_time,
                                      comment=comment)
                # Learn code from unplanned activity
                self._code_suggestor.learn(activity)
            elif mode == "interrupt":
                activity = txt_var.get().strip()
                self.engine.interrupt_current(
                    ls, row, activity, start_time, end_time,
                    comment=comment)
                # Learn code from interrupting activity
                self._code_suggestor.learn(activity)

            self._refresh()

        def on_cancel():
            dlg.destroy()

        tk.Button(
            btn_frame, text=confirm_text,
            font=("Segoe UI", 11, "bold"),
            bg=confirm_color, fg="#1e1e2e", relief=tk.FLAT,
            cursor="hand2", command=on_confirm
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="  Abbrechen  ",
            font=("Segoe UI", 11),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            cursor="hand2", command=on_cancel
        ).pack(side=tk.LEFT, padx=4)

        # Enter auf fokussiertem Button löst diesen aus,
        # sonst (z.B. im Textfeld) → on_confirm
        def _on_return(event):
            w = event.widget
            if isinstance(w, tk.Button):
                w.invoke()
            else:
                on_confirm()

        dlg.bind("<Return>", _on_return)
        dlg.bind("<Escape>", lambda e: on_cancel())

        # Center on parent
        dlg.update_idletasks()
        x = (self.root.winfo_x()
             + (self.root.winfo_width() - dlg.winfo_width()) // 2)
        y = (self.root.winfo_y()
             + (self.root.winfo_height() - dlg.winfo_height()) // 2)
        dlg.geometry(f"+{x}+{y}")

    def _on_interrupt(self):
        """Interrupt the current task with another activity."""
        self.engine.tick()
        best = self.engine.get_best_candidate()
        if best:
            ls, row = best
            self._show_task_dialog("interrupt", ls, row)

    def _on_adhoc(self):
        """Log an unplanned activity without advancing the current item."""
        self._show_task_dialog("adhoc")

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
            self._show_task_dialog("done", ls, row)
        else:
            # Future item — open ad-hoc dialog with name pre-filled
            self._show_task_dialog("adhoc",
                                   prefill_activity=proj_item['activity'])

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
        self._show_task_dialog("skip", ls, row)

    # ------------------------------------------------------------------ #
    #  Log editing handlers                                                #
    # ------------------------------------------------------------------ #

    def _on_done_delete(self, event):
        """Quick-delete: Delete/Backspace on selected log entry."""
        sel = self.done_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        completed = self.engine.get_completed_log()
        if idx < 0 or idx >= len(completed):
            return
        item = completed[idx]
        name = _strip_task_code(item.activity)
        start_str = item.started_at.strftime('%H:%M')
        end_str = item.completed_at.strftime('%H:%M')
        answer = messagebox.askyesno(
            "Eintrag löschen",
            f"Eintrag '{name}' [{start_str}\u2013{end_str}] wirklich löschen?",
            icon="warning"
        )
        if answer:
            self.engine.delete_log_entry(idx)
            self._refresh()

    def _on_done_double_click(self, event):
        """Double-click on log entry → open edit dialog."""
        sel = self.done_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        completed = self.engine.get_completed_log()
        if idx < 0 or idx >= len(completed):
            return
        item = completed[idx]
        self._show_edit_dialog(idx, item)

    def _show_edit_dialog(self, sorted_index: int, item):
        """Edit dialog for a completed log entry.

        Buttons: Ändern, Löschen, Duplizieren, Abbrechen.
        """
        from models import CompletedItem

        dlg = tk.Toplevel(self.root)
        dlg.title("Eintrag bearbeiten")
        dlg.configure(bg=COLOR_BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.minsize(width=520, height=0)

        # ── Activity field ─────────────────────────────────────────────
        tk.Label(
            dlg, text="Bezeichnung:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(10, 2))

        txt_var = tk.StringVar(value=item.activity)
        txt_entry = tk.Entry(
            dlg, textvariable=txt_var, font=("Segoe UI", 11),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=60
        )
        txt_entry.pack(anchor="w", padx=12, pady=(0, 2))
        txt_entry.select_range(0, tk.END)
        txt_entry.focus_set()

        # ── Dynamic window title — shows activity for windowmon ────
        _edit_base_title = "Eintrag bearbeiten"

        def _update_edit_title(*_args):
            activity_text = txt_var.get().strip()
            if activity_text:
                dlg.title(f"{_edit_base_title} \u2014 {activity_text}")
            else:
                dlg.title(_edit_base_title)

        txt_var.trace_add("write", _update_edit_title)
        _update_edit_title()  # set initial title

        # ── Code suggestion row ────────────────────────────────────────
        suggest_frame = tk.Frame(dlg, bg=COLOR_BG)
        suggest_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        lbl_suggest = tk.Label(
            suggest_frame, text="",
            font=("Segoe UI", 8), bg=COLOR_BG, fg="#a6e3a1",
            anchor="w", wraplength=280
        )
        lbl_suggest.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_apply_name = tk.Button(
            suggest_frame, text="  Name übernehmen  ",
            font=("Segoe UI", 8), bg="#89b4fa", fg="#1e1e2e",
            relief=tk.FLAT, cursor="hand2",
            highlightthickness=2, highlightcolor="#f9e2af",
            highlightbackground=COLOR_BG, takefocus=True
        )
        btn_apply_name.pack_forget()

        btn_apply_code = tk.Button(
            suggest_frame, text="  Code anfügen  ",
            font=("Segoe UI", 8), bg="#45475a", fg=COLOR_FG,
            relief=tk.FLAT, cursor="hand2",
            highlightthickness=2, highlightcolor="#f9e2af",
            highlightbackground=COLOR_BG, takefocus=True
        )
        btn_apply_code.pack_forget()

        def _update_suggestion(*_args):
            activity = txt_var.get().strip()
            suggestions = self._code_suggestor.suggest(activity)
            if not suggestions:
                lbl_suggest.config(text="")
                btn_apply_code.pack_forget()
                btn_apply_name.pack_forget()
                return
            code, match_type, matched_name = suggestions[0]
            if match_type == "existing":
                lbl_suggest.config(
                    text=f"✓ Code {code} erkannt", fg="#a6e3a1"
                )
                btn_apply_code.pack_forget()
                btn_apply_name.pack_forget()
            else:
                quality = {
                    "exact": "✓", "prefix": "≈",
                    "alias": "✓", "contains": "?"
                }.get(match_type, "?")
                short_name = (matched_name[:50] + "…"
                              if len(matched_name) > 50 else matched_name)
                lbl_suggest.config(
                    text=f"{quality} Vorschlag: {code} ({short_name})",
                    fg="#a6e3a1" if match_type in ("exact", "alias")
                    else "#f9e2af"
                )
                btn_apply_name.config(
                    command=lambda c=code, n=matched_name:
                        _apply_full_name(n, c)
                )
                btn_apply_name.pack(side=tk.RIGHT, padx=(4, 0))
                btn_apply_code.config(
                    command=lambda c=code: _apply_code(c)
                )
                btn_apply_code.pack(side=tk.RIGHT)

        def _apply_full_name(name: str, code: str):
            txt_var.set(f"{name} {code}")
            txt_entry.icursor(tk.END)

        def _apply_code(code: str):
            current = txt_var.get().strip()
            parts = current.rsplit(None, 1)
            if (len(parts) == 2 and len(parts[1]) == 6
                    and parts[1].isupper()):
                txt_var.set(f"{parts[0]} {code}")
            else:
                txt_var.set(f"{current} {code}")
            txt_entry.icursor(tk.END)

        txt_var.trace_add("write", _update_suggestion)
        if txt_var.get().strip():
            _update_suggestion()

        # ── Time fields ────────────────────────────────────────────────
        now = datetime.now()

        # Start time
        start_frame = tk.Frame(dlg, bg=COLOR_BG)
        start_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

        tk.Label(
            start_frame, text="Begonnen um:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        start_h_var = tk.StringVar(value=f"{item.started_at.hour:02d}")
        start_m_var = tk.StringVar(value=f"{item.started_at.minute:02d}")

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

        # End time
        end_frame = tk.Frame(dlg, bg=COLOR_BG)
        end_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(
            end_frame, text="Erledigt um:  ",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        end_h_var = tk.StringVar(value=f"{item.completed_at.hour:02d}")
        end_m_var = tk.StringVar(value=f"{item.completed_at.minute:02d}")

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

        # ── Comment field ──────────────────────────────────────────────
        tk.Label(
            dlg, text="Kommentar (optional):",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(anchor="w", padx=12, pady=(4, 2))

        comment_var = tk.StringVar(value=item.comment)
        comment_entry = tk.Entry(
            dlg, textvariable=comment_var,
            font=("Segoe UI", 10),
            bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
            width=60
        )
        comment_entry.pack(padx=12, pady=(0, 8))

        # ── Validation label ───────────────────────────────────────────
        lbl_error = tk.Label(
            dlg, text="", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BG, fg=COLOR_SKIP
        )
        lbl_error.pack(padx=12)

        # ── Helper: parse times from spinboxes ─────────────────────────
        def _parse_times():
            """Parse start/end times. Returns (start_dt, end_dt) or None on error."""
            try:
                sh = int(start_h_var.get())
                sm = int(start_m_var.get())
                start_dt = item.started_at.replace(
                    hour=sh, minute=sm, second=0, microsecond=0)
            except ValueError:
                lbl_error.config(text="⚠ Ungültige Startzeit!")
                return None
            try:
                eh = int(end_h_var.get())
                em = int(end_m_var.get())
                end_dt = item.completed_at.replace(
                    hour=eh, minute=em, second=0, microsecond=0)
            except ValueError:
                lbl_error.config(text="⚠ Ungültige Endzeit!")
                return None
            if end_dt < start_dt:
                lbl_error.config(
                    text="⚠ Ende darf nicht vor dem Beginn liegen!")
                return None
            return start_dt, end_dt

        # ── Buttons ────────────────────────────────────────────────────
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=(4, 12))

        def on_update():
            """Ändern — overwrite existing entry."""
            activity = txt_var.get().strip()
            if not activity:
                lbl_error.config(
                    text="⚠ Bezeichnung darf nicht leer sein!")
                return
            times = _parse_times()
            if times is None:
                return
            start_dt, end_dt = times
            minutes = int((end_dt - start_dt).total_seconds() / 60)
            comment = comment_var.get().strip()
            dlg.destroy()
            self.engine.update_log_entry(
                sorted_index, activity=activity,
                list_name=item.list_name, priority=item.priority,
                minutes=minutes, started_at=start_dt,
                completed_at=end_dt, skipped=item.skipped,
                original_activity=item.original_activity,
                comment=comment)
            self._code_suggestor.learn(activity)
            self._refresh()

        def on_delete():
            """Löschen — remove entry."""
            name = _strip_task_code(item.activity)
            start_str = item.started_at.strftime('%H:%M')
            end_str = item.completed_at.strftime('%H:%M')
            answer = messagebox.askyesno(
                "Eintrag löschen",
                f"Eintrag '{name}' [{start_str}\u2013{end_str}] "
                f"wirklich löschen?",
                parent=dlg, icon="warning"
            )
            if answer:
                dlg.destroy()
                self.engine.delete_log_entry(sorted_index)
                self._refresh()

        def on_duplicate():
            """Duplizieren — save as new entry with (possibly modified) values."""
            activity = txt_var.get().strip()
            if not activity:
                lbl_error.config(
                    text="⚠ Bezeichnung darf nicht leer sein!")
                return
            times = _parse_times()
            if times is None:
                return
            start_dt, end_dt = times
            minutes = int((end_dt - start_dt).total_seconds() / 60)
            comment = comment_var.get().strip()
            dlg.destroy()
            self.engine.duplicate_log_entry(
                activity=activity, list_name=item.list_name,
                priority=item.priority, minutes=minutes,
                started_at=start_dt, completed_at=end_dt,
                skipped=item.skipped,
                original_activity=item.original_activity,
                comment=comment)
            self._code_suggestor.learn(activity)
            self._refresh()

        def on_cancel():
            dlg.destroy()

        tk.Button(
            btn_frame, text="  ✓ Ändern  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_DONE, fg="#1e1e2e", relief=tk.FLAT,
            cursor="hand2", command=on_update
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="  🗑 Löschen  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_SKIP, fg="#1e1e2e", relief=tk.FLAT,
            cursor="hand2", command=on_delete
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="  📋 Duplizieren  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_ACCENT, fg="#1e1e2e", relief=tk.FLAT,
            cursor="hand2", command=on_duplicate
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="  Abbrechen  ",
            font=("Segoe UI", 11),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            cursor="hand2", command=on_cancel
        ).pack(side=tk.LEFT, padx=4)

        # Keyboard shortcuts
        def _on_return(event):
            w = event.widget
            if isinstance(w, tk.Button):
                w.invoke()
            else:
                on_update()

        dlg.bind("<Return>", _on_return)
        dlg.bind("<Escape>", lambda e: on_cancel())

        # Center on parent
        dlg.update_idletasks()
        x = (self.root.winfo_x()
             + (self.root.winfo_width() - dlg.winfo_width()) // 2)
        y = (self.root.winfo_y()
             + (self.root.winfo_height() - dlg.winfo_height()) // 2)
        dlg.geometry(f"+{x}+{y}")

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
        # Stop window monitor cleanly
        if self._window_monitor is not None:
            try:
                self._window_monitor.stop()
            except Exception:
                pass
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





# ------------------------------------------------------------------ #
#  Utilities                                                           #
# ------------------------------------------------------------------ #

def _strip_task_code(name: str) -> str:
    """Remove trailing 6-char task code if present (e.g. ' LEMTAU')."""
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and len(parts[1]) == 6 and parts[1].isupper():
        return parts[0]
    return name
