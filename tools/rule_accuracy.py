"""
rule_accuracy.py — Measure how accurate each hardcoded AutoDetect rule is.

For each windowmon entry, compares what classify_entry() returns
with what was actually logged in the planner-log for that time.

Output: per-rule accuracy (% of time the rule's suggested activity
matches the actual logged activity), sorted by total time descending.

Usage:
  cd kontensystem
  py tools/rule_accuracy.py 2026-03-28              # one day
  py tools/rule_accuracy.py 2026-03-03 2026-03-28   # range
"""

import sys
import os
import json
import re
from datetime import date, timedelta, datetime
from collections import defaultdict

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add planner/ to path so we can import windowmon_summary
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "planner"))

from windowmon_summary import classify_entry, load_windowmon, load_planner_log

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_here, "..")
LOG_DIR = os.path.join(_root, "logs")

# Teleworking filters (same as confidence_learner)
TELEWORKING_FILTERS = [
    "Arbeitszeit absolvieren", "BREPDZ", "BRTWGF", "BREPGM", "BREPWC",
    "BREPZE", "BREPZS", "BRFAFA", "BRFAHF", "BRALAB", "BRZG", "BKDD",
]

def _is_teleworking(activity):
    return any(f in activity for f in TELEWORKING_FILTERS)


def _open_with_fallback(path):
    try:
        return open(path, "r", encoding="utf-8")
    except UnicodeDecodeError:
        return open(path, "r", encoding="latin-1")


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
        if start_secs == end_secs:
            if event_secs == start_secs:
                result = activity
        elif start_secs < end_secs:
            if start_secs <= event_secs < end_secs:
                result = activity
        else:
            if event_secs >= start_secs or event_secs < end_secs:
                result = activity
    return result


def _task_code(activity):
    """Extract 4-6 char task code from end of activity name."""
    m = re.search(r'\s([A-Z]{4,6})\s*(?:\(Fs\.\))?\s*$', activity)
    return m.group(1) if m else ""


def _account_code(activity):
    """Extract 2-char account code from task code."""
    tc = _task_code(activity)
    return tc[:2] if tc else ""


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


def fmt_mins(secs):
    m = round(secs / 60)
    if m >= 60:
        return f"{m // 60}h {m % 60:02d}m"
    return f"{m}m"


