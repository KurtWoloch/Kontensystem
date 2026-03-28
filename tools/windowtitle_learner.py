"""
windowtitle_learner.py — Correlate raw window titles with logged activities
and compute AutoDetect learning suggestions.

Usage:
  cd kontensystem
  python tools/windowtitle_learner.py                          # yesterday + today
  python tools/windowtitle_learner.py 2026-03-27               # one day
  python tools/windowtitle_learner.py 2026-03-20 2026-03-27    # range (all days in between)

  Note: On Windows, if piping output set PYTHONIOENCODING=utf-8 first:
    set PYTHONIOENCODING=utf-8 && python tools/windowtitle_learner.py

Output sections:
  1. High-confidence mappings (>= 80% confidence, >= 300s total duration)
     Sorted by total duration descending.
  2. Ambiguous mappings (top confidence < 80%, >= 300s total duration)
     Same format — title is used in multiple different activity contexts.
  3. Rare mappings (< 300s total duration)
     Summary only (count, not individual entries).
"""

import sys
import os
import json
from datetime import date, timedelta, datetime
from collections import defaultdict

# Force UTF-8 output on Windows to handle special characters in window titles
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_here, "..")
LOG_DIR = os.path.join(_root, "logs")

SKIP_TITLES = {"", "Programmumschaltung"}
MIN_SECONDS = 300  # 5 minutes minimum total duration (replaces MIN_OCCURRENCES = 5)
HIGH_CONF_THRESHOLD = 0.80

# Activities containing these substrings are teleworking indicators and are
# excluded from confidence calculations (the private PC window is open but the
# user is actually working on the company laptop).
TELEWORKING_FILTERS = [
    "Arbeitszeit absolvieren",
    "BREPDZ",
    "BRTWGF",
    "BREPGM",
    "BREPWC",
    "BREPZE",
    "BRFAFA",
    "BRFAHF",
    "BRZG",
]


# ── Tee output helper ─────────────────────────────────────────────────────────

