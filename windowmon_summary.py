# -*- coding: utf-8 -*-
"""
windowmon_summary.py — End-of-day activity summary from windowmon JSONL logs.

Reads a day's windowmon log, applies AutoDetect rules to classify window
titles into activities/accounts, aggregates fragmented entries into total
time per activity, and outputs a summary suitable for Aufwandserfassung.

Usage:
    py windowmon_summary.py [--date YYYY-MM-DD] [--detail] [--idle]

Options:
    --date    Target date (default: today)
    --detail  Show individual classified blocks (not just totals)
    --idle    Show idle/Off-PC periods separately
    --planner-log PATH  Cross-reference with planner log for Off-PC activity names

The AutoDetect rules are derived from the alignment report analysis
(alignment-report-2026-03-10.md) and Kurt's windowlog_corrector.py rules.
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════ #
#  AutoDetect Rules                                                          #
#  Map window titles/processes to account codes + activity names.            #
#  Order matters: first match wins.                                          #
# ═══════════════════════════════════════════════════════════════════════════ #

def _title_contains(title: str, *keywords: str) -> bool:
    """Case-insensitive check if title contains ALL keywords."""
    tl = title.lower()
    return all(kw.lower() in tl for kw in keywords)


def _title_contains_any(title: str, *keywords: str) -> bool:
    """Case-insensitive check if title contains ANY keyword."""
    tl = title.lower()
    return any(kw.lower() in tl for kw in keywords)


# Each rule: (match_fn, account, activity)
# match_fn receives (title, process, browser)
AUTODETECT_RULES = [
    # ── Planner idle (Off-PC markers) ──────────────────────────────────
    (lambda t, p, b: p == "planner_idle",
     "IDLE", "Off-PC"),

    # ── Planner app — distinguish phantom vs real usage ────────────────
    # "Aufgabe erledigt" or "Eintrag bearbeiten" dialogs (short = phantom)
    (lambda t, p, b: p == "python.exe" and
     _title_contains_any(t, "Aufgabe erledigt", "Eintrag bearbeiten",
                         "Ungeplante Aktivität"),
     "KS", "Planer-Bedienung (Dialog)"),

    # Planner Off-PC title → use activity from title
    (lambda t, p, b: p == "python.exe" and "Off-PC" in t and
     "Tagesplanung" in t,
     "_PLANNER_OFFPC", ""),  # special: extract activity from title

    # Planner main window
    (lambda t, p, b: p == "python.exe" and
     _title_contains_any(t, "Tagesplanung", "Reaktiver Planer"),
     "KS", "Planer-Bedienung"),

    # ── Old Window Logger ──────────────────────────────────────────────
    # When Window Logger is in foreground, Kurt uses it as "idle" signal:
    # it means the PREVIOUS activity is still running (typically off-PC).
    # Short focus (< few seconds) = just selecting an activity.
    # Long focus = genuine off-PC / andere Aktivität.
    (lambda t, p, b: p == "Window logger.exe",
     "_WINLOGGER", "andere Aktivitaet (Window Logger idle)"),

    # ── Radio / Music ─────────────────────────────────────────────────
    (lambda t, p, b: p == "Radio Würmchen.exe" or
     _title_contains(t, "Radio Würmchen") or
     _title_contains(t, "Radio Wuermchen"),
     "RW", "Radio Würmchen"),

    (lambda t, p, b: _title_contains(t, "Backlink Broadcast") or
     _title_contains(t, "Andon FM"),
     "RW", "Andon FM / Backlink Broadcast"),

    (lambda t, p, b: _title_contains(t, "Live365") and
     p not in ("Live365Scraper.exe",),
     "RW", "Anhören Radiosender (Live365)"),

    (lambda t, p, b: p == "Live365Scraper.exe",
     "RW", "Andon FM Scraper"),

    (lambda t, p, b: p.lower() == "winamp.exe",
     "RW", "Anhören Musik (Winamp)"),

    # ── Arena AI ──────────────────────────────────────────────────────
    (lambda t, p, b: _title_contains_any(t, "Arena AI", "arena.ai",
                                          "artificialanalysis"),
     "RW", "Befragung Arena AI"),

    # ── YouTube ───────────────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains(t, "YouTube"),
     "IN", "Ansehen YouTube-Videos"),

    # ── Social Media / X ──────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains_any(t, "/ X", "twitter.com",
                                                 "x.com"),
     "RA", "Surfen X"),

    (lambda t, p, b: b and _title_contains(t, "moltbook"),
     "IN", "Surfen Moltbook"),

    # ── OpenClaw ──────────────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains(t, "OpenClaw"),
     "KS", "Diskussion OpenClaw"),

    # ── Access DB (Essensplan, Kontensystem) ──────────────────────────
    (lambda t, p, b: p.lower() == "msaccess.exe",
     "LE", "Bearb. Essensdatenbank (Access)"),

    # ── Essensplan (Notepad) ──────────────────────────────────────────
    (lambda t, p, b: p == "notepad.exe" and
     _title_contains_any(t, "Essensplan", "Speiseplan", "Einkaufsliste"),
     "LE", "Bearb. Essensplan"),

    # ── VS Code / Code editing ────────────────────────────────────────
    (lambda t, p, b: p.lower() in ("code.exe", "code - insiders.exe") and
     _title_contains_any(t, "kontensystem", "planner", "Tagesplanung"),
     "KS", "Entwicklung Tagesplanung (VS Code)"),

    (lambda t, p, b: p.lower() in ("code.exe", "code - insiders.exe") and
     _title_contains_any(t, "radio", "würmchen", "wuermchen", "andon",
                          "scraper"),
     "RW", "Entwicklung Radio (VS Code)"),

    (lambda t, p, b: p.lower() in ("code.exe", "code - insiders.exe"),
     "PC", "Bearbeitung in VS Code"),

    # ── BRZ / Work ────────────────────────────────────────────────────
    (lambda t, p, b: _title_contains_any(t, "BRZG", "BRZ"),
     "BR", "Arbeit BRZ"),

    # ── Email (Outlook) ──────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains_any(t, "Outlook", "outlook.live",
                                                 "outlook.office"),
     "IN", "Bearbeitung Mails"),

    # ── Explorer (file management) ────────────────────────────────────
    (lambda t, p, b: p == "explorer.exe" and
     _title_contains_any(t, "USB-STICK", "Kontenverwaltung",
                          "Betrieb"),
     "KS", "Dateiverwaltung (Kontensystem)"),

    (lambda t, p, b: p == "explorer.exe",
     "PC", "Dateiverwaltung (Explorer)"),

    # ── General browsing ──────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains_any(t, "orf.at"),
     "IN", "div. Surfen (News)"),

    (lambda t, p, b: b,
     "IN", "div. Surfen"),

    # ── Fallback ──────────────────────────────────────────────────────
    (lambda t, p, b: True,
     "PC", "Sonstige PC-Nutzung"),
]


# ═══════════════════════════════════════════════════════════════════════════ #
#  Core Processing                                                           #
# ═══════════════════════════════════════════════════════════════════════════ #

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def load_windowmon(date_str: str) -> List[Dict]:
    """Load and parse a day's windowmon JSONL file."""
    path = os.path.join(LOG_DIR, f"windowmon-{date_str}.jsonl")
    if not os.path.exists(path):
        print(f"Datei nicht gefunden: {path}")
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry["_ts"] = datetime.strptime(entry["ts"],
                                                  "%Y-%m-%dT%H:%M:%S")
                entries.append(entry)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"  Warnung: Zeile {line_no} übersprungen: {e}")
    return entries