def main():
    args = sys.argv[1:]
    dates = parse_args(args)

    if not dates:
        print("Error: invalid date range.", file=sys.stderr)
        sys.exit(1)

    # rule_stats[(rule_account, rule_activity)] = {
    #   'total_secs': int,
    #   'match_secs': int,         # rule activity == actual activity
    #   'account_match_secs': int, # at least account matches
    #   'actual_activities': {actual_activity: duration_secs},
    # }
    rule_stats = {}
    total_events = 0
    matched_events = 0

    for date_str in dates:
        wm_path = os.path.join(LOG_DIR, f"windowmon-{date_str}.jsonl")
        log_path = os.path.join(LOG_DIR, f"planner-log-{date_str}.json")

        if not os.path.exists(wm_path) or not os.path.exists(log_path):
            continue

        wm_entries = load_windowmon(date_str)
        with _open_with_fallback(log_path) as f:
            planner_entries = json.load(f)
        intervals = build_log_intervals(planner_entries)

        if not wm_entries or not intervals:
            continue

        # Sort chronologically
        wm_entries.sort(key=lambda e: e.get("_ts", datetime.max))

        for i, entry in enumerate(wm_entries):
            if entry.get("type") in ("idle_start", "idle_end"):
                continue

            dt = entry.get("_ts")
            if dt is None:
                continue

            total_events += 1
            event_secs = dt.hour * 3600 + dt.minute * 60 + dt.second

            # What does the hardcoded rule say?
            rule_account, rule_activity = classify_entry(entry)

            # What was actually logged?
            actual_activity = find_activity(event_secs, intervals)
            if actual_activity is None:
                continue
            if _is_teleworking(actual_activity):
                continue

            matched_events += 1

            # Duration until next event
            duration = 0
            for j in range(i + 1, len(wm_entries)):
                next_dt = wm_entries[j].get("_ts")
                if next_dt is not None:
                    duration = max(0, int((next_dt - dt).total_seconds()))
                    break

            key = (rule_account, rule_activity)
            if key not in rule_stats:
                rule_stats[key] = {
                    'total_secs': 0,
                    'match_secs': 0,
                    'account_match_secs': 0,
                    'actual_activities': defaultdict(int),
                }

            stats = rule_stats[key]
            stats['total_secs'] += duration
            stats['actual_activities'][actual_activity] += duration

            # Exact match: rule activity == actual logged activity
            if rule_activity == actual_activity:
                stats['match_secs'] += duration

            # Account match: at least the account code is correct
            rule_acc = rule_account if rule_account and not rule_account.startswith("_") else _account_code(rule_activity)
            actual_acc = _account_code(actual_activity)
            if rule_acc and actual_acc and rule_acc == actual_acc:
                stats['account_match_secs'] += duration

    # Output
    print(f"{'='*80}")
    print(f"  AUTODETECT RULE ACCURACY ANALYSIS")
    if len(dates) == 1:
        print(f"  Date: {dates[0]}")
    else:
        print(f"  Range: {dates[0]} → {dates[-1]}  ({len(dates)} days)")
    print(f"{'='*80}")
    print(f"\n  Events: {total_events}  |  Matched to activity: {matched_events}")
    print(f"  Unique rule outputs: {len(rule_stats)}")

    # Sort by total time descending
    sorted_rules = sorted(rule_stats.items(), key=lambda x: -x[1]['total_secs'])

    # Section 1: Rules with low activity accuracy (< 50%)
    print(f"\n{'─'*80}")
    print(f"  LOW ACCURACY RULES  (Aktivitäts-Treffer < 50%)")
    print(f"  These rules often classify wrong — confidence store may do better")
    print(f"{'─'*80}\n")

    low_acc = [(k, v) for k, v in sorted_rules
               if v['total_secs'] >= 120 and
               (v['match_secs'] / v['total_secs'] if v['total_secs'] > 0 else 0) < 0.50]

    for (r_acc, r_act), stats in low_acc[:30]:
        total = stats['total_secs']
        match_pct = 100.0 * stats['match_secs'] / total if total > 0 else 0
        acc_pct = 100.0 * stats['account_match_secs'] / total if total > 0 else 0
        top_actual = sorted(stats['actual_activities'].items(), key=lambda x: -x[1])

        print(f"  [{fmt_mins(total):>7}] [{r_acc}] {r_act[:55]}")
        print(f"          Aktivität-Treffer: {match_pct:4.1f}%  |  Konto-Treffer: {acc_pct:4.1f}%")
        for act, secs in top_actual[:3]:
            act_pct = 100.0 * secs / total
            print(f"          → tatsächlich: {act[:50]:<50s} ({act_pct:4.1f}%)")
        if len(top_actual) > 3:
            print(f"          + {len(top_actual) - 3} weitere")
        print()

    # Section 2: Rules with good accuracy (>= 50%)
    print(f"\n{'─'*80}")
    print(f"  ACCURATE RULES  (Aktivitäts-Treffer >= 50%)")
    print(f"{'─'*80}\n")

    high_acc = [(k, v) for k, v in sorted_rules
                if v['total_secs'] >= 120 and
                (v['match_secs'] / v['total_secs'] if v['total_secs'] > 0 else 0) >= 0.50]

    for (r_acc, r_act), stats in high_acc[:30]:
        total = stats['total_secs']
        match_pct = 100.0 * stats['match_secs'] / total if total > 0 else 0
        print(f"  [{fmt_mins(total):>7}] {match_pct:4.1f}%  [{r_acc}] {r_act[:55]}")

    if len(high_acc) > 30:
        print(f"\n  ... und {len(high_acc) - 30} weitere")

    # Section 3: Special accounts summary
    print(f"\n{'─'*80}")
    print(f"  SPECIAL ACCOUNTS (_UNCLASSIFIABLE, _EXPLORER_ACCOUNT_HINT, etc.)")
    print(f"{'─'*80}\n")

    specials = [(k, v) for k, v in sorted_rules
                if k[0].startswith("_") and v['total_secs'] >= 60]
    for (r_acc, r_act), stats in specials:
        total = stats['total_secs']
        top_actual = sorted(stats['actual_activities'].items(), key=lambda x: -x[1])
        print(f"  [{fmt_mins(total):>7}] [{r_acc}] {r_act[:55]}")
        for act, secs in top_actual[:3]:
            act_pct = 100.0 * secs / total
            print(f"          → {act[:50]:<50s} ({act_pct:4.1f}%)")
        if len(top_actual) > 3:
            print(f"          + {len(top_actual) - 3} weitere")
        print()

    # Save
    out_path = os.path.join(LOG_DIR, f"rule-accuracy-{dates[-1]}.txt")
    # Re-run to file would be complex; just note the path
    print(f"\n(Run with: py tools/rule_accuracy.py {dates[0]} {dates[-1]} > logs/rule-accuracy-{dates[-1]}.txt)")


if __name__ == "__main__":
    main()
