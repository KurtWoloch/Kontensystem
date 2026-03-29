"""
title_stability.py — Analyze window title transition stability.

For each window title: how often does it appear WITHOUT causing a change
in the logged activity? Combined with exclusivity (how many different
activities a title maps to), this classifies titles into:

  - STÖRER:  low exclusivity + high stability → title pops up during many
             activities but never indicates a real switch (e.g. Programmumschaltung,
             explorer.exe taskbar)
  - KONSISTENT: high exclusivity + high stability → title belongs to ONE activity
             and stays there (both current and previous title map to the same thing)
  - MARKER:  high exclusivity + low stability → title reliably signals a NEW
             activity (valuable for AutoDetect)
  - AMBIG:   low exclusivity + low stability → title appears across activities
             AND often coincides with real switches (hard to classify)

Usage:
  cd kontensystem
  python tools/title_stability.py                          # yesterday + today
  python tools/title_stability.py 2026-03-28               # one day
  python tools/title_stability.py 2026-03-20 2026-03-28    # range

Output: logs/stability-output-YYYY-MM-DD.txt
"""

import sys
import os
import json
from datetime import date, timedelta, datetime
from collections import defaultdict

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_here, "..")
LOG_DIR = os.path.join(_root, "logs")

# Titles to skip entirely (empty, OS noise)
SKIP_TITLES = {"", "Programmumschaltung"}
# Processes to skip (transient OS UI)
SKIP_PROCESSES = {"ShellExperienceHost.exe", "SearchApp.exe"}

# Minimum total duration (seconds) to include in analysis
MIN_SECONDS = 120  # 2 minutes

# Thresholds for classification
HIGH_EXCLUSIVITY = 0.70   # >= 70% of time spent on one activity
HIGH_STABILITY = 0.70     # >= 70% of appearances cause no activity change


# ── Reuse helpers from windowtitle_learner.py ─────────────────────────────────

def _open_with_fallback(path):
    try:
        return open(path, "r", encoding="utf-8")
    except UnicodeDecodeError:
        return open(path, "r", encoding="latin-1")


