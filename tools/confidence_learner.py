"""
confidence_learner.py — Compute and persist per-window-title activity confidence scores.

Correlates windowmon logs with planner-log activity data using an Exponential
Moving Average (EMA) learning system.

Usage:
  cd kontensystem
  py tools/confidence_learner.py                         # yesterday + today
  py tools/confidence_learner.py 2026-03-28              # one day
  py tools/confidence_learner.py 2026-03-03 2026-03-28   # range

Output:
  data/confidence_store.json  (persistent confidence store)
  logs/confidence-learner-output-YYYY-MM-DD.txt  (report)
"""

import sys
import os
import re
import json
from datetime import date, timedelta, datetime
from collections import defaultdict

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_here, "..")
LOG_DIR = os.path.join(_root, "logs")
DATA_DIR = os.path.join(_root, "data")
STORE_PATH = os.path.join(DATA_DIR, "confidence_store.json")

# Titles/processes to skip entirely
SKIP_TITLES = {"", "Programmumschaltung"}
SKIP_PROCESSES = {"ShellExperienceHost.exe", "SearchApp.exe"}

# EMA parameters
EMA_OLD = 0.80
EMA_NEW = 0.20

# Prune confidences below this threshold
PRUNE_THRESHOLD = 0.01

# Confidence thresholds for report sections
HIGH_CONF_THRESHOLD = 0.70

# Patterns for title normalization (msedge.exe)
_EDGE_SUFFIX_PATTERNS = [
    re.compile(r'\s+und\s+\d+\s+weitere\s+Seite[n]?\s+-\s+Persönlich\s+[–-]\s+Microsoft\s*Edge\s*$', re.IGNORECASE),
    re.compile(r'\s+-\s+Persönlich\s+[–-]\s+Microsoft\s*Edge\s*$', re.IGNORECASE),
]
_KEINE_RUECKMELDUNG = re.compile(r'\s+\(Keine\s+Rückmeldung\)\s*$', re.IGNORECASE)


# ── Tee output ────────────────────────────────────────────────────────────────

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


# ── Title normalization ───────────────────────────────────────────────────────