def load_planner_log(date_str: str) -> List[Dict]:
    """Load planner log for cross-referencing Off-PC activity names."""
    path = os.path.join(LOG_DIR, f"planner-log-{date_str}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_offpc_activity(title: str) -> Tuple[str, str]:
    """Extract account and activity from planner Off-PC title.

    Title format: 'Tagesplanung — Off-PC — Duschen LEMTDU'
    → account from task code (first 2 chars), activity = full name.
    """
    # Split on " — " (em-dash with spaces)
    parts = title.split(" — ")
    if len(parts) >= 3:
        activity = parts[2].strip()
    elif " - Off-PC - " in title:
        # Fallback: regular dashes
        parts = title.split(" - Off-PC - ")
        activity = parts[-1].strip() if len(parts) >= 2 else ""
    else:
        return "LE", "Off-PC (unbekannt)"

    if not activity:
        return "LE", "Off-PC (unbekannt)"

    # Try to extract task code (6 chars at end)
    task_code_match = re.search(r'\s([A-Z]{6})$', activity)
    if task_code_match:
        code = task_code_match.group(1)
        account = code[:2]
        return account, activity

    # No task code → generic
    return "LE", f"Off-PC: {activity}"


def classify_entry(entry: Dict) -> Tuple[str, str]:
    """Apply AutoDetect rules to classify a windowmon entry.

    Returns (account, activity).
    """
    # Handle idle markers
    entry_type = entry.get("type", "")
    if entry_type in ("idle_start", "idle_end"):
        return "IDLE", "Off-PC"

    title = entry.get("title", "")
    process = entry.get("process", "")
    browser = entry.get("browser", "")

    for match_fn, account, activity in AUTODETECT_RULES:
        try:
            if match_fn(title, process, browser):
                # Special case: Planner Off-PC title → extract activity
                if account == "_PLANNER_OFFPC":
                    return _extract_offpc_activity(title)
                return account, activity
        except Exception:
            continue

    return "PC", "Sonstige PC-Nutzung"


def build_activity_blocks(entries: List[Dict],
                          planner_log: Optional[List[Dict]] = None
                          ) -> List[Dict]:
    """Convert raw windowmon entries into classified activity blocks.

    Each block: {account, activity, start, end, duration_s, entries}

    Adjacent entries with the same classification are merged.
    """
    if not entries:
        return []

    blocks = []
    current_block = None

    for entry in entries:
        ts = entry["_ts"]
        account, activity = classify_entry(entry)

        # Skip idle markers as separate entries (they're info-only)
        if entry.get("type") in ("idle_start", "idle_end"):
            continue

        # Special: Window Logger in foreground = "idle" signal.
        # The previous activity continues (user is off-PC or selecting).
        if account == "_WINLOGGER" and current_block:
            current_block["end"] = ts
            current_block["entries"] += 1
            continue

        if (current_block and
                current_block["account"] == account and
                current_block["activity"] == activity and
                (ts - current_block["end"]).total_seconds() < 300):
            # Extend current block (< 5 min gap = same activity)
            current_block["end"] = ts
            current_block["entries"] += 1
        else:
            if current_block:
                blocks.append(current_block)
            current_block = {
                "account": account,
                "activity": activity,
                "start": ts,
                "end": ts,
                "entries": 1,
            }

    if current_block:
        blocks.append(current_block)

    # Set end times: each block ends when the next one starts,
    # BUT cap at a maximum gap to avoid inflating blocks across
    # long Off-PC periods (e.g., BRZ workday on company laptop).
    MAX_BLOCK_GAP_S = 600  # 10 minutes — beyond this, don't extend the block

    for i in range(len(blocks) - 1):
        gap_s = (blocks[i + 1]["start"] - blocks[i]["end"]).total_seconds()
        if gap_s <= MAX_BLOCK_GAP_S:
            blocks[i]["end"] = blocks[i + 1]["start"]
        else:
            # Cap: extend by at most 60 seconds past last entry
            blocks[i]["end"] = blocks[i]["end"] + timedelta(seconds=60)

    # Calculate durations
    for block in blocks:
        block["duration_s"] = max(0, (block["end"] - block["start"]).total_seconds())

    return blocks


def inject_idle_periods(blocks: List[Dict],
                        entries: List[Dict]) -> List[Dict]:
    """Insert Off-PC blocks based on idle markers from the planner.

    Idle markers: {type: "idle_start"} and {type: "idle_end", idle_start: ...}
    These override whatever windowmon saw during that period.
    """
    idle_periods = []
    for entry in entries:
        if entry.get("type") == "idle_end":
            idle_start_str = entry.get("idle_start")
            if idle_start_str:
                try:
                    idle_start = datetime.strptime(idle_start_str,
                                                    "%Y-%m-%dT%H:%M:%S")
                    idle_end = entry["_ts"]
                    idle_periods.append((idle_start, idle_end))
                except ValueError:
                    pass

    if not idle_periods:
        return blocks

    # For each idle period, find the planner Off-PC title if available
    # (from window entries during idle time)
    idle_activities = []
    for idle_start, idle_end in idle_periods:
        # Find the last Off-PC title entry before/during idle
        offpc_account, offpc_activity = "LE", "Off-PC"
        for entry in entries:
            if entry.get("type"):
                continue  # skip markers
            ts = entry["_ts"]
            title = entry.get("title", "")
            if ts <= idle_end and "Off-PC" in title and "Tagesplanung" in title:
                offpc_account, offpc_activity = _extract_offpc_activity(title)

        idle_activities.append({
            "account": offpc_account,
            "activity": offpc_activity,
            "start": idle_start,
            "end": idle_end,
            "duration_s": (idle_end - idle_start).total_seconds(),
            "entries": 0,
            "is_idle": True,
        })

    # Merge idle blocks into the block list, splitting overlapping blocks
    result = []
    idle_idx = 0
    for block in blocks:
        # Check if any idle period overlaps this block
        while idle_idx < len(idle_activities):
            idle = idle_activities[idle_idx]
            if idle["start"] >= block["end"]:
                break  # idle starts after this block
            if idle["end"] <= block["start"]:
                idle_idx += 1
                continue  # idle ended before this block

            # Overlap: idle period cuts into this block
            # Part before idle
            if block["start"] < idle["start"]:
                pre = dict(block)
                pre["end"] = idle["start"]
                pre["duration_s"] = (pre["end"] - pre["start"]).total_seconds()
                if pre["duration_s"] > 0:
                    result.append(pre)

            # The idle block itself
            result.append(idle)

            # Adjust block to start after idle
            block = dict(block)
            block["start"] = idle["end"]
            block["duration_s"] = (block["end"] - block["start"]).total_seconds()
            idle_idx += 1

        if block["duration_s"] > 0:
            result.append(block)

    return result


def aggregate_summary(blocks: List[Dict]) -> Dict[str, float]:
    """Aggregate blocks into total minutes per account/activity."""
    totals = defaultdict(float)
    for block in blocks:
        key = f'{block["account"]}/{block["activity"]}'
        totals[key] += block["duration_s"] / 60.0
    return dict(totals)


def detect_gaps(entries: List[Dict],
                min_gap_minutes: int = 5) -> List[Tuple[datetime, datetime, float]]:
    """Detect gaps in windowmon data (potential Off-PC periods).

    Returns list of (start, end, duration_minutes) for gaps >= min_gap_minutes.
    """
    gaps = []
    for i in range(1, len(entries)):
        if entries[i].get("type"):
            continue  # skip markers
        if entries[i - 1].get("type"):
            continue

        prev_ts = entries[i - 1]["_ts"]
        curr_ts = entries[i]["_ts"]
        gap_min = (curr_ts - prev_ts).total_seconds() / 60.0
        if gap_min >= min_gap_minutes:
            gaps.append((prev_ts, curr_ts, gap_min))
    return gaps


# ═══════════════════════════════════════════════════════════════════════════ #
#  Output Formatting                                                         #
# ═══════════════════════════════════════════════════════════════════════════ #

def print_summary(blocks: List[Dict], totals: Dict[str, float],
                  gaps: List, show_detail: bool, show_idle: bool):
    """Print the activity summary report."""

    print("=" * 76)
    print(f"  WINDOWMON TAGESZUSAMMENFASSUNG")
    if blocks:
        day = blocks[0]["start"].strftime("%d.%m.%Y")
        span = (f'{blocks[0]["start"].strftime("%H:%M")} – '
                f'{blocks[-1]["end"].strftime("%H:%M")}')
        print(f"  Datum: {day}    Zeitraum: {span}")
    print("=" * 76)

    # ── Totals by account ─────────────────────────────────────────────
    account_totals = defaultdict(float)
    for key, mins in totals.items():
        acct = key.split("/")[0]
        account_totals[acct] += mins

    print(f"\n{'KONTO':<6} {'MINUTEN':>8}  {'STUNDEN':>7}")
    print(f"{'-'*6} {'-'*8}  {'-'*7}")
    for acct, mins in sorted(account_totals.items(),
                              key=lambda x: -x[1]):
        if acct == "IDLE" and not show_idle:
            continue
        print(f"{acct:<6} {mins:8.1f}  {mins/60:7.2f}h")
    total_mins = sum(v for k, v in account_totals.items()
                     if k != "IDLE" or show_idle)
    print(f"{'------':6} {'--------':>8}  {'-------':>7}")
    print(f"{'TOTAL':<6} {total_mins:8.1f}  {total_mins/60:7.2f}h")

    # ── Totals by activity ────────────────────────────────────────────
    print(f"\n{'KONTO':<6} {'MIN':>6}  {'AKTIVITÄT'}")
    print(f"{'-'*6} {'-'*6}  {'-'*50}")
    for key, mins in sorted(totals.items(), key=lambda x: -x[1]):
        if mins < 1.0:
            continue
        acct = key.split("/")[0]
        activity = key.split("/", 1)[1]
        if acct == "IDLE" and not show_idle:
            continue
        print(f"{acct:<6} {mins:6.1f}  {activity}")

    # ── Gaps (potential undetected Off-PC) ─────────────────────────────
    if gaps:
        print(f"\n{'='*76}")
        print(f"  ERKANNTE LUECKEN (>= 5 Min. ohne windowmon-Eintraege)")
        print(f"{'='*76}")
        print(f"  {'VON':>8}  {'BIS':>8}  {'DAUER':>6}  MÖGLICHE BEDEUTUNG")
        print(f"  {'-'*8}  {'-'*8}  {'-'*6}  {'-'*40}")
        for start, end, dur in gaps:
            meaning = ""
            hour = start.hour
            if 7 <= hour <= 9:
                meaning = "Morgentoilette / Duschen?"
            elif 12 <= hour <= 13:
                meaning = "Mittagspause?"
            elif 20 <= hour <= 21:
                meaning = "Laufen / Spaziergang?"
            elif 22 <= hour <= 23:
                meaning = "Abendzeremonie?"
            print(f"  {start.strftime('%H:%M'):>8}  {end.strftime('%H:%M'):>8}"
                  f"  {dur:5.1f}m  {meaning}")

    # ── Detailed block view ───────────────────────────────────────────
    if show_detail:
        print(f"\n{'='*76}")
        print(f"  DETAILIERTE BLÖCKE")
        print(f"{'='*76}")
        print(f"  {'VON':>8}  {'BIS':>8}  {'MIN':>5}  {'KONTO':<6} "
              f"{'AKTIVITÄT'}")
        print(f"  {'-'*8}  {'-'*8}  {'-'*5}  {'-'*6} {'-'*44}")
        for block in blocks:
            dur = block["duration_s"] / 60.0
            if dur < 0.15:  # skip < 10 second blocks
                continue
            idle_mark = " [Off-PC]" if block.get("is_idle") else ""
            acct = block["account"]
            if acct == "IDLE" and not show_idle:
                continue
            print(f"  {block['start'].strftime('%H:%M'):>8}  "
                  f"{block['end'].strftime('%H:%M'):>8}  "
                  f"{dur:5.1f}  {acct:<6} "
                  f"{block['activity']}{idle_mark}")


# ═══════════════════════════════════════════════════════════════════════════ #
#  CLI                                                                       #
# ═══════════════════════════════════════════════════════════════════════════ #

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    show_detail = False
    show_idle = False
    planner_log_path = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            date_str = args[i + 1]
            i += 2
        elif args[i] == "--detail":
            show_detail = True
            i += 1
        elif args[i] == "--idle":
            show_idle = True
            i += 1
        elif args[i] == "--planner-log" and i + 1 < len(args):
            planner_log_path = args[i + 1]
            i += 2
        elif args[i] in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"Unbekannter Parameter: {args[i]}")
            sys.exit(1)

    print(f"Lade windowmon-Log für {date_str}...")
    entries = load_windowmon(date_str)
    if not entries:
        print("Keine Einträge gefunden.")
        sys.exit(0)

    # Filter out non-window entries for gap detection
    window_entries = [e for e in entries if not e.get("type")]
    print(f"  {len(window_entries)} Fenster-Einträge, "
          f"{len(entries) - len(window_entries)} Marker")

    # Build classified activity blocks
    blocks = build_activity_blocks(entries)
    print(f"  {len(blocks)} Aktivitätsblöcke erkannt")

    # Inject idle periods
    blocks = inject_idle_periods(blocks, entries)

    # Detect gaps
    gaps = detect_gaps(entries, min_gap_minutes=5)
    if gaps:
        print(f"  {len(gaps)} Luecken >= 5 Min. erkannt")

    # Aggregate
    totals = aggregate_summary(blocks)

    # Output
    print()
    print_summary(blocks, totals, gaps, show_detail, show_idle)


if __name__ == "__main__":
    main()
