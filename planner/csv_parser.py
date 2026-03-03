"""
csv_parser.py — Parse Planungsaktivitaeten.csv into grouped CsvRow lists.

File is semicolon-delimited, Windows-1252 encoded.
Priority uses German decimal separator (comma → dot).
Columns: Activity;Minutes;List;Priority;Weekdays;Starting time;Dependencies;Preceding_Activity
"""
import csv
import re
from datetime import time
from typing import Dict, List, Optional

from models import CsvRow, RowType

CSV_PATH = r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Planungsaktivitaeten.csv"


def _parse_minutes(val: str) -> int:
    """Parse minutes field, returning 0 on failure."""
    try:
        return int(float(val.replace(",", ".")))
    except (ValueError, AttributeError):
        return 0


def _parse_priority(val: str) -> float:
    """Parse German-locale priority (comma as decimal separator)."""
    try:
        return float(val.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return 1.0


def _parse_time(val: str) -> Optional[time]:
    """Parse 'HH:MM' string to time object, None if empty/invalid."""
    if not val or not val.strip():
        return None
    val = val.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", val)
    if m:
        try:
            return time(int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    return None


def _detect_row_type(activity: str) -> tuple[RowType, str]:
    """Identify control-flow rows; return (RowType, target_list)."""
    a = activity.strip()
    al = a.lower()
    if al == "wait until top of hour":
        return RowType.WAIT_UNTIL_TOP_OF_HOUR, ""
    if al == "wait":
        return RowType.WAIT, ""
    # "Start list X", "Stop list X", "Restart list X"
    m = re.match(r"^(start|stop|restart)\s+list\s+(.+)$", a, re.IGNORECASE)
    if m:
        verb = m.group(1).lower()
        target = m.group(2).strip()
        if verb == "start":
            return RowType.START_LIST, target
        elif verb == "stop":
            return RowType.STOP_LIST, target
        elif verb == "restart":
            return RowType.RESTART_LIST, target
    return RowType.ACTIVITY, ""


def parse_csv(path: str = CSV_PATH) -> Dict[str, List[CsvRow]]:
    """
    Parse the CSV and return a dict mapping list_name -> [CsvRow, ...].
    Order within each list preserves CSV row order.
    """
    lists: Dict[str, List[CsvRow]] = {}

    with open(path, encoding="windows-1252", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        header = next(reader, None)  # skip header line

        for lineno, raw_row in enumerate(reader, start=2):
            # Pad to 8 columns
            row = raw_row + [""] * (8 - len(raw_row))

            activity = row[0].strip()
            minutes_str = row[1].strip()
            list_name = row[2].strip()
            priority_str = row[3].strip()
            weekdays = row[4].strip()
            starting_time_str = row[5].strip()
            dependencies = row[6].strip()
            preceding = row[7].strip()

            if not activity or not list_name:
                continue  # skip empty rows

            row_type, target_list = _detect_row_type(activity)

            csv_row = CsvRow(
                activity=activity,
                minutes=_parse_minutes(minutes_str),
                list_name=list_name,
                priority=_parse_priority(priority_str),
                weekdays=weekdays,
                starting_time=_parse_time(starting_time_str),
                dependencies=dependencies,
                preceding_activity=preceding,
                row_type=row_type,
                target_list=target_list,
                original_line=lineno,
            )

            if list_name not in lists:
                lists[list_name] = []
            lists[list_name].append(csv_row)

    return lists


def get_list_names(parsed: Dict[str, List[CsvRow]]) -> List[str]:
    """Return list names in the order they first appear."""
    return list(parsed.keys())
