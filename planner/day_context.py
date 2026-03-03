"""
day_context.py — Day-type detection and condition evaluation.

Day type logic (from analysis):
  Bürotag     = Monday (0) or Wednesday (2), unless Feiertag/Urlaubstag
  Teleworking = Tuesday (1), Thursday (3), Friday (4), unless Feiertag/Urlaubstag
  Wochenende  = Saturday (5), Sunday (6)
  Putztag     = Tuesday (1) or Friday (4)
  BRZ_geplant = same as Bürotag
"""
from datetime import date
from typing import Dict


GERMAN_WEEKDAYS = {
    "Montag": 0,
    "Dienstag": 1,
    "Mittwoch": 2,
    "Donnerstag": 3,
    "Freitag": 4,
    "Samstag": 5,
    "Sonntag": 6,
}


class DayContext:
    """Holds all boolean flags that drive condition evaluation."""

    def __init__(self, weekday: int, is_feiertag: bool = False,
                 is_urlaubstag: bool = False):
        self.weekday = weekday          # 0=Mon … 6=Sun
        self.is_feiertag = is_feiertag
        self.is_urlaubstag = is_urlaubstag

        self.is_wochenende = weekday in (5, 6)
        self.is_burotag = (weekday in (0, 2)) and not (is_feiertag or is_urlaubstag)
        self.is_teleworking = (weekday in (1, 3, 4)) and not (is_feiertag or is_urlaubstag)
        self.is_putztag = weekday in (1, 4)   # Tuesday or Friday
        self.is_brz_geplant = self.is_burotag

        # Jause_zu_Hause: true when Urlaubstag OR Feiertag OR (not Monday AND not Tuesday)
        # From C# ActivityValidator.cs — auto-inferred, not user-set
        self.jause_zu_hause = (is_urlaubstag or is_feiertag or
                               weekday not in (0, 1))

    @classmethod
    def from_today(cls, is_feiertag: bool = False,
                   is_urlaubstag: bool = False) -> "DayContext":
        return cls(date.today().weekday(), is_feiertag, is_urlaubstag)

    def _eval_single_condition(self, token: str) -> bool:
        """Evaluate one comma-split token (may be negated with 'nicht' or '!')."""
        token = token.strip()
        if not token:
            return True

        # Handle negation prefix
        negated = False
        if token.startswith("nicht "):
            negated = True
            token = token[6:].strip()
        elif token.startswith("!"):
            negated = True
            token = token[1:].strip()

        result = self._positive_match(token)
        return (not result) if negated else result

    def _positive_match(self, token: str) -> bool:
        """Match a positive (non-negated) condition token."""
        if token in GERMAN_WEEKDAYS:
            return self.weekday == GERMAN_WEEKDAYS[token]
        if token == "Wochenende":
            return self.is_wochenende
        if token == "Bürotag":
            return self.is_burotag
        if token == "Teleworking":
            return self.is_teleworking
        if token == "Putztag":
            return self.is_putztag
        if token == "Feiertag":
            return self.is_feiertag
        if token == "Urlaubstag":
            return self.is_urlaubstag
        if token == "BRZ_geplant":
            return self.is_brz_geplant
        # Unknown → assume true (permissive for Iteration 1)
        return True

    def matches_weekdays(self, weekdays_str: str) -> bool:
        """Return True if this day matches the Weekdays field value.
        Empty string = always matches.
        Comma-separated list = matches if ANY token is true.
        """
        if not weekdays_str or not weekdays_str.strip():
            return True
        tokens = weekdays_str.split(",")
        return any(self._eval_single_condition(t) for t in tokens)

    def eval_dependency(self, dep_str: str) -> bool:
        """Evaluate the Dependencies field.
        May contain 'Planungsvariablen.X' or '!Planungsvariablen.X'.
        Multiple deps separated by commas — all must be true (AND logic).
        """
        if not dep_str or not dep_str.strip():
            return True

        # Dependencies look like complex C# expressions in a few edge cases;
        # handle the common pattern: [!]Planungsvariablen.VarName
        parts = dep_str.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            negated = False
            if part.startswith("!"):
                negated = True
                part = part[1:].strip()
            # Strip "Planungsvariablen." prefix if present
            if part.startswith("Planungsvariablen."):
                var_name = part[len("Planungsvariablen."):]
            else:
                var_name = part

            val = self._resolve_var(var_name)
            if negated:
                val = not val
            if not val:
                return False
        return True

    def _resolve_var(self, var_name: str) -> bool:
        """Map a variable name to its boolean value."""
        mapping: Dict[str, bool] = {
            "BRZ_geplant": self.is_brz_geplant,
            "Bürotag": self.is_burotag,
            "Teleworking": self.is_teleworking,
            "Wochenende": self.is_wochenende,
            "Putztag": self.is_putztag,
            "Feiertag": self.is_feiertag,
            "Urlaubstag": self.is_urlaubstag,
            "Jause_zu_Hause": self.jause_zu_hause,
        }
        return mapping.get(var_name, True)  # unknown vars → True (permissive)

    def describe(self) -> str:
        parts = []
        days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        parts.append(days[self.weekday])
        if self.is_burotag:
            parts.append("Bürotag")
        if self.is_teleworking:
            parts.append("Teleworking")
        if self.is_wochenende:
            parts.append("Wochenende")
        if self.is_putztag:
            parts.append("Putztag")
        if self.is_feiertag:
            parts.append("Feiertag")
        if self.is_urlaubstag:
            parts.append("Urlaubstag")
        return " | ".join(parts)
