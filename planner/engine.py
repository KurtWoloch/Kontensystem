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
        self.now = datetime.now() # Store current time at initialization

        # Build ListState objects from raw data
        self.lists: Dict[str, ListState] = {}
        for name, rows in raw_lists.items():
            ls = ListState(name=name, rows=rows, active=False)
            self.lists[name] = ls

        # Liste_Morgentoilette starts active automatically
        if "Liste_Morgentoilette" in self.lists:
            self.lists["Liste_Morgentoilette"].active = True

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
        # Sort by priority descending, tie-break by list insertion order (stable sort)
        candidates.sort(key=lambda x: -x[1].priority)
        return candidates[0]

    def get_all_candidates(self) -> List[Tuple[ListState, CsvRow]]:
        """All current candidates sorted by priority (for the queue display)."""
        cands = self._collect_candidates()
        cands.sort(key=lambda x: -x[1].priority)
        return cands

    def mark_done(self, ls: ListState, row: CsvRow,
                  custom_time: Optional[datetime] = None,
                  custom_text: Optional[str] = None,
                  start_time: Optional[datetime] = None):
        """Mark current item as done, advance list."""
        self._record(row, ls.name, skipped=False,
                     custom_time=custom_time, custom_text=custom_text,
                     start_time=start_time)
        ls.current_index += 1
        ls.current_activity = None
        self._resolve(ls, reference_time=custom_time)

    def mark_skip(self, ls: ListState, row: CsvRow):
        """Skip current item, advance list."""
        self._record(row, ls.name, skipped=True)
        ls.current_index += 1
        ls.current_activity = None
        self._resolve(ls)

    def get_active_lists(self) -> List[ListState]:
        return [ls for ls in self.lists.values() if ls.active]

    def get_wait_status(self) -> List[Tuple[str, datetime]]:
        """Return [(list_name, wait_until)] for lists currently waiting."""
        result = []
        for ls in self.lists.values():
            if ls.active and ls.wait_until and ls.wait_until > self.now:
                result.append((ls.name, ls.wait_until))
        return result

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
            }
            for c in self.log
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
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
                                 start_time=started_dt)
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
                                 start_time=started_dt)
                    ls.current_index += 1
                    ls.current_activity = None
                    done_count += 1

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

    def log_adhoc(self, activity: str, start_time: datetime,
                  end_time: datetime, list_name: str = "ungeplant"):
        """Log an unplanned activity without advancing any list."""
        self.log.append(CompletedItem(
            activity=activity,
            list_name=list_name,
            priority=0.0,
            minutes=int((end_time - start_time).total_seconds() / 60),
            started_at=start_time,
            completed_at=end_time,
            skipped=False,
            original_activity="",
        ))

    def _record(self, row: CsvRow, list_name: str, skipped: bool,
                custom_time: Optional[datetime] = None,
                custom_text: Optional[str] = None,
                start_time: Optional[datetime] = None):
        activity_text = custom_text if custom_text else row.activity
        original = row.activity if custom_text and custom_text != row.activity else ""
        completed = custom_time if custom_time else datetime.now()
        started = start_time if start_time else completed
        self.log.append(CompletedItem(
            activity=activity_text,
            list_name=list_name,
            priority=row.priority,
            minutes=row.minutes,
            started_at=started,
            completed_at=completed,
            skipped=skipped,
            original_activity=original,
        ))