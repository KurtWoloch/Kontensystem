#!/usr/bin/env python3
"""
json2table_gui.pyw — GUI-Einstieg fuer json2table

Doppelklick im Dateimanager genuegt (.pyw = kein Konsolenfenster).
Oeffnet eine Dialogbox zur Dateiauswahl und Optionswahl,
dann wird die Konvertierung durchgefuehrt und das Ergebnis geoeffnet.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys

# json2table.py liegt im selben Verzeichnis
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from json2table import load_json, get_columns, to_csv, to_html

# Standardverzeichnis: logs/
KONTENSYSTEM_DIR = os.path.dirname(SCRIPT_DIR)
LOGS_DIR = os.path.join(KONTENSYSTEM_DIR, "logs")
DATA_DIR = os.path.join(KONTENSYSTEM_DIR, "data")

# Farben (Catppuccin Mocha)
BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#89b4fa"
BTN_BG = "#313244"
BTN_ACTIVE = "#45475a"
ENTRY_BG = "#181825"
BORDER = "#45475a"


class Json2TableGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JSON → Tabelle")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # Variablen
        self.input_path = tk.StringVar()
        self.output_format = tk.StringVar(value="html")
        self.sort_column = tk.StringVar(value="(keine)")
        self.sort_reverse = tk.BooleanVar(value=False)
        self.open_after = tk.BooleanVar(value=True)
        self.available_columns = ["(keine)"]
        self.selected_columns = []  # leer = alle

        self._build_ui()
        self.root.mainloop()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 4}

        # Titel
        tk.Label(
            self.root, text="JSON → Tabelle", font=("Segoe UI", 14, "bold"),
            bg=BG, fg=ACCENT
        ).pack(pady=(12, 4))

        tk.Label(
            self.root, text="JSON/JSONL-Dateien in CSV oder HTML konvertieren",
            font=("Segoe UI", 9), bg=BG, fg="#a6adc8"
        ).pack(pady=(0, 8))

        # --- Dateiauswahl ---
        frame_file = tk.Frame(self.root, bg=BG)
        frame_file.pack(fill=tk.X, **pad)

        tk.Label(frame_file, text="Eingabedatei:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(anchor=tk.W)

        row_file = tk.Frame(frame_file, bg=BG)
        row_file.pack(fill=tk.X, pady=(2, 0))

        self.entry_file = tk.Entry(
            row_file, textvariable=self.input_path,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            font=("Segoe UI", 9), relief=tk.FLAT,
            highlightthickness=1, highlightcolor=ACCENT,
            highlightbackground=BORDER
        )
        self.entry_file.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        tk.Button(
            row_file, text="Durchsuchen...", command=self._browse_file,
            bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG,
            font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2"
        ).pack(side=tk.RIGHT, padx=(6, 0))

        # --- Optionen ---
        frame_opts = tk.LabelFrame(
            self.root, text=" Optionen ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief=tk.GROOVE,
            highlightbackground=BORDER, highlightthickness=1
        )
        frame_opts.pack(fill=tk.X, padx=12, pady=8)

        # Format
        row_fmt = tk.Frame(frame_opts, bg=BG)
        row_fmt.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(row_fmt, text="Format:", bg=BG, fg=FG, width=12,
                 anchor=tk.W, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        for val, label in [("html", "HTML-Tabelle"), ("csv", "CSV-Datei")]:
            tk.Radiobutton(
                row_fmt, text=label, variable=self.output_format, value=val,
                bg=BG, fg=FG, selectcolor=BTN_BG, activebackground=BG,
                activeforeground=ACCENT, font=("Segoe UI", 9)
            ).pack(side=tk.LEFT, padx=(0, 12))

        # Sortierung
        row_sort = tk.Frame(frame_opts, bg=BG)
        row_sort.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(row_sort, text="Sortieren:", bg=BG, fg=FG, width=12,
                 anchor=tk.W, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.combo_sort = ttk.Combobox(
            row_sort, textvariable=self.sort_column,
            values=self.available_columns, state="readonly", width=25
        )
        self.combo_sort.pack(side=tk.LEFT)
        tk.Checkbutton(
            row_sort, text="Absteigend", variable=self.sort_reverse,
            bg=BG, fg=FG, selectcolor=BTN_BG, activebackground=BG,
            activeforeground=ACCENT, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=(12, 0))

        # Nach Erstellung oeffnen
        row_open = tk.Frame(frame_opts, bg=BG)
        row_open.pack(fill=tk.X, padx=8, pady=(4, 8))
        tk.Checkbutton(
            row_open, text="Datei nach Erstellung öffnen",
            variable=self.open_after,
            bg=BG, fg=FG, selectcolor=BTN_BG, activebackground=BG,
            activeforeground=ACCENT, font=("Segoe UI", 9)
        ).pack(anchor=tk.W)

        # --- Info-Label ---
        self.info_label = tk.Label(
            self.root, text="", bg=BG, fg="#a6adc8",
            font=("Segoe UI", 9), wraplength=400, justify=tk.LEFT
        )
        self.info_label.pack(padx=12, pady=(0, 4))

        # --- Buttons ---
        frame_btns = tk.Frame(self.root, bg=BG)
        frame_btns.pack(pady=(4, 12))

        tk.Button(
            frame_btns, text="  Konvertieren  ", command=self._convert,
            bg="#a6e3a1", fg="#1e1e2e", activebackground="#94e2d5",
            font=("Segoe UI", 11, "bold"), relief=tk.FLAT, cursor="hand2"
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            frame_btns, text="  Schließen  ", command=self.root.destroy,
            bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE,
            font=("Segoe UI", 11), relief=tk.FLAT, cursor="hand2"
        ).pack(side=tk.LEFT, padx=6)

        # Drag & Drop hint
        self.input_path.trace_add("write", self._on_file_changed)

    def _browse_file(self):
        # Startverzeichnis: logs/ falls vorhanden, sonst data/
        initial = LOGS_DIR if os.path.isdir(LOGS_DIR) else DATA_DIR
        if not os.path.isdir(initial):
            initial = KONTENSYSTEM_DIR

        path = filedialog.askopenfilename(
            title="JSON/JSONL-Datei auswählen",
            initialdir=initial,
            filetypes=[
                ("JSON-Dateien", "*.json"),
                ("JSONL-Dateien", "*.jsonl"),
                ("Alle Dateien", "*.*"),
            ]
        )
        if path:
            self.input_path.set(path)

    def _on_file_changed(self, *_args):
        """Wenn eine Datei ausgewaehlt wird: Spalten ermitteln und Dropdown aktualisieren."""
        path = self.input_path.get().strip()
        if not path or not os.path.exists(path):
            self.info_label.config(text="")
            return

        try:
            data = load_json(path)
            columns = get_columns(data)
            self.available_columns = ["(keine)"] + columns
            self.combo_sort["values"] = self.available_columns
            self.sort_column.set("(keine)")

            # Auto-detect sinnvolle Sortierung
            for auto_col in ["started_at", "est_start", "start_time"]:
                if auto_col in columns:
                    self.sort_column.set(auto_col)
                    break

            self.info_label.config(
                text=f"✓ {len(data)} Einträge, {len(columns)} Spalten erkannt"
            )
        except Exception as e:
            self.info_label.config(text=f"⚠ Fehler beim Lesen: {e}")

    def _convert(self):
        path = self.input_path.get().strip()
        if not path:
            messagebox.showwarning("Keine Datei", "Bitte zuerst eine Datei auswählen.")
            return
        if not os.path.exists(path):
            messagebox.showerror("Nicht gefunden", f"Datei nicht gefunden:\n{path}")
            return

        try:
            data = load_json(path)
            if not data:
                messagebox.showwarning("Leer", "Die Datei enthält keine Daten.")
                return

            columns = get_columns(data)

            # Sortierung
            sort_col = self.sort_column.get()
            if sort_col and sort_col != "(keine)" and sort_col in columns:
                def sort_key(row):
                    val = row.get(sort_col)
                    if val is None:
                        return ""
                    if isinstance(val, (int, float)):
                        return val
                    return str(val)
                data.sort(key=sort_key, reverse=self.sort_reverse.get())

            # Ausgabedatei
            fmt = self.output_format.get()
            ext = ".csv" if fmt == "csv" else ".html"
            from pathlib import Path as P
            output_path = str(P(path).with_suffix(ext))
            title = P(path).stem

            if fmt == "csv":
                to_csv(data, columns, output_path)
            else:
                to_html(data, columns, output_path, title=title)

            self.info_label.config(
                text=f"✓ Gespeichert: {os.path.basename(output_path)} "
                     f"({len(data)} Einträge)"
            )

            if self.open_after.get():
                os.startfile(output_path)

        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler bei der Konvertierung:\n{e}")


if __name__ == "__main__":
    Json2TableGUI()
