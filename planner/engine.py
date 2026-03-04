"""
engine.py — Reactive planning engine.

Core loop:
  - Multiple named lists, each with sequential items.
  - Only "active" lists contribute candidates.
  - Items are filtered by weekday + dependency conditions.
  - Wait items block a list temporarily.
  - Start/Stop/Restart items trigger list state changes.
  - Fixed-time items are deferred until their time arrives.
  - The highest-priority ready item across all active lists is offered to user.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple

from models import CsvRow, CompletedItem, ListState, RowType
from day_context import DayContext


# The log file path
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


class PlannerEngine:

    def __init__(self, raw_lists: Dict[str, List[CsvRow]], ctx: DayContext):
        self.ctx = ctx
        self.log: List[CompletedItem] = []
        self._unsaved = False
        self.now = datetime.now() # Store current time at initialization

        # Build ListState objects from raw data
        self.lists: Dict[str, ListState] = {}
        for name, rows in raw_lists.items():
            ls = ListState(name=name, rows=rows, active=False)
            self.lists[name] = ls

        # Liste_Morgentoilette starts active automatically
        if "Liste_Morgentoilette" in self.lists:
            self.lists["Liste_Morgentoilette"].active = True

        # Auto-activate lists whose first applicable row has a fixed time.
        # These lists are always active but deferred until their time arrives.
        for ls in self.lists.values():
            if ls.active:
                continue  # already active
            for row in ls.rows:
                if not self._row_applies(row):
                    continue  # skip rows that don't apply today
                if row.row_type != RowType.ACTIVITY:
                    break  # control-flow first — don't auto-start
                if row.starting_time:
                    ls.active = True
                    print(f"[ENGINE] Auto-activated '{ls.name}' "
                          f"(fixed time {row.starting_time.strftime('%H:%M')})")
                break  # only check the first applicable row

        # Resolve initial current_activity for all active lists
        for ls in self.lists.values():
            if ls.active:
                self._resolve(ls)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def tick(self):
        """Call periodically (e.g. every 30s) to unblock waiting lists."""
        self.now = datetime.now() # Update current time for checks
        for ls in self.lists.values():
            if ls.active and ls.wait_until and self.now >= ls.wait_until:
                ls.wait_until = None
                self._resolve(ls)

    def get_best_candidate(self) -> Optional[Tuple[ListState, CsvRow]]:
        """Return (ListState, CsvRow) for the highest-priority ready item."""
        candidates = self._collect_candidates()
        if not candidates:
            return None
        # Sort by priority descending; tie-break: fixed-time wins
        candidates.sort(key=lambda x: (-x[1].priority,
                                        0 if x[1].starting_time else 1))
        return candidates[0]

    def get_all_candidates(self) -> List[Tuple[ListState, CsvRow]]:
        """All current candidates sorted by priority (for the queue display)."""
        cands = self._collect_candidates()
        cands.sort(key=lambda x: (-x[1].priority,
                                   0 if x[1].starting_time else 1))
        return cands

    def mark_done(self, ls: ListState, row: CsvRow,
                  custom_time: Optional[datetime] = None,
                  custom_text: Optional[str] = None,
                  start_time: Optional[datetime] = None,
                  comment: str = ""):
        """Mark current item as done, advance list."""
        self._record(row, ls.name, skipped=False,
                     custom_time=custom_time, custom_text=custom_text,
                     start_time=start_time, comment=comment)
        ls.current_index += 1
        ls.current_activity = None
        # Reset interruption state
        ls.pending_start = None
        ls.continuation_count = 0
        self._resolve(ls, reference_time=custom_time)

    def mark_skip(self, ls: ListState, row: CsvRow, comment: str = ""):
        """Skip current item, advance list."""
        self._record(row, ls.name, skipped=True, comment=comment)
        ls.current_index += 1
        ls.current_activity = None
        # Reset interruption state
        ls.pending_start = None
        ls.continuation_count = 0
        self._resolve(ls)

    def interrupt_current(self, ls: ListState, row: CsvRow,
                          interrupt_activity: str,
                          interrupt_start: datetime,
                          interrupt_end: datetime,
                          comment: str = ""):
        """
        Interrupt the current task.

        Logs two entries:
          1) The pre-interruption segment of the current task
             (from pending_start/last_completed_at to interrupt_start)
          2) The interrupting activity (interrupt_start to interrupt_end)

        Then marks the current task as a continuation "(Fs.)" with
        pending_start = interrupt_end.
        """
        # Determine the start time of the pre-interruption segment
        if ls.pending_start:
            pre_start = ls.pending_start
        else:
            last = self.last_completed_at()
            pre_start = last if last else interrupt_start

        # Build the activity name for the pre-interruption segment
        base_name = row.activity
        if ls.continuation_count > 0:
            base_name = f"{row.activity} (Fs.)"

        # 1) Log pre-interruption segment (only if it has positive duration)
        if interrupt_start > pre_start:
            self._record_raw(
                activity=base_name,
                list_name=ls.name,
                priority=row.priority,
                minutes=int((interrupt_start - pre_start).total_seconds() / 60),
                started_at=pre_start,
                completed_at=interrupt_start,
                skipped=False,
                original_activity=row.activity if ls.continuation_count > 0 else "",
            )

        # 2) Log the interrupting activity
        self.log_adhoc(interrupt_activity, interrupt_start, interrupt_end,
                       comment=comment)

        # 3) Set up continuation state
        ls.continuation_count += 1
        ls.pending_start = interrupt_end

    def get_active_lists(self) -> List[ListState]:
        return [ls for ls in self.lists.values() if ls.active]

    def get_wait_status(self) -> List[Tuple[str, datetime]]:
        """Return [(list_name, wait_until)] for lists currently waiting."""
        result = []
        for ls in self.lists.values():
            if ls.active and ls.wait_until and ls.wait_until > self.now:
                result.append((ls.name, ls.wait_until))
        return result

    def get_day_projection(self) -> List[Dict]:
        """
        Simulate the engine forward with preemptive scheduling.

        Higher-priority items that become ready (via fixed start time or
        wait expiry) during a lower-priority item's execution will
        preempt it.  The interrupted item is split: the first segment
        is emitted, and the remaining duration becomes a "(Fs.)"
        continuation that competes normally with other candidates.

        Returns a chronologically ordered list of dicts:
          - 'activity', 'list_name', 'minutes', 'priority'
          - 'fixed_time': Optional[time]
          - 'est_start': datetime, 'est_end': datetime
          - 'state': 'current' | 'upcoming' | 'scheduled'
          - 'is_control': False
        """
        now = datetime.now()
        projection: List[Dict] = []

        class _SimList:
            __slots__ = ('name', 'rows', 'active', 'idx', 'wait_until',
                         'is_current_real')
            def __init__(self, name, rows, active, idx, wait_until):
                self.name = name
                self.rows = rows
                self.active = active
                self.idx = idx
                self.wait_until = wait_until
                self.is_current_real = False

        sim: Dict[str, _SimList] = {}
        for ls in self.lists.values():
            sl = _SimList(
                name=ls.name, rows=ls.rows, active=ls.active,
                idx=ls.current_index,
                wait_until=ls.wait_until if (ls.wait_until and ls.wait_until > now) else None,
            )
            sl.is_current_real = (ls.active and ls.current_activity is not None)
            sim[ls.name] = sl

        last_done = self.last_completed_at()
        cursor = last_done if last_done else now
        first_item = True
        max_items = 500
        items_emitted = 0
        day_ended = False

        # Preempted items: [[orig_activity, list_name, priority, remaining_mins], ...]
        continuations: List[list] = []

        def resolve_front(sl):
            """Consume control-flow rows, return front ACTIVITY or None."""
            while sl.idx < len(sl.rows):
                row = sl.rows[sl.idx]
                if not self._row_applies(row):
                    sl.idx += 1
                    continue
                rt = row.row_type
                if rt == RowType.WAIT:
                    sl.wait_until = cursor + timedelta(minutes=row.minutes)
                    sl.idx += 1
                    return None
                if rt == RowType.WAIT_UNTIL_TOP_OF_HOUR:
                    sl.wait_until = (cursor.replace(
                        minute=0, second=0, microsecond=0)
                        + timedelta(hours=1))
                    sl.idx += 1
                    return None
                if rt == RowType.START_LIST:
                    tgt = row.target_list
                    if tgt in sim and not sim[tgt].active:
                        sim[tgt].active = True
                        sim[tgt].idx = 0
                        sim[tgt].wait_until = None
                    sl.idx += 1
                    continue
                if rt == RowType.STOP_LIST:
                    if row.target_list in sim:
                        sim[row.target_list].active = False
                    sl.idx += 1
                    continue
                if rt == RowType.RESTART_LIST:
                    tgt = row.target_list
                    if tgt in sim:
                        sim[tgt].active = True
                        sim[tgt].wait_until = None
                    sl.idx += 1
                    continue
                if rt == RowType.ACTIVITY:
                    if row.starting_time:
                        target_dt = cursor.replace(
                            hour=row.starting_time.hour,
                            minute=row.starting_time.minute,
                            second=0, microsecond=0)
                        if cursor < target_dt:
                            sl.wait_until = target_dt
                            return None
                    return row
                sl.idx += 1
            return None

        def peek_priority(sl):
            """Non-destructive peek at next activity's priority."""
            idx = sl.idx
            while idx < len(sl.rows):
                row = sl.rows[idx]
                if not self._row_applies(row):
                    idx += 1
                    continue
                if row.row_type == RowType.ACTIVITY:
                    return row.priority
                if row.row_type in (RowType.WAIT, RowType.WAIT_UNTIL_TOP_OF_HOUR):
                    return None  # blocked before next activity
                idx += 1  # skip control-flow
            return None

        while items_emitted < max_items:
            # --- Collect candidates from active, non-waiting lists ---
            list_cands = []
            for sl in sim.values():
                if not sl.active:
                    continue
                if sl.wait_until and cursor < sl.wait_until:
                    continue
                if sl.wait_until:
                    sl.wait_until = None  # expired
                row = resolve_front(sl)
                if row:
                    list_cands.append((sl, row))

            # Merge list candidates + continuations
            all_cands = []
            for sl, row in list_cands:
                all_cands.append({
                    'src': 'list', 'sl': sl, 'row': row,
                    'priority': row.priority, 'minutes': row.minutes,
                    'activity': row.activity, 'list_name': sl.name,
                    'fixed_time': row.starting_time,
                })
            for cont in continuations:
                all_cands.append({
                    'src': 'cont', 'cont': cont,
                    'priority': cont[2], 'minutes': cont[3],
                    'activity': cont[0] + " (Fs.)",
                    'list_name': cont[1], 'fixed_time': None,
                })

            # Sort: highest priority first; then fixed-time wins;
            # then continuations before fresh items (started work and
            # possible sequential dependencies take precedence).
            all_cands.sort(key=lambda x: (
                -x['priority'],
                0 if x.get('fixed_time') else 1,
                0 if x['src'] == 'cont' else 1,
            ))

            if not all_cands:
                # Jump to next wake event
                next_wake = None
                for sl in sim.values():
                    if sl.active and sl.wait_until and sl.wait_until > cursor:
                        if next_wake is None or sl.wait_until < next_wake:
                            next_wake = sl.wait_until
                if next_wake:
                    cursor = next_wake
                    continue
                break  # nothing left

            best = all_cands[0]
            est_start = cursor
            if best.get('fixed_time'):
                ft = best['fixed_time']
                target_dt = cursor.replace(
                    hour=ft.hour, minute=ft.minute,
                    second=0, microsecond=0)
                est_start = max(cursor, target_dt)
            est_end = est_start + timedelta(minutes=best['minutes'])

            # --- Preemption check ---
            # Find the earliest moment a higher-priority item wakes up
            # during [est_start, est_end).
            preempt_at = None
            for sl2 in sim.values():
                if not sl2.active:
                    continue
                wt = sl2.wait_until
                if wt and est_start < wt < est_end:
                    p = peek_priority(sl2)
                    if p is not None and p > best['priority']:
                        if preempt_at is None or wt < preempt_at:
                            preempt_at = wt
            # Also check continuations that are higher priority — but
            # those are already in all_cands and would have been picked
            # if they were higher, so no check needed.

            if preempt_at and preempt_at > est_start:
                # ---- Preemption: split the item ----
                first_mins = int(
                    (preempt_at - est_start).total_seconds() / 60)
                remaining = best['minutes'] - first_mins

                is_current = (first_item and best['src'] == 'list'
                              and best['sl'].is_current_real)
                state = "current" if is_current else "upcoming"
                end_t = max(preempt_at, now) if is_current else preempt_at

                if first_mins > 0:
                    projection.append({
                        'activity': best['activity'],
                        'list_name': best['list_name'],
                        'minutes': first_mins,
                        'priority': best['priority'],
                        'fixed_time': best.get('fixed_time'),
                        'est_start': est_start,
                        'est_end': end_t,
                        'state': state,
                        'is_control': False,
                    })
                    items_emitted += 1

                # Create / update continuation for remaining duration
                if remaining > 0:
                    if best['src'] == 'cont':
                        best['cont'][3] = remaining  # update in-place
                    else:
                        base = best['activity']
                        if base.endswith(" (Fs.)"):
                            base = base[:-6]
                        continuations.append(
                            [base, best['list_name'],
                             best['priority'], remaining])
                        best['sl'].idx += 1  # advance list past item

                cursor = preempt_at
                first_item = False

            else:
                # ---- No preemption: emit full item ----
                is_current = (first_item and best['src'] == 'list'
                              and best['sl'].is_current_real)
                if is_current:
                    state = "current"
                    est_end = max(est_end, now)
                elif best.get('fixed_time') and est_start > now:
                    state = "scheduled"
                else:
                    state = "upcoming"

                projection.append({
                    'activity': best['activity'],
                    'list_name': best['list_name'],
                    'minutes': best['minutes'],
                    'priority': best['priority'],
                    'fixed_time': best.get('fixed_time'),
                    'est_start': est_start,
                    'est_end': est_end,
                    'state': state,
                    'is_control': False,
                })

                if best['src'] == 'list':
                    best['sl'].idx += 1
                else:
                    continuations.remove(best['cont'])

                cursor = est_end
                items_emitted += 1
                first_item = False

                # "Im Bett" marks end of day — stop the simulation
                if "im bett" in best['activity'].lower():
                    day_ended = True
                    break

        return projection

    def items_done_today(self) -> int:
        return sum(1 for c in self.log if not c.skipped)

    def items_skipped_today(self) -> int:
        return sum(1 for c in self.log if c.skipped)

    def save_log(self) -> str:
        """Save completion log as JSON for later Ablauf generation."""
        os.makedirs(LOG_DIR, exist_ok=True)
        path = self._get_log_path()
        data = [
            {
                "activity": c.activity,
                "list": c.list_name,
                "priority": c.priority,
                "minutes": c.minutes,
                "started_at": c.started_at.strftime("%H:%M:%S"),
                "completed_at": c.completed_at.strftime("%H:%M:%S"),
                "skipped": c.skipped,
                "original_activity": c.original_activity,
                "comment": c.comment,
            }
            for c in self.log
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._unsaved = False
        return path

    def load_log(self, path: str) -> Tuple[int, int]:
        """
        Loads completion/skip records from a JSON log file and reconciles
        the planner state by advancing indices.

        Strategy: walk each list's CSV rows in order.  For each row:
          - Non-activity rows (WAIT, START, STOP, RESTART) are processed
            inline, with WAIT timers calculated relative to the last
            completed task's time (not datetime.now()).
          - Activity rows are matched against the log.  If matched,
            record and advance.  If not, stop — this is the next item.

        This correctly handles out-of-order completion times and expired
        wait timers from hours ago.

        Returns (done_count, skip_count).
        """
        if not os.path.exists(path):
            return 0, 0

        with open(path, "r", encoding="utf-8") as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                print(f"ERROR: Could not parse log file: {path}")
                return 0, 0

        done_count = 0
        skip_count = 0
        now = datetime.now()

        log_by_list: Dict[str, List[Dict]] = {}
        for entry in log_data:
            list_name = entry.get("list")
            if list_name:
                log_by_list.setdefault(list_name, []).append(entry)

        # Restore entries from non-engine lists (unplanned, interruptions)
        # so they participate in last_completed_at() and the timeline.
        for list_name, entries in log_by_list.items():
            if list_name in self.lists:
                continue  # handled by the list-matching loop below
            for entry in entries:
                try:
                    started_dt = datetime.strptime(
                        entry.get("started_at", ""), "%H:%M:%S"
                    ).replace(year=now.year, month=now.month, day=now.day)
                except ValueError:
                    started_dt = now
                try:
                    completed_dt = datetime.strptime(
                        entry["completed_at"], "%H:%M:%S"
                    ).replace(year=now.year, month=now.month, day=now.day)
                except ValueError:
                    completed_dt = now
                self.log.append(CompletedItem(
                    activity=entry.get("activity", ""),
                    list_name=list_name,
                    priority=entry.get("priority", 0.0),
                    minutes=entry.get("minutes", 0),
                    started_at=started_dt,
                    completed_at=completed_dt,
                    skipped=entry.get("skipped", False),
                    original_activity=entry.get("original_activity", ""),
                    comment=entry.get("comment", ""),
                ))
                if not entry.get("skipped", False):
                    done_count += 1
                else:
                    skip_count += 1

        for ls in self.lists.values():
            if ls.name not in log_by_list:
                continue

            remaining = list(log_by_list[ls.name])  # mutable copy
            last_completed_at: Optional[datetime] = None

            while ls.current_index < len(ls.rows):
                row = ls.rows[ls.current_index]

                # Skip rows that don't apply today (weekday/dependency)
                if not self._row_applies(row):
                    ls.current_index += 1
                    continue

                # --- Handle control-flow rows inline ---

                if row.row_type == RowType.WAIT:
                    base = last_completed_at if last_completed_at else now
                    expiry = base + timedelta(minutes=row.minutes)
                    if expiry <= now:
                        print(f"[LOAD] WAIT {row.minutes}min in '{ls.name}' "
                              f"already expired (ref: {base.strftime('%H:%M')})")
                        ls.current_index += 1
                        continue  # expired — keep going
                    else:
                        ls.wait_until = expiry
                        print(f"[LOAD] WAIT in '{ls.name}' until "
                              f"{expiry.strftime('%H:%M')} "
                              f"(ref: {base.strftime('%H:%M')})")
                        ls.current_index += 1
                        ls.current_activity = None
                        break  # list blocked — stop processing

                if row.row_type == RowType.WAIT_UNTIL_TOP_OF_HOUR:
                    if last_completed_at:
                        target = (last_completed_at.replace(
                            minute=0, second=0, microsecond=0)
                            + timedelta(hours=1))
                    else:
                        target = self._next_top_of_hour()
                    if target <= now:
                        print(f"[LOAD] WAIT_TOP_OF_HOUR in '{ls.name}' "
                              f"already expired")
                        ls.current_index += 1
                        continue
                    else:
                        ls.wait_until = target
                        ls.current_index += 1
                        ls.current_activity = None
                        break

                if row.row_type == RowType.START_LIST:
                    print(f"[LOAD] Starting list: {row.target_list}")
                    self._start_list(row.target_list,
                                     reference_time=last_completed_at)
                    ls.current_index += 1
                    continue

                if row.row_type == RowType.STOP_LIST:
                    print(f"[LOAD] Stopping list: {row.target_list}")
                    self._stop_list(row.target_list)
                    ls.current_index += 1
                    continue

                if row.row_type == RowType.RESTART_LIST:
                    print(f"[LOAD] Restarting list: {row.target_list}")
                    self._restart_list(row.target_list,
                                       reference_time=last_completed_at)
                    ls.current_index += 1
                    continue

                # --- It's an ACTIVITY row — match against log ---

                match_idx = None
                for i, log_entry in enumerate(remaining):
                    log_act = log_entry["activity"]
                    log_orig = log_entry.get("original_activity", "")
                    if log_act == row.activity or \
                       (log_orig and log_orig == row.activity):
                        match_idx = i
                        break

                if match_idx is None:
                    break  # no match → this is the next item to do

                # Consume the matched entry
                log_entry = remaining.pop(match_idx)

                # Parse completion time
                try:
                    completed_dt = datetime.strptime(
                        log_entry["completed_at"], "%H:%M:%S"
                    ).replace(year=now.year, month=now.month, day=now.day)
                except ValueError:
                    completed_dt = now

                last_completed_at = completed_dt

                # Parse start time (falls back to completed_dt if missing)
                try:
                    started_dt = datetime.strptime(
                        log_entry.get("started_at", ""), "%H:%M:%S"
                    ).replace(year=now.year, month=now.month, day=now.day)
                except ValueError:
                    started_dt = completed_dt

                if log_entry["skipped"]:
                    # Record directly — don't call mark_skip (avoids _resolve)
                    self._record(row, ls.name, skipped=True,
                                 start_time=started_dt,
                                 comment=log_entry.get("comment", ""),
                                 _from_replay=True)
                    ls.current_index += 1
                    ls.current_activity = None
                    skip_count += 1
                else:
                    custom_text = log_entry.get("activity")
                    if custom_text == row.activity:
                        custom_text = None
                    # Record directly — don't call mark_done (avoids _resolve)
                    self._record(row, ls.name, skipped=False,
                                 custom_time=completed_dt,
                                 custom_text=custom_text,
                                 start_time=started_dt,
                                 comment=log_entry.get("comment", ""),
                                 _from_replay=True)
                    ls.current_index += 1
                    ls.current_activity = None
                    done_count += 1

        # Sort log chronologically — entries were added per-list, not in
        # time order. last_completed_at() relies on the last entry being
        # the most recent.
        self.log.sort(key=lambda c: c.completed_at)

        # Final resolve — only for active lists not currently blocked
        for ls in self.lists.values():
            if ls.active and not ls.wait_until:
                self._resolve(ls)

        return done_count, skip_count

    def _get_log_path(self) -> str:
        os.makedirs(LOG_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(LOG_DIR, f"planner-log-{today}.json")

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _collect_candidates(self) -> List[Tuple[ListState, CsvRow]]:
        """Collect one ready item from each active, unblocked list."""
        result = []
        now = datetime.now()
        for ls in self.lists.values():
            if not ls.active:
                continue
            if ls.wait_until and ls.wait_until > now:
                continue  # list is still in Wait
            if ls.current_activity is None:
                continue  # list exhausted or deferred
            row = ls.current_activity
            # Check fixed start time
            if row.starting_time:
                target = datetime.now().replace(
                    hour=row.starting_time.hour,
                    minute=row.starting_time.minute,
                    second=0, microsecond=0
                )
                if now < target:
                    continue  # not yet time
            result.append((ls, row))
        return result

    def _resolve(self, ls: ListState,
                 reference_time: Optional[datetime] = None):
        """
        Scan forward from ls.current_index, consuming control-flow rows
        until we reach a real activity or block/exhaust the list.
        Sets ls.current_activity appropriately.

        reference_time: if set, WAIT timers are calculated relative to
        this time (e.g. a backdated completion time).  If the resulting
        expiry is already past, the WAIT is skipped entirely.
        """
        now = datetime.now()
        while ls.current_index < len(ls.rows):
            row = ls.rows[ls.current_index]

            # Check if this row applies to today
            if not self._row_applies(row):
                print(f"[ENGINE] Skipping row {ls.current_index + 1} in '{ls.name}': Does not apply today.")
                ls.current_index += 1
                continue

            rtype = row.row_type

            if rtype == RowType.WAIT:
                base = reference_time if reference_time else now
                expiry = base + timedelta(minutes=row.minutes)
                if expiry <= now:
                    print(f"[ENGINE] WAIT {row.minutes}min in '{ls.name}' "
                          f"already expired (ref: {base.strftime('%H:%M')})")
                    ls.current_index += 1
                    continue  # expired — skip it
                ls.wait_until = expiry
                print(f"[ENGINE] List '{ls.name}' set to WAIT until "
                      f"{expiry.strftime('%H:%M')} "
                      f"(ref: {base.strftime('%H:%M')}).")
                ls.current_index += 1
                ls.current_activity = None
                return  # list is blocked

            if rtype == RowType.WAIT_UNTIL_TOP_OF_HOUR:
                if reference_time:
                    target = (reference_time.replace(
                        minute=0, second=0, microsecond=0)
                        + timedelta(hours=1))
                else:
                    target = self._next_top_of_hour()
                if target <= now:
                    print(f"[ENGINE] WAIT_TOP_OF_HOUR in '{ls.name}' "
                          f"already expired")
                    ls.current_index += 1
                    continue
                ls.wait_until = target
                print(f"[ENGINE] List '{ls.name}' set to WAIT until "
                      f"{target.strftime('%H:%M')}.")
                ls.current_index += 1
                ls.current_activity = None
                return  # list is blocked

            if rtype == RowType.START_LIST:
                print(f"[ENGINE] Starting list: {row.target_list}")
                self._start_list(row.target_list,
                                 reference_time=reference_time)
                ls.current_index += 1
                continue

            if rtype == RowType.STOP_LIST:
                print(f"[ENGINE] Stopping list: {row.target_list}")
                self._stop_list(row.target_list)
                ls.current_index += 1
                continue

            if rtype == RowType.RESTART_LIST:
                print(f"[ENGINE] Restarting list: {row.target_list}")
                self._restart_list(row.target_list,
                                   reference_time=reference_time)
                ls.current_index += 1
                continue

            # It's a real activity — set as current
            ls.current_activity = row
            return

        # Exhausted
        ls.current_activity = None

    def _row_applies(self, row: CsvRow) -> bool:
        """Return True if row's weekday + dependency conditions pass."""
        if not self.ctx.matches_weekdays(row.weekdays):
            return False
        if not self.ctx.eval_dependency(row.dependencies):
            return False
        return True

    def _start_list(self, name: str,
                    reference_time: Optional[datetime] = None):
        if name in self.lists:
            ls = self.lists[name]
            if not ls.active:
                ls.active = True
                ls.current_index = 0
                ls.wait_until = None
                ls.current_activity = None
                self._resolve(ls, reference_time=reference_time)

    def _stop_list(self, name: str):
        if name in self.lists:
            ls = self.lists[name]
            ls.active = False
            ls.current_activity = None

    def _restart_list(self, name: str,
                      reference_time: Optional[datetime] = None):
        if name in self.lists:
            ls = self.lists[name]
            ls.active = True
            ls.wait_until = None
            self._resolve(ls, reference_time=reference_time)

    @staticmethod
    def _next_top_of_hour() -> datetime:
        now = datetime.now()
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    def last_completed_at(self) -> Optional[datetime]:
        """Return the completion time of the last logged entry, or None."""
        if self.log:
            return self.log[-1].completed_at
        return None

    @property
    def unsaved_changes(self) -> bool:
        """True if there are log entries added since last save."""
        return self._unsaved

    def log_adhoc(self, activity: str, start_time: datetime,
                  end_time: datetime, list_name: str = "ungeplant",
                  comment: str = ""):
        """Log an unplanned activity without advancing any list."""
        self._unsaved = True
        self.log.append(CompletedItem(
            activity=activity,
            list_name=list_name,
            priority=0.0,
            minutes=int((end_time - start_time).total_seconds() / 60),
            started_at=start_time,
            completed_at=end_time,
            skipped=False,
            original_activity="",
            comment=comment,
        ))

    def _record_raw(self, activity: str, list_name: str, priority: float,
                    minutes: int, started_at: datetime,
                    completed_at: datetime, skipped: bool,
                    original_activity: str = "",
                    comment: str = ""):
        """Low-level log append for interrupt segments etc."""
        self._unsaved = True
        self.log.append(CompletedItem(
            activity=activity,
            list_name=list_name,
            priority=priority,
            minutes=minutes,
            started_at=started_at,
            completed_at=completed_at,
            skipped=skipped,
            original_activity=original_activity,
            comment=comment,
        ))

    def _record(self, row: CsvRow, list_name: str, skipped: bool,
                custom_time: Optional[datetime] = None,
                custom_text: Optional[str] = None,
                start_time: Optional[datetime] = None,
                comment: str = "",
                _from_replay: bool = False):
        activity_text = custom_text if custom_text else row.activity
        original = row.activity if custom_text and custom_text != row.activity else ""
        completed = custom_time if custom_time else datetime.now()
        started = start_time if start_time else completed
        if not _from_replay:
            self._unsaved = True
        self.log.append(CompletedItem(
            activity=activity_text,
            list_name=list_name,
            priority=row.priority,
            minutes=row.minutes,
            started_at=started,
            completed_at=completed,
            skipped=skipped,
            original_activity=original,
            comment=comment,
        ))