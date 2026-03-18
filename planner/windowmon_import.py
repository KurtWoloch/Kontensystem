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
import json
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

# Add parent dir for windowmon_summary imports
_parent = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from windowmon_summary import (
    load_windowmon, classify_entry, build_activity_blocks,
    _extract_offpc_activity, LOG_DIR,
)
from models import CompletedItem
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
#  Gap Detection                                                             #
# ═══════════════════════════════════════════════════════════════════════════ #

def find_planner_gaps(completed: List[CompletedItem],
                      day_start: datetime,
                      day_end: datetime,
                      min_gap_minutes: int = 2) -> List[Tuple[datetime, datetime]]:
    """Find time gaps in the planner log where no activity was logged.

    Returns list of (gap_start, gap_end) tuples >= min_gap_minutes.
    """
    if not completed:
        return [(day_start, day_end)]

    # Sort by start time
    sorted_log = sorted(completed, key=lambda c: c.started_at)

    gaps = []
    # Gap before first entry
    if (sorted_log[0].started_at - day_start).total_seconds() / 60 >= min_gap_minutes:
        gaps.append((day_start, sorted_log[0].started_at))

    # Gaps between entries — use high-water-mark of completed_at
    # to handle overlapping entries (e.g., a long activity like
    # "Besuch Schwimmbad" 07:53-08:49 followed by 0-duration skipped
    # entries at 07:53:06, 07:53:09, 07:53:22 — the high-water-mark
    # stays at 08:49, preventing a false gap from 07:53:22 to 08:49)
    max_completed = sorted_log[0].completed_at
    for i in range(len(sorted_log) - 1):
        max_completed = max(max_completed, sorted_log[i].completed_at)
        start_next = sorted_log[i + 1].started_at
        gap_min = (start_next - max_completed).total_seconds() / 60
        if gap_min >= min_gap_minutes:
            gaps.append((max_completed, start_next))

    # Gap after last entry (use high-water-mark, not just last entry)
    max_completed = max(max_completed, sorted_log[-1].completed_at)
    if (day_end - max_completed).total_seconds() / 60 >= min_gap_minutes:
        gaps.append((max_completed, day_end))

    return gaps


