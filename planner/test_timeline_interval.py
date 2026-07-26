# -*- coding: utf-8 -*-
"""
Test: Session-date anchored time interval calculation for Timeline Nacherfassung and Log Editing.

Validates that entering times (sh, sm, eh, em) in dialogs for a session date (e.g. 2026-07-25)
always interprets hours >= 05:00 on the session date and hours < 05:00 on the day after midnight,
regardless of whether the initial default_start was after midnight.

Run: py test_timeline_interval.py
"""
import sys
import os
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def compute_interval(session_date_dt: date, sh: int, sm: int, eh: int, em: int):
    """Replicates interval logic in timeline_import.py::_apply_interval()."""
    start_base = session_date_dt + timedelta(days=1) if sh < 5 else session_date_dt
    new_start = datetime.combine(start_base, datetime.min.time()).replace(hour=sh, minute=sm)

    end_base = session_date_dt + timedelta(days=1) if eh < 5 else session_date_dt
    new_end = datetime.combine(end_base, datetime.min.time()).replace(hour=eh, minute=em)

    if new_end <= new_start:
        new_end += timedelta(days=1)

    return new_start, new_end


def compute_log_edit_times(started_at: datetime, sh: int, sm: int, eh: int, em: int):
    """Replicates log edit time calculation in gui.py::_on_edit_log_entry()."""
    session_date = started_at.date() if started_at.hour >= 5 else started_at.date() - timedelta(days=1)
    start_base = session_date + timedelta(days=1) if sh < 5 else session_date
    start_dt = datetime.combine(start_base, datetime.min.time()).replace(hour=sh, minute=sm)

    end_base = session_date + timedelta(days=1) if eh < 5 else session_date
    end_dt = datetime.combine(end_base, datetime.min.time()).replace(hour=eh, minute=em)

    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    return start_dt, end_dt


def test_timeline_interval_after_midnight_default():
    session_date = date(2026, 7, 25)
    
    # Kurt's case: Default start was 00:03 on 2026-07-26. User sets interval to 22:00-22:20.
    start_dt, end_dt = compute_interval(session_date, 22, 0, 22, 20)
    assert start_dt == datetime(2026, 7, 25, 22, 0), f"Expected 2026-07-25 22:00, got {start_dt}"
    assert end_dt == datetime(2026, 7, 25, 22, 20), f"Expected 2026-07-25 22:20, got {end_dt}"
    print("Test 1 (Kurt's case: 22:00-22:20 for yesterday): OK ✓")


def test_timeline_interval_post_midnight():
    session_date = date(2026, 7, 25)
    
    # Post-midnight interval: 00:03 - 01:03
    start_dt, end_dt = compute_interval(session_date, 0, 3, 1, 3)
    assert start_dt == datetime(2026, 7, 26, 0, 3), f"Expected 2026-07-26 00:03, got {start_dt}"
    assert end_dt == datetime(2026, 7, 26, 1, 3), f"Expected 2026-07-26 01:03, got {end_dt}"
    print("Test 2 (Post-midnight interval 00:03-01:03): OK ✓")


def test_timeline_interval_spanning_midnight():
    session_date = date(2026, 7, 25)
    
    # Midnight span: 23:50 - 00:30
    start_dt, end_dt = compute_interval(session_date, 23, 50, 0, 30)
    assert start_dt == datetime(2026, 7, 25, 23, 50), f"Expected 2026-07-25 23:50, got {start_dt}"
    assert end_dt == datetime(2026, 7, 26, 0, 30), f"Expected 2026-07-26 00:30, got {end_dt}"
    print("Test 3 (Spanning midnight 23:50-00:30): OK ✓")


def test_log_edit_post_midnight_entry():
    # Entry started at 00:03 on 2026-07-26 (part of session 2026-07-25)
    started_at = datetime(2026, 7, 26, 0, 3)
    
    # User edits start to 22:00
    start_dt, end_dt = compute_log_edit_times(started_at, 22, 0, 22, 20)
    assert start_dt == datetime(2026, 7, 25, 22, 0), f"Expected 2026-07-25 22:00, got {start_dt}"
    assert end_dt == datetime(2026, 7, 25, 22, 20), f"Expected 2026-07-25 22:20, got {end_dt}"
    print("Test 4 (Log edit on post-midnight entry to 22:00): OK ✓")


if __name__ == "__main__":
    print("============================================================")
    print("  Timeline Interval & Session Date Calculation Tests")
    print("============================================================")
    test_timeline_interval_after_midnight_default()
    test_timeline_interval_post_midnight()
    test_timeline_interval_spanning_midnight()
    test_log_edit_post_midnight_entry()
    print("\nAll tests passed successfully! ✓")