def normalize_title(process, title):
    """
    Normalize a window title to a stable key for confidence lookup.

    Rules:
    1. For msedge.exe: strip Edge-specific suffixes
    2. For any process: strip " (Keine Rückmeldung)" suffix
    3. Strip trailing whitespace
    """
    result = title

    if process and process.lower() == "msedge.exe":
        for pattern in _EDGE_SUFFIX_PATTERNS:
            result = pattern.sub("", result)

    result = _KEINE_RUECKMELDUNG.sub("", result)
    result = result.rstrip()
    return result


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
    """Load planner-log-YYYY-MM-DD.json and return a list of entry dicts."""
    path = os.path.join(LOG_DIR, f"planner-log-{date_str}.json")
    if not os.path.exists(path):
        return []
    try:
        with _open_with_fallback(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []
    return data if isinstance(data, list) else []


# ── Time parsing helpers ──────────────────────────────────────────────────────

def hhmm_to_secs(t_str):
    """Convert 'HH:MM:SS' or 'HH:MM' to seconds since midnight. Returns None on failure."""
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
    """Return True if event_secs falls in [start_secs, end_secs). Handles midnight crossing."""
    if start_secs == end_secs:
        return event_secs == start_secs
    if start_secs < end_secs:
        return start_secs <= event_secs < end_secs
    else:
        return event_secs >= start_secs or event_secs < end_secs


# ── Build planner interval lookup ─────────────────────────────────────────────

def build_log_intervals(planner_entries):
    """Parse planner-log entries into (start_secs, end_secs, activity) tuples."""
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
    """Find which planner activity covers event_secs. Last match wins for overlaps."""
    result = None
    for start_secs, end_secs, activity in intervals:
        if event_in_range(event_secs, start_secs, end_secs):
            result = activity
    return result


# ── Date helpers ──────────────────────────────────────────────────────────────

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


# ── Step 1: Compute daily observations ───────────────────────────────────────

def process_day(date_str, observations, transitions):
    """
    Process one day and accumulate observations and transition counts.

    observations: dict mapping store_key → {activity: total_duration_seconds}
    transitions:  dict mapping store_key → {backward_same, backward_total,
                                             forward_same, forward_total}
    store_key format: "process||normalized_title"

    Returns (events_processed, events_matched).
    """
    wm_events = load_windowmon(date_str)
    planner_entries = load_planner_log(date_str)

    if not wm_events:
        return 0, 0

    intervals = build_log_intervals(planner_entries)

    def parse_dt(ts_str):
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return None

    # Filter and parse events
    filtered = []
    for e in wm_events:
        if e.get("type") in ("idle_start", "idle_end"):
            continue
        process = e.get("process", "").strip()
        title = e.get("title", "").strip()
        if title in SKIP_TITLES:
            continue
        if process in SKIP_PROCESSES:
            continue
        dt = parse_dt(e.get("ts", ""))
        filtered.append((dt, process, title))

    # Sort chronologically (None timestamps go last)
    filtered.sort(key=lambda x: x[0] if x[0] is not None else datetime.max)

    processed = 0
    matched_count = 0

    # Build event_data: list of (store_key, activity_or_None, duration_secs)
    event_data = []
    for i, (dt, process, title) in enumerate(filtered):
        processed += 1

        norm_title = normalize_title(process, title)
        store_key = f"{process}||{norm_title}"

        if dt is None:
            event_data.append((store_key, None, 0))
            continue

        event_secs = dt.hour * 3600 + dt.minute * 60 + dt.second

        # Duration until next event with a valid timestamp
        duration_seconds = 0
        for j in range(i + 1, len(filtered)):
            next_dt = filtered[j][0]
            if next_dt is not None:
                diff = (next_dt - dt).total_seconds()
                duration_seconds = max(0, int(diff))
                break

        activity = find_activity(event_secs, intervals)
        event_data.append((store_key, activity, duration_seconds))

    # Update observations (existing logic)
    for store_key, activity, duration_secs in event_data:
        if activity is None:
            continue
        matched_count += 1
        if store_key not in observations:
            observations[store_key] = defaultdict(int)
        observations[store_key][activity] += duration_secs

    # ── Transition computation ─────────────────────────────────────────────
    # Build matched_events list: (store_key, activity) for events with activities
    matched_events = [(sk, act) for sk, act, _ in event_data if act is not None]
    n = len(matched_events)

    if n > 0:
        # Precompute backward neighbor index for each position.
        # For a run of consecutive events with the same key, all events in the run
        # share the same backward neighbor: the last event of the preceding run
        # (which has a different key by construction).
        backward_idx = [-1] * n
        last_run_end = -1   # index of last event of the most recent different-key run
        pos = 0
        while pos < n:
            key = matched_events[pos][0]
            end = pos
            while end < n and matched_events[end][0] == key:
                end += 1
            # Run is [pos, end)
            for k in range(pos, end):
                backward_idx[k] = last_run_end
            last_run_end = end - 1
            pos = end

        # Precompute forward neighbor index for each position (right-to-left pass).
        forward_idx = [-1] * n
        next_run_start = -1  # index of first event of the next different-key run
        pos = n - 1
        while pos >= 0:
            key = matched_events[pos][0]
            start = pos
            while start >= 0 and matched_events[start][0] == key:
                start -= 1
            # Run is [start+1, pos]
            for k in range(start + 1, pos + 1):
                forward_idx[k] = next_run_start
            next_run_start = start + 1
            pos = start

        # Accumulate transition counts
        for i, (key, act) in enumerate(matched_events):
            if key not in transitions:
                transitions[key] = {
                    'backward_same': 0, 'backward_total': 0,
                    'forward_same': 0,  'forward_total': 0,
                }

            bi = backward_idx[i]
            if bi >= 0:
                _, prev_act = matched_events[bi]
                transitions[key]['backward_total'] += 1
                if prev_act == act:
                    transitions[key]['backward_same'] += 1

            fi = forward_idx[i]
            if fi >= 0:
                _, next_act = matched_events[fi]
                transitions[key]['forward_total'] += 1
                if next_act == act:
                    transitions[key]['forward_same'] += 1

    return processed, matched_count


# ── Step 2: Load confidence store ─────────────────────────────────────────────

def load_store():
    """Load confidence_store.json. Returns empty dict if not found."""
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError, OSError):
        return {}


