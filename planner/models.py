"""
models.py — Data classes for the reactive planner.
"""
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional, List


class RowType(Enum):
    ACTIVITY = "activity"
    WAIT = "wait"
    WAIT_UNTIL_TOP_OF_HOUR = "wait_top"
    START_LIST = "start_list"
    STOP_LIST = "stop_list"
    RESTART_LIST = "restart_list"
    CONDITION = "condition"       # Wenn "<question>", <action>


@dataclass
class CsvRow:
    """One parsed row from Planungsaktivitaeten.csv."""
    activity: str
    minutes: int
    list_name: str
    priority: float
    weekdays: str
    starting_time: Optional[time]  # None if not set
    dependencies: str
    preceding_activity: str
    row_type: RowType
    target_list: str = ""        # for Start/Stop/Restart rows
    original_line: int = 0       # 1-based line number in CSV (for debugging)
    condition_question: str = ""      # CONDITION: question text (without quotes)
    condition_action: str = ""        # CONDITION: action if Yes (activity or "start list X")
    condition_else_action: str = ""   # CONDITION: action if No  (optional; empty = just skip)


@dataclass
class ListState:
    """Runtime state for one named list."""
    name: str
    rows: List[CsvRow] = field(default_factory=list)
    current_index: int = 0
    active: bool = False
    wait_until: Optional[datetime] = None   # list is blocked until this time
    current_activity: Optional[CsvRow] = None  # resolved front-of-queue item
    # Interruption tracking
    pending_start: Optional[datetime] = None   # resume start time after interruption
    continuation_count: int = 0                # how many times current item was interrupted
    # Replay tracking: indices already completed during log reload
    # (used to skip over out-of-order completions)
    replay_done_indices: set = field(default_factory=set)


@dataclass
class CompletedItem:
    """A record of a completed (or skipped) activity."""
    activity: str
    list_name: str
    priority: float
    minutes: int
    started_at: datetime          # when the activity started
    completed_at: datetime        # when the activity ended
    skipped: bool = False
    original_activity: str = ""   # original name before user edit (empty = unchanged)
    comment: str = ""             # optional user comment (skip reason, notes, etc.)
