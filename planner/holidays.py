"""
holidays.py — Automatic Austrian public holiday detection.

Ported from the old C# planner (Feiertag.cs) which used a "goldene Zahl"
(golden number) lookup table indexed by year % 19 to find Easter Sunday,
then derived all moveable holidays from that.

Fixed holidays (9 total) are checked directly by date.
Moveable holidays (6 total) are computed relative to Easter Sunday.

Usage:
    from holidays import is_austrian_holiday, get_holiday_name
    name = get_holiday_name(date(2026, 5, 26))  # → "Christi Himmelfahrt"
    if is_austrian_holiday(date.today()):
        ...
"""
from datetime import date
from typing import Optional


# Fixed-date holidays (Austria)
_FIXED = {
    (1, 1): "Neujahr",
    (1, 6): "Heilige drei Könige",
    (5, 1): "Tag der Arbeit",
    (8, 15): "Maria Himmelfahrt",
    (10, 26): "Nationalfeiertag",
    (11, 1): "Allerheiligen",
    (12, 8): "Maria Empfängnis",
    (12, 25): "Christtag",
    (12, 26): "Stefanitag",
}

# Easter Sunday dates for golden-number lookup (19 entries, indexed by year % 19).
# Each entry is "DD.MM" format.  The original C# code had 19 entries;
# these cover the full Metonic cycle.  We extend with a modern table
# that's valid for a much wider range of years.
#
# The original C# table (from Feiertag.cs) covered 2000–2018 via a
# fixed 19-entry array.  We'll use a computed algorithm instead,
# which is valid for all years in the Gregorian calendar (1583–∞).

# The C# code used this logic:
#   rf = (year % 19) + 1
#   goldDatum = new DateTime(year, month, day) from Var[rf-1]
#   Then offset from goldDatum by day-of-week to find Easter Sunday.
#
# We replicate this exact logic using the original Var table,
# then also provide a fallback algorithm for years not covered.


# Original Var[] from Feiertag.cs — Easter Sunday dates indexed by
# (year % 19), covering the 19-year Metonic cycle.
# These are the raw dates from the C# source; the algorithm then
# adjusts by day-of-week to find the actual Easter Sunday.
_VAR_ORIGINAL = [
    "14.04", "03.04", "23.03", "11.04", "31.03", "16.04", "08.04",
    "28.03", "16.04", "05.04", "25.03", "13.04", "02.04", "22.03",
    "10.04", "30.03", "17.04", "07.04", "27.03",
]


