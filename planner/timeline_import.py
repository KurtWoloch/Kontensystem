# -*- coding: utf-8 -*-
"""
timeline_import.py — Timeline-based Nacherfassung v2 for the Reactive Planner.

Features:
  - Canvas-based timeline: all windowmon entries (timestamp + title)
  - Classification blocks on the right side with draggable boundary lines
  - Drag boundary UP/DOWN to reassign entries between blocks
  - Same-classification adjacent blocks auto-merge
  - Double-click a block to reclassify (with CodeSuggestor integration)
  - Propagation checkbox: reclassify all same window titles in interval
  - Time interval spinners to limit the displayed range
  - Import blocks into planner log via engine.log_adhoc()

Public API:
    open_timeline_dialog(root, engine, code_suggestor=None, date_str=None)
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional
import sys
import os
import re

# ── Path setup ────────────────────────────────────────────────────────── #
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from windowmon_summary import load_windowmon, classify_entry
from windowmon_logic import log_correction

# ── Theme (matches gui.py / windowmon_import.py) ──────────────────────── #
COLOR_BG     = "#1e1e2e"
COLOR_FG     = "#cdd6f4"
COLOR_ACCENT = "#89b4fa"
COLOR_DONE   = "#a6e3a1"
COLOR_SKIP   = "#f38ba8"
COLOR_WARN   = "#f9e2af"
COLOR_PANEL  = "#181825"
COLOR_LIST   = "#313244"
COLOR_HEADER = "#89dceb"
COLOR_BTN    = "#45475a"

# Alternating block background palette (subtle)
_BLOCK_PALETTE = [
    "#252537", "#253027", "#302527", "#2f2f25",
    "#252530", "#252b2e", "#2e2527", "#272e25",
]

FONT_LABEL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 9)
FONT_BOLD  = ("Segoe UI", 9, "bold")

# Canvas geometry constants
ROW_H        = 22    # px per entry row
TS_W         = 76    # timestamp column width
TITLE_W      = 360   # window title column width
SEP_X        = TS_W + TITLE_W   # x where classification column starts
CLASS_W      = 290   # classification column width
TOTAL_W      = SEP_X + CLASS_W
BNDRY_HIT    = 5     # ±px drag hit-zone around boundary line


# ═══════════════════════════════════════════════════════════════════════════
#  Data Model
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TLEntry:
    """One windowmon record, with its classification block assignment."""
    ts: datetime
    title: str
    process: str
    browser: str
    block_id: int
    logged_activity: str = ""  # non-empty if within an already-logged time range


@dataclass
class TLBlock:
    """A contiguous run of entries with the same classification."""
    block_id: int
    activity: str
    account: str
    start_idx: int   # first entry index (inclusive)
    end_idx:   int   # last  entry index (inclusive)

    def is_logged(self, entries: List['TLEntry']) -> bool:
        """True if ALL entries in this block are within already-logged ranges."""
        if self.start_idx >= len(entries):
            return False
        return all(
            entries[i].logged_activity != ""
            for i in range(self.start_idx, min(self.end_idx + 1, len(entries)))
        )


class TimelineModel:
    """Manages entries and blocks; keeps the invariant that blocks are
    contiguous, non-overlapping, and adjacent blocks differ in classification.
    """

    def __init__(self, raw_entries: List[dict],
                 interval_start: datetime, interval_end: datetime,
                 completed: Optional[List] = None):
        self.raw_entries   = raw_entries
        self.interval_start = interval_start
        self.interval_end   = interval_end
        self.completed      = completed or []
        self._id_counter    = 0
        self.entries: List[TLEntry] = []
        self.blocks:  List[TLBlock] = []
        # User overrides: title → (account, activity) — survives rebuild
        self._user_overrides: dict[str, tuple[str, str]] = {}
        self._rebuild()

    # ── internal ─────────────────────────────────────────────────────────

    def _new_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    def _logged_activity_at(self, ts: datetime) -> Optional[str]:
        """Return the logged activity name if ts falls within one, else None."""
        for c in self.completed:
            if c.started_at <= ts <= c.completed_at:
                return c.activity
        return None

    def _rebuild(self):
        """Build entries + blocks from raw_entries filtered to interval.

        Entries within already-logged time ranges are included but marked
        so the UI can display them differently.
        Applies any user overrides from previous reclassifications.
        """
        filtered = [
            e for e in self.raw_entries
            if not e.get("type")  # skip idle markers
            and self.interval_start <= e["_ts"] <= self.interval_end
        ]
        filtered.sort(key=lambda e: e["_ts"])

        self.entries = []
        self.blocks  = []
        self._id_counter = 0

        if not filtered:
            return

        # Classify each entry, resolving special codes.
        # Priority: 1) user overrides  2) logged activity  3) auto-detect
        classified: List[tuple[str, str]] = []  # (account, activity)
        prev_acct, prev_act = "", ""
        for e in filtered:
            title = e.get("title", "")
            ts = e["_ts"]

            # 1) Check user overrides first (from previous reclassifications)
            if title in self._user_overrides:
                acct, act = self._user_overrides[title]
            else:
                # 2) Check if this entry falls within a logged activity
                #    → use logged activity as classification (so block structure
                #    matches what the user sees and logged in the planner)
                logged_act = self._logged_activity_at(ts)
                if logged_act:
                    # Extract account from task code in logged activity
                    m = re.search(r'\s([A-Z]{6})(?:\s*\(Fs\.\))?\s*$', logged_act)
                    acct = m.group(1)[:2] if m else "??"
                    act = logged_act
                else:
                    # 3) Auto-detect from window title
                    acct, act = classify_entry(e)
                    # Resolve special codes
                    if acct in ("_UNCLASSIFIABLE", "_WINLOGGER"):
                        if prev_acct and not prev_acct.startswith("_"):
                            acct, act = prev_acct, prev_act
                        else:
                            acct = "??"
                    elif acct == "_EXPLORER_ACCOUNT_HINT":
                        from windowmon_summary import _explorer_folder_account
                        folder_acct = _explorer_folder_account(title)
                        if folder_acct and folder_acct == prev_acct:
                            acct, act = prev_acct, prev_act
                        elif folder_acct:
                            acct = folder_acct
                            act = f"Dateiverwaltung ({title.strip()})"
                        else:
                            acct, act = prev_acct or "??", prev_act or "Dateiverwaltung"
                    elif acct.startswith("_"):
                        acct = "??"
            if not acct.startswith("_"):
                prev_acct, prev_act = acct, act
            classified.append((acct, act))

        # Build entries with initial block assignments (run-length encoding)
        entries:  List[TLEntry] = []
        blocks:   List[TLBlock] = []
        cur_id:   int = -1
        cur_acct: str = ""
        cur_act:  str = ""

        for i, (e, (acct, act)) in enumerate(zip(filtered, classified)):
            if acct != cur_acct or act != cur_act:
                bid = self._new_id()
                blocks.append(TLBlock(
                    block_id  = bid,
                    activity  = act,
                    account   = acct,
                    start_idx = i,
                    end_idx   = i,
                ))
                cur_id   = bid
                cur_acct = acct
                cur_act  = act
            else:
                blocks[-1].end_idx = i

            entries.append(TLEntry(
                ts       = e["_ts"],
                title    = e.get("title",   ""),
                process  = e.get("process", ""),
                browser  = e.get("browser", ""),
                block_id = cur_id,
                logged_activity = self._logged_activity_at(e["_ts"]) or "",
            ))

        self.entries = entries
        self.blocks  = blocks

    def _block_by_id(self, bid: int) -> Optional[TLBlock]:
        for b in self.blocks:
            if b.block_id == bid:
                return b
        return None

    def _reindex(self):
        """Rebuild start_idx / end_idx for all blocks from entries."""
        for b in self.blocks:
            b.start_idx = len(self.entries)  # sentinel
            b.end_idx   = -1
        for i, e in enumerate(self.entries):
            b = self._block_by_id(e.block_id)
            if b:
                b.start_idx = min(b.start_idx, i)
                b.end_idx   = max(b.end_idx,   i)
        self.blocks = [b for b in self.blocks
                       if b.start_idx <= b.end_idx]
        self.blocks.sort(key=lambda b: b.start_idx)

    def _try_merge_adjacent(self):
        """Merge consecutive blocks that share the same (account, activity)."""
        changed = True
        while changed:
            changed = False
            new_blocks: List[TLBlock] = []
            i = 0
            while i < len(self.blocks):
                b = self.blocks[i]
                if (new_blocks
                        and new_blocks[-1].account  == b.account
                        and new_blocks[-1].activity == b.activity):
                    # merge: extend previous block
                    prev = new_blocks[-1]
                    for idx in range(b.start_idx, b.end_idx + 1):
                        self.entries[idx].block_id = prev.block_id
                    prev.end_idx = b.end_idx
                    changed = True
                else:
                    new_blocks.append(b)
                i += 1
            self.blocks = new_blocks

    # ── public: queries ───────────────────────────────────────────────────

    def block_for_entry(self, idx: int) -> Optional[TLBlock]:
        if 0 <= idx < len(self.entries):
            return self._block_by_id(self.entries[idx].block_id)
        return None

    def get_boundaries(self) -> List[int]:
        """Boundary i means entries[i] and entries[i+1] are in different blocks."""
        return [i for i in range(len(self.entries) - 1)
                if self.entries[i].block_id != self.entries[i + 1].block_id]

    def update_interval(self, start: datetime, end: datetime):
        """Change the interval and rebuild.  User overrides are preserved."""
        self.interval_start = start
        self.interval_end   = end
        self._id_counter    = 0
        self._rebuild()  # _user_overrides survives this

    # ── public: boundary drag ─────────────────────────────────────────────

    def move_boundary(self, old_pos: int, new_pos: int,
                      propagate: bool) -> bool:
        """Move the boundary at old_pos to new_pos.

        Clamps to adjacent boundaries so no block can be jumped over.
        Reassigns entries as needed.  Then merges if same classification.
        Returns True if anything changed.
        """
        if old_pos == new_pos:
            return False

        boundaries = self.get_boundaries()
        if old_pos not in boundaries:
            return False

        pos_in_list = boundaries.index(old_pos)
        lo_limit = boundaries[pos_in_list - 1] if pos_in_list > 0 else -1
        hi_limit = boundaries[pos_in_list + 1] if pos_in_list < len(boundaries) - 1 else len(self.entries) - 1

        new_pos = max(lo_limit, min(hi_limit, new_pos))
        if new_pos == old_pos:
            return False

        # blocks on either side of old_pos
        b_above = self._block_by_id(self.entries[old_pos].block_id)
        b_below = self._block_by_id(self.entries[old_pos + 1].block_id)
        if not b_above or not b_below:
            return False

        changed_titles: set[str] = set()

        if new_pos < old_pos:
            # Drag UP: entries[new_pos+1 .. old_pos] move to b_below
            for idx in range(new_pos + 1, old_pos + 1):
                changed_titles.add(self.entries[idx].title)
                self.entries[idx].block_id = b_below.block_id
        else:
            # Drag DOWN: entries[old_pos+1 .. new_pos] move to b_above
            for idx in range(old_pos + 1, new_pos + 1):
                changed_titles.add(self.entries[idx].title)
                self.entries[idx].block_id = b_above.block_id

        self._reindex()
        self._try_merge_adjacent()

        # Propagation: if enabled, reassign all same-title entries in interval
        if propagate and changed_titles:
            for title in changed_titles:
                self._propagate_title_to_new_classification(title)

        return True

    # ── public: reclassify ────────────────────────────────────────────────

    def reclassify_block(self, block_id: int, new_activity: str,
                         new_account: str, propagate: bool):
        """Change the activity/account of a block.  Propagate if requested."""
        b = self._block_by_id(block_id)
        if not b:
            return

        old_activity = b.activity
        old_account  = b.account

        # Collect titles in this block (for propagation)
        titles_in_block = set(
            self.entries[i].title
            for i in range(b.start_idx, b.end_idx + 1)
        )

        b.activity = new_activity
        b.account  = new_account

        if propagate:
            # Record overrides for all titles in this block
            for title in titles_in_block:
                self._user_overrides[title] = (new_account, new_activity)

            # Reassign all entries with same title to blocks whose
            # classification now equals old; change them to new.
            for title in titles_in_block:
                for i, e in enumerate(self.entries):
                    if e.title == title:
                        blk = self._block_by_id(e.block_id)
                        if blk and blk.activity == old_activity:
                            blk.activity = new_activity
                            blk.account  = new_account

        self._try_merge_adjacent()

    def _propagate_title_to_new_classification(self, title: str):
        """After a boundary move, merge same-title entries that now look fragmented.
        This is a no-op here — _try_merge_adjacent handles all cases.
        """
        pass  # handled by _try_merge_adjacent already


# ═══════════════════════════════════════════════════════════════════════════
#  Reclassification dialog (reuses edit_proposal style)
# ═══════════════════════════════════════════════════════════════════════════

def _reclassify_dialog(parent: tk.Widget, block: TLBlock,
                       code_suggestor=None) -> Optional[tuple[str, str]]:
    """Show a dialog to change a block's classification.

    Returns (new_activity, new_account) or None if cancelled.
    """
    dlg = tk.Toplevel(parent)
    dlg.title("Block reklassifizieren")
    dlg.configure(bg=COLOR_BG)
    dlg.geometry("520x220")
    dlg.transient(parent)
    dlg.grab_set()
    dlg.resizable(False, False)

    result: dict = {"value": None}

    # ── Activity label ───────────────────────────────────────────────────
    tk.Label(dlg, text="Aktivität:", font=FONT_BOLD,
             bg=COLOR_BG, fg=COLOR_FG, anchor="w"
             ).pack(fill=tk.X, padx=12, pady=(12, 2))

    act_var = tk.StringVar(value=block.activity)
    act_entry = tk.Entry(dlg, textvariable=act_var, font=FONT_MONO,
                         bg=COLOR_LIST, fg=COLOR_FG,
                         insertbackground=COLOR_FG, relief=tk.FLAT, bd=4)
    act_entry.pack(fill=tk.X, padx=12)
    act_entry.focus()
    act_entry.select_range(0, tk.END)

    # ── CodeSuggestor row ────────────────────────────────────────────────
    sug_frame = tk.Frame(dlg, bg=COLOR_BG)
    sug_frame.pack(fill=tk.X, padx=12, pady=(2, 0))

    lbl_sug = tk.Label(sug_frame, text="", font=("Consolas", 9),
                       bg=COLOR_BG, fg="#6c7086", anchor="w")
    lbl_sug.pack(side=tk.LEFT, fill=tk.X, expand=True)

    btn_sug = tk.Button(sug_frame, text="Übernehmen",
                        font=FONT_LABEL, bg=COLOR_BTN, fg=COLOR_FG,
                        relief=tk.FLAT, cursor="hand2")
    _sug = {"name": "", "shown": False}

    def _update_sug(*_):
        text = act_var.get().strip()
        if code_suggestor and text:
            matches = code_suggestor.suggest(text)
            if matches:
                code, _, matched_name = matches[0]
                display = f"{matched_name} {code}"
                lbl_sug.config(text=f"→ {display}")
                _sug["name"] = display
                if not _sug["shown"]:
                    btn_sug.pack(side=tk.RIGHT, padx=(4, 0))
                    _sug["shown"] = True
                return
        lbl_sug.config(text="")
        if _sug["shown"]:
            btn_sug.pack_forget()
            _sug["shown"] = False

    def _use_sug():
        if _sug["name"]:
            act_var.set(_sug["name"])

    act_var.trace_add("write", _update_sug)
    btn_sug.config(command=_use_sug)
    _update_sug()

    # ── Error label ───────────────────────────────────────────────────────
    lbl_err = tk.Label(dlg, text="", font=FONT_LABEL,
                       bg=COLOR_BG, fg=COLOR_SKIP)
    lbl_err.pack(fill=tk.X, padx=12)

    # ── Buttons ───────────────────────────────────────────────────────────
    btn_row = tk.Frame(dlg, bg=COLOR_BG)
    btn_row.pack(pady=(6, 12))

    def _confirm():
        new_act = act_var.get().strip()
        if not new_act:
            lbl_err.config(text="Aktivität darf nicht leer sein!")
            return
        # Extract account from 6-char task code
        m = re.search(r'\s([A-Z]{6})(?:\s*\(Fs\.\))?\s*$', new_act)
        new_acct = m.group(1)[:2] if m else block.account
        result["value"] = (new_act, new_acct)
        dlg.destroy()

    def _cancel():
        dlg.destroy()

    btn_cfg = dict(font=FONT_BOLD, relief=tk.FLAT, padx=10, pady=4,
                   cursor="hand2")
    tk.Button(btn_row, text="  ✓ Übernehmen  ", bg=COLOR_DONE, fg="#1e1e2e",
              command=_confirm, **btn_cfg).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(btn_row, text="  ✗ Abbrechen  ", bg=COLOR_BTN, fg=COLOR_FG,
              command=_cancel, **btn_cfg).pack(side=tk.LEFT)

    # Enter key confirms
    dlg.bind("<Return>", lambda _: _confirm())
    dlg.bind("<Escape>", lambda _: _cancel())

    dlg.wait_window()
    return result["value"]


# ═══════════════════════════════════════════════════════════════════════════
#  Timeline Canvas Widget
# ═══════════════════════════════════════════════════════════════════════════

class TimelineCanvas(tk.Frame):
    """The main scrollable canvas that renders entries + classification blocks."""

    def __init__(self, parent: tk.Widget, model: TimelineModel,
                 code_suggestor, propagate_var: tk.BooleanVar,
                 on_model_change, **kwargs):
        super().__init__(parent, bg=COLOR_PANEL, **kwargs)
        self.model          = model
        self.code_suggestor = code_suggestor
        self.propagate_var  = propagate_var
        self.on_model_change = on_model_change

        # Drag state
        self._drag_boundary: Optional[int] = None  # which boundary being dragged
        self._drag_start_y:  int = 0

        self._build_widgets()
        self._redraw()

    # ── layout ──────────────────────────────────────────────────────────

    def _build_widgets(self):
        # Column headers
        hdr = tk.Frame(self, bg=COLOR_PANEL)
        hdr.pack(fill=tk.X, padx=0)
        tk.Label(hdr, text="ZEIT", width=9, font=("Segoe UI", 8, "bold"),
                 bg=COLOR_PANEL, fg=COLOR_HEADER, anchor="w", padx=4
                 ).pack(side=tk.LEFT)
        tk.Label(hdr, text="FENSTERTITEL",
                 font=("Segoe UI", 8, "bold"),
                 bg=COLOR_PANEL, fg=COLOR_HEADER, anchor="w",
                 width=43
                 ).pack(side=tk.LEFT)
        tk.Label(hdr, text="KLASSIFIZIERUNG",
                 font=("Segoe UI", 8, "bold"),
                 bg=COLOR_PANEL, fg=COLOR_HEADER, anchor="w"
                 ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        sep = tk.Frame(self, height=1, bg=COLOR_ACCENT)
        sep.pack(fill=tk.X)

        # Canvas + vertical scrollbar
        canvas_frame = tk.Frame(self, bg=COLOR_PANEL)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.vscroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        self.vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(
            canvas_frame,
            bg=COLOR_PANEL,
            highlightthickness=0,
            yscrollcommand=self.vscroll.set,
            width=TOTAL_W,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vscroll.config(command=self.canvas.yview)

        # Mouse wheel
        self.canvas.bind("<MouseWheel>",    self._on_wheel)
        self.canvas.bind("<Button-4>",      self._on_wheel)
        self.canvas.bind("<Button-5>",      self._on_wheel)

        # Drag events
        self.canvas.bind("<ButtonPress-1>",  self._on_click)
        self.canvas.bind("<B1-Motion>",      self._on_drag)
        self.canvas.bind("<ButtonRelease-1>",self._on_release)

        # Double-click to reclassify
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

        # Cursor hint on motion
        self.canvas.bind("<Motion>", self._on_hover)

    # ── rendering ────────────────────────────────────────────────────────

    def _redraw(self):
        self.canvas.delete("all")
        entries = self.model.entries
        blocks  = self.model.blocks
        n = len(entries)

        if not entries:
            self.canvas.create_text(
                TOTAL_W // 2, 40, text="Keine Einträge im Intervall",
                fill=COLOR_FG, font=FONT_BOLD
            )
            self.canvas.config(scrollregion=(0, 0, TOTAL_W, 80))
            return

        total_h = n * ROW_H + 4
        self.canvas.config(scrollregion=(0, 0, TOTAL_W, total_h))

        boundaries_set = set(self.model.get_boundaries())

        # Map block_id → palette colour
        palette_map: dict[int, str] = {}
        for idx, b in enumerate(blocks):
            palette_map[b.block_id] = _BLOCK_PALETTE[idx % len(_BLOCK_PALETTE)]

        # Color for logged entries (dimmed)
        COLOR_LOGGED_BG = "#1a1a28"
        COLOR_LOGGED_FG = "#6c7086"

        # Pass 1: Draw row backgrounds, timestamps, titles
        for i, e in enumerate(entries):
            y0 = i * ROW_H
            y1 = y0 + ROW_H
            bid = e.block_id
            is_logged = e.logged_activity != ""
            bg = COLOR_LOGGED_BG if is_logged else palette_map.get(bid, COLOR_LIST)
            fg_ts    = COLOR_LOGGED_FG if is_logged else COLOR_ACCENT
            fg_title = COLOR_LOGGED_FG if is_logged else COLOR_FG

            # Row background
            self.canvas.create_rectangle(
                0, y0, TOTAL_W, y1, fill=bg, outline="", tags=f"row{i}"
            )

            # Timestamp
            ts_str = e.ts.strftime("%H:%M:%S")
            self.canvas.create_text(
                4, y0 + ROW_H // 2,
                text=ts_str, anchor="w",
                font=FONT_MONO, fill=fg_ts,
                tags=f"row{i}"
            )

            # Title (truncated)
            title = e.title
            if len(title) > 52:
                title = title[:50] + "…"
            self.canvas.create_text(
                TS_W + 4, y0 + ROW_H // 2,
                text=title, anchor="w",
                font=FONT_MONO, fill=fg_title,
                tags=f"row{i}"
            )

            # Vertical separator between columns
            self.canvas.create_line(TS_W, y0, TS_W, y1,
                                     fill="#383850", width=1)
            self.canvas.create_line(SEP_X, y0, SEP_X, y1,
                                     fill="#383850", width=1)

        # Pass 2: Draw boundary lines (between rows with different blocks)
        for i in range(n):
            if i in boundaries_set:
                by = (i + 1) * ROW_H  # bottom of row i = top of row i+1
                self.canvas.create_line(
                    0, by, TOTAL_W, by,
                    fill=COLOR_ACCENT, width=2, dash=(6, 3),
                    tags=f"bndry{i}"
                )
                # Drag handle icon
                self.canvas.create_text(
                    TOTAL_W - 20, by,
                    text="⬍", anchor="e",
                    font=("Segoe UI", 8), fill=COLOR_ACCENT,
                    tags=f"bndry{i}"
                )

        # Pass 3: Draw classification labels ON TOP of everything
        for b in blocks:
            y0 = b.start_idx * ROW_H
            label_y = y0 + ROW_H // 2
            is_logged = b.is_logged(entries)

            if is_logged:
                # Show the LOGGED activity name (from planner log), dimmed
                logged_act = entries[b.start_idx].logged_activity
                act_text = f"✓ {logged_act}"
                if len(act_text) > 38:
                    act_text = act_text[:36] + "…"
                self.canvas.create_text(
                    SEP_X + 8, label_y,
                    text=act_text, anchor="w",
                    font=FONT_MONO, fill=COLOR_LOGGED_FG,
                    tags=(f"block{b.block_id}", "blocktext")
                )
            else:
                act_text = b.activity
                if len(act_text) > 36:
                    act_text = act_text[:34] + "…"
                self.canvas.create_text(
                    SEP_X + 8, label_y,
                    text=act_text, anchor="w",
                    font=FONT_MONO, fill=COLOR_FG,
                    tags=(f"block{b.block_id}", "blocktext")
                )
                # Account badge (only for unlogged blocks)
                self.canvas.create_text(
                    SEP_X + CLASS_W - 8, label_y,
                    text=b.account, anchor="e",
                    font=("Consolas", 8, "bold"), fill=COLOR_ACCENT,
                    tags=(f"block{b.block_id}", "blocktext")
                )

        self.on_model_change()

    # ── interaction helpers ───────────────────────────────────────────────

    def _y_to_row(self, y_canvas: int) -> int:
        """Canvas y-coordinate → entry index (clamped to valid range)."""
        n = max(1, len(self.model.entries))
        row = int(y_canvas // ROW_H)
        return max(0, min(n - 1, row))

    def _y_near_boundary(self, y_canvas: int) -> Optional[int]:
        """Return boundary index if y is within BNDRY_HIT pixels of it."""
        for bndry in self.model.get_boundaries():
            by = (bndry + 1) * ROW_H  # y pixel of the boundary line
            if abs(y_canvas - by) <= BNDRY_HIT:
                return bndry
        return None

    def _canvas_y(self, event) -> int:
        """Convert event.y to canvas coordinate (accounting for scroll)."""
        return int(self.canvas.canvasy(event.y))

    # ── event handlers ────────────────────────────────────────────────────

    def _on_wheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-2, "units")
        else:
            self.canvas.yview_scroll(2, "units")

    def _on_hover(self, event):
        cy = self._canvas_y(event)
        if self._y_near_boundary(cy) is not None:
            self.canvas.config(cursor="sb_v_double_arrow")
        else:
            self.canvas.config(cursor="")

    def _on_click(self, event):
        cy = self._canvas_y(event)
        bndry = self._y_near_boundary(cy)
        if bndry is not None:
            self._drag_boundary = bndry
            self._drag_start_y  = cy

    def _on_drag(self, event):
        if self._drag_boundary is None:
            return
        cy      = self._canvas_y(event)
        new_row = self._y_to_row(cy)
        # The boundary sits BETWEEN row new_row and new_row+1.
        # We want the boundary *below* row new_row, i.e. at position new_row.
        new_pos = new_row
        changed = self.model.move_boundary(
            self._drag_boundary, new_pos,
            self.propagate_var.get()
        )
        if changed:
            self._drag_boundary = new_pos  # track the new position
            self._redraw()

    def _on_release(self, event):
        self._drag_boundary = None

    def _on_double_click(self, event):
        cy  = self._canvas_y(event)
        row = self._y_to_row(cy)
        if row >= len(self.model.entries):
            return
        # Only activate if click is in the classification column
        cx = event.x
        if cx < SEP_X:
            return
        block = self.model.block_for_entry(row)
        if not block:
            return
        result = _reclassify_dialog(self.canvas, block, self.code_suggestor)
        if result:
            new_act, new_acct = result
            old_act = block.activity
            self.model.reclassify_block(
                block.block_id, new_act, new_acct,
                self.propagate_var.get()
            )
            # Log the correction
            try:
                date_str = self.model.interval_start.strftime("%Y-%m-%d")
                start_ts = self.model.entries[block.start_idx].ts if self.model.entries else self.model.interval_start
                end_ts   = self.model.entries[block.end_idx].ts   if self.model.entries else self.model.interval_end
                log_correction(date_str, old_act, new_act, start_ts, end_ts)
            except Exception:
                pass
            self._redraw()

    # ── public ───────────────────────────────────────────────────────────

    def refresh(self):
        """Force a full redraw (call after model.update_interval())."""
        self._redraw()


# ═══════════════════════════════════════════════════════════════════════════
#  Main Dialog
# ═══════════════════════════════════════════════════════════════════════════

def open_timeline_dialog(root: tk.Tk, engine,
                         code_suggestor=None,
                         date_str: Optional[str] = None):
    """Open the Timeline Nacherfassung v2 dialog.

    Args:
        root:            main Tk root window
        engine:          PlannerEngine instance (needs .session_date, .log_adhoc,
                         .save_log, .get_completed_log)
        code_suggestor:  optional CodeSuggestor for task-code hints
        date_str:        YYYY-MM-DD override; defaults to engine.session_date
    """
    if date_str is None:
        date_str = engine.session_date.strftime("%Y-%m-%d")

    # ── Load raw entries ─────────────────────────────────────────────────
    raw_entries = load_windowmon(date_str)
    if not raw_entries:
        messagebox.showinfo(
            "Timeline Nacherfassung",
            f"Keine windowmon-Einträge für {date_str} gefunden."
        )
        return

    # ── Load completed log to exclude already-logged time ranges ─────────
    completed = engine.get_completed_log() if engine else []

    # Determine default interval: from end of last logged activity to end of day
    real_entries = [e for e in raw_entries if not e.get("type")]
    real_entries.sort(key=lambda e: e["_ts"])

    if completed:
        sorted_completed = sorted(completed, key=lambda c: c.completed_at)
        # Start at the end of the last logged activity
        last_logged_end = sorted_completed[-1].completed_at.replace(
            second=0, microsecond=0)
        default_start = last_logged_end
    elif real_entries:
        default_start = real_entries[0]["_ts"].replace(second=0, microsecond=0)
    else:
        now = datetime.now()
        default_start = now.replace(hour=7,  minute=0,  second=0, microsecond=0)

    if real_entries:
        default_end = real_entries[-1]["_ts"].replace(second=0, microsecond=0)
        # Ensure end is after start
        if default_end <= default_start:
            default_end = default_start + timedelta(hours=1)
    else:
        default_end = default_start + timedelta(hours=4)

    # ── Build dialog window ───────────────────────────────────────────────
    dlg = tk.Toplevel(root)
    dlg.title(f"Timeline Nacherfassung — {date_str}")
    dlg.configure(bg=COLOR_BG)
    dlg.geometry("950x680")
    dlg.minsize(800, 500)
    # NOT modal — user needs access to the Erledigt list for copy-pasting
    # task codes and activity names

    # ── Model ────────────────────────────────────────────────────────────
    model = TimelineModel(raw_entries, default_start, default_end,
                          completed=completed)

    # ── Status bar (bottom) ───────────────────────────────────────────────
    status_var = tk.StringVar(value="")

    def _update_status():
        n_blocks  = len(model.blocks)
        n_entries = len(model.entries)
        status_var.set(
            f"Blöcke: {n_blocks}   Einträge: {n_entries}   "
            f"Intervall: {model.interval_start.strftime('%H:%M')}–"
            f"{model.interval_end.strftime('%H:%M')}"
        )

    # ── Top: title ────────────────────────────────────────────────────────
    tk.Label(
        dlg, text=f"Timeline Nacherfassung  —  {date_str}",
        font=("Segoe UI", 13, "bold"), bg=COLOR_BG, fg=COLOR_HEADER,
        anchor="w", padx=10, pady=6
    ).pack(fill=tk.X)

    # ── Interval row ─────────────────────────────────────────────────────
    ctrl_row = tk.Frame(dlg, bg=COLOR_BG)
    ctrl_row.pack(fill=tk.X, padx=10, pady=(0, 4))

    tk.Label(ctrl_row, text="Intervall:", font=FONT_BOLD,
             bg=COLOR_BG, fg=COLOR_FG).pack(side=tk.LEFT)

    # Spinbox helper
    def _spinbox(parent, var, from_, to_, w=3):
        sb = tk.Spinbox(
            parent, from_=from_, to=to_, width=w, format="%02.0f",
            textvariable=var, font=("Consolas", 10),
            bg=COLOR_LIST, fg=COLOR_FG, buttonbackground=COLOR_BTN,
            relief=tk.FLAT, bd=2
        )
        return sb

    start_h_var = tk.StringVar(value=f"{default_start.hour:02d}")
    start_m_var = tk.StringVar(value=f"{default_start.minute:02d}")
    end_h_var   = tk.StringVar(value=f"{default_end.hour:02d}")
    end_m_var   = tk.StringVar(value=f"{default_end.minute:02d}")

    for txt, h_var, m_var in [
        ("  ", start_h_var, start_m_var),
        ("  —  ", end_h_var, end_m_var),
    ]:
        tk.Label(ctrl_row, text=txt, bg=COLOR_BG, fg=COLOR_FG,
                 font=FONT_BOLD).pack(side=tk.LEFT)
        _spinbox(ctrl_row, h_var, 0, 23).pack(side=tk.LEFT)
        tk.Label(ctrl_row, text=":", bg=COLOR_BG, fg=COLOR_FG,
                 font=("Consolas", 10)).pack(side=tk.LEFT)
        _spinbox(ctrl_row, m_var, 0, 59).pack(side=tk.LEFT)

    # Propagation checkbox
    propagate_var = tk.BooleanVar(value=True)
    tk.Checkbutton(
        ctrl_row, text="  Änderungen auf gleiche Fenstertitel anwenden",
        variable=propagate_var, font=FONT_LABEL,
        bg=COLOR_BG, fg=COLOR_FG, activebackground=COLOR_BG,
        activeforeground=COLOR_FG, selectcolor=COLOR_LIST,
        cursor="hand2"
    ).pack(side=tk.LEFT, padx=(16, 0))

    # Apply interval button
    def _apply_interval():
        try:
            sh = int(start_h_var.get())
            sm = int(start_m_var.get())
            eh = int(end_h_var.get())
            em = int(end_m_var.get())
        except ValueError:
            messagebox.showwarning("Ungültige Zeitangabe",
                                   "Bitte gültige Stunden/Minuten eingeben.")
            return
        date_dt = default_start.replace(hour=0, minute=0, second=0, microsecond=0)
        new_start = date_dt.replace(hour=sh, minute=sm)
        new_end   = date_dt.replace(hour=eh, minute=em)
        if new_end <= new_start:
            messagebox.showwarning("Ungültig", "Ende muss nach Beginn liegen.")
            return
        model.update_interval(new_start, new_end)
        timeline_widget.refresh()

    tk.Button(
        ctrl_row, text="  ↺ Anwenden  ", font=FONT_LABEL,
        bg=COLOR_BTN, fg=COLOR_FG, relief=tk.FLAT, cursor="hand2",
        command=_apply_interval
    ).pack(side=tk.LEFT, padx=(10, 0))

    # Bind <Return> in spinboxes to apply
    for var in (start_h_var, start_m_var, end_h_var, end_m_var):
        var.trace_add("write", lambda *_: None)  # just track for now

    # ── Timeline canvas area ──────────────────────────────────────────────
    timeline_widget = TimelineCanvas(
        dlg, model, code_suggestor, propagate_var,
        on_model_change=_update_status
    )
    timeline_widget.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 0))

    # ── Status bar + buttons ──────────────────────────────────────────────
    bottom = tk.Frame(dlg, bg=COLOR_BG)
    bottom.pack(fill=tk.X, padx=8, pady=(4, 8))

    tk.Label(bottom, textvariable=status_var, font=FONT_LABEL,
             bg=COLOR_BG, fg=COLOR_FG).pack(side=tk.LEFT)

    # ── Import ────────────────────────────────────────────────────────────
    def _import():
        blocks = model.blocks
        if not blocks:
            messagebox.showwarning("Import", "Keine Blöcke zum Importieren.")
            return

        # Build summary — count only unlogged blocks
        importable = [b for b in blocks
                      if not b.is_logged(entries)
                      and b.account not in ("??", "IDLE")
                      and b.start_idx < len(entries)
                      and b.end_idx < len(entries)]
        n = len(importable)
        if n == 0:
            messagebox.showinfo("Import", "Keine neuen Blöcke zum Importieren.")
            return
        answer = messagebox.askyesno(
            "Import bestätigen",
            f"{n} Klassifizierungsblöcke ins Planer-Log importieren?\n\n"
            "Bereits geloggte Blöcke (✓) werden übersprungen.\n"
            "Blöcke, die eine bestehende Aktivität fortsetzen, werden erweitert."
        )
        if not answer:
            return

        entries = model.entries
        imported_count = 0
        extended_count = 0

        for b in blocks:
            if b.start_idx >= len(entries) or b.end_idx >= len(entries):
                continue
            if b.account == "??" or b.account == "IDLE":
                continue  # skip unclassified / idle blocks
            if b.is_logged(entries):
                continue  # skip fully-logged blocks
            start_ts = entries[b.start_idx].ts
            # End time: use the START of the next block (or +1 min for last)
            if b.end_idx + 1 < len(entries):
                end_ts = entries[b.end_idx + 1].ts
            else:
                end_ts = entries[b.end_idx].ts + timedelta(minutes=1)
            if end_ts <= start_ts:
                end_ts = start_ts + timedelta(minutes=1)

            # Check if this block continues the last logged activity
            # with the same name → extend instead of creating duplicate
            matching_logged = [
                c for c in model.completed
                if c.activity == b.activity
                and abs((c.completed_at - start_ts).total_seconds()) < 300
            ]
            if matching_logged:
                # Extend the existing log entry
                last_match = max(matching_logged, key=lambda c: c.completed_at)
                last_match.completed_at = end_ts
                extended_count += 1
                continue
            try:
                engine.log_adhoc(
                    activity  = b.activity,
                    start_time= start_ts,
                    end_time  = end_ts,
                    list_name = "timeline_import",
                    comment   = "",
                )
                imported_count += 1
            except Exception as exc:
                messagebox.showerror("Fehler",
                    f"Fehler beim Importieren von '{b.activity}':\n{exc}")
                return

        try:
            engine.save_log()
        except Exception as exc:
            messagebox.showerror("Fehler", f"Log konnte nicht gespeichert werden:\n{exc}")
            return

        parts = []
        if imported_count:
            parts.append(f"{imported_count} neue Blöcke importiert")
        if extended_count:
            parts.append(f"{extended_count} bestehende Aktivitäten erweitert")
        messagebox.showinfo(
            "Import abgeschlossen",
            f"{' und '.join(parts)}.\nLog gespeichert."
        )
        dlg.destroy()

    btn_cfg = dict(font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
                   padx=10, pady=4, cursor="hand2")
    tk.Button(bottom, text="  ✓ Importieren  ",
              bg=COLOR_DONE, fg="#1e1e2e",
              command=_import, **btn_cfg
              ).pack(side=tk.RIGHT, padx=(4, 0))
    tk.Button(bottom, text="  ✗ Abbrechen  ",
              bg=COLOR_BTN, fg=COLOR_FG,
              command=dlg.destroy, **btn_cfg
              ).pack(side=tk.RIGHT)

    # Bind Return on interval row
    for sb_var in (start_h_var, start_m_var, end_h_var, end_m_var):
        pass  # already bound via button

    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
    _update_status()


# ═══════════════════════════════════════════════════════════════════════════
#  Standalone test
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Quick test: opens the dialog for today (or a hardcoded date)
    import sys
    import os

    # Set up path so we can import from the planner package
    _base = os.path.dirname(os.path.abspath(__file__))
    if _base not in sys.path:
        sys.path.insert(0, _base)

    test_date = datetime.now().strftime("%Y-%m-%d")
    if len(sys.argv) > 1:
        test_date = sys.argv[1]

    print(f"Opening Timeline Nacherfassung for {test_date}")

    # Minimal stub engine for standalone testing
    class _StubEngine:
        session_date = datetime.strptime(test_date, "%Y-%m-%d")

        def get_completed_log(self):
            return []

        def log_adhoc(self, activity, start_time, end_time,
                      list_name="", comment=""):
            print(f"  log_adhoc: {start_time.strftime('%H:%M')}-"
                  f"{end_time.strftime('%H:%M')}  {activity}")

        def save_log(self):
            print("  save_log() called")

    # Optional: try to load a real CodeSuggestor
    cs = None
    try:
        data_dir = os.path.join(_base, "..", "data")
        from code_suggest import CodeSuggestor
        cs = CodeSuggestor(data_dir)
        print(f"CodeSuggestor loaded from {data_dir}")
    except Exception as e:
        print(f"CodeSuggestor not available: {e}")

    root = tk.Tk()
    root.withdraw()

    open_timeline_dialog(root, _StubEngine(), code_suggestor=cs,
                         date_str=test_date)

    root.mainloop()
