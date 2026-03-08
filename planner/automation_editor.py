"""
automation_editor.py — tkinter editor for task automations.

Opens as a dialog from the planner or standalone.
Allows creating, editing, and deleting automation entries
in data/automations.json, with task picking from the master task list.
"""
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Optional

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
AUTOMATIONS_PATH = os.path.join(DATA_DIR, "automations.json")
MASTER_TASK_LIST = os.path.join(DATA_DIR, "master_task_list_v4.jsonl")

# Theme — matches planner gui.py
COLOR_BG = "#1e1e2e"
COLOR_FG = "#cdd6f4"
COLOR_ACCENT = "#89b4fa"
COLOR_DONE = "#a6e3a1"
COLOR_SKIP = "#f38ba8"
COLOR_PANEL = "#181825"
COLOR_LIST = "#313244"
COLOR_HEADER = "#89dceb"
COLOR_BTN = "#45475a"
COLOR_WARN = "#f9e2af"


# ------------------------------------------------------------------ #
#  Data I/O                                                            #
# ------------------------------------------------------------------ #

def _load_automations() -> List[Dict[str, Any]]:
    if not os.path.exists(AUTOMATIONS_PATH):
        return []
    try:
        with open(AUTOMATIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("automations", [])
    except (json.JSONDecodeError, OSError):
        return []


def _save_automations(automations: List[Dict[str, Any]]):
    data = {
        "_comment": (
            "Maps task codes or activity name prefixes to automations. "
            "type: 'shell' (run command) or 'url' (open in browser)."
        ),
        "automations": automations,
    }
    tmp = AUTOMATIONS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, AUTOMATIONS_PATH)


