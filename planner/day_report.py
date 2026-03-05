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
import sys
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
    actual_done = []
    actual_skipped = []
    actual_unplanned = []

    for entry in log_data:
        item = {
            'activity': entry['activity'],
            'list': entry.get('list', ''),
            'minutes': entry.get('minutes', 0),
            'started_at': entry.get('started_at', ''),
            'completed_at': entry.get('completed_at', ''),
            'comment': entry.get('comment', ''),
            'original': entry.get('original_activity', ''),
        }
        if entry.get('skipped'):
            actual_skipped.append(item)
        elif item['list'] == 'ungeplant':
            actual_unplanned.append(item)
        else:
            actual_done.append(item)

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

    # Actual time spent (from log, done items only)
    actual_total_mins = 0
    for item in actual_done:
        start = parse_time(item['started_at'])
        end = parse_time(item['completed_at'])
        if start is not None and end is not None:
            actual_total_mins += max(0, end - start)

    unplanned_mins = 0
    for item in actual_unplanned:
        start = parse_time(item['started_at'])
        end = parse_time(item['completed_at'])
        if start is not None and end is not None:
            unplanned_mins += max(0, end - start)

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
    lines.append(f"  ⏱  Tatsächliche Arbeitszeit: {fmt_minutes(actual_total_mins):>10}")
    lines.append("")

    # --- Drift analysis ---

    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║  DRIFT-ANALYSE                                        ║")
    lines.append("╚═══════════════════════════════════════════════════════╝")
    lines.append("")

    # Compare planned start vs actual start for completed items
    drift_items = []
    for p in completed_planned:
        p_start = parse_time(p['est_start'])
        if p_start is None:
            continue
        # Find matching actual entry
        for a in actual_done:
            a_name = a['activity']
            if a['original']:
                a_name = a['original']
            base_p = p['activity']
            if base_p.endswith(" (Fs.)"):
                base_p = base_p[:-6]
            if a_name == p['activity'] or a_name == base_p:
                a_start = parse_time(a['started_at'])
                if a_start is not None:
                    drift = a_start - p_start
                    drift_items.append((p['activity'], drift, p_start, a_start))
                break

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
        for item in actual_unplanned:
            start = item['started_at'][:5] if item['started_at'] else '?'
            end = item['completed_at'][:5] if item['completed_at'] else '?'
            comment = f"  — {item['comment']}" if item['comment'] else ""
            lines.append(f"  📝 {start}–{end}  {item['activity'][:40]}{comment}")
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
