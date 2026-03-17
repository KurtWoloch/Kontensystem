"""
autodetect_audit.py — Compare AutoDetect classifications against actual planner log.

Finds:
1. UNCLASSIFIABLE entries (potential new rules)
2. Mismatches between AutoDetect proposals and what was actually logged
3. Classification summary (what AutoDetect sees vs what was logged)
"""
import sys
import os
import json
from datetime import datetime
from collections import defaultdict

# Add paths
_here = os.path.dirname(os.path.abspath(__file__))
_planner = os.path.join(_here, "..", "planner")
_root = os.path.join(_here, "..")
sys.path.insert(0, _planner)
sys.path.insert(0, _root)

from windowmon_summary import load_windowmon, classify_entry, build_activity_blocks

LOG_DIR = os.path.join(_root, "logs")


def analyze_day(date_str, log_end=None):
    entries = load_windowmon(date_str)
    if not entries:
        print(f"No windowmon data for {date_str}")
        return

    # Filter out idle markers
    real = [e for e in entries if not e.get("type")]
    if log_end:
        real = [e for e in real if e["_ts"].strftime("%H:%M") <= log_end]

    print(f"\n{'='*70}")
    print(f"  AUTODETECT AUDIT — {date_str}")
    if log_end:
        print(f"  (bis {log_end})")
    print(f"{'='*70}")
    print(f"\nRaw entries: {len(real)}")

    # ── 1. UNCLASSIFIABLE entries ──────────────────────────────────────
    print(f"\n{'─'*70}")
    print("  1. UNCLASSIFIABLE entries (→ potential new AutoDetect rules)")
    print(f"{'─'*70}\n")

    unclass = defaultdict(lambda: {"count": 0, "first": None, "last": None})
    for e in real:
        acc, act = classify_entry(e)
        if acc == "_UNCLASSIFIABLE":
            proc = e.get("process", "")
            title = e.get("title", "")
            # Normalize: remove hwnd-specific parts
            key = f"{proc}: {title[:70]}"
            u = unclass[key]
            u["count"] += 1
            ts = e["_ts"].strftime("%H:%M")
            if u["first"] is None:
                u["first"] = ts
            u["last"] = ts

    if unclass:
        for key, info in sorted(unclass.items(), key=lambda x: -x[1]["count"]):
            if info["count"] >= 2:  # Only show repeated patterns
                print(f"  [{info['count']:3d}x] {key}")
                print(f"         {info['first']}–{info['last']}")
        singles = sum(1 for v in unclass.values() if v["count"] == 1)
        if singles:
            print(f"\n  + {singles} single-occurrence unclassifiable entries (not shown)")
    else:
        print("  None — all entries classified! ✓")

    # ── 2. Classification summary ──────────────────────────────────────
    print(f"\n{'─'*70}")
    print("  2. Classification summary (account/activity → count)")
    print(f"{'─'*70}\n")

    class_summary = defaultdict(lambda: {"count": 0, "first": None, "last": None, "proc": ""})
    for e in real:
        acc, act = classify_entry(e)
        if acc.startswith("_"):
            continue  # skip specials
        key = f"{acc} / {act}"
        c = class_summary[key]
        c["count"] += 1
        ts = e["_ts"].strftime("%H:%M")
        if c["first"] is None:
            c["first"] = ts
        c["last"] = ts
        c["proc"] = e.get("process", "")

    for key, info in sorted(class_summary.items(), key=lambda x: -x[1]["count"])[:25]:
        print(f"  [{info['count']:3d}x] {key}  ({info['first']}–{info['last']})")

    # ── 3. AutoDetect blocks vs planner log ────────────────────────────
    print(f"\n{'─'*70}")
    print("  3. AutoDetect blocks vs actual planner log (mismatches)")
    print(f"{'─'*70}\n")

    blocks = build_activity_blocks(real)

    # Load planner log
    log_path = os.path.join(LOG_DIR, f"planner-log-{date_str}.json")
    logged = []
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            logged = json.load(f)

    # Parse log times
    log_entries = []
    for entry in logged:
        try:
            ls = datetime.strptime(f"{date_str} {entry['started_at']}", "%Y-%m-%d %H:%M:%S")
            le = datetime.strptime(f"{date_str} {entry['completed_at']}", "%Y-%m-%d %H:%M:%S")
            log_entries.append((ls, le, entry))
        except (KeyError, ValueError):
            continue

    mismatches = 0
    matches = 0
    for block in blocks:
        bstart = block["start"]
        bend = block["end"]
        b_act = block["activity"]
        b_acc = block["account"]
        dur_s = block.get("duration_s", 0)
        if dur_s < 60:
            continue

        # Find overlapping logged activity
        for ls, le, entry in log_entries:
            # Check if block falls within logged entry
            if ls <= bstart and le >= bend:
                logged_act = entry["activity"]
                logged_list = entry.get("list", "")

                # Extract task code from logged activity
                import re
                logged_code = ""
                m = re.search(r'\s([A-Z]{6})(?:\s|$)', logged_act)
                if m:
                    logged_code = m.group(1)

                block_code = ""
                m2 = re.search(r'\s([A-Z]{6})(?:\s|$)', b_act)
                if m2:
                    block_code = m2.group(1)

                # Check mismatch
                if block_code and logged_code and block_code != logged_code:
                    mismatches += 1
                    print(f"  {bstart.strftime('%H:%M')}–{bend.strftime('%H:%M')}  "
                          f"({int(dur_s)}s)")
                    print(f"    AutoDetect: [{b_acc}] {b_act[:60]}")
                    print(f"    Logged as:  {logged_act[:60]}")
                    print(f"    Source:     {logged_list}")
                    print()
                elif block_code and logged_code:
                    matches += 1
                break

    if mismatches == 0:
        print("  No mismatches found between AutoDetect and log! ✓")
    print(f"\n  Summary: {matches} matches, {mismatches} mismatches")

    # ── 4. Corrections analysis ────────────────────────────────────────
    print(f"\n{'─'*70}")
    print("  4. Manual corrections applied (from autodetect-corrections)")
    print(f"{'─'*70}\n")

    corr_path = os.path.join(LOG_DIR, f"autodetect-corrections-{date_str}.json")
    if os.path.exists(corr_path):
        with open(corr_path, "r", encoding="utf-8") as f:
            corrections = json.load(f)
        # Group by original → corrected
        corr_groups = defaultdict(list)
        for c in corrections:
            key = f"{c['original']} → {c['corrected']}"
            corr_groups[key].append(f"{c['start']}–{c['end']}")

        for key, times in sorted(corr_groups.items(), key=lambda x: -len(x[1])):
            print(f"  [{len(times):2d}x] {key}")
            if len(times) <= 3:
                for t in times:
                    print(f"         {t}")
        print(f"\n  Total corrections: {len(corrections)}")
    else:
        print("  No corrections file found.")


if __name__ == "__main__":
    dates = sys.argv[1:] if len(sys.argv) > 1 else ["2026-03-16", "2026-03-17"]
    for d in dates:
        # Check for :HH:MM suffix for log_end
        log_end = None
        if ":" in d and len(d) > 10:
            parts = d.split(":", 1)
            d = parts[0]
            log_end = parts[1]
        if d == "2026-03-17" and log_end is None:
            log_end = "11:32"
        analyze_day(d, log_end)