# ── Step 3: Update confidences and transitions using EMA ─────────────────────

def update_store(store, observations, transitions, dates):
    """
    Apply EMA updates to the store based on observations and transitions.

    Returns (updated_keys, new_keys) sets.
    """
    last_date = max(dates) if dates else date.today().isoformat()
    updated_keys = set()
    new_keys = set()

    for store_key, activity_durations in observations.items():
        total_secs = sum(activity_durations.values())
        if total_secs == 0:
            continue

        # Compute import confidences (time share per activity)
        import_conf = {
            act: dur / total_secs
            for act, dur in activity_durations.items()
        }

        # Compute observed transition probabilities from accumulated counts
        t = transitions.get(store_key, {})
        bt = t.get('backward_total', 0)
        ft = t.get('forward_total', 0)
        obs_p_before = t['backward_same'] / bt if bt > 0 else None
        obs_p_after  = t['forward_same']  / ft if ft > 0 else None

        if store_key in store:
            # EMA update for existing entry
            entry = store[store_key]
            old_conf = entry.get("confidences", {})

            # Merge all activity keys from old and import
            all_activities = set(old_conf.keys()) | set(import_conf.keys())
            new_conf = {}
            for act in all_activities:
                old_val = old_conf.get(act, 0.0)
                imp_val = import_conf.get(act, 0.0)
                new_conf[act] = EMA_OLD * old_val + EMA_NEW * imp_val

            # Prune low-confidence entries
            new_conf = {act: v for act, v in new_conf.items() if v >= PRUNE_THRESHOLD}

            # Normalize to sum to 1.0
            conf_total = sum(new_conf.values())
            if conf_total > 0:
                new_conf = {act: v / conf_total for act, v in new_conf.items()}

            entry["confidences"] = new_conf
            entry["total_secs"] = entry.get("total_secs", 0) + total_secs
            entry["last_seen"] = last_date

            # EMA update for transition probabilities (only if we have new data)
            if obs_p_before is not None:
                old_p_before = entry.get("p_same_before", 1.0)
                entry["p_same_before"] = EMA_OLD * old_p_before + EMA_NEW * obs_p_before
            elif "p_same_before" not in entry:
                entry["p_same_before"] = 1.0

            if obs_p_after is not None:
                old_p_after = entry.get("p_same_after", 1.0)
                entry["p_same_after"] = EMA_OLD * old_p_after + EMA_NEW * obs_p_after
            elif "p_same_after" not in entry:
                entry["p_same_after"] = 1.0

            updated_keys.add(store_key)

        else:
            # New entry: use import confidences directly
            store[store_key] = {
                "confidences": dict(import_conf),
                "total_secs": total_secs,
                "last_seen": last_date,
                "p_same_before": obs_p_before if obs_p_before is not None else 1.0,
                "p_same_after":  obs_p_after  if obs_p_after  is not None else 1.0,
            }
            new_keys.add(store_key)

    return updated_keys, new_keys


# ── Step 5: Save store ────────────────────────────────────────────────────────