def _consolidate_blocks(blocks: List[Dict], max_gap_s: int = 120,
                        noise_threshold_s: int = 30) -> List[Dict]:
    """Merge adjacent blocks with the same classification, and absorb noise.

    Three passes:
    0. Pre-merge same-account runs: consecutive blocks with the same
       account code are merged BEFORE noise absorption. This prevents
       a sequence of short same-account blocks (e.g., 15s Statistik_heute
       + 5s Programmumschaltung + 20s Library Andon FM — all account RA)
       from being individually absorbed as noise into a neighboring
       long block of a different account. The merged RA block (~2 min)
       is then correctly too long for noise absorption and survives as
       a separate proposal.
    1. Absorb noise: blocks shorter than noise_threshold_s are absorbed
       into the longer neighboring block (handles 2s Explorer flashes
       between OpenClaw sessions).
    2. Merge adjacent: blocks with the same account/activity within
       max_gap_s are merged into one.
    """
    if len(blocks) < 2:
        return blocks

    # Pass 0: Pre-merge same-account runs (bridging short foreign blocks)
    # This ensures that a sequence of short blocks belonging to the same
    # account (e.g., Excel Statistik → Explorer "Lebenserhaltung" →
    # Excel Library — RA/LE/RA) is treated as one RA block for noise-
    # absorption purposes.
    #
    # Two sub-passes:
    #   0a. Merge directly adjacent same-account blocks
    #   0b. Bridge: if block[i] and block[i+2] have the same account
    #       and block[i+1] is short (< noise_threshold_s), absorb
    #       block[i+1] into block[i] and then merge block[i]+block[i+2].
    #       This handles "RA → short LE explorer → RA" sequences where
    #       the explorer was just navigation to the next RA file.

    # Sub-pass 0a: merge directly adjacent same-account blocks
    premerged = [dict(blocks[0])]
    for block in blocks[1:]:
        prev = premerged[-1]
        gap_s = (block["start"] - prev["end"]).total_seconds()
        if (prev["account"] == block["account"] and
                prev["account"] not in ("", "_UNCLASSIFIABLE") and
                gap_s <= 60):
            prev_dur = prev.get("duration_s", 0)
            block_dur = block.get("duration_s", 0)
            if block_dur > prev_dur:
                prev["activity"] = block["activity"]
            prev["end"] = block["end"]
            prev["entries"] += block["entries"]
            prev["duration_s"] = (prev["end"] - prev["start"]).total_seconds()
        else:
            premerged.append(dict(block))

    # Sub-pass 0b: bridge short foreign blocks between same-account blocks
    # Runs iteratively until no more bridges can be made, because one
    # bridge may create a new same-account pair that enables another bridge.
    # Example: KS → RA(3s) → KS(1s) → IN(24s) → RA(6s) → IN(17s) → KS(286s)
    # Pass 1: bridge RA(3s) between KS blocks → merged KS
    # Pass 2: bridge KS+IN(24s)+RA(6s)+IN(17s)+KS → eventually one KS block
    if len(premerged) >= 3:
        changed = True
        while changed:
            changed = False
            bridged = [dict(premerged[0])]
            i = 1
            while i < len(premerged):
                block = dict(premerged[i])
                block_dur = block.get("duration_s", 0)

                # Check if this short block is sandwiched between same-account
                # Use a higher threshold (60s) than noise_threshold_s (30s)
                # because rapid tab-switching (email check, quick glance at
                # another site) between two blocks of the same activity
                # should be absorbed even if it's slightly longer than noise.
                bridge_threshold_s = max(noise_threshold_s, 60)
                if (i + 1 < len(premerged) and
                        block_dur < bridge_threshold_s and
                        bridged[-1]["account"] == premerged[i + 1]["account"] and
                        bridged[-1]["account"] not in ("", "_UNCLASSIFIABLE")):
                    # Absorb the short foreign block into the previous block
                    prev = bridged[-1]
                    nxt = dict(premerged[i + 1])
                    # Extend prev to cover both the bridge and the next block
                    prev["end"] = nxt["end"]
                    prev["entries"] += block["entries"] + nxt["entries"]
                    prev["duration_s"] = (
                        prev["end"] - prev["start"]).total_seconds()
                    # Keep activity of the longer sub-block
                    nxt_dur = nxt.get("duration_s", 0)
                    if nxt_dur > prev.get("duration_s", 0) - nxt_dur:
                        prev["activity"] = nxt["activity"]
                    i += 2  # skip both the bridge and the next block
                    changed = True
                else:
                    bridged.append(block)
                    i += 1
            premerged = bridged

    # Pass 1: Absorb noise — replace short blocks with their longer neighbor
    absorbed = list(premerged)
    changed = True
    while changed:
        changed = False
        new_list = []
        i = 0
        while i < len(absorbed):
            block = dict(absorbed[i])
            dur = block.get("duration_s", 0)

            if dur < noise_threshold_s and len(absorbed) > 1:
                # This block is noise — absorb into a neighbor
                if new_list and i > 0 and (i == len(absorbed) - 1 or
                              new_list[-1].get("duration_s", 0) >=
                              absorbed[i + 1].get("duration_s", 0)):
                    # Absorb into previous (longer or only option)
                    prev = new_list[-1]
                    prev["end"] = block["end"]
                    prev["entries"] += block["entries"]
                    prev["duration_s"] = (prev["end"] -
                                           prev["start"]).total_seconds()
                    changed = True
                    i += 1
                    continue
                elif i < len(absorbed) - 1:
                    # Absorb into next
                    nxt = dict(absorbed[i + 1])
                    nxt["start"] = block["start"]
                    nxt["entries"] += block["entries"]
                    nxt["duration_s"] = (nxt["end"] -
                                          nxt["start"]).total_seconds()
                    absorbed[i + 1] = nxt
                    changed = True
                    i += 1
                    continue

            new_list.append(block)
            i += 1
        absorbed = new_list

    # Pass 1.5: Re-run bridging after noise absorption.
    # Noise absorption can change the landscape: blocks that were
    # separated by a noise block (now absorbed) may have created new
    # short blocks sandwiched between same-account blocks.
    # Example: KS → RW(4s) → RA(32s) → KS
    #   Pass 0b couldn't bridge RW(4s) because KS≠RA neighbors.
    #   Pass 1 absorbs RW(4s) into KS → now: KS → RA(32s) → KS.
    #   RA(32s) < bridge_threshold(60s) but bridging already ran.
    #   This pass catches it.
    if len(absorbed) >= 3:
        changed = True
        while changed:
            changed = False
            bridged2 = [dict(absorbed[0])]
            i = 1
            while i < len(absorbed):
                block = dict(absorbed[i])
                block_dur = block.get("duration_s", 0)
                bridge_threshold_s = max(noise_threshold_s, 60)
                if (i + 1 < len(absorbed) and
                        block_dur < bridge_threshold_s and
                        bridged2[-1]["account"] == absorbed[i + 1]["account"] and
                        bridged2[-1]["account"] not in ("", "_UNCLASSIFIABLE")):
                    prev = bridged2[-1]
                    nxt = dict(absorbed[i + 1])
                    prev["end"] = nxt["end"]
                    prev["entries"] += block["entries"] + nxt["entries"]
                    prev["duration_s"] = (
                        prev["end"] - prev["start"]).total_seconds()
                    nxt_dur = nxt.get("duration_s", 0)
                    if nxt_dur > prev.get("duration_s", 0) - nxt_dur:
                        prev["activity"] = nxt["activity"]
                    i += 2
                    changed = True
                else:
                    bridged2.append(block)
                    i += 1
            absorbed = bridged2

    # Pass 2: Merge adjacent blocks with same classification
    merged = [dict(absorbed[0])]
    for block in absorbed[1:]:
        prev = merged[-1]
        gap_s = (block["start"] - prev["end"]).total_seconds()

        if (prev["account"] == block["account"] and
                prev["activity"] == block["activity"] and
                gap_s <= max_gap_s):
            prev["end"] = block["end"]
            prev["entries"] += block["entries"]
            prev["duration_s"] = (prev["end"] - prev["start"]).total_seconds()
        else:
            merged.append(dict(block))

    return merged