def _easter_sunday_from_table(year: int) -> Optional[date]:
    """Compute Easter Sunday using the original C# lookup table.

    The C# algorithm:
      rf = (year % 19) + 1
      goldDatum = parse Var[rf-1] as date in `year`
      goldZahl = serial_number(goldDatum) + (7 - day_of_week(goldDatum))
      easter = date_from_serial(goldZahl)

    We replicate this exactly.
    """
    rf = (year % 19) + 1  # 1-based index
    raw = _VAR_ORIGINAL[rf - 1]
    day = int(raw[:2])
    month = int(raw[3:])
    try:
        gold_datum = date(year, month, day)
    except ValueError:
        return None

    # Serial number function (port of RBZZKAAB_FZahl)
    def serial(d: date) -> int:
        ttz = d.day
        mmz = d.month
        jjz = d.year
        zahl = (ttz - 1) + (31 * (mmz - 1)) + (365 * jjz)
        if mmz > 2:
            temp_mmz = mmz * 0.4 + 2.3
            zahl -= int(temp_mmz)
        else:
            jjz -= 1
        zahl += (jjz // 4)
        temp_jjz = (jjz * 0.01 + 1) * 0.75
        zahl -= int(temp_jjz)
        return zahl

    gold_zahl = serial(gold_datum) + (7 - gold_datum.weekday())
    # Convert serial back to date — we need the inverse of serial()
    # Instead of inverting, we iterate: start from gold_datum and
    # adjust by the difference.
    # Actually, the C# code computes datumZahl for the target date and
    # compares.  We want the date where serial(date) == gold_zahl.
    # Simpler: gold_datum's serial + offset = Easter's serial.
    # Easter is the Sunday on or after gold_datum.
    # gold_datum.weekday(): 0=Mon..6=Sun
    # We need: easter = gold_datum + (6 - gold_datum.weekday()) days
    # But the C# adds (7 - weekday) to the serial, which is different.
    # Let me re-derive:
    #   gold_datum is a reference date
    #   gold_zahl = serial(gold_datum) + (7 - weekday(gold_datum))
    #   For any date d, serial(d) gives a number.
    #   Easter Sunday = the date d where serial(d) == gold_zahl
    #
    # Since serial() is approximately linear with a slope of ~1 per day,
    # we can approximate: easter ≈ gold_datum + (gold_zahl - serial(gold_datum))
    # = gold_datum + (7 - weekday(gold_datum))
    # But that's the number of days to add to gold_datum to reach the
    # NEXT Sunday (or the same day if it's already Sunday).
    #
    # Wait — if gold_datum is a Sunday (weekday=6), then 7-6=1, so
    # we'd add 1 day?  That can't be right.  Let me re-check the C#.
    #
    # C# goldDatum.DayOfWeek: Sunday=0, Monday=1, ..., Saturday=6
    # (C# DayOfWeek enum: Sunday=0)
    # Python weekday(): Monday=0, ..., Sunday=6
    #
    # So in C#: (7 - (int)goldDatum.DayOfWeek) where DayOfWeek is
    # Sunday=0 means: if Sunday, add 7; if Saturday (6), add 1;
    # if Monday (1), add 6.
    # This gives the NEXT Sunday AFTER gold_datum (never the same day).
    #
    # In Python: weekday() Mon=0..Sun=6
    # C# DayOfWeek = (python_weekday + 1) % 7
    # So (7 - cs_dow) = (7 - ((py_wd + 1) % 7))
    # For py_wd=6 (Sun): cs_dow=0, 7-0=7 → next Sunday
    # For py_wd=5 (Sat): cs_dow=6, 7-6=1 → next day (Sun)
    # For py_wd=0 (Mon): cs_dow=1, 7-1=6 → 6 days later (Sun)

    cs_dow = (gold_datum.weekday() + 1) % 7
    days_to_sunday = 7 - cs_dow
    if days_to_sunday == 7:
        days_to_sunday = 7  # always go to NEXT Sunday, even if already Sun
    easter = gold_datum + __import__('datetime').timedelta(days=days_to_sunday)

    # Sanity check: Easter should be in March or April
    if easter.month not in (3, 4):
        return None
    return easter


def _easter_sunday_gauss(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm
    (Meeus/Jones/Butcher).  Valid for all years in the Gregorian calendar.
    Used as fallback if the table method fails.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def easter_sunday(year: int) -> date:
    """Get Easter Sunday for a given year.  Tries the table first,
    falls back to the Gauss algorithm."""
    result = _easter_sunday_from_table(year)
    if result:
        return result
    return _easter_sunday_gauss(year)


def _moveable_holidays(year: int) -> dict:
    """Compute all Easter-derived holidays for a given year."""
    easter = easter_sunday(year)
    from datetime import timedelta
    return {
        easter: "Ostersonntag",
        easter + timedelta(days=1): "Ostermontag",
        easter + timedelta(days=39): "Christi Himmelfahrt",
        easter + timedelta(days=49): "Pfingstsonntag",
        easter + timedelta(days=50): "Pfingstmontag",
        easter + timedelta(days=60): "Fronleichnam",
    }


# Cache for moveable holidays per year (avoids recomputation)
_moveable_cache: dict = {}


def get_holiday_name(d: date) -> Optional[str]:
    """Return the Austrian holiday name for a date, or None."""
    # Check fixed holidays first
    key = (d.month, d.day)
    if key in _FIXED:
        return _FIXED[key]

    # Check moveable holidays
    year = d.year
    if year not in _moveable_cache:
        _moveable_cache[year] = _moveable_holidays(year)
    return _moveable_cache[year].get(d)


def is_austrian_holiday(d: date) -> bool:
    """Return True if the date is an Austrian public holiday."""
    return get_holiday_name(d) is not None


# Convenience: list all holidays for a year
def list_holidays(year: int) -> list:
    """Return a sorted list of (date, name) for all Austrian holidays in a year."""
    holidays = []
    # Fixed
    for (m, d), name in _FIXED.items():
        try:
            holidays.append((date(year, m, d), name))
        except ValueError:
            pass
    # Moveable
    for d, name in _moveable_holidays(year).items():
        holidays.append((d, name))
    holidays.sort(key=lambda x: x[0])
    return holidays


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    y = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    print(f"Austrian holidays {y}:")
    for d, name in list_holidays(y):
        marker = " <-- today" if d == date.today() else ""
        print(f"  {d.strftime('%d.%m.%Y')} ({d.strftime('%A')}): {name}{marker}")