def _load_tasks() -> List[Dict[str, Any]]:
    """Load tasks from master task list for the picker."""
    tasks = []
    if not os.path.exists(MASTER_TASK_LIST):
        return tasks
    try:
        with open(MASTER_TASK_LIST, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tasks.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return tasks


# ------------------------------------------------------------------ #
#  Main Editor Window                                                  #
# ------------------------------------------------------------------ #

class AutomationEditor:
    """Editor for automations.json — can be opened as a Toplevel or root."""

    def __init__(self, parent: Optional[tk.Tk] = None):
        if parent:
            self.win = tk.Toplevel(parent)
        else:
            self.win = tk.Tk()
        self.win.title("Automationen verwalten")
        self.win.configure(bg=COLOR_BG)
        self.win.geometry("820x520")
        self.win.minsize(700, 400)

        self._automations = _load_automations()
        self._tasks = _load_tasks()
        self._dirty = False

        self._build_ui()
        self._populate_list()

        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- #
    #  UI                                                               #
    # ---------------------------------------------------------------- #

    def _build_ui(self):
        # ── Title bar ─────────────────────────────────────────────────
        top = tk.Frame(self.win, bg=COLOR_BG)
        top.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Label(
            top, text="⚡ Automationen", font=("Segoe UI", 14, "bold"),
            bg=COLOR_BG, fg=COLOR_ACCENT
        ).pack(side=tk.LEFT)

        tk.Label(
            top, text=f"({len(self._automations)} Einträge)",
            font=("Segoe UI", 10), bg=COLOR_BG, fg="#6c7086"
        ).pack(side=tk.LEFT, padx=(10, 0))
        self._lbl_count = top.winfo_children()[-1]

        # ── Main list ─────────────────────────────────────────────────
        list_frame = tk.Frame(self.win, bg=COLOR_PANEL)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 6))

        cols = ("task", "type", "command", "label")
        self.tree = ttk.Treeview(
            list_frame, columns=cols, show="headings",
            selectmode="browse", height=12
        )

        # Style the treeview to match dark theme
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=COLOR_LIST, foreground=COLOR_FG,
                        fieldbackground=COLOR_LIST,
                        font=("Segoe UI", 9),
                        rowheight=26)
        style.configure("Treeview.Heading",
                        background=COLOR_BTN, foreground=COLOR_HEADER,
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                   background=[("selected", COLOR_ACCENT)],
                   foreground=[("selected", "#1e1e2e")])

        self.tree.heading("task", text="Aufgabe / Code")
        self.tree.heading("type", text="Typ")
        self.tree.heading("command", text="Befehl / URL")
        self.tree.heading("label", text="Button-Text")

        self.tree.column("task", width=200, minwidth=120)
        self.tree.column("type", width=60, minwidth=50)
        self.tree.column("command", width=360, minwidth=150)
        self.tree.column("label", width=160, minwidth=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<Double-1>", lambda e: self._on_edit())

        # ── Buttons ───────────────────────────────────────────────────
        btn_frame = tk.Frame(self.win, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        btn_cfg = dict(font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
                       bd=0, padx=12, pady=5, cursor="hand2")

        tk.Button(
            btn_frame, text="➕ Neu", bg=COLOR_DONE, fg="#1e1e2e",
            command=self._on_add, **btn_cfg
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            btn_frame, text="✏️ Bearbeiten", bg=COLOR_ACCENT, fg="#1e1e2e",
            command=self._on_edit, **btn_cfg
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            btn_frame, text="🗑️ Löschen", bg=COLOR_SKIP, fg="#1e1e2e",
            command=self._on_delete, **btn_cfg
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            btn_frame, text="💾 Speichern", bg=COLOR_LIST, fg=COLOR_FG,
            command=self._on_save, **btn_cfg
        ).pack(side=tk.RIGHT)

    def _populate_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, auto in enumerate(self._automations):
            match_display = auto.get("match", "")
            match_type = auto.get("match_type", "code")
            if match_type != "code":
                match_display = f"[{match_type}] {match_display}"
            auto_type = auto.get("type", "shell")
            cmd = auto.get("command", "") or auto.get("url", "")
            label = auto.get("label", "")
            self.tree.insert("", tk.END, iid=str(i),
                             values=(match_display, auto_type, cmd, label))
        self._lbl_count.config(text=f"({len(self._automations)} Einträge)")

    def _get_selected_index(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    # ---------------------------------------------------------------- #
    #  CRUD handlers                                                    #
    # ---------------------------------------------------------------- #

    def _on_add(self):
        dlg = _AutomationDialog(self.win, self._tasks, title="Neue Automation")
        self.win.wait_window(dlg.dlg)
        if dlg.result:
            self._automations.append(dlg.result)
            self._dirty = True
            self._populate_list()

    def _on_edit(self):
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag auswählen.")
            return
        existing = self._automations[idx]
        dlg = _AutomationDialog(self.win, self._tasks,
                                title="Automation bearbeiten",
                                existing=existing)
        self.win.wait_window(dlg.dlg)
        if dlg.result:
            self._automations[idx] = dlg.result
            self._dirty = True
            self._populate_list()

    def _on_delete(self):
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag auswählen.")
            return
        auto = self._automations[idx]
        match = auto.get("match", "?")
        if not messagebox.askyesno(
            "Löschen bestätigen",
            f"Automation für '{match}' wirklich löschen?"
        ):
            return
        del self._automations[idx]
        self._dirty = True
        self._populate_list()

    def _on_save(self):
        _save_automations(self._automations)
        self._dirty = False
        messagebox.showinfo("Gespeichert",
                            f"Automationen gespeichert.\n{AUTOMATIONS_PATH}")

    def _on_close(self):
        if self._dirty:
            answer = messagebox.askyesnocancel(
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen.\n"
                "Vor dem Schließen speichern?",
                icon="warning"
            )
            if answer is None:
                return  # cancel
            if answer:
                _save_automations(self._automations)
        self.win.destroy()


# ------------------------------------------------------------------ #
#  Add / Edit Dialog                                                   #
# ------------------------------------------------------------------ #

class _AutomationDialog:
    """Modal dialog for creating or editing a single automation entry."""

    def __init__(self, parent, tasks: List[Dict],
                 title: str = "Automation",
                 existing: Optional[Dict] = None):
        self.result: Optional[Dict] = None
        self._tasks = tasks

        self.dlg = tk.Toplevel(parent)
        self.dlg.title(title)
        self.dlg.configure(bg=COLOR_BG)
        self.dlg.resizable(False, False)
        self.dlg.grab_set()
        self.dlg.transient(parent)

        self._build(existing)

        # Center
        self.dlg.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() -
                                  self.dlg.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() -
                                  self.dlg.winfo_height()) // 2
        self.dlg.geometry(f"+{x}+{y}")

    def _build(self, existing: Optional[Dict]):
        pad = dict(padx=12, pady=(4, 2))
        entry_cfg = dict(font=("Segoe UI", 10), bg=COLOR_LIST,
                         fg=COLOR_FG, insertbackground=COLOR_FG)

        # ── Section 1: Task picker ────────────────────────────────────
        tk.Label(
            self.dlg, text="Aufgabe auswählen:",
            font=("Segoe UI", 9, "bold"), bg=COLOR_BG, fg=COLOR_HEADER
        ).pack(anchor="w", **pad)

        # Search field
        search_frame = tk.Frame(self.dlg, bg=COLOR_BG)
        search_frame.pack(fill=tk.X, padx=12, pady=(0, 2))

        tk.Label(
            search_frame, text="🔍", font=("Segoe UI", 10),
            bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(
            search_frame, textvariable=self._search_var,
            width=55, **entry_cfg
        )
        self._search_entry.pack(side=tk.LEFT, padx=(4, 0), fill=tk.X,
                                expand=True)
        self._search_var.trace_add("write", self._on_search)

        # Task listbox
        task_frame = tk.Frame(self.dlg, bg=COLOR_LIST)
        task_frame.pack(fill=tk.BOTH, padx=12, pady=(0, 6), expand=True)

        self._task_listbox = tk.Listbox(
            task_frame, bg=COLOR_LIST, fg=COLOR_FG,
            font=("Consolas", 9), selectbackground=COLOR_ACCENT,
            selectforeground="#1e1e2e",
            relief=tk.FLAT, height=8, activestyle="none",
            highlightthickness=0, exportselection=False
        )
        task_scroll = ttk.Scrollbar(task_frame, orient=tk.VERTICAL,
                                    command=self._task_listbox.yview)
        self._task_listbox.configure(yscrollcommand=task_scroll.set)
        task_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._task_listbox.pack(fill=tk.BOTH, expand=True)
        self._task_listbox.bind("<<ListboxSelect>>", self._on_task_select)

        # Build display list of tasks (filtered later by search)
        self._task_display: List[Dict] = []
        self._populate_task_list("")

        # Selected task info
        self._lbl_selected = tk.Label(
            self.dlg, text="Kein Task ausgewählt",
            font=("Segoe UI", 8, "italic"), bg=COLOR_BG, fg="#6c7086"
        )
        self._lbl_selected.pack(anchor="w", padx=12, pady=(0, 6))

        # ── Section 2: Match settings ─────────────────────────────────
        match_frame = tk.Frame(self.dlg, bg=COLOR_BG)
        match_frame.pack(fill=tk.X, padx=12, pady=(2, 2))

        tk.Label(
            match_frame, text="Zuordnung:",
            font=("Segoe UI", 9, "bold"), bg=COLOR_BG, fg=COLOR_HEADER
        ).pack(side=tk.LEFT)

        self._match_type_var = tk.StringVar(
            value=existing.get("match_type", "code") if existing else "code"
        )
        for val, label in [("code", "Code"), ("prefix", "Prefix"),
                           ("contains", "Enthält")]:
            tk.Radiobutton(
                match_frame, text=label, variable=self._match_type_var,
                value=val, font=("Segoe UI", 9),
                bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_LIST,
                activebackground=COLOR_BG, activeforeground=COLOR_FG
            ).pack(side=tk.LEFT, padx=(10, 0))

        # Match value (auto-filled from task selection, but editable)
        mv_frame = tk.Frame(self.dlg, bg=COLOR_BG)
        mv_frame.pack(fill=tk.X, padx=12, pady=(2, 6))

        tk.Label(
            mv_frame, text="Match-Wert:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        self._match_var = tk.StringVar(
            value=existing.get("match", "") if existing else ""
        )
        tk.Entry(
            mv_frame, textvariable=self._match_var, width=30, **entry_cfg
        ).pack(side=tk.LEFT, padx=(8, 0))

        # ── Section 3: Automation type ────────────────────────────────
        type_frame = tk.Frame(self.dlg, bg=COLOR_BG)
        type_frame.pack(fill=tk.X, padx=12, pady=(2, 2))

        tk.Label(
            type_frame, text="Typ:",
            font=("Segoe UI", 9, "bold"), bg=COLOR_BG, fg=COLOR_HEADER
        ).pack(side=tk.LEFT)

        self._type_var = tk.StringVar(
            value=existing.get("type", "shell") if existing else "shell"
        )
        tk.Radiobutton(
            type_frame, text="Shell (Programm/Befehl)",
            variable=self._type_var, value="shell",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG,
            selectcolor=COLOR_LIST,
            activebackground=COLOR_BG, activeforeground=COLOR_FG,
            command=self._on_type_change
        ).pack(side=tk.LEFT, padx=(10, 0))

        tk.Radiobutton(
            type_frame, text="URL (Browser)",
            variable=self._type_var, value="url",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG,
            selectcolor=COLOR_LIST,
            activebackground=COLOR_BG, activeforeground=COLOR_FG,
            command=self._on_type_change
        ).pack(side=tk.LEFT, padx=(10, 0))

        # ── Section 4: Command / URL ──────────────────────────────────
        cmd_frame = tk.Frame(self.dlg, bg=COLOR_BG)
        cmd_frame.pack(fill=tk.X, padx=12, pady=(2, 2))

        self._lbl_cmd = tk.Label(
            cmd_frame, text="Befehl:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        )
        self._lbl_cmd.pack(side=tk.LEFT)

        self._cmd_var = tk.StringVar(
            value=(existing.get("command", "") or existing.get("url", ""))
            if existing else ""
        )
        self._cmd_entry = tk.Entry(
            cmd_frame, textvariable=self._cmd_var, width=50, **entry_cfg
        )
        self._cmd_entry.pack(side=tk.LEFT, padx=(8, 4), fill=tk.X,
                             expand=True)

        self._btn_browse = tk.Button(
            cmd_frame, text="📂", font=("Segoe UI", 10),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            cursor="hand2", command=self._on_browse
        )
        self._btn_browse.pack(side=tk.LEFT)

        # ── Section 5: Label ──────────────────────────────────────────
        lbl_frame = tk.Frame(self.dlg, bg=COLOR_BG)
        lbl_frame.pack(fill=tk.X, padx=12, pady=(6, 2))

        tk.Label(
            lbl_frame, text="Button-Text:",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_FG
        ).pack(side=tk.LEFT)

        self._label_var = tk.StringVar(
            value=existing.get("label", "") if existing else ""
        )
        tk.Entry(
            lbl_frame, textvariable=self._label_var, width=40, **entry_cfg
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(
            lbl_frame, text="(wird im Planer als \"▶ ...\" angezeigt)",
            font=("Segoe UI", 8, "italic"), bg=COLOR_BG, fg="#6c7086"
        ).pack(side=tk.LEFT, padx=(8, 0))

        # ── Validation message ────────────────────────────────────────
        self._lbl_error = tk.Label(
            self.dlg, text="", font=("Segoe UI", 9, "bold"),
            bg=COLOR_BG, fg=COLOR_SKIP
        )
        self._lbl_error.pack(padx=12, pady=(4, 0))

        # ── Buttons ──────────────────────────────────────────────────
        btn_frame = tk.Frame(self.dlg, bg=COLOR_BG)
        btn_frame.pack(pady=(6, 12))

        tk.Button(
            btn_frame, text="  ✓ Übernehmen  ",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_DONE, fg="#1e1e2e", relief=tk.FLAT,
            cursor="hand2", command=self._on_confirm
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="  Abbrechen  ",
            font=("Segoe UI", 11),
            bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT,
            cursor="hand2", command=self._on_cancel
        ).pack(side=tk.LEFT, padx=4)

        self.dlg.bind("<Escape>", lambda e: self._on_cancel())

        # Apply initial type state
        self._on_type_change()

        # If editing, try to highlight the matching task in the list
        if existing:
            self._search_entry.focus_set()
        else:
            self._search_entry.focus_set()

    # ---------------------------------------------------------------- #
    #  Task list                                                        #
    # ---------------------------------------------------------------- #

    def _populate_task_list(self, query: str):
        self._task_listbox.delete(0, tk.END)
        self._task_display = []
        q = query.lower().strip()

        for t in self._tasks:
            name = t.get("name", "")
            code = t.get("code", "")
            display = f"{name}"
            if code:
                display += f"  [{code}]"

            if q and q not in display.lower():
                continue

            self._task_display.append(t)
            self._task_listbox.insert(tk.END, display)

    def _on_search(self, *_args):
        self._populate_task_list(self._search_var.get())

    def _on_task_select(self, _event):
        sel = self._task_listbox.curselection()
        if not sel:
            return
        task = self._task_display[sel[0]]
        code = task.get("code", "")
        name = task.get("name", "")
        list_name = task.get("list", "")
        prio = task.get("priority", 0)

        info = name
        if code:
            info += f"  •  Code: {code}"
        if list_name:
            info += f"  •  Liste: {list_name}"
        if prio:
            info += f"  •  Prio: {prio}"
        self._lbl_selected.config(text=info, fg=COLOR_DONE)

        # Auto-fill match value
        if code and self._match_type_var.get() == "code":
            self._match_var.set(code)
        elif not code:
            # No code — switch to prefix match
            self._match_type_var.set("prefix")
            self._match_var.set(name)

        # Auto-suggest label from task name if empty
        if not self._label_var.get():
            # Use a short version of the name
            short = name.split("/")[0].strip() if "/" in name else name
            if len(short) > 40:
                short = short[:37] + "…"
            self._label_var.set(f"{short} starten")

    # ---------------------------------------------------------------- #
    #  Type switching                                                   #
    # ---------------------------------------------------------------- #

    def _on_type_change(self):
        if self._type_var.get() == "shell":
            self._lbl_cmd.config(text="Befehl:")
            self._btn_browse.pack(side=tk.LEFT)
        else:
            self._lbl_cmd.config(text="URL:")
            self._btn_browse.pack_forget()

    def _on_browse(self):
        path = filedialog.askopenfilename(
            title="Programm auswählen",
            filetypes=[
                ("Programme", "*.exe;*.bat;*.cmd;*.ps1;*.py"),
                ("Alle Dateien", "*.*"),
            ]
        )
        if path:
            self._cmd_var.set(path)

    # ---------------------------------------------------------------- #
    #  Confirm / Cancel                                                 #
    # ---------------------------------------------------------------- #

    def _on_confirm(self):
        match_val = self._match_var.get().strip()
        match_type = self._match_type_var.get()
        auto_type = self._type_var.get()
        cmd = self._cmd_var.get().strip()
        label = self._label_var.get().strip()

        # Validate
        if not match_val:
            self._lbl_error.config(
                text="⚠ Match-Wert darf nicht leer sein!")
            return
        if not cmd:
            field = "Befehl" if auto_type == "shell" else "URL"
            self._lbl_error.config(
                text=f"⚠ {field} darf nicht leer sein!")
            return

        self.result = {
            "match": match_val,
            "match_type": match_type,
            "type": auto_type,
        }
        if auto_type == "shell":
            self.result["command"] = cmd
        else:
            self.result["url"] = cmd
        if label:
            self.result["label"] = label

        self.dlg.destroy()

    def _on_cancel(self):
        self.dlg.destroy()


# ------------------------------------------------------------------ #
#  Standalone entry point                                              #
# ------------------------------------------------------------------ #

def open_editor(parent: Optional[tk.Tk] = None):
    """Open the automation editor. Call from the planner or standalone."""
    editor = AutomationEditor(parent)
    return editor


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # hide the dummy root
    editor = AutomationEditor(parent=None)
    # When running standalone, the editor *is* the root
    editor.win.mainloop()
