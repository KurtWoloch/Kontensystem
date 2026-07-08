"""
day_report.py — Compare the day's initial projection against actual results.

Usage:
    py planner/day_report.py                  # today
    py planner/day_report.py 2026-03-04       # specific date

Reads:
    logs/projection-YYYY-MM-DD.json   (ideal plan from startup)
    logs/planner-log-YYYY-MM-DD.json  (actual log from the day)

Outputs a human-readable report to stdout and saves it to:
    logs/report-YYYY-MM-DD.txt
"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime


SCRIPT_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(SCRIPT_DIR, "..", "logs")


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_time(s):
    """Parse 'HH:MM' or 'HH:MM:SS' into minutes since midnight."""
    if not s:
        return None
    parts = s.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def fmt_minutes(mins):
    """Format minutes as Xh YYm."""
    if mins < 0:
        return f"-{fmt_minutes(-mins)}"
    h = mins // 60
    m = mins % 60
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def extract_task_code(activity_name):
    """Extract the 6-char (or 4-6 char) task code from the end of an activity name.

    Examples:
        'Anhören RW-Prg. / Tonträger RWMPAR' -> 'RWMPAR'
        'Morgensport' -> None
    """
    if not activity_name:
        return None
    name = activity_name.strip()
    if name.endswith(" (Verlängerung)"):
        name = name[:-15].strip()
    if name.endswith(" (Fs.)"):
        name = name[:-6].strip()
        
    words = name.strip().split()
    if words:
        last = words[-1]
        if re.match(r'^[A-ZÄÖÜß]{4,6}$', last):
            return last
    return None


def is_wenn_dialog(activity: str) -> bool:
    """Check if this is a conditional dialog entry (auto-generated, 0 duration)."""
    return activity.strip().startswith("Wenn ")


def is_im_bett(activity: str) -> bool:
    return activity.strip().lower().startswith("im bett")


def is_aufstehen(activity: str) -> bool:
    return "aufstehen" in activity.strip().lower()


def find_gaps_and_overlaps(log_data):
    real_entries = []
    for e in log_data:
        started = e.get("started_at", "")
        completed = e.get("completed_at", "")
        skipped = e.get("skipped", False)
        activity = e.get("activity", "")

        if not started or not completed:
            continue

        if is_wenn_dialog(activity):
            continue

        if skipped and started == completed:
            continue

        start_m = parse_time(started)
        end_m = parse_time(completed)
        if start_m is None or end_m is None:
            continue

        if skipped and start_m == end_m:
            continue

        real_entries.append({
            "activity": activity,
            "start": start_m,
            "end": end_m,
            "started_str": started[:5],
            "completed_str": completed[:5],
            "skipped": skipped
        })

    real_entries.sort(key=lambda x: (x["start"], x["end"]))

    gaps = []
    overlaps = []
    
    for i in range(len(real_entries) - 1):
        curr = real_entries[i]
        nxt = real_entries[i + 1]

        gap_minutes = nxt["start"] - curr["end"]

        if is_im_bett(curr["activity"]) and is_aufstehen(nxt["activity"]):
            continue

        if gap_minutes > 1:
            gaps.append({
                "minutes": gap_minutes,
                "after": f'{curr["activity"]} (bis {curr["completed_str"]})',
                "before": f'{nxt["activity"]} (ab {nxt["started_str"]})',
            })
        elif gap_minutes < 0:
            overlap = abs(gap_minutes)
            if curr["skipped"] or nxt["skipped"]:
                continue
            if overlap > 0:
                overlaps.append({
                    "minutes": overlap,
                    "entry1": f'{curr["activity"]} ({curr["started_str"]}–{curr["completed_str"]})',
                    "entry2": f'{nxt["activity"]} ({nxt["started_str"]}–{nxt["completed_str"]})',
                })
                
    return gaps, overlaps


def _generate_projection_for_date(date_str, log_data):
    """Generate a projection for a past date using its log and weekday.

    This creates a fresh PlannerEngine with the correct DayContext,
    finds the earliest start time from the log, and runs the
    projection simulation.

    Returns a list of projection dicts (same format as projection JSON),
    or None on failure.
    """
    from day_context import DayContext
    from csv_parser import parse_csv
    from engine import PlannerEngine

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: Invalid date format: {date_str}")
        return None

    weekday = dt.weekday()

    # Auto-detect work type from weekday (same logic as DayContext)
    # Mon(0), Wed(2) = Bürotag; Tue(1), Thu(3), Fri(4) = Teleworking
    if weekday in (0, 2):
        work_type = "burotag"
    elif weekday in (1, 3, 4):
        work_type = "teleworking"
    else:
        work_type = "auto"

    ctx = DayContext(weekday=weekday, work_type_override=work_type)

    # Find earliest start time from log (skip after-midnight entries)
    earliest = None
    for entry in log_data:
        raw = entry.get("started_at", "")
        try:
            t = datetime.strptime(raw, "%H:%M:%S")
            if t.hour < 5:
                continue  # after-midnight tail
            candidate = dt.replace(hour=t.hour, minute=t.minute,
                                   second=0, microsecond=0)
            if earliest is None or candidate < earliest:
                earliest = candidate
        except ValueError:
            continue

    if earliest is None:
        print(f"ERROR: No valid start times found in log for {date_str}")
        return None

    print(f"[Report] Generating projection for {date_str} "
          f"(weekday={weekday}, start={earliest.strftime('%H:%M')})")

    raw_lists = parse_csv()
    engine = PlannerEngine(raw_lists, ctx, session_date=dt)
    projection = engine.get_day_projection(start_time=earliest)

    # Convert to serializable format (same as save_initial_projection)
    data = []
    for item in projection:
        est_start = item.get('est_start')
        est_end = item.get('est_end')
        data.append({
            'activity': item['activity'],
            'list_name': item['list_name'],
            'minutes': item['minutes'],
            'priority': item['priority'],
            'fixed_time': (item['fixed_time'].strftime('%H:%M')
                           if item.get('fixed_time') else None),
            'est_start': (est_start.strftime('%H:%M')
                          if isinstance(est_start, datetime) else None),
            'est_end': (est_end.strftime('%H:%M')
                        if isinstance(est_end, datetime) else None),
            'state': item['state'],
        })

    # Save it so it doesn't need regeneration next time
    proj_path = os.path.join(LOG_DIR, f"projection-{date_str}.json")
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(proj_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[Report] Projection saved: {proj_path} ({len(data)} items)")

    return data


def generate_report(date_str):
    proj_path = os.path.join(LOG_DIR, f"projection-{date_str}.json")
    log_path = os.path.join(LOG_DIR, f"planner-log-{date_str}.json")

    log_data = load_json(log_path)

    if not log_data:
        print(f"ERROR: No log found for {date_str}")
        print(f"  Expected: {log_path}")
        return None

    projection = load_json(proj_path)

    if not projection:
        print(f"No projection found for {date_str} — generating from log...")
        projection = _generate_projection_for_date(date_str, log_data)
        if not projection:
            print(f"ERROR: Could not generate projection for {date_str}")
            return None

    lines = []
    lines.append(f"{'='*65}")
    lines.append(f"  TAGESBERICHT — {date_str}")
    lines.append(f"{'='*65}")
    lines.append("")

    # --- Build lookup structures ---

    # Planned items (from projection)
    planned = []
    for item in projection:
        planned.append({
            'activity': item['activity'],
            'list': item.get('list_name', ''),
            'minutes': item['minutes'],
            'est_start': item.get('est_start', ''),
            'est_end': item.get('est_end', ''),
        })

    # Actual items (from log)
    # Classification (new 2026-04-29):
    #   - skipped     : entry.skipped == True
    #   - planned     : activity name matches a projection entry, OR original_activity
    #                   is set and that name matches a projection entry
    #   - unplanned   : everything else (incl. timeline_import entries that don't
    #                   match anything in projection)
    # PLUS: per-activity overflow detection. If the SUM of logged minutes for a
    # given (matched) activity name exceeds the SUM of planned minutes for that
    # name, the overflow part is reclassified as unplanned with a "(Verlängerung)"
    # marker. This catches cases where a planned activity was extended via
    # timeline_import / extra log entries.
    actual_skipped = []

    # Step 1: Build the set of activity names known to the projection.
    # We strip " (Fs.)" suffix because continuations share the base activity
    # in the planning sense.
    def _base_name(name):
        if name and name.endswith(" (Fs.)"):
            return name[:-6]
        return name

    planned_names = set()
    planned_minutes_by_name = defaultdict(int)
    for p in planned:
        bn = _base_name(p['activity'])
        planned_names.add(bn)
        planned_minutes_by_name[bn] += p['minutes']

    # Step 2: Compute logged minutes per (resolved) activity name. For each
    # log entry that has original_activity set we resolve to that name.
    def _resolved_name(entry):
        orig = entry.get('original_activity', '') or ''
        if orig:
            return _base_name(orig)
        return _base_name(entry.get('activity', ''))

    def _entry_duration(entry):
        start = parse_time(entry.get('started_at', ''))
        end = parse_time(entry.get('completed_at', ''))
        if start is not None and end is not None:
            return max(0, end - start)
        return 0

    logged_minutes_by_name = defaultdict(int)
    for entry in log_data:
        if entry.get('skipped'):
            continue
        name = _resolved_name(entry)
        if name in planned_names:
            logged_minutes_by_name[name] += _entry_duration(entry)

    # Step 3: Determine per-activity "planned budget remaining". We walk log
    # entries in chronological order. For each entry whose name matches a
    # planned name, the first minutes consume the planned budget; once a name's
    # budget is exhausted, further entries (or the trailing portion of an
    # entry that crosses the boundary) are reclassified as unplanned with a
    # "(Verlängerung)" marker. Entries whose name has no planned counterpart
    # are always fully unplanned.
    actual_done = []
    actual_unplanned = []

    log_chrono = sorted(
        [e for e in log_data if not e.get('skipped')],
        key=lambda e: parse_time(e.get('started_at', '')) or 0
    )

    planned_budget_remaining = dict(planned_minutes_by_name)

    def _make_item(entry):
        return {
            'activity': entry['activity'],
            'list': entry.get('list', ''),
            'minutes': entry.get('minutes', 0),
            'started_at': entry.get('started_at', ''),
            'completed_at': entry.get('completed_at', ''),
            'comment': entry.get('comment', ''),
            'original': entry.get('original_activity', ''),
        }

    for entry in log_chrono:
        name = _resolved_name(entry)
        dur = _entry_duration(entry)
        item = _make_item(entry)

        if name not in planned_names:
            actual_unplanned.append(item)
            continue

        budget = planned_budget_remaining.get(name, 0)
        if budget >= dur:
            # Entry fits entirely in planned budget.
            planned_budget_remaining[name] = budget - dur
            actual_done.append(item)
        elif budget > 0:
            # Entry partially fits. Split: first `budget` mins planned, rest
            # unplanned. We don't synthesize fake start/end times — the
            # planned half keeps the original times (so drift analysis still
            # finds it) and the extension entry gets a marker plus its share
            # of minutes via `minutes` field.
            planned_item = dict(item)
            actual_done.append(planned_item)

            ext_item = dict(item)
            ext_item['activity'] = item['activity'] + " (Verlängerung)"
            ext_item['_overflow_minutes'] = dur - budget
            actual_unplanned.append(ext_item)
            planned_budget_remaining[name] = 0
        else:
            # No budget left — entire entry is overflow.
            ext_item = dict(item)
            ext_item['activity'] = item['activity'] + " (Verlängerung)"
            ext_item['_overflow_minutes'] = dur
            actual_unplanned.append(ext_item)

    for entry in log_data:
        if entry.get('skipped'):
            actual_skipped.append(_make_item(entry))

    # --- Match planned items to actual ---

    # Build set of completed activity names (including originals for renames)
    done_names = set()
    for item in actual_done:
        done_names.add(item['activity'])
        if item['original']:
            done_names.add(item['original'])
        # Handle (Fs.) continuations — the base name was done
        act = item['activity']
        if act.endswith(" (Fs.)"):
            done_names.add(act[:-6])

    skipped_names = set()
    for item in actual_skipped:
        skipped_names.add(item['activity'])
        if item['original']:
            skipped_names.add(item['original'])

    # Classify planned items
    completed_planned = []
    skipped_planned = []
    missing_planned = []  # neither done nor skipped — just disappeared

    for p in planned:
        base = p['activity']
        if base.endswith(" (Fs.)"):
            base = base[:-6]
        if base in done_names or p['activity'] in done_names:
            completed_planned.append(p)
        elif base in skipped_names or p['activity'] in skipped_names:
            skipped_planned.append(p)
        else:
            missing_planned.append(p)

    # --- Compute totals ---

    total_planned_mins = sum(p['minutes'] for p in planned)
    completed_mins = sum(p['minutes'] for p in completed_planned)
    skipped_mins = sum(p['minutes'] for p in skipped_planned)
    missing_mins = sum(p['minutes'] for p in missing_planned)

    # Actual time spent. We compute these *before* item_duration is defined
    # (see below) by inlining the same logic; for the summary we just need
    # totals. actual_total_mins = clock-time of done entries minus overflow
    # siblings. unplanned_mins = clock-time of unplanned entries (for items
    # carrying _overflow_minutes use that value).
    def _entry_clock(item):
        start = parse_time(item['started_at'])
        end = parse_time(item['completed_at'])
        if start is not None and end is not None:
            return max(0, end - start)
        return 0

    overflow_total = sum(
        u['_overflow_minutes']
        for u in actual_unplanned if '_overflow_minutes' in u
    )
    # Plan-execution time: clock-time of done entries minus overflow siblings.
    # This is what was *actually used* on planned activities.
    plan_execution_mins = sum(_entry_clock(item) for item in actual_done) - overflow_total

    unplanned_mins = 0
    for u in actual_unplanned:
        if '_overflow_minutes' in u:
            unplanned_mins += u['_overflow_minutes']
        else:
            unplanned_mins += _entry_clock(u)

    # Total clock time = plan_execution + unplanned (no double-counting because
    # we already split entries into done + extension).
    actual_total_mins = plan_execution_mins + unplanned_mins

    # --- Coverage metrics ---

    if total_planned_mins > 0:
        completion_pct = completed_mins / total_planned_mins * 100
        skipped_pct = skipped_mins / total_planned_mins * 100
        missing_pct = missing_mins / total_planned_mins * 100
    else:
        completion_pct = skipped_pct = missing_pct = 0

    # --- Output Report ---

    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║  ZUSAMMENFASSUNG                                      ║")
    lines.append("╚═══════════════════════════════════════════════════════╝")
    lines.append("")
    lines.append(f"  Geplante Aktivitäten:     {len(planned):>4}")
    lines.append(f"  Geplante Gesamtzeit:      {fmt_minutes(total_planned_mins):>10}")
    lines.append("")
    lines.append(f"  ✓ Erledigt (geplant):     {len(completed_planned):>4}  "
                 f"({fmt_minutes(completed_mins):>10})  "
                 f"= {completion_pct:.1f}%")
    lines.append(f"  ⏭ Übersprungen:           {len(skipped_planned):>4}  "
                 f"({fmt_minutes(skipped_mins):>10})  "
                 f"= {skipped_pct:.1f}%")
    lines.append(f"  ✗ Nicht erreicht:         {len(missing_planned):>4}  "
                 f"({fmt_minutes(missing_mins):>10})  "
                 f"= {missing_pct:.1f}%")
    lines.append("")
    lines.append(f"  📝 Ungeplante Aktivitäten: {len(actual_unplanned):>3}  "
                 f"({fmt_minutes(unplanned_mins):>10})")
    lines.append(f"  ⏱  Plan-Ausführungszeit:    {fmt_minutes(plan_execution_mins):>10}")
    lines.append(f"  ⏱  Tatsächliche Arbeitszeit: {fmt_minutes(actual_total_mins):>10}")
    lines.append("")

    # --- Log Gaps & Overlaps ---

    gaps, overlaps = find_gaps_and_overlaps(log_data)

    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║  LOG-LÜCKEN UND ÜBERSCHNEIDUNGEN                      ║")
    lines.append("╚═══════════════════════════════════════════════════════╝")
    lines.append("")
    if not gaps and not overlaps:
        lines.append("  (keine Lücken oder Überschneidungen gefunden - hervorragend!)")
    else:
        if gaps:
            lines.append(f"  Lücken ({len(gaps)}):")
            for g in gaps:
                lines.append(f"    • {g['minutes']} min Lücke")
                lines.append(f"      nach: {g['after']}")
                lines.append(f"      vor:  {g['before']}")
            lines.append("")
        if overlaps:
            lines.append(f"  Überschneidungen ({len(overlaps)}):")
            for o in overlaps:
                lines.append(f"    • {o['minutes']} min Überschneidung")
                lines.append(f"      zwischen: {o['entry1']}")
                lines.append(f"      und:      {o['entry2']}")
            lines.append("")
    lines.append("")

    # --- Drift analysis ---

    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║  DRIFT-ANALYSE                                        ║")
    lines.append("╚═══════════════════════════════════════════════════════╝")
    lines.append("")

    # 1:1 matching: sort actual_done by start time, consume each match once.
    # Priority: original_activity match > current activity name match.
    # Planned items are processed in their original (chronological est_start) order.
    actual_done_sorted = sorted(
        actual_done,
        key=lambda a: parse_time(a['started_at']) if parse_time(a['started_at']) is not None else 9999
    )
    consumed = [False] * len(actual_done_sorted)

    drift_items = []
    for p in completed_planned:
        p_start = parse_time(p['est_start'])
        if p_start is None:
            continue

        base_p = p['activity']
        if base_p.endswith(" (Fs.)"):
            base_p = base_p[:-6]

        # Find first unconsumed actual entry that matches this planned item.
        # original_activity is treated as a strong match signal.
        matched_idx = None
        for i, a in enumerate(actual_done_sorted):
            if consumed[i]:
                continue
            orig = a.get('original', '') or ''
            a_name = a['activity']
            if (orig == p['activity'] or orig == base_p
                    or a_name == p['activity'] or a_name == base_p):
                matched_idx = i
                break

        if matched_idx is not None:
            a = actual_done_sorted[matched_idx]
            consumed[matched_idx] = True
            a_start = parse_time(a['started_at'])
            if a_start is not None:
                drift = a_start - p_start
                drift_items.append((p['activity'], drift, p_start, a_start))

    if drift_items:
        # Sort by absolute drift descending
        drift_items.sort(key=lambda x: abs(x[1]), reverse=True)

        lines.append(f"  {'Aktivität':<35} {'Geplant':>7} {'Tatsächl.':>9} {'Drift':>8}")
        lines.append(f"  {'─'*35} {'─'*7} {'─'*9} {'─'*8}")

        for name, drift, p_start, a_start in drift_items[:15]:
            p_str = f"{p_start // 60:02d}:{p_start % 60:02d}"
            a_str = f"{a_start // 60:02d}:{a_start % 60:02d}"
            d_str = f"+{fmt_minutes(drift)}" if drift >= 0 else f"{fmt_minutes(drift)}"
            display = name[:35]
            lines.append(f"  {display:<35} {p_str:>7} {a_str:>9} {d_str:>8}")

        if len(drift_items) > 15:
            lines.append(f"  ... und {len(drift_items) - 15} weitere")
    else:
        lines.append("  (keine Drift-Daten verfügbar)")

    lines.append("")

    # --- Time aggregation sections ---

    # Collect all logged entries (done + unplanned, not skipped)
    all_logged = actual_done + actual_unplanned

    # Helper: compute duration in minutes from a log item.
    # Synthesized "(Verlängerung)" entries carry _overflow_minutes; normal
    # entries are measured by clock-time delta. When a log entry was split
    # (the entry kept its full clock-time in actual_done plus a Verlängerung
    # sibling in actual_unplanned), we subtract the overflow from the
    # done-side entry to avoid double counting in per-activity aggregates.
    overflow_to_subtract = defaultdict(int)
    for u in actual_unplanned:
        if '_overflow_minutes' in u:
            # Match by activity-id approximation: same start time + base name.
            base = u['activity']
            if base.endswith(" (Verlängerung)"):
                base = base[:-len(" (Verlängerung)")]
            overflow_to_subtract[(base, u['started_at'])] += u['_overflow_minutes']

    def item_duration(item):
        if '_overflow_minutes' in item:
            return item['_overflow_minutes']
        start = parse_time(item['started_at'])
        end = parse_time(item['completed_at'])
        if start is not None and end is not None:
            dur = max(0, end - start)
            sub = overflow_to_subtract.get((item['activity'], item['started_at']), 0)
            return max(0, dur - sub)
        return 0

    # --- ZEITVERBRAUCH NACH AKTIVITÄT ---
    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║  ZEITVERBRAUCH NACH AKTIVITÄT                         ║")
    lines.append("╚═══════════════════════════════════════════════════════╝")
    lines.append("")

    by_activity = defaultdict(int)
    for item in all_logged:
        if is_wenn_dialog(item['activity']) or is_im_bett(item['activity']):
            continue
        by_activity[item['activity']] += item_duration(item)

    sorted_by_activity = sorted(by_activity.items(), key=lambda x: x[1], reverse=True)

    if sorted_by_activity:
        lines.append(f"  {'Aktivität':<40} {'Zeit':>8}")
        lines.append(f"  {'─'*40} {'─'*8}")
        for name, mins in sorted_by_activity[:20]:
            display = name[:40]
            lines.append(f"  {display:<40} {fmt_minutes(mins):>8}")
        if len(sorted_by_activity) > 20:
            lines.append(f"  ... und {len(sorted_by_activity) - 20} weitere Aktivitäten")
    else:
        lines.append("  (keine Daten)")

    lines.append("")

    # --- ZEITVERBRAUCH NACH TASK-KÜRZEL ---
    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║  ZEITVERBRAUCH NACH TASK-KÜRZEL                       ║")
    lines.append("╚═══════════════════════════════════════════════════════╝")
    lines.append("")

    by_code = defaultdict(int)
    for item in all_logged:
        if is_wenn_dialog(item['activity']) or is_im_bett(item['activity']):
            continue
        code = extract_task_code(item['activity']) or "(kein Kürzel)"
        by_code[code] += item_duration(item)

    sorted_by_code = sorted(by_code.items(), key=lambda x: x[1], reverse=True)

    if sorted_by_code:
        lines.append(f"  {'Kürzel':<12} {'Zeit':>8}")
        lines.append(f"  {'─'*12} {'─'*8}")
        for code, mins in sorted_by_code[:20]:
            lines.append(f"  {code:<12} {fmt_minutes(mins):>8}")
        if len(sorted_by_code) > 20:
            lines.append(f"  ... und {len(sorted_by_code) - 20} weitere Kürzel")
    else:
        lines.append("  (keine Daten)")

    lines.append("")

    # --- ZEITVERBRAUCH NACH KONTENBEREICH ---
    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║  ZEITVERBRAUCH NACH KONTENBEREICH                     ║")
    lines.append("╚═══════════════════════════════════════════════════════╝")
    lines.append("")

    by_area = defaultdict(int)
    for item in all_logged:
        if is_wenn_dialog(item['activity']) or is_im_bett(item['activity']):
            continue
        code = extract_task_code(item['activity'])
        if code and len(code) >= 2:
            area = code[:2]
        else:
            area = "(–)"
        by_area[area] += item_duration(item)

    sorted_by_area = sorted(by_area.items(), key=lambda x: x[1], reverse=True)

    if sorted_by_area:
        lines.append(f"  {'Bereich':<8} {'Zeit':>8}")
        lines.append(f"  {'─'*8} {'─'*8}")
        for area, mins in sorted_by_area:
            lines.append(f"  {area:<8} {fmt_minutes(mins):>8}")
    else:
        lines.append("  (keine Daten)")

    lines.append("")

    # --- AKTIVITÄTEN OHNE TASK-KÜRZEL ---
    no_code_activities = []
    for item in all_logged:
        if is_wenn_dialog(item['activity']):
            continue
        if is_im_bett(item['activity']):
            continue
        code = extract_task_code(item['activity'])
        if not code:
            no_code_activities.append(item)

    no_code_activities.sort(key=lambda x: parse_time(x['started_at']) or 0)

    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║  AKTIVITÄTEN OHNE TASK-KÜRZEL                         ║")
    lines.append("╚═══════════════════════════════════════════════════════╝")
    lines.append("")
    if not no_code_activities:
        lines.append("  (alle Aktivitäten haben ein gültiges Task-Kürzel!)")
    else:
        lines.append(f"  Gefunden: {len(no_code_activities)} Einträge ohne Kürzel")
        lines.append("")
        for item in no_code_activities:
            start_str = item['started_at'][:5] if item['started_at'] else "??:??"
            end_str = item['completed_at'][:5] if item['completed_at'] else "??:??"
            dur = item_duration(item)
            lines.append(f"  • [{start_str}–{end_str}] {item['activity']} ({dur}m)")
    lines.append("")

    # --- Skipped items with reasons ---

    if actual_skipped:
        lines.append("╔═══════════════════════════════════════════════════════╗")
        lines.append("║  ÜBERSPRUNGENE AKTIVITÄTEN                            ║")
        lines.append("╚═══════════════════════════════════════════════════════╝")
        lines.append("")
        for item in actual_skipped:
            reason = item['comment'] if item['comment'] else "(kein Grund)"
            lines.append(f"  ⏭ {item['activity'][:45]}")
            lines.append(f"    Grund: {reason}")
        lines.append("")

    # --- Unplanned items ---

    if actual_unplanned:
        lines.append("╔═══════════════════════════════════════════════════════╗")
        lines.append("║  UNGEPLANTE AKTIVITÄTEN                               ║")
        lines.append("╚═══════════════════════════════════════════════════════╝")
        lines.append("")
        # New 2026-04-29: aggregate by activity name (timeline_import
        # produces many 1-min fragments of the same activity). Sort by
        # total minutes descending.
        unp_agg = defaultdict(lambda: {'minutes': 0, 'count': 0,
                                        'first_start': None, 'last_end': None})
        for item in actual_unplanned:
            key = item['activity']
            mins = item_duration(item)
            agg = unp_agg[key]
            agg['minutes'] += mins
            agg['count'] += 1
            s = item['started_at'][:5] if item['started_at'] else None
            e = item['completed_at'][:5] if item['completed_at'] else None
            if s and (agg['first_start'] is None or s < agg['first_start']):
                agg['first_start'] = s
            if e and (agg['last_end'] is None or e > agg['last_end']):
                agg['last_end'] = e

        sorted_unp = sorted(unp_agg.items(), key=lambda x: -x[1]['minutes'])
        total_unp = sum(d['minutes'] for _, d in sorted_unp)
        total_sessions = sum(d['count'] for _, d in sorted_unp)

        lines.append(f"  {'Aktivität':<45} {'Zeit':>8} {'Sess.':>6} {'Range':<13}")
        lines.append(f"  {'─'*45} {'─'*8} {'─'*6} {'─'*13}")
        for name, d in sorted_unp:
            display = name[:45]
            zeit = fmt_minutes(d['minutes'])
            cnt = d['count']
            rng = f"{d['first_start'] or '?'}–{d['last_end'] or '?'}"
            lines.append(f"  {display:<45} {zeit:>8} {cnt:>6} {rng:<13}")
        lines.append("")
        lines.append(f"  Gesamt ungeplant: {fmt_minutes(total_unp)} über "
                     f"{total_sessions} Einträge / "
                     f"{len(sorted_unp)} verschiedene Aktivitäten")
        lines.append("")

    # --- Not reached items ---

    if missing_planned:
        lines.append("╔═══════════════════════════════════════════════════════╗")
        lines.append("║  NICHT ERREICHTE AKTIVITÄTEN                          ║")
        lines.append("╚═══════════════════════════════════════════════════════╝")
        lines.append("")
        for p in missing_planned:
            lines.append(f"  ✗ {p['est_start'] or '?':>5}  "
                         f"{p['activity'][:40]}  ({p['minutes']}m)")
        lines.append("")

    lines.append(f"{'='*65}")

    report = "\n".join(lines)
    return report


def main():
    # Ensure stdout can handle Unicode (box-drawing chars, etc.)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    report = generate_report(date_str)
    if report is None:
        sys.exit(1)

    print(report)

    # Save report to file
    os.makedirs(LOG_DIR, exist_ok=True)
    report_path = os.path.join(LOG_DIR, f"report-{date_str}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport gespeichert: {report_path}")


if __name__ == "__main__":
    main()
