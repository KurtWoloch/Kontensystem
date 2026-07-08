"""
holidays.py — Automatic Austrian public holiday detection.

Uses the elegant Anonymous Gregorian algorithm (Meeus/Jones/Butcher)
to compute Easter Sunday and derives all Austrian public holidays.
"""
from datetime import date, timedelta
from functools import lru_cache
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


@lru_cache(maxsize=16)
def easter_sunday(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm
    (Meeus/Jones/Butcher). Valid for all years in the Gregorian calendar (1583–∞).
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


@lru_cache(maxsize=16)
def _moveable_holidays(year: int) -> dict[date, str]:
    """Compute all Easter-derived Austrian holidays for a given year."""
    easter = easter_sunday(year)
    return {
        easter: "Ostersonntag",
        easter + timedelta(days=1): "Ostermontag",
        easter + timedelta(days=39): "Christi Himmelfahrt",
        easter + timedelta(days=49): "Pfingstsonntag",
        easter + timedelta(days=50): "Pfingstmontag",
        easter + timedelta(days=60): "Fronleichnam",
    }


def get_holiday_name(d: date) -> Optional[str]:
    """Return the Austrian holiday name for a date, or None."""
    # Check fixed holidays first
    key = (d.month, d.day)
    if key in _FIXED:
        return _FIXED[key]

    # Check moveable holidays
    return _moveable_holidays(d.year).get(d)


def is_austrian_holiday(d: date) -> bool:
    """Return True if the date is an Austrian public holiday."""
    return get_holiday_name(d) is not None


def list_holidays(year: int) -> list[tuple[date, str]]:
    """Return a sorted list of (date, name) for all Austrian holidays in a year."""
    holidays = []
    # Fixed
    for (m, d), name in _FIXED.items():
        try:
            holidays.append((date(year, m, d), name))
        except ValueError:
            pass  # Handles leap year edge cases if they ever appear in _FIXED
    # Moveable
    for d, name in _moveable_holidays(year).items():
        holidays.append((d, name))
    
    holidays.sort(key=lambda x: x[0])
    return holidays


if __name__ == "__main__":
    import sys
    # Keep output clean and correct for Windows terminal encoding
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    y = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    print(f"Austrian holidays {y}:")
    for d, name in list_holidays(y):
        marker = " <-- today" if d == date.today() else ""
        print(f"  {d.strftime('%d.%m.%Y')} ({d.strftime('%A')}): {name}{marker}")