class TeeOutput:
    """Write to both a primary stream and a file simultaneously."""

    def __init__(self, stream, filepath):
        self._stream = stream
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        self._file = open(filepath, "w", encoding="utf-8")
        self._filepath = filepath

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)
        return len(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def close(self):
        self._file.close()

    @property
    def filepath(self):
        return self._filepath

    def __getattr__(self, name):
        return getattr(self._stream, name)


# ── File loading helpers ──────────────────────────────────────────────────────

def _open_with_fallback(path):
    """Open a file trying UTF-8 first, then Latin-1."""
    try:
        return open(path, "r", encoding="utf-8")
    except UnicodeDecodeError:
        return open(path, "r", encoding="latin-1")


def load_windowmon(date_str):
    """Load windowmon-YYYY-MM-DD.jsonl and return a list of event dicts."""
    path = os.path.join(LOG_DIR, f"windowmon-{date_str}.jsonl")
    if not os.path.exists(path):
        return []
    events = []
    with _open_with_fallback(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(entry)
    return events


def load_planner_log(date_str):
    """Load planner-log-YYYY-MM-DD.json and return a list of entry dicts."""
    path = os.path.join(LOG_DIR, f"planner-log-{date_str}.json")
    if not os.path.exists(path):
        return []
    try:
        with _open_with_fallback(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(data, list):
        return data
    return []


# ── Time parsing helpers ──────────────────────────────────────────────────────

def ts_to_secs(ts_str):
    """
    Convert an ISO timestamp like '2026-03-27T06:11:01' to seconds since midnight.
    Returns None on failure.
    """
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.hour * 3600 + dt.minute * 60 + dt.second
    except (ValueError, TypeError):
        return None


def hhmm_to_secs(t_str):
    """
    Convert 'HH:MM:SS' or 'HH:MM' to seconds since midnight.
    Returns None on failure.
    """
    if not t_str:
        return None
    parts = t_str.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return h * 3600 + m * 60 + s
    except (ValueError, IndexError):
        return None


def event_in_range(event_secs, start_secs, end_secs):
    """
    Return True if event_secs falls in [start_secs, end_secs).
    Handles midnight crossing (end_secs < start_secs).
    """
    if start_secs == end_secs:
        # Zero-duration entry: treat as point match
        return event_secs == start_secs
    if start_secs < end_secs:
        # Normal case: no midnight crossing
        return start_secs <= event_secs < end_secs
    else:
        # Midnight crossing: e.g. started_at=23:58, completed_at=00:02
        return event_secs >= start_secs or event_secs < end_secs


# ── Build planner interval lookup for a single day ───────────────────────────

def build_log_intervals(planner_entries):
    """
    Parse planner-log entries into a list of (start_secs, end_secs, activity).
    Skips entries with skipped=True.
    Returns list sorted by start_secs.
    """
    intervals = []
    for entry in planner_entries:
        if entry.get("skipped", False):
            continue
        activity = entry.get("activity", "").strip()
        if not activity:
            continue
        start_secs = hhmm_to_secs(entry.get("started_at", ""))
        end_secs = hhmm_to_secs(entry.get("completed_at", ""))
        if start_secs is None or end_secs is None:
            continue
        intervals.append((start_secs, end_secs, activity))
    return intervals


def find_activity(event_secs, intervals):
    """
    Find the planner activity whose time range contains event_secs.
    Returns the activity string or None if not found.
    Iterates through all intervals; last match wins for overlapping entries.
    """
    result = None
    for start_secs, end_secs, activity in intervals:
        if event_in_range(event_secs, start_secs, end_secs):
            result = activity
    return result


def is_teleworking(activity):
    """Return True if the activity matches any teleworking filter substring."""
    return any(f in activity for f in TELEWORKING_FILTERS)


# ── Core correlation logic ────────────────────────────────────────────────────

def process_day(date_str, mapping_counts):
    """
    Process one day and accumulate (process, title) → {activity: duration_seconds}
    in mapping_counts. Duration is computed as the time (in seconds) until the next
    event on the same day; the last event of the day gets duration 0.

    Returns (events_processed, events_matched, teleworking_filtered).
    """
    wm_events = load_windowmon(date_str)
    planner_entries = load_planner_log(date_str)

    if not wm_events:
        return 0, 0, 0  # (events_processed, events_matched, teleworking_filtered)

    intervals = build_log_intervals(planner_entries)

    # Filter out idle events
    non_idle = [e for e in wm_events if e.get("type") not in ("idle_start", "idle_end")]

    # Parse datetime for each event (needed for duration calculation)
    def parse_dt(ts_str):
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return None

    events_with_dt = [(parse_dt(e.get("ts", "")), e) for e in non_idle]

    # Sort chronologically (events with None timestamps go last)
    events_with_dt.sort(key=lambda x: x[0] if x[0] is not None else datetime.max)

    processed = 0
    matched = 0
    teleworking_filtered = 0

    for i, (dt, event) in enumerate(events_with_dt):
        title = event.get("title", "").strip()
        process = event.get("process", "").strip()

        # Skip empty or blocked titles
        if title in SKIP_TITLES:
            continue

        processed += 1

        if dt is None:
            continue

        event_secs = dt.hour * 3600 + dt.minute * 60 + dt.second

        # Duration = seconds until the next event with a valid timestamp.
        # The last event of the day (or the last one with a valid timestamp)
        # gets duration 0.
        duration_seconds = 0
        for j in range(i + 1, len(events_with_dt)):
            next_dt, _ = events_with_dt[j]
            if next_dt is not None:
                diff = (next_dt - dt).total_seconds()
                duration_seconds = max(0, int(diff))
                break

        activity = find_activity(event_secs, intervals)
        if activity is None:
            continue

        matched += 1

        # Teleworking filter: don't skew confidence for windows left open
        # while the user is actually working on the company laptop.
        if is_teleworking(activity):
            teleworking_filtered += 1
            continue

        key = (process, title)
        if key not in mapping_counts:
            mapping_counts[key] = defaultdict(int)
        mapping_counts[key][activity] += duration_seconds

    return processed, matched, teleworking_filtered


# ── Date range helpers ────────────────────────────────────────────────────────

def date_range(start_str, end_str):
    """Return list of date strings for all days from start_str to end_str (inclusive)."""
    try:
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
    except ValueError:
        return []
    dates = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def parse_args(argv):
    """
    Parse command-line arguments and return a list of date strings to process.
    No args → yesterday + today.
    One arg → that single day.
    Two args → all days in range (inclusive).
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    if len(argv) == 0:
        return [yesterday.isoformat(), today.isoformat()]
    elif len(argv) == 1:
        return [argv[0]]
    else:
        return date_range(argv[0], argv[1])


# ── Output formatting ─────────────────────────────────────────────────────────

def format_mapping_entry(key, activity_counts):
    """Format a single (process, title) → activities block with time-based stats."""
    process, title = key
    total_secs = sum(activity_counts.values())
    total_mins = round(total_secs / 60)
    sorted_acts = sorted(activity_counts.items(), key=lambda x: -x[1])

    lines = []
    lines.append(f"[{total_mins:4d}m] {process}: \"{title}\"")
    for act, secs in sorted_acts:
        pct = 100.0 * secs / total_secs if total_secs > 0 else 0
        act_mins = round(secs / 60)
        lines.append(f"        \u2192 {act:<50s} ({pct:5.1f}%, {act_mins:3d}m)")
    return "\n".join(lines)


def print_section(title, entries):
    """Print a labeled section with entries."""
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}\n")
    if entries:
        for block in entries:
            print(block)
            print()
    else:
        print("  (none)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    dates = parse_args(args)

    if not dates:
        print("Error: invalid date range.", file=sys.stderr)
        sys.exit(1)

    # Set up tee output: log file named after the last date in the range
    last_date = dates[-1]
    log_rel = f"logs/learner-output-{last_date}.txt"
    log_abs = os.path.join(_root, log_rel)
    original_stdout = sys.stdout
    tee = TeeOutput(sys.stdout, log_abs)
    sys.stdout = tee

    try:
        print(f"{'='*70}")
        print(f"  WINDOW TITLE LEARNER")
        if len(dates) == 1:
            print(f"  Date: {dates[0]}")
        else:
            print(f"  Dates: {dates[0]} → {dates[-1]}  ({len(dates)} days)")
        print(f"{'='*70}")

        # Accumulate all mappings across days
        mapping_counts = {}  # (process, title) → {activity: duration_seconds}
        total_events = 0
        total_matched = 0
        total_teleworking = 0
        days_with_data = 0

        for d in dates:
            n_events, n_matched, n_tw = process_day(d, mapping_counts)
            if n_events > 0:
                days_with_data += 1
            total_events += n_events
            total_matched += n_matched
            total_teleworking += n_tw

        print(f"\n  Days processed: {len(dates)}  |  Days with data: {days_with_data}")
        print(f"  Window events:  {total_events}  |  Matched to activity: {total_matched}")
        match_pct = 100.0 * total_matched / total_events if total_events > 0 else 0
        print(f"  Match rate:     {match_pct:.1f}%")
        print(f"  Unique (process, title) pairs: {len(mapping_counts)}")

        # Categorize mappings
        high_conf = []   # (total_secs, key, activity_counts) — conf >= 80%, secs >= MIN_SECONDS
        ambiguous = []   # (total_secs, key, activity_counts) — top conf < 80%, secs >= MIN_SECONDS
        rare_count = 0   # number of (process, title) pairs below MIN_SECONDS
        rare_secs = 0    # total seconds in rare mappings

        for key, activity_counts in mapping_counts.items():
            total_secs = sum(activity_counts.values())
            if total_secs < MIN_SECONDS:
                rare_count += 1
                rare_secs += total_secs
                continue
            top_secs = max(activity_counts.values())
            top_conf = top_secs / total_secs
            if top_conf >= HIGH_CONF_THRESHOLD:
                high_conf.append((total_secs, key, activity_counts))
            else:
                ambiguous.append((total_secs, key, activity_counts))

        # Sort high-confidence entries by total duration descending
        high_conf.sort(key=lambda x: -x[0])
        ambiguous.sort(key=lambda x: -x[0])

        # ── Section 1: High-confidence ────────────────────────────────────────
        print(f"\n{'='*70}")
        print(f"  1. HOCHKONFIDENTE MAPPINGS  (>= {int(HIGH_CONF_THRESHOLD*100)}% Confidence, >= {MIN_SECONDS}s Gesamtdauer)")
        print(f"{'='*70}")

        if high_conf:
            print()
            for total_secs, key, activity_counts in high_conf:
                print(format_mapping_entry(key, activity_counts))
                print()
        else:
            print("\n  (keine)")

        # ── Section 2: Ambiguous ──────────────────────────────────────────────
        print(f"\n{'='*70}")
        print(f"  2. AMBIGE MAPPINGS  (Top-Confidence < {int(HIGH_CONF_THRESHOLD*100)}%, >= {MIN_SECONDS}s Gesamtdauer)")
        print(f"{'='*70}")

        if ambiguous:
            print()
            for total_secs, key, activity_counts in ambiguous:
                print(format_mapping_entry(key, activity_counts))
                print()
        else:
            print("\n  (keine)")

        # ── Section 3: Rare ───────────────────────────────────────────────────
        print(f"\n{'='*70}")
        print(f"  3. SELTENE MAPPINGS  (< {MIN_SECONDS}s Gesamtdauer)")
        print(f"{'='*70}\n")

        if rare_count > 0:
            rare_mins = round(rare_secs / 60)
            print(f"  {rare_count} (process, title)-Kombinationen mit insgesamt {rare_mins}m Gesamtdauer")
            print(f"  — nicht einzeln aufgelistet.")
        else:
            print("  (keine)")

        # ── Teleworking summary ───────────────────────────────────────────────
        if total_matched > 0:
            tw_pct = 100.0 * total_teleworking / total_matched
            print(f"\n  Teleworking-Events gefiltert: {total_teleworking} ({tw_pct:.1f}% aller gematchten Events)")

        print()
        print(f"Output saved to: {log_rel}")

    finally:
        sys.stdout = original_stdout
        tee.close()


if __name__ == "__main__":
    main()
