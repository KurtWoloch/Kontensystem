"""
windowmon_logic.py — Pure data logic for windowmon-based gap detection and proposals.

Contains all non-GUI functions extracted from windowmon_import.py:
- find_planner_gaps()
- _consolidate_blocks() (with _task_code helper)
- _get_preceding_activity()
- _process_gap()
- get_windowmon_proposals()
- log_correction()
- _load_day_overrides()
- _find_planner_context()

No tkinter imports. GUI code lives in windowmon_import.py.
"""
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from windowmon_summary import (
    load_windowmon, classify_entry, build_activity_blocks,
    _extract_offpc_activity, LOG_DIR,
)
from models import CompletedItem


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


def _task_code(activity: str) -> str:
    """Extract trailing 6-char task code, or '' if none."""
    m = re.search(r'\s([A-Z]{6})(?:\s*\(Fs\.\))?\s*$', activity)
    return m.group(1) if m else ""


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
    # Only merge when both blocks share the same task code (or neither
    # has one).  Blocks with *different* specific codes (e.g., KSPLNA
    # vs KSPLEN) are distinct activities that happen to share an account
    # prefix and must NOT be merged.

    premerged = [dict(blocks[0])]
    for block in blocks[1:]:
        prev = premerged[-1]
        gap_s = (block["start"] - prev["end"]).total_seconds()
        prev_code = _task_code(prev["activity"])
        block_code = _task_code(block["activity"])
        # Merge only when same account AND same task code (or both generic)
        codes_compatible = (prev_code == block_code or
                            (not prev_code and not block_code))
        if (prev["account"] == block["account"] and
                prev["account"] not in ("", "_UNCLASSIFIABLE") and
                gap_s <= 60 and codes_compatible):
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
                        bridged[-1]["account"] not in ("", "_UNCLASSIFIABLE") and
                        _task_code(bridged[-1]["activity"]) ==
                        _task_code(premerged[i + 1]["activity"])):
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
                        bridged2[-1]["account"] not in ("", "_UNCLASSIFIABLE") and
                        _task_code(bridged2[-1]["activity"]) ==
                        _task_code(absorbed[i + 1]["activity"])):
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


def _get_preceding_activity(entries: List[Dict], before_ts: datetime,
                             ) -> Optional[Tuple[Dict, str, str]]:
    """Find the last known window activity before a given timestamp.

    Returns (entry, account, activity) or None if not found or unclassifiable.
    """
    preceding = [
        e for e in entries
        if not e.get("type") and e["_ts"] < before_ts
    ]
    if not preceding:
        return None
    last_entry = max(preceding, key=lambda e: e["_ts"])
    account, activity = classify_entry(last_entry)
    if account in ("_UNCLASSIFIABLE", "_WINLOGGER",
                   "_EXPLORER_ACCOUNT_HINT"):
        return None
    return last_entry, account, activity


