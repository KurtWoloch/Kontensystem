"""
startup_dialog.py — Startup configuration dialog.

Asks user to confirm/override the auto-detected day type before
the main planner window opens.
"""
import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
from typing import Optional, Dict, Any
import re

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
        self.selected_date: date = date.today()
        self._build()

    def _build(self):
        self.win = tk.Toplevel(self.root)
        self.win.title("Tagesplanung starten")
        self.win.configure(bg=COLOR_BG)
        self.win.resizable(False, False)
        self.win.grab_set()

        self.selected_date = date.today()
        self._load_yaml_for_date(self.selected_date)

        # Title
        tk.Label(
            self.win,
            text="Tagesplanung — Tageskonfiguration",
            font=("Segoe UI", 13, "bold"),
            bg=COLOR_BG, fg=COLOR_ACCENT, pady=10
        ).pack(padx=20)

        # Date picker row
        date_frame = tk.Frame(self.win, bg=COLOR_BG)
        date_frame.pack(padx=20, pady=(4, 0))

        tk.Label(
            date_frame, text="Datum:",
            font=("Segoe UI", 10), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        tk.Button(
            date_frame, text="◀", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            width=2, cursor="hand2",
            command=self._date_prev
        ).pack(side=tk.LEFT, padx=(8, 2))

        self.var_date = tk.StringVar(
            value=self.selected_date.strftime("%d.%m.%Y"))
        self.date_entry = tk.Entry(
            date_frame, textvariable=self.var_date,
            font=("Segoe UI", 10), width=12, justify=tk.CENTER,
            bg=COLOR_PANEL, fg=COLOR_FG, insertbackground=COLOR_FG,
            relief=tk.FLAT
        )
        self.date_entry.pack(side=tk.LEFT, padx=2)
        self.date_entry.bind("<Return>", lambda *_: self._apply_date_from_entry())
        self.date_entry.bind("<FocusOut>", lambda *_: self._apply_date_from_entry())

        tk.Button(
            date_frame, text="▶", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            width=2, cursor="hand2",
            command=self._date_next
        ).pack(side=tk.LEFT, padx=(2, 4))

        tk.Button(
            date_frame, text="Heute", font=("Segoe UI", 9),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            padx=6, cursor="hand2",
            command=self._date_today
        ).pack(side=tk.LEFT, padx=(4, 0))

        # Day name + past-day indicator
        self.lbl_dayname = tk.Label(
            self.win, text="", font=("Segoe UI", 10),
            bg=COLOR_BG, fg=COLOR_FG
        )
        self.lbl_dayname.pack()

        # YAML info labels (dynamic — updated on date change)
        self.lbl_yaml_note = tk.Label(
            self.win, text="", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BG, fg="#f9e2af", wraplength=400, justify=tk.LEFT
        )
        self.lbl_yaml_note.pack(padx=20, pady=(4, 0))

        self.lbl_yaml_early = tk.Label(
            self.win, text="", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BG, fg="#f9e2af"
        )
        self.lbl_yaml_early.pack(padx=20, pady=(4, 0))

        self.lbl_yaml_dto = tk.Label(
            self.win, text="", font=("Segoe UI", 8, "italic"),
            bg=COLOR_BG, fg="#6c7086"
        )
        self.lbl_yaml_dto.pack(padx=20, pady=(2, 0))

        # Date validation error label
        self.lbl_date_error = tk.Label(
            self.win, text="", font=("Segoe UI", 8, "bold"),
            bg=COLOR_BG, fg="#f38ba8"
        )
        self.lbl_date_error.pack(padx=20, pady=(2, 0))

        self._update_date_display()

        # Frame for options
        frame = tk.Frame(self.win, bg=COLOR_PANEL, padx=16, pady=14)
        frame.pack(padx=20, pady=10, fill=tk.X)

        # Work type selector (only meaningful Mon–Fri)
        is_weekday = self.selected_date.weekday() < 5
        wt_frame = tk.Frame(frame, bg=COLOR_PANEL)
        wt_frame.pack(anchor="w", pady=(0, 8))
        tk.Label(
            wt_frame, text="Arbeitstyp:",
            font=("Segoe UI", 10), bg=COLOR_PANEL, fg=COLOR_FG
        ).pack(side=tk.LEFT)
        self.var_work_type = tk.StringVar(value=self._prefill_work_type)
        wt_combo = ttk.Combobox(
            wt_frame, textvariable=self.var_work_type,
            values=["auto", "Bürotag", "Teleworking"],
            state="readonly" if is_weekday else "disabled",
            width=14, font=("Segoe UI", 10)
        )
        wt_combo.pack(side=tk.LEFT, padx=(8, 0))
        wt_combo.bind("<<ComboboxSelected>>", lambda *_: self._update_preview())

        # Feiertag checkbox
        self.var_feiertag = tk.BooleanVar(value=self._prefill_feiertag)
        tk.Checkbutton(
            frame, text="Feiertag", variable=self.var_feiertag,
            bg=COLOR_PANEL, fg=COLOR_FG, selectcolor=COLOR_BTN,
            activebackground=COLOR_PANEL, activeforeground=COLOR_FG,
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        # Urlaubstag checkbox
        self.var_urlaubstag = tk.BooleanVar(value=self._prefill_urlaubstag)
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

    def _load_yaml_for_date(self, d: date):
        """Load YAML overrides for the given date and set prefill values."""
        self.yaml_overrides = load_exceptions_for_date(d)
        yaml_dto = self.yaml_overrides.get("dayTypeOverride")
        self.yaml_putztag = self.yaml_overrides.get("putztag")

        self._prefill_urlaubstag = (yaml_dto == "Urlaubstag")
        self._prefill_feiertag = (yaml_dto == "Feiertag")
        if yaml_dto in ("Bürotag", "Teleworking"):
            self._prefill_work_type = yaml_dto
        else:
            self._prefill_work_type = "auto"

    def _update_date_display(self):
        """Update all date-dependent labels and checkboxes."""
        d = self.selected_date
        dayname = GERMAN_DAYS[d.weekday()]
        is_past = d < date.today()
        is_today = d == date.today()

        # Day name label
        if is_today:
            self.lbl_dayname.config(
                text=f"Heute: {d.strftime('%d.%m.%Y')} ({dayname})",
                fg=COLOR_FG)
        elif is_past:
            self.lbl_dayname.config(
                text=f"{d.strftime('%d.%m.%Y')} ({dayname}) — Nacherfassung",
                fg="#fab387")  # orange for past days
        else:
            self.lbl_dayname.config(
                text=f"{d.strftime('%d.%m.%Y')} ({dayname}) — Zukunft",
                fg="#89b4fa")

        # YAML info
        yaml_note = self.yaml_overrides.get("specialNote")
        yaml_early = self.yaml_overrides.get("earlyWorkStart")
        yaml_dto = self.yaml_overrides.get("dayTypeOverride")

        self.lbl_yaml_note.config(
            text=f"📋 {yaml_note}" if yaml_note else "")
        self.lbl_yaml_early.config(
            text=f"⏰ Liste_Arbeit startet {yaml_early}h früher als normal"
            if yaml_early else "")
        self.lbl_yaml_dto.config(
            text=f"(Aus YAML: {yaml_dto})" if yaml_dto else "")

        self.lbl_date_error.config(text="")

        # Update checkboxes to YAML prefills for new date
        if hasattr(self, 'var_feiertag'):
            self.var_feiertag.set(self._prefill_feiertag)
        if hasattr(self, 'var_urlaubstag'):
            self.var_urlaubstag.set(self._prefill_urlaubstag)
        if hasattr(self, 'var_work_type'):
            self.var_work_type.set(self._prefill_work_type)

        self._update_preview()

    def _apply_date_from_entry(self):
        """Parse the date entry field and update selected_date."""
        raw = self.var_date.get().strip()
        m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', raw)
        if not m:
            self.lbl_date_error.config(text="Ungültiges Format (TT.MM.JJJJ)")
            return
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            self.lbl_date_error.config(text="Ungültiges Datum")
            return
        self._set_date(d)

    def _date_prev(self):
        self._set_date(self.selected_date - timedelta(days=1))

    def _date_next(self):
        self._set_date(self.selected_date + timedelta(days=1))

    def _date_today(self):
        self._set_date(date.today())

    def _set_date(self, d: date):
        """Set the selected date and refresh all dependent UI."""
        self.selected_date = d
        self.var_date.set(d.strftime("%d.%m.%Y"))
        self._load_yaml_for_date(d)
        self._update_date_display()

    def _update_preview(self):
        if not hasattr(self, 'lbl_preview'):
            return
        ctx = DayContext.from_date(
            self.selected_date,
            is_feiertag=self.var_feiertag.get() if hasattr(self, 'var_feiertag') else False,
            is_urlaubstag=self.var_urlaubstag.get() if hasattr(self, 'var_urlaubstag') else False,
            work_type_override=self._work_type_key() if hasattr(self, 'var_work_type') else "auto",
            putztag_override=self.yaml_putztag,
        )
        self.lbl_preview.config(text=f"Tagestyp: {ctx.describe()}")

    def _on_start(self):
        # Apply any pending date entry
        self._apply_date_from_entry()
        self.result = DayContext.from_date(
            self.selected_date,
            is_feiertag=self.var_feiertag.get(),
            is_urlaubstag=self.var_urlaubstag.get(),
            work_type_override=self._work_type_key(),
            putztag_override=self.yaml_putztag,
        )
        self.win.destroy()

    def _on_cancel(self):
        self.result = None
        self.win.destroy()


def show_startup_dialog() -> 'Optional[tuple[DayContext, Dict[str, Any], date]]':
    """Show the dialog and return (DayContext, yaml_overrides, selected_date), or None if cancelled."""
    root = tk.Tk()
    root.withdraw()  # hide the empty root window
    dlg = StartupDialog(root)
    ctx = dlg.result
    yaml_overrides = dlg.yaml_overrides
    selected_date = dlg.selected_date
    root.destroy()
    if ctx is None:
        return None
    return (ctx, yaml_overrides, selected_date)