def save_store(store):
    """Write confidence_store.json with sorted keys, indent=2, ensure_ascii=False."""
    os.makedirs(DATA_DIR, exist_ok=True)
    # Sort keys at top level and also sort confidences within each entry
    sorted_store = {}
    for key in sorted(store.keys()):
        entry = store[key]
        sorted_entry = {
            "confidences": dict(sorted(entry.get("confidences", {}).items())),
            "total_secs": entry.get("total_secs", 0),
            "last_seen": entry.get("last_seen", ""),
            "p_same_before": entry.get("p_same_before", 1.0),
            "p_same_after":  entry.get("p_same_after",  1.0),
        }
        sorted_store[key] = sorted_entry

    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted_store, f, indent=2, ensure_ascii=False)


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_time(secs):
    """Format seconds as Xh YYm or just Zm."""
    m = round(secs / 60)
    if m >= 60:
        return f"{m // 60}h {m % 60:02d}m"
    return f"{m}m"


def top_activity(confidences):
    """Return (activity, confidence) for the highest confidence activity."""
    if not confidences:
        return ("(none)", 0.0)
    return max(confidences.items(), key=lambda x: x[1])


# ── Step 6: Print summary report ─────────────────────────────────────────────

def print_report(store, observations, updated_keys, new_keys, dates,
                 total_events, total_matched, days_with_data):
    """Print the full summary report."""
    start_date = dates[0] if dates else "?"
    end_date = dates[-1] if dates else "?"

    print(f"{'='*75}")
    print(f"  CONFIDENCE LEARNER")
    if len(dates) == 1:
        print(f"  Date: {start_date}")
    else:
        print(f"  Date range: {start_date} → {end_date}  ({len(dates)} days)")
    print(f"{'='*75}")

    print(f"\n  Days processed: {len(dates)}  |  Days with data: {days_with_data}")
    print(f"  Window events:  {total_events}  |  Matched to activity: {total_matched}")
    match_pct = 100.0 * total_matched / total_events if total_events > 0 else 0.0
    print(f"  Match rate:     {match_pct:.1f}%")
    print(f"  Unique normalized keys observed: {len(observations)}")

    # ── TOP CONFIDENT MAPPINGS ────────────────────────────────────────────────
    print(f"\n{'─'*75}")
    print(f"  TOP CONFIDENT MAPPINGS  (top confidence >= {int(HIGH_CONF_THRESHOLD*100)}%)")
    print(f"{'─'*75}\n")

    confident_entries = []
    for key, entry in store.items():
        confs = entry.get("confidences", {})
        if not confs:
            continue
        top_act, top_conf = top_activity(confs)
        if top_conf >= HIGH_CONF_THRESHOLD:
            confident_entries.append((entry.get("total_secs", 0), key, top_act, top_conf))

    confident_entries.sort(key=lambda x: -x[0])
    top30 = confident_entries[:30]

    if top30:
        for total_secs, key, top_act, top_conf in top30:
            # Split key into process and title
            parts = key.split("||", 1)
            proc = parts[0] if len(parts) > 1 else ""
            title = parts[1] if len(parts) > 1 else key
            display_title = title[:60] if len(title) > 60 else title
            marker = " [NEW]" if key in new_keys else ""
            entry = store.get(key, {})
            p_before = entry.get("p_same_before", 1.0)
            p_after  = entry.get("p_same_after",  1.0)
            print(f"  [{fmt_time(total_secs):>6}] {proc}: \"{display_title}\"{marker}")
            print(f"           → {top_act[:55]:<55s} ({top_conf*100:.1f}%)  ←{p_before*100:.0f}% →{p_after*100:.0f}%")
    else:
        print("  (none)")

    if len(confident_entries) > 30:
        print(f"\n  ... and {len(confident_entries) - 30} more confident entries not shown")

    # ── AMBIGUOUS MAPPINGS ────────────────────────────────────────────────────
    print(f"\n{'─'*75}")
    print(f"  AMBIGUOUS MAPPINGS  (top confidence < {int(HIGH_CONF_THRESHOLD*100)}%)")
    print(f"{'─'*75}\n")

    ambiguous_entries = []
    for key, entry in store.items():
        confs = entry.get("confidences", {})
        if not confs:
            continue
        top_act, top_conf = top_activity(confs)
        if top_conf < HIGH_CONF_THRESHOLD:
            ambiguous_entries.append((entry.get("total_secs", 0), key, confs))

    ambiguous_entries.sort(key=lambda x: -x[0])
    top20_amb = ambiguous_entries[:20]

    if top20_amb:
        for total_secs, key, confs in top20_amb:
            parts = key.split("||", 1)
            proc = parts[0] if len(parts) > 1 else ""
            title = parts[1] if len(parts) > 1 else key
            display_title = title[:55] if len(title) > 55 else title
            marker = " [NEW]" if key in new_keys else ""
            entry = store.get(key, {})
            p_before = entry.get("p_same_before", 1.0)
            p_after  = entry.get("p_same_after",  1.0)
            print(f"  [{fmt_time(total_secs):>6}] {proc}: \"{display_title}\"{marker}")
            sorted_acts = sorted(confs.items(), key=lambda x: -x[1])
            for act, conf in sorted_acts[:3]:
                print(f"           → {act[:50]:<50s} ({conf*100:.1f}%)")
            if len(sorted_acts) > 3:
                print(f"           + {len(sorted_acts) - 3} more activities")
            print(f"           ←{p_before*100:.0f}% →{p_after*100:.0f}%")
            print()
    else:
        print("  (none)\n")

    if len(ambiguous_entries) > 20:
        print(f"  ... and {len(ambiguous_entries) - 20} more ambiguous entries not shown")

    # ── NEWLY LEARNED ─────────────────────────────────────────────────────────
    print(f"\n{'─'*75}")
    print(f"  NEWLY LEARNED  (titles not previously in store)")
    print(f"{'─'*75}\n")

    newly_learned = []
    for key in new_keys:
        entry = store.get(key, {})
        total_secs = entry.get("total_secs", 0)
        confs = entry.get("confidences", {})
        top_act, top_conf = top_activity(confs)
        newly_learned.append((total_secs, key, top_act, top_conf))

    newly_learned.sort(key=lambda x: -x[0])
    top20_new = newly_learned[:20]

    if top20_new:
        for total_secs, key, top_act, top_conf in top20_new:
            parts = key.split("||", 1)
            proc = parts[0] if len(parts) > 1 else ""
            title = parts[1] if len(parts) > 1 else key
            display_title = title[:60] if len(title) > 60 else title
            print(f"  [{fmt_time(total_secs):>6}] {proc}: \"{display_title}\"")
            print(f"           → {top_act[:55]:<55s} ({top_conf*100:.1f}%)")
    else:
        print("  (none)")

    if len(newly_learned) > 20:
        print(f"\n  ... and {len(newly_learned) - 20} more newly learned entries not shown")

    # ── TRANSITION ANALYSIS ───────────────────────────────────────────────────
    print(f"\n{'─'*75}")
    print(f"  TRANSITION ANALYSIS")
    print(f"{'─'*75}")

    # Build flat list: (total_secs, key, top_act, top_conf, p_before, p_after)
    all_entries_trans = []
    for key, entry in store.items():
        confs = entry.get("confidences", {})
        if not confs:
            continue
        top_act, top_conf = top_activity(confs)
        total_secs = entry.get("total_secs", 0)
        p_before = entry.get("p_same_before", 1.0)
        p_after  = entry.get("p_same_after",  1.0)
        all_entries_trans.append((total_secs, key, top_act, top_conf, p_before, p_after))

    def _show_trans_entry(tup):
        total_secs, key, top_act, top_conf, p_before, p_after = tup
        parts = key.split("||", 1)
        proc  = parts[0] if len(parts) > 1 else ""
        title = parts[1] if len(parts) > 1 else key
        disp  = title[:50] if len(title) > 50 else title
        print(f"  [{fmt_time(total_secs):>6}] {proc}: \"{disp}\"")
        print(f"           → {top_act[:50]:<50s} ({top_conf*100:.1f}%)  ←{p_before*100:.0f}% →{p_after*100:.0f}%")

    # 1. DURCHREICHER (←hoch →hoch, schwache eigene Zuordnung)
    print(f"\n  DURCHREICHER (←hoch →hoch) — rauscharme Titel ohne eigene Aktivität\n")
    durchreicher = sorted(
        [e for e in all_entries_trans if e[4] >= 0.80 and e[5] >= 0.80 and e[3] < 0.70],
        key=lambda x: -x[0]
    )
    if durchreicher:
        for e in durchreicher[:15]:
            _show_trans_entry(e)
    else:
        print("  (keine)")

    # 2. EINTRITTS-MARKER (←niedrig →hoch)
    print(f"\n  EINTRITTS-MARKER (←niedrig →hoch) — Titel signalisiert START einer neuen Aktivität\n")
    eintritte = sorted(
        [e for e in all_entries_trans if e[4] < 0.50 and e[5] >= 0.70],
        key=lambda x: -x[0]
    )
    if eintritte:
        for e in eintritte[:15]:
            _show_trans_entry(e)
    else:
        print("  (keine)")

    # 3. AUSTRITTS-MARKER (←hoch →niedrig)
    print(f"\n  AUSTRITTS-MARKER (←hoch →niedrig) — Titel signalisiert ENDE einer Aktivität\n")
    austritte = sorted(
        [e for e in all_entries_trans if e[4] >= 0.70 and e[5] < 0.50],
        key=lambda x: -x[0]
    )
    if austritte:
        for e in austritte[:15]:
            _show_trans_entry(e)
    else:
        print("  (keine)")

    # ── Summary stats ─────────────────────────────────────────────────────────
    total_entries = len(store)
    n_updated = len(updated_keys)
    n_new = len(new_keys)
    n_unchanged = total_entries - n_updated - n_new

    print(f"\n{'='*75}")
    print(f"  SUMMARY")
    print(f"{'='*75}")
    print(f"  Total entries in store : {total_entries}")
    print(f"  Entries updated (EMA)  : {n_updated}")
    print(f"  Entries new            : {n_new}")
    print(f"  Entries unchanged      : {n_unchanged}")
    print(f"  Store path             : {STORE_PATH}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    dates = parse_args(args)

    if not dates:
        print("Error: invalid date range.", file=sys.stderr)
        sys.exit(1)

    # Set up tee output
    last_date = dates[-1]
    log_path = os.path.join(_root, f"logs/confidence-learner-output-{last_date}.txt")
    original_stdout = sys.stdout
    tee = TeeOutput(sys.stdout, log_path)
    sys.stdout = tee

    try:
        # ── Step 1: Compute daily observations and transitions ─────────────────
        observations = {}   # store_key → {activity: total_duration_seconds}
        transitions  = {}   # store_key → {backward_same, backward_total,
                            #               forward_same,  forward_total}
        total_events = 0
        total_matched = 0
        days_with_data = 0

        for d in dates:
            n_events, n_matched = process_day(d, observations, transitions)
            if n_events > 0:
                days_with_data += 1
            total_events  += n_events
            total_matched += n_matched

        # ── Step 2: Load existing confidence store ────────────────────────────
        store = load_store()

        # ── Step 3 & 4: Update confidences + transitions using EMA ───────────
        updated_keys, new_keys = update_store(store, observations, transitions, dates)

        # ── Step 5: Save updated store ────────────────────────────────────────
        save_store(store)

        # ── Step 6: Print summary report ──────────────────────────────────────
        print_report(
            store, observations, updated_keys, new_keys, dates,
            total_events, total_matched, days_with_data
        )

        print(f"Output saved to: logs/confidence-learner-output-{last_date}.txt")

    finally:
        sys.stdout = original_stdout
        tee.close()


if __name__ == "__main__":
    main()
