"""
windowmon_import.py — "Nacherfassung aus windowmon" import dialog.

Compares the planner log with the windowmon summary to find gaps,
proposes auto-classified entries, and lets the user review/edit/merge
them before importing into the planner log.

Workflow:
  1. Find time gaps in planner log
  2. Classify windowmon entries for those gaps
  3. Show proposal list (filter: >= 1 min duration)
  4. User reviews each: Accept / Edit / Ignore
  5. Optional: merge same-activity entries
  6. Import accepted entries into planner log
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Dict, Optional

from windowmon_logic import find_planner_gaps, get_windowmon_proposals, log_correction
from code_suggest import CodeSuggestor

# ── Theme (match gui.py) ──────────────────────────────────────────────── #
COLOR_BG = "#1e1e2e"
COLOR_FG = "#cdd6f4"
COLOR_ACCENT = "#89b4fa"
COLOR_DONE = "#a6e3a1"
COLOR_SKIP = "#f38ba8"
COLOR_WARN = "#f9e2af"
COLOR_PANEL = "#181825"
COLOR_LIST = "#313244"
COLOR_HEADER = "#89dceb"
COLOR_BTN = "#45475a"



# ═══════════════════════════════════════════════════════════════════════════ #
#  Raw windowmon viewer dialog                                               #
# ═══════════════════════════════════════════════════════════════════════════ #

def show_raw_windowmon(parent: tk.Toplevel, raw_entries: List[Dict],
                       start: datetime, end: datetime):
    """Show raw windowmon entries as a table for a time range."""
    dlg = tk.Toplevel(parent)
    dlg.title(f"windowmon {start.strftime('%H:%M')}-{end.strftime('%H:%M')}")
    dlg.configure(bg=COLOR_BG)
    dlg.geometry("750x400")
    dlg.transient(parent)
    dlg.grab_set()

    tk.Label(
        dlg, text=f"windowmon-Einträge {start.strftime('%H:%M:%S')} - "
                  f"{end.strftime('%H:%M:%S')} ({len(raw_entries)} Einträge)",
        font=("Segoe UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_HEADER,
        anchor="w", padx=8, pady=6
    ).pack(fill=tk.X)

    # Table frame with scrollbar
    table_frame = tk.Frame(dlg, bg=COLOR_BG)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
    listbox = tk.Listbox(
        table_frame, bg=COLOR_LIST, fg=COLOR_FG,
        font=("Consolas", 9), selectbackground=COLOR_ACCENT,
        relief=tk.FLAT, bd=0, activestyle="none",
        highlightthickness=0,
        yscrollcommand=scrollbar.set
    )
    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.pack(fill=tk.BOTH, expand=True)

    # Header
    header = f"{'Zeit':>8}  {'Prozess':<20} {'Browser':<8} {'Titel'}"
    listbox.insert(tk.END, header)
    listbox.insert(tk.END, "-" * 90)

    for entry in raw_entries:
        ts = entry["_ts"].strftime("%H:%M:%S")
        proc = entry.get("process", "")[:20]
        browser = entry.get("browser", "")[:8]
        title = entry.get("title", "")[:60]
        line = f"{ts:>8}  {proc:<20} {browser:<8} {title}"
        listbox.insert(tk.END, line)

    # Close button
    tk.Button(
        dlg, text="  ✗ Schließen  ", font=("Segoe UI", 10, "bold"),
        bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT, padx=12, pady=4,
        cursor="hand2", command=dlg.destroy
    ).pack(pady=(0, 8))


# ═══════════════════════════════════════════════════════════════════════════ #
#  Edit proposal dialog                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

def edit_proposal(parent: tk.Toplevel, proposal: Dict,
                  code_suggestor: Optional[CodeSuggestor] = None) -> bool:
    """Edit a single proposal. Returns True if user confirmed changes."""
    dlg = tk.Toplevel(parent)
    dlg.title("Vorschlag bearbeiten")
    dlg.configure(bg=COLOR_BG)
    dlg.geometry("550x420")
    dlg.transient(parent)
    dlg.grab_set()

    result = {"confirmed": False}

    # Activity name
    tk.Label(
        dlg, text="Aktivität:", font=("Segoe UI", 10),
        bg=COLOR_BG, fg=COLOR_FG, anchor="w"
    ).pack(fill=tk.X, padx=12, pady=(10, 2))

    activity_var = tk.StringVar(value=proposal["activity"])
    activity_entry = tk.Entry(
        dlg, textvariable=activity_var, font=("Consolas", 11),
        bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
        relief=tk.FLAT, bd=4
    )
    activity_entry.pack(fill=tk.X, padx=12)

    # Code suggestion
    suggest_frame = tk.Frame(dlg, bg=COLOR_BG)
    suggest_frame.pack(fill=tk.X, padx=12, pady=(2, 0))

    lbl_suggest = tk.Label(
        suggest_frame, text="", font=("Consolas", 9),
        bg=COLOR_BG, fg="#6c7086", anchor="w"
    )
    lbl_suggest.pack(side=tk.LEFT, fill=tk.X, expand=True)

    btn_use_suggest = tk.Button(
        suggest_frame, text="Name übernehmen",
        font=("Segoe UI", 9), bg=COLOR_BTN, fg=COLOR_FG,
        relief=tk.FLAT, cursor="hand2"
    )

    _suggest_match = {"name": "", "visible": False}

    def update_suggestion(*args):
        text = activity_var.get().strip()
        if code_suggestor and text:
            matches = code_suggestor.suggest(text)
            if matches:
                code, match_type, matched_name = matches[0]
                # Display format: "Name CODE" (standard Kontensystem format)
                display_name = f"{matched_name} {code}"
                lbl_suggest.config(text=f"-> {display_name}")
                _suggest_match["name"] = display_name
                if not _suggest_match["visible"]:
                    btn_use_suggest.pack(side=tk.RIGHT, padx=(4, 0))
                    _suggest_match["visible"] = True
                return
        lbl_suggest.config(text="")
        if _suggest_match["visible"]:
            btn_use_suggest.pack_forget()
            _suggest_match["visible"] = False

    def use_suggestion():
        if _suggest_match["name"]:
            activity_var.set(_suggest_match["name"])

    activity_var.trace_add("write", update_suggestion)
    btn_use_suggest.config(command=use_suggestion)
    update_suggestion()

    # Time fields (Spinbox — matching the standard planner dialog style)
    start_frame = tk.Frame(dlg, bg=COLOR_BG)
    start_frame.pack(fill=tk.X, padx=12, pady=(10, 0))

    tk.Label(start_frame, text="Begonnen um:  ",
             font=("Segoe UI", 10), bg=COLOR_BG, fg=COLOR_FG
             ).pack(side=tk.LEFT)
    start_h = tk.StringVar(value=f"{proposal['start'].hour:02d}")
    start_m = tk.StringVar(value=f"{proposal['start'].minute:02d}")
    tk.Spinbox(start_frame, from_=0, to=23, width=3, format="%02.0f",
               textvariable=start_h, font=("Consolas", 11),
               bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
               ).pack(side=tk.LEFT, padx=(8, 0))
    tk.Label(start_frame, text=":", font=("Consolas", 11),
             bg=COLOR_BG, fg=COLOR_FG).pack(side=tk.LEFT)
    tk.Spinbox(start_frame, from_=0, to=59, width=3, format="%02.0f",
               textvariable=start_m, font=("Consolas", 11),
               bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
               ).pack(side=tk.LEFT)

    end_frame = tk.Frame(dlg, bg=COLOR_BG)
    end_frame.pack(fill=tk.X, padx=12, pady=(4, 0))

    tk.Label(end_frame, text="Erledigt um:  ",
             font=("Segoe UI", 10), bg=COLOR_BG, fg=COLOR_FG
             ).pack(side=tk.LEFT)
    end_h = tk.StringVar(value=f"{proposal['end'].hour:02d}")
    end_m = tk.StringVar(value=f"{proposal['end'].minute:02d}")
    tk.Spinbox(end_frame, from_=0, to=23, width=3, format="%02.0f",
               textvariable=end_h, font=("Consolas", 11),
               bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
               ).pack(side=tk.LEFT, padx=(8, 0))
    tk.Label(end_frame, text=":", font=("Consolas", 11),
             bg=COLOR_BG, fg=COLOR_FG).pack(side=tk.LEFT)
    tk.Spinbox(end_frame, from_=0, to=59, width=3, format="%02.0f",
               textvariable=end_m, font=("Consolas", 11),
               bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN
               ).pack(side=tk.LEFT)

    # Comment
    tk.Label(
        dlg, text="Kommentar (optional):", font=("Segoe UI", 10),
        bg=COLOR_BG, fg=COLOR_FG, anchor="w"
    ).pack(fill=tk.X, padx=12, pady=(10, 2))

    comment_var = tk.StringVar(value=proposal.get("comment", ""))
    tk.Entry(
        dlg, textvariable=comment_var, font=("Consolas", 10),
        bg=COLOR_LIST, fg=COLOR_FG, insertbackground=COLOR_FG,
        relief=tk.FLAT, bd=4
    ).pack(fill=tk.X, padx=12)

    # Source info
    tk.Label(
        dlg, text=f"Quelle: {proposal['entry_count']} windowmon-Einträge, "
                  f"Original: {proposal['original_activity']}",
        font=("Segoe UI", 8), bg=COLOR_BG, fg="#6c7086", anchor="w"
    ).pack(fill=tk.X, padx=12, pady=(8, 0))

    # Error label
    lbl_error = tk.Label(dlg, text="", font=("Segoe UI", 9, "bold"),
                         bg=COLOR_BG, fg=COLOR_SKIP)
    lbl_error.pack(padx=12)

    # Buttons
    btn_row = tk.Frame(dlg, bg=COLOR_BG)
    btn_row.pack(pady=(8, 12))

    def on_view_raw():
        show_raw_windowmon(dlg, proposal["raw_entries"],
                           proposal["start"], proposal["end"])

    tk.Button(
        btn_row, text="  📋 windowmon anzeigen  ",
        font=("Segoe UI", 10), bg=COLOR_ACCENT, fg="#1e1e2e",
        relief=tk.FLAT, padx=8, pady=4, cursor="hand2",
        command=on_view_raw
    ).pack(side=tk.LEFT, padx=(0, 8))

    def on_confirm():
        try:
            sh = int(start_h.get())
            sm = int(start_m.get())
            eh = int(end_h.get())
            em = int(end_m.get())
            new_start = proposal["start"].replace(hour=sh, minute=sm,
                                                   second=0)
            new_end = proposal["end"].replace(hour=eh, minute=em,
                                               second=0)
            if new_end <= new_start:
                lbl_error.config(text="Ende muss nach Beginn liegen!")
                return
        except ValueError:
            lbl_error.config(text="Ungültige Zeitangabe!")
            return

        new_activity = activity_var.get().strip()
        if not new_activity:
            lbl_error.config(text="Aktivität darf nicht leer sein!")
            return

        proposal["activity"] = new_activity
        proposal["start"] = new_start
        proposal["end"] = new_end
        proposal["duration_min"] = (new_end - new_start).total_seconds() / 60
        proposal["comment"] = comment_var.get().strip()
        proposal["status"] = "edited"
        result["confirmed"] = True
        dlg.destroy()

    tk.Button(
        btn_row, text="  ✓ Übernehmen  ",
        font=("Segoe UI", 10, "bold"), bg=COLOR_DONE, fg="#1e1e2e",
        relief=tk.FLAT, padx=12, pady=4, cursor="hand2",
        command=on_confirm
    ).pack(side=tk.LEFT, padx=(0, 4))

    tk.Button(
        btn_row, text="  ✗ Abbrechen  ",
        font=("Segoe UI", 10), bg=COLOR_BTN, fg=COLOR_FG,
        relief=tk.FLAT, padx=12, pady=4, cursor="hand2",
        command=dlg.destroy
    ).pack(side=tk.LEFT)

    dlg.wait_window()
    return result["confirmed"]


# ═══════════════════════════════════════════════════════════════════════════ #
#  Main Import Dialog                                                        #
# ═══════════════════════════════════════════════════════════════════════════ #

def open_import_dialog(root: tk.Tk, engine, code_suggestor=None):
    """Open the windowmon import dialog.

    Args:
        root: main tkinter root window
        engine: PlannerEngine instance
        code_suggestor: optional CodeSuggestor for task code hints
    """
    date_str = engine.session_date.strftime("%Y-%m-%d")

    # ── Gather data ────────────────────────────────────────────────────
    completed = engine.get_completed_log()

    # Determine day boundaries from log or defaults
    # For past days, use 23:59 of that day as the end boundary
    is_past = engine.session_date < datetime.now().date()
    if completed:
        sorted_log = sorted(completed, key=lambda c: c.started_at)
        day_start = sorted_log[0].started_at.replace(second=0, microsecond=0)
        if is_past:
            day_end = datetime.combine(engine.session_date,
                                       datetime.min.time()).replace(
                hour=23, minute=59, second=0, microsecond=0)
        else:
            day_end = datetime.now().replace(second=0, microsecond=0)
    else:
        if is_past:
            base = datetime.combine(engine.session_date,
                                    datetime.min.time())
        else:
            base = datetime.now()
        day_start = base.replace(hour=6, minute=0, second=0, microsecond=0)
        day_end = base.replace(hour=23, minute=59, second=0, microsecond=0) if is_past else base.replace(second=0, microsecond=0)

    gaps = find_planner_gaps(completed, day_start, day_end)
    proposals = get_windowmon_proposals(date_str, gaps, completed=completed)

    if not proposals:
        messagebox.showinfo(
            "Nacherfassung aus windowmon",
            "Keine Vorschläge gefunden.\n\n"
            "Entweder gibt es keine Lücken im Planer-Log, "
            "oder keine windowmon-Einträge für die Lücken."
        )
        return

    # ── Build dialog ───────────────────────────────────────────────────
    dlg = tk.Toplevel(root)
    dlg.title(f"Nacherfassung aus windowmon - {date_str}")
    dlg.configure(bg=COLOR_BG)
    dlg.geometry("820x600")
    dlg.transient(root)
    dlg.grab_set()

    # Header
    tk.Label(
        dlg, text=f"Nacherfassung aus windowmon",
        font=("Segoe UI", 14, "bold"), bg=COLOR_BG, fg=COLOR_HEADER,
        anchor="w", padx=10, pady=6
    ).pack(fill=tk.X)

    tk.Label(
        dlg, text=f"{len(proposals)} Vorschläge aus {len(gaps)} Lücken  "
                  f"(nur Blöcke >= 1 Min.)",
        font=("Segoe UI", 9), bg=COLOR_BG, fg="#6c7086",
        anchor="w", padx=10
    ).pack(fill=tk.X)

    # ── Proposal list ──────────────────────────────────────────────────
    list_frame = tk.Frame(dlg, bg=COLOR_PANEL)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))

    # Canvas + scrollbar for proposal cards
    canvas = tk.Canvas(list_frame, bg=COLOR_PANEL, highlightthickness=0)
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                               command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg=COLOR_PANEL)

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(fill=tk.BOTH, expand=True)

    # Mouse wheel scrolling (guard against destroyed widget)
    def _on_mousewheel(event):
        try:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            pass  # canvas already destroyed
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # Status tracking
    status_var = tk.StringVar(value="")

    def update_status():
        accepted = sum(1 for p in proposals
                       if p["status"] in ("accepted", "edited"))
        ignored = sum(1 for p in proposals if p["status"] == "ignored")
        pending = sum(1 for p in proposals if p["status"] == "pending")
        status_var.set(
            f"Akzeptiert: {accepted}  |  Ignoriert: {ignored}  |  "
            f"Offen: {pending}"
        )

    def build_proposal_rows():
        """Build or rebuild the proposal cards in the scroll frame."""
        # Preserve scroll position across rebuilds
        try:
            scroll_pos = canvas.yview()[0]
        except Exception:
            scroll_pos = 0.0

        for widget in scroll_frame.winfo_children():
            widget.destroy()

        for i, prop in enumerate(proposals):
            row_bg = COLOR_LIST if prop["status"] == "pending" else (
                "#2a4028" if prop["status"] in ("accepted", "edited")
                else "#402828" if prop["status"] == "ignored"
                else COLOR_LIST
            )

            row = tk.Frame(scroll_frame, bg=row_bg, relief=tk.FLAT, bd=1)
            row.pack(fill=tk.X, padx=4, pady=2)

            # Time + duration
            time_str = (f"{prop['start'].strftime('%H:%M')} - "
                        f"{prop['end'].strftime('%H:%M')}")
            dur_str = f"{prop['duration_min']:.0f} Min."

            tk.Label(
                row, text=f"{time_str}  ({dur_str})",
                font=("Consolas", 10, "bold"), bg=row_bg, fg=COLOR_ACCENT,
                anchor="w", padx=6, pady=2
            ).pack(fill=tk.X)

            # Activity + account
            acct = prop["account"]
            activity = prop["activity"]
            status_icon = {
                "pending": "",
                "accepted": " ✓",
                "edited": " ✏",
                "ignored": " ✗",
            }.get(prop["status"], "")

            tk.Label(
                row, text=f"{acct} / {activity}{status_icon}",
                font=("Segoe UI", 10), bg=row_bg, fg=COLOR_FG,
                anchor="w", padx=6
            ).pack(fill=tk.X)

            # Source info
            source_text = f"{prop['entry_count']} Einträge"
            if prop.get("planner_context"):
                source_text += "  ← aus Planer-Aktivität"
            elif prop.get("original_activity") != prop.get("activity"):
                source_text += f"  (AutoDetect: {prop['original_activity']})"
            tk.Label(
                row, text=source_text,
                font=("Segoe UI", 8), bg=row_bg, fg="#6c7086",
                anchor="w", padx=6
            ).pack(fill=tk.X)

            # Action buttons
            btn_row = tk.Frame(row, bg=row_bg)
            btn_row.pack(fill=tk.X, padx=4, pady=(2, 4))

            idx = i  # capture for closures

            def make_accept(j=idx):
                def fn():
                    proposals[j]["status"] = "accepted"
                    update_status()
                    build_proposal_rows()
                return fn

            def make_edit(j=idx):
                def fn():
                    confirmed = edit_proposal(dlg, proposals[j],
                                               code_suggestor)
                    if confirmed:
                        log_correction(
                            date_str,
                            proposals[j]["original_activity"],
                            proposals[j]["activity"],
                            proposals[j]["start"],
                            proposals[j]["end"],
                        )
                    update_status()
                    build_proposal_rows()
                return fn

            def make_ignore(j=idx):
                def fn():
                    proposals[j]["status"] = "ignored"
                    update_status()
                    build_proposal_rows()
                return fn

            def make_view_raw(j=idx):
                def fn():
                    show_raw_windowmon(dlg, proposals[j]["raw_entries"],
                                       proposals[j]["start"],
                                       proposals[j]["end"])
                return fn

            btn_cfg = dict(font=("Segoe UI", 10), relief=tk.FLAT,
                           padx=6, pady=1, cursor="hand2")

            if prop["status"] == "pending":
                tk.Button(btn_row, text="  ✓ Übernehmen  ",
                          bg=COLOR_DONE, fg="#1e1e2e",
                          command=make_accept(), **btn_cfg
                          ).pack(side=tk.LEFT, padx=(0, 3))
                tk.Button(btn_row, text="  ✏ Bearbeiten  ",
                          bg=COLOR_WARN, fg="#1e1e2e",
                          command=make_edit(), **btn_cfg
                          ).pack(side=tk.LEFT, padx=(0, 3))
                tk.Button(btn_row, text="  ✗ Ignorieren  ",
                          bg=COLOR_SKIP, fg="#1e1e2e",
                          command=make_ignore(), **btn_cfg
                          ).pack(side=tk.LEFT, padx=(0, 3))
            else:
                # Allow re-editing or resetting
                tk.Button(btn_row, text="  ✏ Bearbeiten  ",
                          bg=COLOR_WARN, fg="#1e1e2e",
                          command=make_edit(), **btn_cfg
                          ).pack(side=tk.LEFT, padx=(0, 3))
                def make_reset(j=idx):
                    def fn():
                        proposals[j]["status"] = "pending"
                        update_status()
                        build_proposal_rows()
                    return fn
                tk.Button(btn_row, text="  ↩ Zurücksetzen  ",
                          bg=COLOR_BTN, fg=COLOR_FG,
                          command=make_reset(), **btn_cfg
                          ).pack(side=tk.LEFT, padx=(0, 3))

            # Always show raw view button
            tk.Button(btn_row, text="  📋 windowmon  ",
                      bg=COLOR_ACCENT, fg="#1e1e2e",
                      command=make_view_raw(), **btn_cfg
                      ).pack(side=tk.RIGHT)

        # Restore scroll position after rebuild
        scroll_frame.update_idletasks()
        canvas.yview_moveto(scroll_pos)

    build_proposal_rows()
    update_status()

    # ── Bottom bar ─────────────────────────────────────────────────────
    bottom = tk.Frame(dlg, bg=COLOR_BG)
    bottom.pack(fill=tk.X, padx=8, pady=(6, 8))

    lbl_status = tk.Label(
        bottom, textvariable=status_var,
        font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
    )
    lbl_status.pack(side=tk.LEFT)

    def on_merge():
        """Merge accepted/edited entries with same activity name."""
        to_merge = [p for p in proposals
                    if p["status"] in ("accepted", "edited")]
        if len(to_merge) < 2:
            messagebox.showinfo("Zusammenfassen",
                                "Weniger als 2 akzeptierte Einträge — "
                                "nichts zum Zusammenfassen.")
            return

        # Group by activity name
        groups = {}
        for p in to_merge:
            key = p["activity"]
            if key not in groups:
                groups[key] = []
            groups[key].append(p)

        merge_count = 0
        for key, group in groups.items():
            if len(group) < 2:
                continue
            # Keep the first, merge others into it
            first = group[0]
            for other in group[1:]:
                first["start"] = min(first["start"], other["start"])
                first["end"] = max(first["end"], other["end"])
                first["duration_min"] += other["duration_min"]
                first["entry_count"] += other["entry_count"]
                first["raw_entries"] = (first["raw_entries"] +
                                         other["raw_entries"])
                # Remove merged entry from proposals
                other["status"] = "_merged"
                merge_count += 1

        # Remove merged entries
        proposals[:] = [p for p in proposals if p["status"] != "_merged"]

        if merge_count > 0:
            messagebox.showinfo(
                "Zusammengefasst",
                f"{merge_count} Einträge zusammengefasst."
            )
        build_proposal_rows()
        update_status()

    def on_import():
        """Import all accepted/edited entries into the planner log."""
        to_import = [p for p in proposals
                     if p["status"] in ("accepted", "edited")]
        if not to_import:
            messagebox.showwarning("Import",
                                    "Keine akzeptierten Einträge zum Import.")
            return

        answer = messagebox.askyesno(
            "Import bestätigen",
            f"{len(to_import)} Einträge ins Planer-Log importieren?"
        )
        if not answer:
            return

        for p in to_import:
            engine.log_adhoc(
                activity=p["activity"],
                start_time=p["start"],
                end_time=p["end"],
                list_name="windowmon_import",
                comment=p.get("comment", ""),
            )

        engine.save_log()
        messagebox.showinfo(
            "Import abgeschlossen",
            f"{len(to_import)} Einträge importiert und Log gespeichert."
        )
        dlg.destroy()

    tk.Button(
        bottom, text="  🔗 Gleiche zusammenfassen  ",
        font=("Segoe UI", 10, "bold"), bg=COLOR_WARN, fg="#1e1e2e",
        relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
        command=on_merge
    ).pack(side=tk.RIGHT, padx=(4, 0))

    tk.Button(
        bottom, text="  ✓ Importieren  ",
        font=("Segoe UI", 10, "bold"), bg=COLOR_DONE, fg="#1e1e2e",
        relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
        command=on_import
    ).pack(side=tk.RIGHT, padx=(4, 0))

    tk.Button(
        bottom, text="  ✗ Abbrechen  ",
        font=("Segoe UI", 10), bg=COLOR_BTN, fg=COLOR_FG,
        relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
        command=dlg.destroy
    ).pack(side=tk.RIGHT)

    # Unbind mousewheel on close
    def on_close():
        canvas.unbind_all("<MouseWheel>")
        dlg.destroy()

    dlg.protocol("WM_DELETE_WINDOW", on_close)