# AutoDetect names that are too generic for day-overrides.
# These are catch-all categories where different corrections likely mean
# different things, so the last correction shouldn't apply to all future
# instances of the same original name.
_GENERIC_ACTIVITIES = frozenset({
    "Sonstige PC-Nutzung",
    "div. Surfen",
    "div. Surfen (News)",
    "Bearbeitung in VS Code",
    "Dateiverwaltung (Explorer)",
})


def _load_day_overrides(date_str: str) -> Dict[str, str]:
    """Load today's corrections as overrides: original_name → last corrected_name.

    When a user corrects "Diskussion OpenClaw" → "Bearbeitung Tagesplaner KSPLEN",
    all subsequent proposals with the same original AutoDetect name will use the
    corrected name as default. Last correction wins (most recent context).

    Generic catch-all activities (e.g. "Sonstige PC-Nutzung") are excluded
    because they map to many different real activities.
    """
    path = os.path.join(LOG_DIR, f"autodetect-corrections-{date_str}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            corrections = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    overrides: Dict[str, str] = {}
    for entry in corrections:
        original = entry.get("original", "")
        corrected = entry.get("corrected", "")
        if original and corrected and original != corrected:
            if original not in _GENERIC_ACTIVITIES:
                overrides[original] = corrected
    return overrides


def _find_planner_context(completed: List, gap_start: datetime
                          ) -> Optional[Dict]:
    """Find the planner activity that was active during a gap.

    Returns {account, activity, task_code} or None.

    Logic: find the activity whose time span (started_at → completed_at)
    overlaps with the gap start. This ensures we get the activity that
    was actually running, not one that already finished.

    If no overlapping activity is found, fall back to the last completed
    activity before the gap — but only if it ended within 5 minutes of
    the gap start (to avoid stale context from hours ago).
    """
    if not completed:
        return None

    def _extract_info(item):
        """Extract account/activity/code from a CompletedItem."""
        task_code = ""
        code_match = re.search(r'\s([A-Z]{6})(?:\s*\(Fs\.\))?\s*$',
                               item.activity)
        if code_match:
            task_code = code_match.group(1)
        account = task_code[:2] if task_code else ""
        return {
            "account": account,
            "activity": item.activity,
            "task_code": task_code,
            "list_name": item.list_name,
        }

    # First: look for an activity that was still running at gap_start
    # (started before gap, completed after gap_start — or not yet completed)
    overlapping = [
        c for c in completed
        if not c.skipped
        and c.started_at <= gap_start
        and c.completed_at >= gap_start
    ]
    if overlapping:
        # Take the most recently started one
        best = max(overlapping, key=lambda c: c.started_at)
        return _extract_info(best)

    # Fallback: last completed activity before the gap, but only if recent
    # (within 5 minutes — avoids stale context from a different phase of day)
    candidates = [
        c for c in completed
        if c.started_at <= gap_start and not c.skipped
    ]
    if candidates:
        last = max(candidates, key=lambda c: c.completed_at)
        gap_after = (gap_start - last.completed_at).total_seconds()
        if gap_after <= 300:  # 5 minutes
            return _extract_info(last)

    return None


def get_windowmon_proposals(date_str: str,
                            gaps: List[Tuple[datetime, datetime]],
                            completed: Optional[List] = None,
                            ) -> List[Dict]:
    """Get auto-classified windowmon blocks that fall within planner gaps.

    Returns list of proposal dicts:
      {account, activity, start, end, duration_min, raw_entries, entry_count}

    Filters out blocks < 1 minute (same-minute start/end).
    Applies day overrides from corrections file (last correction for each
    original AutoDetect name becomes the default for subsequent proposals).

    If `completed` (list of CompletedItem) is provided, proposals whose
    account matches the planner's active activity at that time will
    inherit the planner activity name + task code instead of the generic
    AutoDetect classification. This implements the "planner context"
    heuristic: if you were working on "Bearb. Essensplan LEEPEP" and
    windowmon sees Access DB (account LE), it proposes LEEPEP instead
    of "Bearb. unbekannte Datenbank".
    """
    entries = load_windowmon(date_str)
    if not entries:
        return []

    # Load today's corrections as overrides
    day_overrides = _load_day_overrides(date_str)

    # Sort entries by timestamp (they may arrive slightly out of order
    # due to idle markers being backdated)
    entries.sort(key=lambda e: e["_ts"])

    proposals = []

    for gap_start, gap_end in gaps:
        # Filter windowmon entries within this gap
        gap_entries = [
            e for e in entries
            if not e.get("type")  # skip markers
            and gap_start <= e["_ts"] <= gap_end
        ]
        if not gap_entries:
            continue

        # Find planner context for this gap (what was supposed to be running)
        planner_ctx = None
        if completed:
            planner_ctx = _find_planner_context(completed, gap_start)

        # Build classified blocks for this gap
        blocks = build_activity_blocks(gap_entries)

        # Consolidate: merge adjacent blocks with same classification
        # This handles rapid switching (e.g., 2s Explorer between two
        # OpenClaw blocks → one OpenClaw block)
        blocks = _consolidate_blocks(blocks, max_gap_s=120)

        for block in blocks:
            # Clamp to gap boundaries
            block_start = max(block["start"], gap_start)
            block_end = min(block["end"], gap_end)

            # Filter: must cross at least one minute boundary
            # (e.g., 08:52:31-08:53:29 → 08:52-08:53 = OK;
            #  08:57:01-08:57:35 → 08:57-08:57 = drop)
            if block_start.strftime("%H:%M") == block_end.strftime("%H:%M"):
                continue

            duration_min = (block_end - block_start).total_seconds() / 60

            # Collect raw entries for this block's time range
            raw = [
                e for e in gap_entries
                if block_start <= e["_ts"] <= block_end
            ]

            activity = block["activity"]
            account = block["account"]

            # ── Planner context enrichment ─────────────────────────────
            # If the autodetect account matches the planner's active
            # activity account, inherit the planner's activity name + code.
            # This handles: "Bearb. unbekannte Datenbank" (LE) while
            # planner says "Bearb. Essensplan LEEPEP" (LE) → use LEEPEP.
            #
            # IMPORTANT: Only apply planner context when the AutoDetect
            # did NOT already produce a specific classification (i.e.,
            # one with a 6-char task code). If AutoDetect already knows
            # what this is (e.g., Statistik_heute.csv → RAAFAN), the
            # planner context must not override it — even if accounts
            # match. This prevents e.g. a recently-imported "Ansehen
            # Youtube-Videos RAYTYT" (RA) from overwriting a correctly
            # classified "Untersuchung Rotation Andon FM RAAFAN" (RA).
            planner_override = False
            block_has_specific_code = bool(
                re.search(r'\s[A-Z]{6}(?:\s|$)', activity)
            )
            if (planner_ctx and planner_ctx["account"] and
                    account == planner_ctx["account"]
                    and not block_has_specific_code):
                activity = planner_ctx["activity"]
                planner_override = True

            # Apply day override if this AutoDetect name was corrected before
            # (day overrides take precedence over planner context only if
            # planner context wasn't applied)
            override_applied = False
            if not planner_override and activity in day_overrides:
                activity = day_overrides[activity]
                override_applied = True
                # Try to derive account from 6-char task code at end
                code_match = re.search(r'\s([A-Z]{6})$', activity)
                if code_match:
                    account = code_match.group(1)[:2]

            proposals.append({
                "account": account,
                "activity": activity,
                "start": block_start,
                "end": block_end,
                "duration_min": duration_min,
                "raw_entries": raw,
                "entry_count": len(raw),
                "status": "pending",  # pending / accepted / edited / ignored
                "original_activity": block["activity"],
                "comment": "",
                "planner_context": planner_override,
            })

    # Sort by start time
    proposals.sort(key=lambda p: p["start"])
    return proposals


# ═══════════════════════════════════════════════════════════════════════════ #
#  Corrections Log                                                           #
# ═══════════════════════════════════════════════════════════════════════════ #

def log_correction(date_str: str, original: str, corrected: str,
                   start: datetime, end: datetime):
    """Log an AutoDetect correction for future rule improvement."""
    if original == corrected:
        return
    path = os.path.join(LOG_DIR,
                        f"autodetect-corrections-{date_str}.json")
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
        "original": original,
        "corrected": corrected,
    }
    # Append to existing file
    existing = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    existing.append(entry)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


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
    if completed:
        sorted_log = sorted(completed, key=lambda c: c.started_at)
        day_start = sorted_log[0].started_at.replace(second=0, microsecond=0)
        day_end = datetime.now().replace(second=0, microsecond=0)
    else:
        now = datetime.now()
        day_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
        day_end = now.replace(second=0, microsecond=0)

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
