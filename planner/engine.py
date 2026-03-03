"""
engine.py — Reactive planning engine.

Core loop:
  - Multiple named lists, each with sequential items.
  - Only "active" lists contribute candidates.
  - Items are filtered by weekday + dependency conditions.
  - Wait items block a list temporarily.
  - Start/Stop/Restart list items trigger list state changes.
  - Fixed-time items are deferred until their time arrives.
  - The highest-priority ready item across all active lists is offered to user.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from models import CsvRow, CompletedItem, ListState, RowType
from day_context import DayContext


# The log file path
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


class PlannerEngine:

    def __init__(self, raw_lists: Dict[str, List[CsvRow]], ctx: DayContext):
        self.ctx = ctx
        self.log: List[CompletedItem] = []

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
        now = datetime.now()
        for ls in self.lists.values():
            if ls.active and ls.wait_until and now >= ls.wait_until:
                ls.wait_until = None
                self._resolve(ls)

    def get_best_candidate(self) -> Optional[Tuple[ListState, CsvRow]]:
        """Return (ListState, CsvRow) for the highest-priority ready item."""
        candidates = self._collect_candidates()
        if not candidates:
            return None
        # Sort by priority descending, tie-break by list insertion order
        candidates.sort(key=lambda x: -x[1].priority)
        return candidates[0]

    def get_all_candidates(self) -> List[Tuple[ListState, CsvRow]]:
        """All current candidates sorted by priority (for the queue display)."""
        cands = self._collect_candidates()
        cands.sort(key=lambda x: -x[1].priority)
        return cands

    def mark_done(self, ls: ListState, row: CsvRow,
                  custom_time: Optional[datetime] = None,
                  custom_text: Optional[str] = None):
        """Mark current item as done, advance list."""
        self._record(row, ls.name, skipped=False,
                     custom_time=custom_time, custom_text=custom_text)
        ls.current_index += 1
        ls.current_activity = None
        self._resolve(ls)

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
        now = datetime.now()
        result = []
        for ls in self.lists.values():
            if ls.active and ls.wait_until and ls.wait_until > now:
                result.append((ls.name, ls.wait_until))
        return result

    def items_done_today(self) -> int:
        return sum(1 for c in self.log if not c.skipped)

    def items_skipped_today(self) -> int:
        return sum(1 for c in self.log if c.skipped)

    def save_log(self):
        """Save completion log as JSON for later Ablauf generation."""
        os.makedirs(LOG_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        path = os.path.join(LOG_DIR, f"planner-log-{today}.json")
        data = []
        for c in self.log:
            entry = {
                "activity": c.activity,
                "list": c.list_name,
                "priority": c.priority,
                "minutes": c.minutes,
                "completed_at": c.completed_at.strftime("%H:%M:%S"),
                "skipped": c.skipped,
            }
            if c.original_activity:
                entry["original_activity"] = c.original_activity
            data.append(entry)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

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

    def _resolve(self, ls: ListState):
        """
        Scan forward from ls.current_index, consuming control-flow rows
        until we reach a real activity or block/exhaust the list.
        Sets ls.current_activity appropriately.
        """
        while ls.current_index < len(ls.rows):
            row = ls.rows[ls.current_index]

            # Check if this row applies to today
            if not self._row_applies(row):
                ls.current_index += 1
                continue

            rtype = row.row_type

            if rtype == RowType.WAIT:
                ls.wait_until = datetime.now() + timedelta(minutes=row.minutes)
                ls.current_index += 1
                ls.current_activity = None
                return  # list is blocked

            if rtype == RowType.WAIT_UNTIL_TOP_OF_HOUR:
                ls.wait_until = self._next_top_of_hour()
                ls.current_index += 1
                ls.current_activity = None
                return  # list is blocked

            if rtype == RowType.START_LIST:
                self._start_list(row.target_list)
                ls.current_index += 1
                continue

            if rtype == RowType.STOP_LIST:
                self._stop_list(row.target_list)
                ls.current_index += 1
                continue

            if rtype == RowType.RESTART_LIST:
                self._restart_list(row.target_list)
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

    def _start_list(self, name: str):
        if name in self.lists:
            ls = self.lists[name]
            if not ls.active:
                ls.active = True
                ls.current_index = 0
                ls.wait_until = None
                ls.current_activity = None
                self._resolve(ls)

    def _stop_list(self, name: str):
        if name in self.lists:
            ls = self.lists[name]
            ls.active = False
            ls.current_activity = None

    def _restart_list(self, name: str):
        if name in self.lists:
            ls = self.lists[name]
            ls.active = True
            ls.wait_until = None
            # Restart = re-activate at current index (don't reset to 0)
            self._resolve(ls)

    @staticmethod
    def _next_top_of_hour() -> datetime:
        now = datetime.now()
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    def _record(self, row: CsvRow, list_name: str, skipped: bool,
                custom_time: Optional[datetime] = None,
                custom_text: Optional[str] = None):
        activity_text = custom_text if custom_text else row.activity
        original = row.activity if custom_text and custom_text != row.activity else ""
        self.log.append(CompletedItem(
            activity=activity_text,
            list_name=list_name,
            priority=row.priority,
            minutes=row.minutes,
            completed_at=custom_time if custom_time else datetime.now(),
            skipped=skipped,
            original_activity=original,
        ))
