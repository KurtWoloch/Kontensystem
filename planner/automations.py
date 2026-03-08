"""
automations.py — Load and match task automations.

Automations are defined in data/automations.json and map task codes
or activity name prefixes to shell commands or URLs.
"""
import json
import os
import subprocess
import webbrowser
from typing import Optional, Dict, Any, List


AUTOMATIONS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "automations.json"
)


def load_automations(path: str = AUTOMATIONS_PATH) -> List[Dict[str, Any]]:
    """Load automations list from JSON config."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("automations", [])
    except (json.JSONDecodeError, OSError) as e:
        print(f"[AUTOMATIONS] Error loading {path}: {e}")
        return []


def find_automation(activity: str,
                    automations: List[Dict[str, Any]]
                    ) -> Optional[Dict[str, Any]]:
    """
    Find the first matching automation for an activity string.

    Match types:
      - 'code': matches if the 6-char task code at the end of the
        activity name equals the match value.
      - 'prefix': matches if the activity starts with the match value.
      - 'contains': matches if the match value appears anywhere in
        the activity name.
    """
    if not activity or not automations:
        return None

    # Extract trailing 6-char code if present
    parts = activity.rsplit(" ", 1)
    task_code = ""
    if len(parts) == 2 and len(parts[1]) == 6 and parts[1].isupper():
        task_code = parts[1]

    for auto in automations:
        match_val = auto.get("match", "")
        match_type = auto.get("match_type", "code")

        if match_type == "code" and task_code:
            if task_code == match_val:
                return auto
        elif match_type == "prefix":
            if activity.startswith(match_val):
                return auto
        elif match_type == "contains":
            if match_val in activity:
                return auto

    return None


def run_automation(auto: Dict[str, Any]) -> bool:
    """
    Execute an automation entry.

    Returns True if launched successfully, False on error.
    """
    auto_type = auto.get("type", "shell")

    try:
        if auto_type == "url":
            url = auto.get("url", "")
            if url:
                webbrowser.open(url)
                print(f"[AUTOMATIONS] Opened URL: {url}")
                return True
        elif auto_type == "shell":
            command = auto.get("command", "")
            if command:
                # Use subprocess.Popen to launch without blocking
                subprocess.Popen(
                    command,
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP,
                )
                print(f"[AUTOMATIONS] Launched: {command}")
                return True
    except Exception as e:
        print(f"[AUTOMATIONS] Error running automation: {e}")
        return False

    print("[AUTOMATIONS] No command/url found in automation entry.")
    return False
