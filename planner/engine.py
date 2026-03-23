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
import re
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple

from models import CsvRow, CompletedItem, ListState, RowType
from day_context import DayContext


# The log file path
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


class PlannerEngine:

    def __init__(self, raw_lists: Dict[str, List[CsvRow]], ctx: DayContext,
                 session_date: Optional[datetime] = None,
                 early_work_hours: Optional[int] = None,
                 yaml_overrides: Optional[Dict] = None):
        self.ctx = ctx
        self.log: List[CompletedItem] = []
        self._unsaved = False
        self.now = datetime.now() # Store current time at initialization
        # session_date anchors log filenames to the day the session started,
        # so saving after midnight still writes to the correct day's file.
        self.session_date = (session_date or datetime.now()).date()

        # Apply early work start: shift all fixed times in Liste_Arbeit
        if early_work_hours and "Liste_Arbeit" in raw_lists:
            delta = timedelta(hours=early_work_hours)
            for row in raw_lists["Liste_Arbeit"]:
                if row.starting_time:
                    original = datetime.combine(
                        self.session_date, row.starting_time)
                    shifted = original - delta
                    row.starting_time = shifted.time()
                    print(f"[ENGINE] Early start: {row.activity[:40]}… "
                          f"shifted to {row.starting_time.strftime('%H:%M')}")

        # Apply YAML overrides: removeActivities + addEvents
        if yaml_overrides:
            self._apply_yaml_overrides(raw_lists, yaml_overrides)

        # Build ListState objects from raw data
        self.lists: Dict[str, ListState] = {}
        for name, rows in raw_lists.items():
            ls = ListState(name=name, rows=rows, active=False)
            self.lists[name] = ls

        # Liste_Morgentoilette starts active automatically
        if "Liste_Morgentoilette" in self.lists:
            self.lists["Liste_Morgentoilette"].active = True

        # Liste_YAML (from YAML addEvents) starts active automatically
        if "Liste_YAML" in self.lists:
            self.lists["Liste_YAML"].active = True
            print("[ENGINE] Auto-activated 'Liste_YAML' (YAML addEvents)")

        # Auto-activate lists that have any applicable row with a fixed time.
        # These lists are always active but deferred until their time arrives.
        for ls in self.lists.values():
            if ls.active:
                continue  # already active
            for row in ls.rows:
                if not self._row_applies(row):
                    continue  # skip rows that don't apply today
                if row.row_type != RowType.ACTIVITY:
                    continue  # skip control-flow rows
                if row.starting_time:
                    ls.active = True
                    print(f"[ENGINE] Auto-activated '{ls.name}' "
                          f"(fixed time {row.starting_time.strftime('%H:%M')})")
                    break

        # Resolve initial current_activity for all active lists
        for ls in self.lists.values():
            if ls.active:
                self._resolve(ls)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  YAML overrides                                                      #
    # ------------------------------------------------------------------ #

    def _apply_yaml_overrides(self, raw_lists: Dict[str, List[CsvRow]],
                              overrides: Dict):
        """Apply removeActivities and addEvents from YAML exceptions."""
        # --- removeActivities: filter matching rows, track positions ---
        remove_set = set(overrides.get("removeActivities", []))
        # Track first removal index per list for untimed event insertion
        # {list_name: first_removed_index}
        removal_points: Dict[str, int] = {}

        if remove_set:
            for list_name, rows in raw_lists.items():
                filtered = []
                first_removed_idx = None
                for i, r in enumerate(rows):
                    if r.row_type == RowType.ACTIVITY and r.activity in remove_set:
                        if first_removed_idx is None:
                            first_removed_idx = len(filtered)
                        print(f"[YAML] Removing '{r.activity}' "
                              f"from '{list_name}' (pos {i})")
                    else:
                        filtered.append(r)

                removed = len(rows) - len(filtered)
                if removed > 0:
                    raw_lists[list_name] = filtered
                    removal_points[list_name] = first_removed_idx

        # --- addEvents: timed → Liste_YAML, untimed → insert at removal point ---
        add_events = overrides.get("addEvents", [])
        if add_events:
            # Separate timed and untimed events
            timed_rows: List[CsvRow] = []
            untimed_rows: List[CsvRow] = []

            for evt in add_events:
                name = evt.get("name", "")
                mins = evt.get("durationMinutes", 0)
                prio = evt.get("priority", 1.84)
                start_str = evt.get("startTime")

                start_time = None
                if start_str:
                    try:
                        t = datetime.strptime(start_str, "%H:%M")
                        start_time = t.time()
                    except ValueError:
                        print(f"[YAML] Bad startTime '{start_str}' "
                              f"for '{name}', ignoring")

                row = CsvRow(
                    activity=name,
                    minutes=mins,
                    list_name="",  # set below depending on placement
                    priority=prio,
                    weekdays="",        # always applies (YAML is date-specific)
                    starting_time=start_time,
                    dependencies="",
                    preceding_activity="",
                    row_type=RowType.ACTIVITY,
                    target_list="",
                    original_line=0,
                )

                if start_time:
                    timed_rows.append(row)
                else:
                    untimed_rows.append(row)

            # Insert untimed events at the removal point in the list
            # that had the most removals (typically Liste_Schwimmbad
            # or the list where the replaced activities came from)
            if untimed_rows and removal_points:
                # Pick the list with the earliest removal point
                # (first list alphabetically if tied — but usually
                # there's a clear candidate)
                target_list = min(removal_points.keys(),
                                  key=lambda k: removal_points[k])
                insert_idx = removal_points[target_list]
                target_rows = raw_lists[target_list]

                for i, row in enumerate(untimed_rows):
                    row.list_name = target_list
                    target_rows.insert(insert_idx + i, row)
                    print(f"[YAML] Inserted '{row.activity}' into "
                          f"'{target_list}' at position {insert_idx + i}")
            elif untimed_rows:
                # No removal points — fall back to Liste_YAML
                for row in untimed_rows:
                    row.list_name = "Liste_YAML"
                    print(f"[YAML] Added '{row.activity}' to Liste_YAML "
                          f"(no removal point found)")
                timed_rows = untimed_rows + timed_rows
                untimed_rows = []

            # Timed events go into Liste_YAML (activated by fixed time)
            if timed_rows:
                for row in timed_rows:
                    row.list_name = "Liste_YAML"
                    time_info = (f" at {row.starting_time.strftime('%H:%M')}"
                                 if row.starting_time else "")
                    print(f"[YAML] Added '{row.activity}' to Liste_YAML"
                          f" ({row.minutes}m, prio {row.priority}){time_info}")

                timed_rows.sort(key=lambda r: r.starting_time or time(0, 0))
                raw_lists["Liste_YAML"] = timed_rows

    # ------------------------------------------------------------------ #
    #  Tick / candidates                                                   #
    # ------------------------------------------------------------------ #

    def tick(self):
        """Call periodically (e.g. every 30s) to unblock waiting lists."""
        self.now = datetime.now() # Update current time for checks
        for ls in self.lists.values():
            if ls.active and ls.wait_until and self.now >= ls.wait_until:
                ls.wait_until = None
                self._resolve(ls)

    # ------------------------------------------------------------------ #
    #  Task locking — prevents silent preemption                           #
    # ------------------------------------------------------------------ #

    # The locked task is what the user is currently working on.
    # It stays on screen until explicitly completed, skipped, or
    # interrupted — even if higher-priority candidates appear.
    _locked_task: Optional[Tuple[str, str]] = None  # (list_name, activity)

    def lock_current(self):
        """Lock the current best candidate so it stays on screen."""
        best = self._pick_best_unlocked()
        if best:
            ls, row = best
            self._locked_task = (ls.name, row.activity)

    def _pick_best_unlocked(self) -> Optional[Tuple[ListState, CsvRow]]:
        """Raw priority-based selection without lock logic."""
        candidates = self._collect_candidates()
        if not candidates:
            return None
        candidates.sort(key=lambda x: (-x[1].priority,
                                        0 if x[1].starting_time else 1))
        return candidates[0]

    def get_best_candidate(self) -> Optional[Tuple[ListState, CsvRow]]:
        """Return the locked task if set, otherwise the highest-priority
        ready item (and lock it)."""
        candidates = self._collect_candidates()
        if not candidates:
            self._locked_task = None
            return None

        # If we have a lock, find and return the locked item
        if self._locked_task:
            lock_list, lock_act = self._locked_task
            for ls, row in candidates:
                if ls.name == lock_list and row.activity == lock_act:
                    return (ls, row)
            # Locked item is no longer a candidate (list exhausted,
            # deactivated, etc.) — release the lock
            self._locked_task = None

        # No lock (or lock released) — pick best and lock it
        candidates.sort(key=lambda x: (-x[1].priority,
                                        0 if x[1].starting_time else 1))
        best = candidates[0]
        ls, row = best
        self._locked_task = (ls.name, row.activity)
        return best

    def get_preemption_candidate(self) -> Optional[Tuple[ListState, CsvRow]]:
        """If a higher-priority item wants to preempt the locked task,
        return it. Otherwise return None."""
        if not self._locked_task:
            return None
        candidates = self._collect_candidates()
        if not candidates:
            return None

        # Find the locked item's priority
        lock_list, lock_act = self._locked_task
        locked_priority = None
        for ls, row in candidates:
            if ls.name == lock_list and row.activity == lock_act:
                locked_priority = row.priority
                break
        if locked_priority is None:
            return None  # lock no longer valid

        # Find the best non-locked candidate
        candidates.sort(key=lambda x: (-x[1].priority,
                                        0 if x[1].starting_time else 1))
        for ls, row in candidates:
            if ls.name == lock_list and row.activity == lock_act:
                continue  # skip the locked item itself
            if row.priority > locked_priority:
                return (ls, row)
            break  # sorted by priority, so no need to check further

        return None

    def get_all_candidates(self) -> List[Tuple[ListState, CsvRow]]:
        """All current candidates sorted by priority (for the queue display)."""
        cands = self._collect_candidates()
        cands.sort(key=lambda x: (-x[1].priority,
                                   0 if x[1].starting_time else 1))
        return cands

    # Regex for detecting "start list X" actions in condition branches
    _LIST_START_RE = re.compile(r'^start\s+list\s+(.+)$', re.IGNORECASE)

    def answer_condition(self, ls: ListState, row: CsvRow, answer: bool):
        """Answer a CONDITION (Wenn) row.

        answer=True:
          - action = row.condition_action
          - If "start list X"  → activate list X, log with "Entscheidung: Ja"
          - If plain activity  → log with "Entscheidung: Ja", insert synthetic
        answer=False:
          - action = row.condition_else_action (may be empty)
          - If "start list X"  → activate list X, log with "Entscheidung: Nein"
          - If plain activity  → log with "Entscheidung: Nein", insert synthetic
          - If empty           → log as skipped with "Entscheidung: Nein"
        """
        self._locked_task = None
        now = datetime.now()

        action = row.condition_action if answer else row.condition_else_action
        comment_prefix = "Entscheidung: Ja" if answer else "Entscheidung: Nein"

        # Categorise the action
        list_m = self._LIST_START_RE.match(action.strip()) if action else None

        if list_m:
            target_list = list_m.group(1).strip()
            comment = f"{comment_prefix} → Start Liste: {target_list}"
            skipped = False
        elif action:
            comment = comment_prefix
            skipped = False
        else:
            # No action defined for this branch → just skip past the row
            comment = comment_prefix
            skipped = True

        # Log the condition row itself
        self._record(row, ls.name, skipped=skipped,
                     custom_time=now, start_time=now, comment=comment)

        # Advance past the condition row
        ls.current_index += 1
        ls.current_activity = None
        ls.pending_start = None
        ls.continuation_count = 0

        # Execute the action
        if list_m:
            self._start_list(list_m.group(1).strip())
        elif action:
            # Insert a synthetic ACTIVITY row so the user can log it normally
            synthetic = CsvRow(
                activity=action,
                minutes=row.minutes,   # inherit (usually 0 for WENN rows)
                list_name=ls.name,
                priority=row.priority,
                weekdays="",           # always applies — runtime-injected
                starting_time=None,
                dependencies="",
                preceding_activity="",
                row_type=RowType.ACTIVITY,
                target_list="",
                original_line=0,
            )
            ls.rows.insert(ls.current_index, synthetic)

        self._resolve(ls)

    def mark_done(self, ls: ListState, row: CsvRow,
                  custom_time: Optional[datetime] = None,
                  custom_text: Optional[str] = None,
                  start_time: Optional[datetime] = None,
                  comment: str = ""):
        """Mark current item as done, advance list."""
        self._locked_task = None  # release lock
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
        self._locked_task = None  # release lock
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
        self._locked_task = None  # release lock — will re-lock on next get_best_candidate
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

    def get_day_projection(self,
                           start_time: Optional[datetime] = None
                           ) -> List[Dict]:
        """
        Simulate the engine forward with preemptive scheduling.

        Higher-priority items that become ready (via fixed start time or
        wait expiry) during a lower-priority item's execution will
        preempt it.  The interrupted item is split: the first segment
        is emitted, and the remaining duration becomes a "(Fs.)"
        continuation that competes normally with other candidates.

        Args:
            start_time: If set, use this as the simulation start
                instead of datetime.now().  Used when generating the
                initial projection on a restart (so it reflects the
                real start of the day, not the restart time).

        Returns a chronologically ordered list of dicts:
          - 'activity', 'list_name', 'minutes', 'priority'
          - 'fixed_time': Optional[time]
          - 'est_start': datetime, 'est_end': datetime
          - 'state': 'current' | 'upcoming' | 'scheduled'
          - 'is_control': False
        """
        now = start_time if start_time else datetime.now()
        projection: List[Dict] = []

        class _SimList:
            __slots__ = ('name', 'rows', 'active', 'idx', 'wait_until',
                         'is_current_real', 'replay_done')
            def __init__(self, name, rows, active, idx, wait_until,
                         replay_done=None):
                self.name = name
                self.rows = rows
                self.active = active
                self.idx = idx
                self.wait_until = wait_until
                self.is_current_real = False
                self.replay_done = replay_done or set()

        sim: Dict[str, _SimList] = {}
        for ls in self.lists.values():
            sl = _SimList(
                name=ls.name, rows=ls.rows, active=ls.active,
                idx=ls.current_index,
                wait_until=ls.wait_until if (ls.wait_until and ls.wait_until > now) else None,
                replay_done=set(ls.replay_done_indices),
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
                # Skip rows already completed during log replay
                if sl.idx in sl.replay_done:
                    sl.idx += 1
                    continue
                # V8: skip activities already logged out-of-order
                if (row.row_type == RowType.ACTIVITY
                        and self._is_already_logged(row.activity, sl.name)):
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
                if rt == RowType.CONDITION:
                    # Check fixed start time (same as ACTIVITY)
                    if row.starting_time:
                        target_dt = cursor.replace(
                            hour=row.starting_time.hour,
                            minute=row.starting_time.minute,
                            second=0, microsecond=0)
                        if cursor < target_dt:
                            sl.wait_until = target_dt
                            return None
                    # Default assumption: Nein — apply the else branch
                    else_action = row.condition_else_action
                    if else_action:
                        em = re.match(r'^start\s+list\s+(.+)$',
                                      else_action.strip(), re.IGNORECASE)
                        if em:
                            tgt = em.group(1).strip()
                            if tgt in sim and not sim[tgt].active:
                                sim[tgt].active = True
                                sim[tgt].idx = 0
                                sim[tgt].wait_until = None
                    # Emit as 0-min marker; outer loop does sl.idx += 1
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

    def get_completed_log(self) -> List[CompletedItem]:
        """Return completed/skipped items sorted by started_at."""
        return sorted(self.log, key=lambda c: c.started_at)

    def items_done_today(self) -> int:
        return sum(1 for c in self.log if not c.skipped)

    def items_skipped_today(self) -> int:
        return sum(1 for c in self.log if c.skipped)

    def save_log(self) -> str:
        """Save completion log as JSON for later Ablauf generation."""
        os.makedirs(LOG_DIR, exist_ok=True)
        path = self._get_log_path()
        # Sort by started_at so retroactive entries fill gaps correctly
        sorted_log = sorted(self.log, key=lambda c: c.started_at)
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
            for c in sorted_log
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._unsaved = False
        return path

    def load_log(self, path: str) -> Tuple[int, int]:
        """
        Loads completion/skip records from a JSON log file and reconciles
        the planner state by advancing indices.

        Strategy (two-phase):

        Phase 1 — Unconditional restore:
          ALL log entries are loaded into self.log.  What was logged
          stays logged, regardless of whether it matches a CSV row.

        Phase 2 — List reconciliation:
          Walk each list's CSV rows in order.  For each activity row,
          search the log for a matching entry (by activity text or
          original_activity).  If matched, consume it and advance the
          index.  If NOT matched, skip that CSV row but CONTINUE
          checking subsequent rows (don't break).  Control-flow rows
          (WAIT, START, STOP, RESTART) are processed when reached,
          but only if at least one preceding activity was matched
          (proving the session advanced past that point).

        This ensures:
        - Save → Load never loses log entries or creates gaps
        - Out-of-order completions are handled
        - Repeated activities consume one log entry each
        - Continuations (Fs.) match via original_activity

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

        def _parse_log_time(time_str: str) -> datetime:
            """Parse HH:MM:SS from log, anchored to session_date."""
            try:
                t = datetime.strptime(time_str, "%H:%M:%S")
            except ValueError:
                return now
            base = self.session_date
            if t.hour < 5:
                base = self.session_date + timedelta(days=1)
            return t.replace(year=base.year, month=base.month, day=base.day)

        # ============================================================
        # PHASE 1: Unconditionally restore ALL log entries
        # ============================================================
        for entry in log_data:
            started_dt = _parse_log_time(entry.get("started_at", ""))
            completed_dt = _parse_log_time(entry.get("completed_at", ""))
            self.log.append(CompletedItem(
                activity=entry.get("activity", ""),
                list_name=entry.get("list", ""),
                priority=entry.get("priority", 0.0),
                minutes=entry.get("minutes", 0),
                started_at=started_dt,
                completed_at=completed_dt,
                skipped=entry.get("skipped", False),
                original_activity=entry.get("original_activity", ""),
                comment=entry.get("comment", ""),
            ))
            if entry.get("skipped", False):
                skip_count += 1
            else:
                done_count += 1

        # ============================================================
        # PHASE 2: Reconcile list indices against the log
        # ============================================================
        # Group log entries by list name — include ALL list names from
        # the log, even if the list isn't in self.lists yet (it might
        # get started via START_LIST during reconciliation).
        log_by_list: Dict[str, List[Dict]] = {}
        for entry in log_data:
            list_name = entry.get("list")
            if list_name:
                log_by_list.setdefault(list_name, []).append(entry)

        # Process lists.  Lists that get started via START_LIST during
        # this loop need a second pass, so we track them.
        reconciled: set = set()

        def _reconcile_list(ls):
            """Match a list's CSV rows against its log entries."""
            if ls.name in reconciled:
                return
            reconciled.add(ls.name)

            if ls.name not in log_by_list:
                return

            remaining = list(log_by_list[ls.name])
            last_completed_at_local: Optional[datetime] = None
            # Track which CSV indices were matched
            matched_indices: set = set()
            # Track whether we've passed an unmatched ACTIVITY.
            # Once that happens, we must NOT execute control-flow
            # rows (START_LIST, STOP_LIST, etc.) because the session
            # hasn't actually reached that point yet.
            hit_unmatched_activity = False

            save_index = ls.current_index
            while ls.current_index < len(ls.rows):
                row = ls.rows[ls.current_index]

                if not self._row_applies(row):
                    ls.current_index += 1
                    continue

                # --- Handle control-flow rows ---
                if row.row_type == RowType.WAIT:
                    base = (last_completed_at_local
                            if last_completed_at_local else now)
                    expiry = base + timedelta(minutes=row.minutes)
                    if expiry <= now or remaining:
                        if expiry > now and remaining:
                            print(f"[LOAD] WAIT {row.minutes}min in "
                                  f"'{ls.name}' — served (later entries)")
                        else:
                            print(f"[LOAD] WAIT {row.minutes}min in "
                                  f"'{ls.name}' already expired "
                                  f"(ref: {base.strftime('%H:%M')})")
                        ls.current_index += 1
                        continue
                    else:
                        ls.wait_until = expiry
                        print(f"[LOAD] WAIT in '{ls.name}' until "
                              f"{expiry.strftime('%H:%M')} "
                              f"(ref: {base.strftime('%H:%M')})")
                        ls.current_index += 1
                        ls.current_activity = None
                        break

                if row.row_type == RowType.WAIT_UNTIL_TOP_OF_HOUR:
                    if last_completed_at_local:
                        target = (last_completed_at_local.replace(
                            minute=0, second=0, microsecond=0)
                            + timedelta(hours=1))
                    else:
                        target = self._next_top_of_hour()
                    if target <= now or remaining:
                        if target > now and remaining:
                            print(f"[LOAD] WAIT_TOP_OF_HOUR in "
                                  f"'{ls.name}' — served")
                        ls.current_index += 1
                        continue
                    else:
                        ls.wait_until = target
                        ls.current_index += 1
                        ls.current_activity = None
                        break

                if row.row_type == RowType.START_LIST:
                    if hit_unmatched_activity:
                        # Session hasn't reached this point yet —
                        # don't activate the target list prematurely.
                        ls.current_index += 1
                        continue
                    print(f"[LOAD] Starting list: {row.target_list}")
                    self._start_list(row.target_list,
                                     reference_time=last_completed_at_local)
                    ls.current_index += 1
                    # Reconcile the newly started list immediately
                    if (row.target_list in self.lists and
                            row.target_list not in reconciled):
                        _reconcile_list(self.lists[row.target_list])
                    continue

                if row.row_type == RowType.STOP_LIST:
                    if hit_unmatched_activity:
                        ls.current_index += 1
                        continue
                    print(f"[LOAD] Stopping list: {row.target_list}")
                    self._stop_list(row.target_list)
                    ls.current_index += 1
                    continue

                if row.row_type == RowType.RESTART_LIST:
                    if hit_unmatched_activity:
                        ls.current_index += 1
                        continue
                    print(f"[LOAD] Restarting list: {row.target_list}")
                    self._restart_list(row.target_list,
                                       reference_time=last_completed_at_local)
                    ls.current_index += 1
                    if (row.target_list in self.lists and
                            row.target_list not in reconciled):
                        _reconcile_list(self.lists[row.target_list])
                    continue

                if row.row_type == RowType.CONDITION:
                    if remaining:
                        ls.current_index += 1
                        continue
                    else:
                        break

                # --- ACTIVITY row — match against log ---
                match_idx = None
                for i, log_entry in enumerate(remaining):
                    log_act = log_entry["activity"]
                    log_orig = log_entry.get("original_activity", "")
                    if log_act == row.activity or \
                       (log_orig and log_orig == row.activity):
                        match_idx = i
                        break

                if match_idx is not None:
                    log_entry = remaining.pop(match_idx)
                    completed_dt = _parse_log_time(
                        log_entry.get("completed_at", ""))
                    last_completed_at_local = completed_dt
                    matched_indices.add(ls.current_index)
                    ls.current_index += 1
                    ls.current_activity = None
                else:
                    # No match — this activity wasn't completed yet.
                    # Mark that we've passed an unmatched activity so
                    # subsequent control-flow rows won't fire.
                    hit_unmatched_activity = True
                    ls.current_index += 1

                if not remaining:
                    break

            # Store matched indices so _resolve() can skip them
            ls.replay_done_indices = matched_indices

            # Reset index to the start so _resolve() walks from
            # the beginning, skipping matched + non-applicable rows
            ls.current_index = save_index
            ls.current_activity = None

        for ls in self.lists.values():
            _reconcile_list(ls)

        # Sort log chronologically
        self.log.sort(key=lambda c: c.completed_at)

        # Final resolve — only for active lists not currently blocked
        for ls in self.lists.values():
            if ls.active and not ls.wait_until:
                self._resolve(ls)

        return done_count, skip_count

    def _get_log_path(self) -> str:
        os.makedirs(LOG_DIR, exist_ok=True)
        day_str = self.session_date.strftime("%Y-%m-%d")
        return os.path.join(LOG_DIR, f"planner-log-{day_str}.json")

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

            # Skip rows that were already completed during log replay
            # (out-of-order completions from a previous session)
            if ls.current_index in ls.replay_done_indices:
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

            # V8: skip activities already logged out-of-order
            if self._is_already_logged(row.activity, ls.name):
                print(f"[ENGINE] Auto-skip '{row.activity[:40]}' in "
                      f"'{ls.name}' (already logged)")
                ls.current_index += 1
                continue

            # It's a real activity — set as current
            ls.current_activity = row
            return

        # Exhausted
        ls.current_activity = None

    def _is_already_logged(self, activity: str, list_name: str) -> bool:
        """Check if an activity is already in the log (V8: out-of-order logging).

        Matches by activity name (exact) OR original_activity.
        Only matches within the same list to avoid false positives
        from identically named activities in different lists.
        """
        for item in self.log:
            if item.list_name != list_name:
                continue
            if item.activity == activity:
                return True
            if item.original_activity and item.original_activity == activity:
                return True
        return False

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
        # V8: if logged under a real list (not "ungeplant"), re-resolve
        # that list so the queue skips the now-logged activity
        if list_name != "ungeplant" and list_name in self.lists:
            ls = self.lists[list_name]
            if ls.active and ls.current_activity:
                if self._is_already_logged(ls.current_activity.activity,
                                           ls.name):
                    ls.current_index += 1
                    ls.current_activity = None
                    self._locked_task = None
                    self._resolve(ls)

    def delete_log_entry(self, sorted_index: int) -> bool:
        """Delete a log entry by its index in the sorted (by started_at) log.

        Removes from in-memory log and rewrites the JSON file.
        Returns True on success, False if index is out of range.
        """
        sorted_log = sorted(self.log, key=lambda c: c.started_at)
        if sorted_index < 0 or sorted_index >= len(sorted_log):
            return False
        target = sorted_log[sorted_index]
        self.log.remove(target)
        self._unsaved = True
        return True

    def update_log_entry(self, sorted_index: int,
                         activity: str, list_name: str,
                         priority: float, minutes: int,
                         started_at: datetime, completed_at: datetime,
                         skipped: bool, original_activity: str = "",
                         comment: str = "") -> bool:
        """Update a log entry in-place by its index in the sorted log.

        Rewrites the JSON file after updating.
        Returns True on success, False if index is out of range.
        """
        sorted_log = sorted(self.log, key=lambda c: c.started_at)
        if sorted_index < 0 or sorted_index >= len(sorted_log):
            return False
        target = sorted_log[sorted_index]
        target.activity = activity
        target.list_name = list_name
        target.priority = priority
        target.minutes = minutes
        target.started_at = started_at
        target.completed_at = completed_at
        target.skipped = skipped
        target.original_activity = original_activity
        target.comment = comment
        self._unsaved = True
        return True

    def duplicate_log_entry(self, activity: str, list_name: str,
                            priority: float, minutes: int,
                            started_at: datetime, completed_at: datetime,
                            skipped: bool, original_activity: str = "",
                            comment: str = ""):
        """Add a new log entry (used for duplicating an existing one)."""
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