def _process_gap(gap_start: datetime, gap_end: datetime,
                 entries: List[Dict], completed: Optional[List],
                 day_overrides: Dict[str, str]) -> List[Dict]:
    """Process a single gap: classify events, build blocks, consolidate.

    Returns list of proposal dicts for this gap (may be empty).
    """
    proposals = []

    # Filter windowmon entries within this gap
    gap_entries = [
        e for e in entries
        if not e.get("type")  # skip markers
        and gap_start <= e["_ts"] <= gap_end
    ]
    if not gap_entries:
        # No window switch during this gap — the last window before the
        # gap is still active.  Find the most recent entry before gap_start
        # and create a synthetic proposal covering the entire gap.
        preceding_result = _get_preceding_activity(entries, gap_start)
        if preceding_result is None:
            return []
        last_entry, account, activity = preceding_result

        # Must cross at least one minute boundary
        if gap_start.strftime("%H:%M") == gap_end.strftime("%H:%M"):
            return []

        duration_min = (gap_end - gap_start).total_seconds() / 60

        # Apply day overrides
        original_activity = activity
        if activity in day_overrides:
            activity = day_overrides[activity]
            code_match = re.search(r'\s([A-Z]{6})$', activity)
            if code_match:
                account = code_match.group(1)[:2]

        # Apply planner context
        planner_override = False
        if completed:
            planner_ctx_synth = _find_planner_context(completed, gap_start)
            if (planner_ctx_synth and planner_ctx_synth["account"] and
                    account == planner_ctx_synth["account"] and
                    not re.search(r'\s[A-Z]{6}(?:\s|$)', activity)):
                activity = planner_ctx_synth["activity"]
                planner_override = True

        proposals.append({
            "account": account,
            "activity": activity,
            "start": gap_start,
            "end": gap_end,
            "duration_min": duration_min,
            "raw_entries": [last_entry],
            "entry_count": 1,
            "status": "pending",
            "original_activity": original_activity,
            "comment": "(kein Fensterwechsel — letztes Fenster fortgesetzt)",
            "planner_context": planner_override,
        })
        return proposals

    # Find planner context for this gap (what was supposed to be running)
    planner_ctx = None
    if completed:
        planner_ctx = _find_planner_context(completed, gap_start)

    # Build classified blocks for this gap
    blocks = build_activity_blocks(gap_entries)

    # ── Pre-enrichment: Apply planner context & day overrides BEFORE consolidation ──
    for block in blocks:
        activity = block["activity"]
        account = block["account"]
        block["original_activity"] = activity

        planner_override = False
        block_has_specific_code = bool(
            re.search(r'\s[A-Z]{6}(?:\s|$)', activity)
        )
        if (planner_ctx and planner_ctx["account"] and
                account == planner_ctx["account"]
                and not block_has_specific_code):
            activity = planner_ctx["activity"]
            planner_override = True

        override_applied = False
        if not planner_override and activity in day_overrides:
            activity = day_overrides[activity]
            override_applied = True
            code_match = re.search(r'\s([A-Z]{6})$', activity)
            if code_match:
                account = code_match.group(1)[:2]

        block["activity"] = activity
        block["account"] = account
        block["planner_context"] = planner_override

    # Consolidate: merge adjacent blocks with same classification
    # This handles rapid switching (e.g., 2s Explorer between two
    # OpenClaw blocks → one OpenClaw block)
    blocks = _consolidate_blocks(blocks, max_gap_s=120)

    # Collect clamped blocks and detect sub-gaps between them.
    # A sub-gap occurs when blocks don't fully cover a gap (e.g.,
    # blocks at 22:22-22:23 and 22:33-22:36 leave 22:23-22:33 empty
    # because no window switch happened — the last window was still
    # active, typically an Off-PC activity like brushing teeth).
    clamped_blocks = []
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

        prop = {
            "account": block["account"],
            "activity": block["activity"],
            "start": block_start,
            "end": block_end,
            "duration_min": duration_min,
            "raw_entries": raw,
            "entry_count": len(raw),
            "status": "pending",  # pending / accepted / edited / ignored
            "original_activity": block.get("original_activity", block["activity"]),
            "comment": "",
            "planner_context": block.get("planner_context", False),
        }
        proposals.append(prop)
        clamped_blocks.append(prop)

    # ── Sub-gap detection: fill gaps between blocks within this gap ──
    # Sort clamped blocks by start time, then look for uncovered
    # intervals >= 2 minutes.  For each sub-gap, propose the
    # activity of the preceding block (last window still active).
    clamped_blocks.sort(key=lambda b: b["start"])
    sub_gap_min_minutes = 2

    # Check: gap_start → first block
    if clamped_blocks:
        first_start = clamped_blocks[0]["start"]
        if (first_start - gap_start).total_seconds() / 60 >= sub_gap_min_minutes:
            # Find last entry before this sub-gap
            preceding_result = _get_preceding_activity(entries, gap_start)
            if preceding_result is not None:
                last_e, sg_account, sg_activity = preceding_result
                sg_original = sg_activity
                if sg_activity in day_overrides:
                    sg_activity = day_overrides[sg_activity]
                    cm = re.search(r'\s([A-Z]{6})$', sg_activity)
                    if cm:
                        sg_account = cm.group(1)[:2]
                proposals.append({
                    "account": sg_account,
                    "activity": sg_activity,
                    "start": gap_start,
                    "end": first_start,
                    "duration_min": (first_start - gap_start).total_seconds() / 60,
                    "raw_entries": [last_e],
                    "entry_count": 1,
                    "status": "pending",
                    "original_activity": sg_original,
                    "comment": "(kein Fensterwechsel — letztes Fenster fortgesetzt)",
                    "planner_context": False,
                })

        # Check: between consecutive blocks — extend the preceding
        # block to cover the sub-gap (no new window = same activity).
        # This avoids creating a second proposal for the same activity
        # that would need manual merging.
        for idx in range(len(clamped_blocks) - 1):
            prev_end = clamped_blocks[idx]["end"]
            next_start = clamped_blocks[idx + 1]["start"]
            if (next_start - prev_end).total_seconds() / 60 >= sub_gap_min_minutes:
                prev_b = clamped_blocks[idx]
                prev_b["end"] = next_start
                prev_b["duration_min"] = (
                    prev_b["end"] - prev_b["start"]
                ).total_seconds() / 60
                if not prev_b.get("comment"):
                    prev_b["comment"] = (
                        "(kein Fensterwechsel — letztes Fenster fortgesetzt)")

        # Check: last block → gap_end — extend last block
        last_end = clamped_blocks[-1]["end"]
        if (gap_end - last_end).total_seconds() / 60 >= sub_gap_min_minutes:
            last_b = clamped_blocks[-1]
            last_b["end"] = gap_end
            last_b["duration_min"] = (
                last_b["end"] - last_b["start"]
            ).total_seconds() / 60
            if not last_b.get("comment"):
                last_b["comment"] = (
                    "(kein Fensterwechsel — letztes Fenster fortgesetzt)")

    # ── Post-processing: KSPLEA → KSPLNA in nacherfassungs-context ──
    # When a KSPLEA block (planner main window = "Erfassung Ablauf") is
    # adjacent to other windowmon_import proposals (especially KSPLNA),
    # it's almost always part of a nacherfassung session, not a quick
    # "mark one task done" interaction.  Reclassify to KSPLNA.
    # Exception: very short isolated KSPLEA blocks (< 2 min) between
    # regular planner activities could be genuine erfassung — but even
    # those are rare enough that KSPLNA is the safer default.
    for i, prop in enumerate(proposals):
        if "KSPLEA" not in prop.get("activity", ""):
            continue
        # Check neighbors: is there another proposal nearby?
        has_neighbor = len(proposals) > 1
        if has_neighbor:
            prop["activity"] = prop["activity"].replace(
                "Erfassung Ablauf KSPLEA", "Nacherfassung Ablauf KSPLNA")
            prop["account"] = "KS"
            if "KSPLEA" in prop.get("original_activity", ""):
                # Keep original for correction tracking
                pass

    # ── Final merge: consolidate adjacent proposals with same activity ──
    # After KSPLEA→KSPLNA conversion (and other reclassifications),
    # adjacent proposals may now share the same account+activity but
    # weren't merged earlier because they had different classifications
    # at consolidation time.  Merge them now.
    if len(proposals) > 1:
        proposals.sort(key=lambda p: p["start"])
        merged_proposals = [proposals[0]]
        for prop in proposals[1:]:
            prev = merged_proposals[-1]
            gap_s = (prop["start"] - prev["end"]).total_seconds()
            if (prev["account"] == prop["account"] and
                    prev["activity"] == prop["activity"] and
                    gap_s <= 120):
                # Merge: extend previous proposal
                prev["end"] = prop["end"]
                prev["duration_min"] = (
                    prev["end"] - prev["start"]).total_seconds() / 60
                prev["raw_entries"] = (
                    prev.get("raw_entries", []) + prop.get("raw_entries", []))
                prev["entry_count"] = (
                    prev.get("entry_count", 0) + prop.get("entry_count", 0))
            else:
                merged_proposals.append(prop)
        proposals = merged_proposals

    return proposals


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
        proposals.extend(
            _process_gap(gap_start, gap_end, entries, completed, day_overrides)
        )

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
