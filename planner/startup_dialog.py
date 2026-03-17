"""
startup_dialog.py — Startup configuration dialog.

Asks user to confirm/override the auto-detected day type before
the main planner window opens.
"""
import tkinter as tk
from tkinter import ttk
from datetime import date
from typing import Optional, Dict, Any

from day_context import DayContext
from yaml_loader import load_exceptions_for_date

GERMAN_DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
               "Freitag", "Samstag", "Sonntag"]

COLOR_BG = "#1e1e2e"
COLOR_FG = "#cdd6f4"
COLOR_ACCENT = "#89b4fa"
COLOR_PANEL = "#181825"
COLOR_BTN = "#45475a"


class StartupDialog:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.result: Optional[DayContext] = None
        self.yaml_overrides: Dict[str, Any] = {}
        self._build()

    def _build(self):
        self.win = tk.Toplevel(self.root)
        self.win.title("Tagesplanung starten")
        self.win.configure(bg=COLOR_BG)
        self.win.resizable(False, False)
        self.win.grab_set()

        today = date.today()
        weekday = today.weekday()
        dayname = GERMAN_DAYS[weekday]

        # Load YAML overrides for today
        self.yaml_overrides = load_exceptions_for_date(today)
        yaml_dto = self.yaml_overrides.get("dayTypeOverride")
        yaml_note = self.yaml_overrides.get("specialNote")
        yaml_early = self.yaml_overrides.get("earlyWorkStart")
        self.yaml_putztag = self.yaml_overrides.get("putztag")  # True/False/None

        # Determine pre-fill values from YAML
        prefill_urlaubstag = (yaml_dto == "Urlaubstag")
        prefill_feiertag = (yaml_dto == "Feiertag")
        if yaml_dto in ("Bürotag", "Teleworking"):
            prefill_work_type = yaml_dto
        elif prefill_urlaubstag or prefill_feiertag:
            prefill_work_type = "auto"
        else:
            prefill_work_type = "auto"

        # Title
        tk.Label(
            self.win,
            text="Tagesplanung — Tageskonfiguration",
            font=("Segoe UI", 13, "bold"),
            bg=COLOR_BG, fg=COLOR_ACCENT, pady=10
        ).pack(padx=20)

        tk.Label(
            self.win,
            text=f"Heute: {today.strftime('%d.%m.%Y')} ({dayname})",
            font=("Segoe UI", 10),
            bg=COLOR_BG, fg=COLOR_FG
        ).pack()

        # Show YAML special note if present
        if yaml_note:
            tk.Label(
                self.win,
                text=f"📋 {yaml_note}",
                font=("Segoe UI", 9, "bold"),
                bg=COLOR_BG, fg="#f9e2af",
                wraplength=400, justify=tk.LEFT
            ).pack(padx=20, pady=(4, 0))

        # Show early work start note if present
        if yaml_early:
            tk.Label(
                self.win,
                text=f"⏰ Liste_Arbeit startet {yaml_early}h früher als normal",
                font=("Segoe UI", 9, "bold"),
                bg=COLOR_BG, fg="#f9e2af"
            ).pack(padx=20, pady=(4, 0))

        # Show YAML auto-detection hint
        if yaml_dto:
            tk.Label(
                self.win,
                text=f"(Aus YAML: {yaml_dto})",
                font=("Segoe UI", 8, "italic"),
                bg=COLOR_BG, fg="#6c7086"
            ).pack(padx=20, pady=(2, 0))

        # Frame for options
        frame = tk.Frame(self.win, bg=COLOR_PANEL, padx=16, pady=14)
        frame.pack(padx=20, pady=10, fill=tk.X)

        # Work type selector (only meaningful Mon–Fri)
        is_weekday = today.weekday() < 5
        wt_frame = tk.Frame(frame, bg=COLOR_PANEL)
        wt_frame.pack(anchor="w", pady=(0, 8))
        tk.Label(
            wt_frame, text="Arbeitstyp:",
            font=("Segoe UI", 10), bg=COLOR_PANEL, fg=COLOR_FG
        ).pack(side=tk.LEFT)
        self.var_work_type = tk.StringVar(value=prefill_work_type)
        wt_combo = ttk.Combobox(
            wt_frame, textvariable=self.var_work_type,
            values=["auto", "Bürotag", "Teleworking"],
            state="readonly" if is_weekday else "disabled",
            width=14, font=("Segoe UI", 10)
        )
        wt_combo.pack(side=tk.LEFT, padx=(8, 0))
        wt_combo.bind("<<ComboboxSelected>>", lambda *_: self._update_preview())

        # Feiertag checkbox
        self.var_feiertag = tk.BooleanVar(value=prefill_feiertag)
        tk.Checkbutton(
            frame, text="Feiertag", variable=self.var_feiertag,
            bg=COLOR_PANEL, fg=COLOR_FG, selectcolor=COLOR_BTN,
            activebackground=COLOR_PANEL, activeforeground=COLOR_FG,
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        # Urlaubstag checkbox
        self.var_urlaubstag = tk.BooleanVar(value=prefill_urlaubstag)
        tk.Checkbutton(
            frame, text="Urlaubstag", variable=self.var_urlaubstag,
            bg=COLOR_PANEL, fg=COLOR_FG, selectcolor=COLOR_BTN,
            activebackground=COLOR_PANEL, activeforeground=COLOR_FG,
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        # Day type preview label
        self.lbl_preview = tk.Label(
            self.win, text="", font=("Segoe UI", 9, "italic"),
            bg=COLOR_BG, fg=COLOR_FG
        )
        self.lbl_preview.pack()
        self._update_preview()

        # Bind updates to checkboxes
        self.var_feiertag.trace_add("write", lambda *_: self._update_preview())
        self.var_urlaubstag.trace_add("write", lambda *_: self._update_preview())

        # Buttons
        btn_frame = tk.Frame(self.win, bg=COLOR_BG)
        btn_frame.pack(pady=12)

        tk.Button(
            btn_frame, text="  Starten  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_ACCENT, fg="#1e1e2e",
            relief=tk.FLAT, bd=0, padx=16, pady=6,
            cursor="hand2", command=self._on_start
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="  Abbrechen  ",
            font=("Segoe UI", 11),
            bg=COLOR_BTN, fg=COLOR_FG,
            relief=tk.FLAT, bd=0, padx=16, pady=6,
            cursor="hand2", command=self._on_cancel
        ).pack(side=tk.LEFT)

        # Center on screen
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        self.win.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.root.wait_window(self.win)

    def _work_type_key(self) -> str:
        """Map combobox value to DayContext key."""
        val = self.var_work_type.get()
        if val == "Bürotag":
            return "burotag"
        elif val == "Teleworking":
            return "teleworking"
        return "auto"

    def _update_preview(self):
        ctx = DayContext.from_today(
            is_feiertag=self.var_feiertag.get(),
            is_urlaubstag=self.var_urlaubstag.get(),
            work_type_override=self._work_type_key(),
            putztag_override=self.yaml_putztag,
        )
        self.lbl_preview.config(text=f"Tagestyp: {ctx.describe()}")

    def _on_start(self):
        self.result = DayContext.from_today(
            is_feiertag=self.var_feiertag.get(),
            is_urlaubstag=self.var_urlaubstag.get(),
            work_type_override=self._work_type_key(),
            putztag_override=self.yaml_putztag,
        )
        self.win.destroy()

    def _on_cancel(self):
        self.result = None
        self.win.destroy()


def show_startup_dialog() -> 'Optional[tuple[DayContext, Dict[str, Any]]]':
    """Show the dialog and return (DayContext, yaml_overrides), or None if cancelled."""
    root = tk.Tk()
    root.withdraw()  # hide the empty root window
    dlg = StartupDialog(root)
    ctx = dlg.result
    yaml_overrides = dlg.yaml_overrides
    root.destroy()
    if ctx is None:
        return None
    return (ctx, yaml_overrides)
