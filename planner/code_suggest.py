"""
code_suggest.py — Auto-suggest 6-char task codes for activity names.

Builds a lookup from the master task list (JSONL) and planner CSV,
then provides fuzzy matching to suggest codes for unplanned activities.
"""
import json
import os
import re
from typing import Optional, List, Tuple


class CodeSuggestor:
    """Suggests 6-char task codes for activity names."""

    def __init__(self, data_dir: str, csv_path: str = ""):
        """Load the master task list and optionally the planner CSV.

        Args:
            data_dir:  Path to kontensystem/data/ (contains master_task_list_v4.jsonl)
            csv_path:  Path to Planungsaktivitaeten.csv (optional, for extra lookups)
        """
        # code → task name (for display)
        self._code_names: dict[str, str] = {}
        # normalized name → code  (exact match)
        self._name_to_code: dict[str, str] = {}
        # list of (prefix_lower, code, name) for prefix matching
        self._prefix_index: list[tuple[str, str, str]] = []

        self._data_dir = data_dir
        self._learned_path = os.path.join(data_dir, "learned_codes.csv")

        self._load_master_task_list(data_dir)
        self._load_learned_codes()
        if csv_path and os.path.exists(csv_path):
            self._load_csv(csv_path)

    def _load_master_task_list(self, data_dir: str):
        """Load codes from master_task_list_v4.jsonl (or v3 as fallback)."""
        for version in ("v4", "v3"):
            path = os.path.join(data_dir, f"master_task_list_{version}.jsonl")
            if os.path.exists(path):
                break
        else:
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                task = json.loads(line)
                name = task.get("name", "")
                code = task.get("code", "")
                if code and len(code) == 6 and name:
                    norm = self._normalize(name)
                    self._name_to_code[norm] = code
                    self._code_names[code] = name
                    self._prefix_index.append((norm, code, name))

        # Sort prefix index by name length descending (longer = more specific)
        self._prefix_index.sort(key=lambda x: len(x[0]), reverse=True)

        # Keyword aliases: map common unplanned activity patterns to codes.
        # These catch variations that don't match by name/prefix alone.
        self._keyword_aliases: list[tuple[list[str], str]] = [
            # Planner development work
            (["tagesplanung", "openclaw"], "KSPLEN"),
            (["tagesplaner", "openclaw"], "KSPLEN"),
            (["bugfixing", "tagesplanung"], "KSPLEN"),
            (["erweiterung", "tagesplanung"], "KSPLEN"),
            (["verbesserung", "tagesplanung"], "KSPLEN"),
            (["korrektur", "tagesplanung"], "KSPLEN"),
            (["modifizierung", "tagesplanung"], "KSPLEN"),
            # Moltbook / OpenClaw surfing
            (["moltbook"], "INOCMB"),
            (["openclaw", "memories"], "INOCMB"),
            (["openclaw", "moltbook"], "INOCMB"),
            # Radio scans
            (["scan", "radio"], "RASCRA"),
            # Andon / Thinking Frequencies
            (["andon"], "RAAFKO"),
            (["thinking", "frequencies"], "RAAFKO"),
            # Nacherfassung
            (["nacherfassung", "ablauf"], "KSPLNA"),
        ]

    def _load_csv(self, csv_path: str):
        """Extract additional name→code mappings from the planner CSV."""
        try:
            with open(csv_path, "r", encoding="windows-1252") as f:
                header = f.readline()
                for line in f:
                    parts = line.strip().split(";")
                    if len(parts) < 3:
                        continue
                    # CSV columns: Bezeichnung;(various);Code;...
                    # The activity name is col 0, code might be in the name
                    activity = parts[0].strip()
                    if not activity:
                        continue
                    # Check if the activity name itself ends with a 6-char code
                    code = self._extract_code(activity)
                    if code:
                        base_name = activity[:-(len(code))].strip()
                        if base_name:
                            norm = self._normalize(base_name)
                            if norm not in self._name_to_code:
                                self._name_to_code[norm] = code
                                self._prefix_index.append((norm, code, base_name))
        except Exception:
            pass  # CSV is optional; don't crash if unreadable

    def _load_learned_codes(self):
        """Load dynamically learned code→name mappings from learned_codes.csv.

        File format: CODE;Activity Name (semicolon-delimited, UTF-8)
        """
        if not os.path.exists(self._learned_path):
            return
        try:
            with open(self._learned_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(";", 1)
                    if len(parts) != 2:
                        continue
                    code = parts[0].strip()
                    name = parts[1].strip()
                    if code and len(code) == 6 and code.isupper() and name:
                        self._register(code, name)
        except Exception:
            pass  # Don't crash if file is malformed

    def _register(self, code: str, name: str):
        """Register a code→name mapping in all indexes."""
        norm = self._normalize(name)
        if code not in self._code_names:
            self._code_names[code] = name
        if norm not in self._name_to_code:
            self._name_to_code[norm] = code
            self._prefix_index.append((norm, code, name))

    def learn(self, activity: str):
        """Learn a new code→name mapping from a logged activity.

        If the activity ends with a 6-char code that isn't already known,
        saves it to learned_codes.csv for future sessions.
        """
        code = self._extract_code(activity)
        if not code:
            return
        base_name = activity[:-(len(code))].strip()
        if not base_name:
            return
        # Already known? Skip
        norm = self._normalize(base_name)
        if norm in self._name_to_code and self._name_to_code[norm] == code:
            return
        # Register in memory
        self._register(code, base_name)
        # Persist to file
        try:
            os.makedirs(os.path.dirname(self._learned_path), exist_ok=True)
            with open(self._learned_path, "a", encoding="utf-8") as f:
                f.write(f"{code};{base_name}\n")
        except Exception:
            pass  # Best-effort persistence

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize for matching: lowercase, collapse whitespace, strip punctuation edges."""
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        # Remove trailing punctuation like periods, commas
        text = text.rstrip(".,;:!? ")
        return text

    @staticmethod
    def _extract_code(activity: str) -> Optional[str]:
        """Extract a 6-char uppercase code from the end of an activity name."""
        parts = activity.rstrip().rsplit(None, 1)
        if len(parts) == 2:
            candidate = parts[1]
            if len(candidate) == 6 and candidate.isupper() and candidate.isalpha():
                return candidate
        return None

    def suggest(self, activity: str) -> List[Tuple[str, str, str]]:
        """Suggest codes for an activity name.

        Returns a list of (code, match_type, matched_name) tuples,
        best match first. Returns empty list if no match found.

        match_type is one of: "exact", "prefix", "contains"
        """
        if not activity or not activity.strip():
            return []

        # If the activity already has a code, just validate it
        existing = self._extract_code(activity)
        if existing and existing in self._code_names:
            return [(existing, "existing", self._code_names[existing])]

        norm = self._normalize(activity)
        # Also try without trailing (Fs.) marker for interruptions
        norm_stripped = re.sub(r"\s*\(fs\.\)\s*$", "", norm, flags=re.IGNORECASE)

        results = []
        seen_codes = set()

        # Strategy 1: Exact match
        for n in (norm, norm_stripped):
            if n in self._name_to_code:
                code = self._name_to_code[n]
                if code not in seen_codes:
                    results.append((code, "exact", self._code_names.get(code, "")))
                    seen_codes.add(code)

        # Strategy 2: Input starts with a known task name (or vice versa)
        for prefix_norm, code, name in self._prefix_index:
            if code in seen_codes:
                continue
            if norm.startswith(prefix_norm) or prefix_norm.startswith(norm):
                results.append((code, "prefix", name))
                seen_codes.add(code)
                if len(results) >= 5:
                    break

        # Strategy 3: Keyword alias patterns (curated)
        if not results:
            for keywords, code in self._keyword_aliases:
                if code in seen_codes:
                    continue
                if all(kw in norm for kw in keywords):
                    name = self._code_names.get(code, code)
                    results.append((code, "alias", name))
                    seen_codes.add(code)
                    break  # aliases are high confidence, take first match

        # Strategy 4: Keyword containment (less precise)
        if len(results) < 3:
            # Extract significant words (>3 chars)
            words = [w for w in norm.split() if len(w) > 3]
            for prefix_norm, code, name in self._prefix_index:
                if code in seen_codes:
                    continue
                if any(w in prefix_norm for w in words):
                    results.append((code, "contains", name))
                    seen_codes.add(code)
                    if len(results) >= 5:
                        break

        return results

    def get_best(self, activity: str) -> Optional[Tuple[str, str]]:
        """Return the single best (code, matched_name) or None."""
        suggestions = self.suggest(activity)
        if suggestions:
            return (suggestions[0][0], suggestions[0][2])
        return None
