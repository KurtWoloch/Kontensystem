"""
yaml_loader.py — Load schedule_exceptions.yaml and find today's overrides.

Returns a dict with applicable overrides for a given date:
  - dayTypeOverride: str or None ("Urlaubstag", "Bürotag", "Teleworking")
  - specialNote: str or None
  - earlyWorkStart: int or None (hours to shift Liste_Arbeit earlier)
  - addEvents: list of dicts
  - removeActivities: list of strings
  - adjustStartTimes: list of dicts
"""
import os
import sys
from datetime import date
from typing import Dict, Any, Optional

# PyYAML may not be installed — handle gracefully
try:
    import yaml
except ImportError:
    yaml = None

YAML_PATH = (
    r"C:\Users\kurt_\Betrieb\Kontenverwaltung"
    r"\Tagesplanung_AI\Tagesplanung\schedule_exceptions.yaml"
)


def load_exceptions_for_date(
    target_date: Optional[date] = None,
    path: str = YAML_PATH
) -> Dict[str, Any]:
    """Load YAML and return overrides for the target date.

    Returns a dict with keys:
      dayTypeOverride, specialNote, earlyWorkStart,
      addEvents, removeActivities, adjustStartTimes
    All default to None or empty list if not set.
    """
    result: Dict[str, Any] = {
        "dayTypeOverride": None,
        "specialNote": None,
        "earlyWorkStart": None,
        "addEvents": [],
        "removeActivities": [],
        "adjustStartTimes": [],
    }

    if target_date is None:
        target_date = date.today()

    if not os.path.exists(path):
        return result

    target_str = target_date.strftime("%Y-%m-%d")

    if yaml is None:
        # Fallback: simple line-based scan for the date
        return _parse_without_yaml(path, target_str, result)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"[YAML] Error loading {path}: {e}", file=sys.stderr)
        return result

    if not data or "exceptions" not in data:
        return result

    for entry in data["exceptions"]:
        entry_date = str(entry.get("date", "")).strip()
        if entry_date != target_str:
            continue

        # Found a matching entry
        if "dayTypeOverride" in entry:
            result["dayTypeOverride"] = entry["dayTypeOverride"]
        if "specialNote" in entry:
            result["specialNote"] = entry["specialNote"]
        if "earlyWorkStart" in entry:
            result["earlyWorkStart"] = int(entry["earlyWorkStart"])
        if "addEvents" in entry:
            result["addEvents"] = entry["addEvents"]
        if "removeActivities" in entry:
            result["removeActivities"] = entry["removeActivities"]
        if "adjustStartTimes" in entry:
            result["adjustStartTimes"] = entry["adjustStartTimes"]

        # Don't break — multiple entries for the same date are merged
        # (later entries overwrite earlier ones for scalar fields)

    return result


def _parse_without_yaml(
    path: str, target_str: str, result: Dict[str, Any]
) -> Dict[str, Any]:
    """Minimal fallback parser when PyYAML is not installed.

    Only extracts dayTypeOverride, specialNote, and earlyWorkStart.
    """
    import re
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return result

    in_target_block = False
    for line in lines:
        stripped = line.strip()

        # Detect date block start
        m = re.match(r'^-\s+date:\s*"?(\d{4}-\d{2}-\d{2})"?', stripped)
        if m:
            in_target_block = (m.group(1) == target_str)
            continue

        if not in_target_block:
            continue

        # New block starts with "- date:" → end current
        if stripped.startswith("- date:"):
            break

        # Extract fields
        m = re.match(r'dayTypeOverride:\s*"?([^"#]+)"?', stripped)
        if m:
            result["dayTypeOverride"] = m.group(1).strip()

        m = re.match(r'specialNote:\s*"?([^"#]+)"?', stripped)
        if m:
            result["specialNote"] = m.group(1).strip()

        m = re.match(r'earlyWorkStart:\s*(\d+)', stripped)
        if m:
            result["earlyWorkStart"] = int(m.group(1))

    return result