def load_windowmon(date_str):
    path = os.path.join(LOG_DIR, f"windowmon-{date_str}.jsonl")
    if not os.path.exists(path):
        return []
    events = []
    with _open_with_fallback(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def load_planner_log(date_str):
    path = os.path.join(LOG_DIR, f"planner-log-{date_str}.json")
    if not os.path.exists(path):
        return []
    try:
        with _open_with_fallback(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def hhmm_to_secs(t_str):
    if not t_str:
        return None
    parts = t_str.split(":")
    try:
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return h * 3600 + m * 60 + s
    except (ValueError, IndexError):
        return None


def event_in_range(event_secs, start_secs, end_secs):
    if start_secs == end_secs:
        return event_secs == start_secs
    if start_secs < end_secs:
        return start_secs <= event_secs < end_secs
    return event_secs >= start_secs or event_secs < end_secs


def build_log_intervals(planner_entries):
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
    result = None
    for start_secs, end_secs, activity in intervals:
        if event_in_range(event_secs, start_secs, end_secs):
            result = activity
    return result


# ── Tee output ────────────────────────────────────────────────────────────────

class TeeOutput:
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


# ── Date helpers ──────────────────────────────────────────────────────────────

def date_range(start_str, end_str):
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
    today = date.today()
    yesterday = today - timedelta(days=1)
    if len(argv) == 0:
        return [yesterday.isoformat(), today.isoformat()]
    elif len(argv) == 1:
        return [argv[0]]
    else:
        return date_range(argv[0], argv[1])


# ── Core analysis ─────────────────────────────────────────────────────────────

def process_day(date_str, title_stats):
    """
    For each window title event, determine:
    1. Which activity it maps to (via planner-log intervals)
    2. Whether that activity is different from the PREVIOUS event's activity

    Accumulates into title_stats:
      (process, title) → {
          'total': int,           # total appearances
          'no_change': int,       # appearances where activity == previous activity
          'change': int,          # appearances where activity != previous activity
          'no_match': int,        # event had no matching activity in log
          'activities': {activity: duration_seconds},  # for exclusivity
          'total_secs': int,      # total duration
      }

    Returns (events_processed, events_matched).
    """
    wm_events = load_windowmon(date_str)
    planner_entries = load_planner_log(date_str)

    if not wm_events:
        return 0, 0

    intervals = build_log_intervals(planner_entries)

    # Filter idle events and parse timestamps
    def parse_dt(ts_str):
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return None

    filtered = []
    for e in wm_events:
        if e.get("type") in ("idle_start", "idle_end"):
            continue
        dt = parse_dt(e.get("ts", ""))
        if dt is None:
            continue
        title = e.get("title", "").strip()
        process = e.get("process", "").strip()
        if title in SKIP_TITLES or process in SKIP_PROCESSES:
            continue
        filtered.append((dt, title, process))

    filtered.sort(key=lambda x: x[0])

    processed = 0
    matched = 0
    prev_activity = None

    for i, (dt, title, process) in enumerate(filtered):
        processed += 1
        event_secs = dt.hour * 3600 + dt.minute * 60 + dt.second
        activity = find_activity(event_secs, intervals)

        # Duration until next event
        duration = 0
        for j in range(i + 1, len(filtered)):
            next_dt = filtered[j][0]
            diff = (next_dt - dt).total_seconds()
            duration = max(0, int(diff))
            break

        key = (process, title)
        if key not in title_stats:
            title_stats[key] = {
                'total': 0,
                'no_change': 0,
                'change': 0,
                'no_match': 0,
                'activities': defaultdict(int),
                'total_secs': 0,
            }

        stats = title_stats[key]
        stats['total'] += 1
        stats['total_secs'] += duration

        if activity is None:
            stats['no_match'] += 1
            # Don't update prev_activity — gap in log coverage
        else:
            matched += 1
            stats['activities'][activity] += duration

            if prev_activity is not None:
                if activity == prev_activity:
                    stats['no_change'] += 1
                else:
                    stats['change'] += 1
            # else: first event of the day, neither change nor no_change

            prev_activity = activity

    return processed, matched


def classify(exclusivity, stability):
    """Classify a title based on exclusivity and stability."""
    if exclusivity >= HIGH_EXCLUSIVITY and stability >= HIGH_STABILITY:
        return "KONSISTENT"
    elif exclusivity >= HIGH_EXCLUSIVITY and stability < HIGH_STABILITY:
        return "MARKER"
    elif exclusivity < HIGH_EXCLUSIVITY and stability >= HIGH_STABILITY:
        return "STÖRER"
    else:
        return "AMBIG"


def fmt_mins(secs):
    m = round(secs / 60)
    if m >= 60:
        return f"{m // 60}h {m % 60:02d}m"
    return f"{m}m"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    dates = parse_args(args)

    if not dates:
        print("Error: invalid date range.", file=sys.stderr)
        sys.exit(1)

    last_date = dates[-1]
    log_path = os.path.join(_root, f"logs/stability-output-{last_date}.txt")
    original_stdout = sys.stdout
    tee = TeeOutput(sys.stdout, log_path)
    sys.stdout = tee

    try:
        print(f"{'='*75}")
        print(f"  FENSTERTITEL-STABILITÄTSANALYSE")
        if len(dates) == 1:
            print(f"  Datum: {dates[0]}")
        else:
            print(f"  Zeitraum: {dates[0]} → {dates[-1]}  ({len(dates)} Tage)")
        print(f"{'='*75}")

        title_stats = {}
        total_events = 0
        total_matched = 0
        days_with_data = 0

        for d in dates:
            n_proc, n_match = process_day(d, title_stats)
            if n_proc > 0:
                days_with_data += 1
            total_events += n_proc
            total_matched += n_match

        print(f"\n  Tage verarbeitet: {len(dates)}  |  Mit Daten: {days_with_data}")
        print(f"  Fenster-Events:   {total_events}  |  Gematchte: {total_matched}")
        print(f"  Einzigartige (Prozess, Titel)-Paare: {len(title_stats)}")

        # Compute metrics and classify
        classified = []  # (class, exclusivity, stability, total_secs, transitions, key, stats)

        for key, stats in title_stats.items():
            if stats['total_secs'] < MIN_SECONDS:
                continue

            # Exclusivity: what % of time is spent on the dominant activity?
            acts = stats['activities']
            total_act_secs = sum(acts.values())
            if total_act_secs > 0:
                top_secs = max(acts.values())
                exclusivity = top_secs / total_act_secs
            else:
                exclusivity = 0

            # Stability: of all transitions (change + no_change), what % are no_change?
            transitions = stats['no_change'] + stats['change']
            if transitions > 0:
                stability = stats['no_change'] / transitions
            else:
                stability = 1.0  # no transitions observed → fully stable by default

            cls = classify(exclusivity, stability)
            classified.append((
                cls, exclusivity, stability, stats['total_secs'],
                transitions, key, stats
            ))

        # Sort by class priority, then by total_secs descending
        class_order = {"STÖRER": 0, "MARKER": 1, "AMBIG": 2, "KONSISTENT": 3}
        classified.sort(key=lambda x: (class_order.get(x[0], 9), -x[3]))

        # Count per class
        class_counts = defaultdict(int)
        class_secs = defaultdict(int)
        for cls, excl, stab, tsecs, trans, key, stats in classified:
            class_counts[cls] += 1
            class_secs[cls] += tsecs

        print(f"\n  Klassifiziert (>= {MIN_SECONDS}s Dauer): {len(classified)}")
        print()
        print(f"  {'Klasse':<12} {'Anzahl':>6} {'Gesamtzeit':>10}  Beschreibung")
        print(f"  {'─'*12} {'─'*6} {'─'*10}  {'─'*40}")
        descs = {
            "STÖRER":     "Niedrige Exkl. + Hohe Stab. → Noise/Popup",
            "MARKER":     "Hohe Exkl. + Niedrige Stab. → Wechsel-Signal",
            "KONSISTENT": "Hohe Exkl. + Hohe Stab. → Stabile Zuordnung",
            "AMBIG":      "Niedrige Exkl. + Niedrige Stab. → Unklar",
        }
        for cls in ["STÖRER", "MARKER", "KONSISTENT", "AMBIG"]:
            n = class_counts.get(cls, 0)
            s = class_secs.get(cls, 0)
            print(f"  {cls:<12} {n:>6} {fmt_mins(s):>10}  {descs[cls]}")

        # ── Detail sections per class ─────────────────────────────────────────

        for cls in ["STÖRER", "MARKER", "AMBIG", "KONSISTENT"]:
            items = [x for x in classified if x[0] == cls]
            if not items:
                continue

            emoji = {"STÖRER": "🚫", "MARKER": "🎯", "KONSISTENT": "✅", "AMBIG": "❓"}
            print(f"\n{'='*75}")
            print(f"  {emoji.get(cls, '')} {cls} — {descs[cls]}")
            print(f"{'='*75}\n")

            # Sort within class by total_secs descending
            items.sort(key=lambda x: -x[3])

            for _, excl, stab, tsecs, trans, key, stats in items[:30]:
                process, title = key
                display_title = title[:60] if len(title) > 60 else title
                n_acts = len(stats['activities'])

                print(f"  [{fmt_mins(tsecs):>6}] {process}: \"{display_title}\"")
                print(f"          Exkl={excl:.0%}  Stab={stab:.0%}  "
                      f"Wechsel={stats['change']}/{trans}  "
                      f"Aktivitäten={n_acts}")

                # Show top activities
                sorted_acts = sorted(stats['activities'].items(), key=lambda x: -x[1])
                for act, act_secs in sorted_acts[:3]:
                    pct = 100.0 * act_secs / sum(stats['activities'].values())
                    print(f"          → {act[:50]:<50s} ({pct:4.1f}%, {fmt_mins(act_secs)})")
                if len(sorted_acts) > 3:
                    print(f"          + {len(sorted_acts) - 3} weitere")
                print()

            if len(items) > 30:
                print(f"  ... und {len(items) - 30} weitere {cls}-Einträge\n")

        print(f"\nOutput gespeichert: logs/stability-output-{last_date}.txt")

    finally:
        sys.stdout = original_stdout
        tee.close()


if __name__ == "__main__":
    main()
