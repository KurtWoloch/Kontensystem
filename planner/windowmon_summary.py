# -*- coding: utf-8 -*-
"""
windowmon_summary.py — End-of-day activity summary from windowmon JSONL logs.

Reads a day's windowmon log, applies AutoDetect rules to classify window
titles into activities/accounts, aggregates fragmented entries into total
time per activity, and outputs a summary suitable for Aufwandserfassung.

Usage:
    py windowmon_summary.py [--date YYYY-MM-DD] [--detail] [--idle]

Options:
    --date    Target date (default: today)
    --detail  Show individual classified blocks (not just totals)
    --idle    Show idle/Off-PC periods separately
    --planner-log PATH  Cross-reference with planner log for Off-PC activity names

The AutoDetect rules are derived from the alignment report analysis
(alignment-report-2026-03-10.md) and Kurt's windowlog_corrector.py rules.
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════ #
#  Confidence Store                                                          #
#  Lazy-loading singleton for confidence_learner data.                       #
# ═══════════════════════════════════════════════════════════════════════════ #

class ConfidenceStore:
    """Lazy-loading confidence store from confidence_learner data."""

    _instance = None
    _data = None
    _thresholds = None   # Per-title confidence threshold overrides (#25)

    # Minimum confidence to use a store suggestion
    MIN_CONFIDENCE = 0.50
    # If p_same_before AND p_same_after are above this, the title is a
    # "Durchreicher" (noise) and the previous activity should continue.
    DURCHREICHER_THRESHOLD = 0.85

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if ConfidenceStore._data is None:
            self._load()

    def _load(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data"
        )
        store_path = os.path.join(data_dir, "confidence_store.json")
        if os.path.exists(store_path):
            try:
                with open(store_path, "r", encoding="utf-8") as f:
                    ConfidenceStore._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                ConfidenceStore._data = {}
        else:
            ConfidenceStore._data = {}

        # Load per-title confidence threshold overrides (Issue #25)
        thresholds_path = os.path.join(data_dir, "confidence_thresholds.json")
        if os.path.exists(thresholds_path):
            try:
                with open(thresholds_path, "r", encoding="utf-8") as f:
                    ConfidenceStore._thresholds = json.load(f).get("overrides", [])
            except (json.JSONDecodeError, IOError):
                ConfidenceStore._thresholds = []
        else:
            ConfidenceStore._thresholds = []

    def _match_threshold_override(self, process, norm_title):
        """Check if a per-title threshold override applies (Issue #25).

        Returns the matching override dict, or None.
        """
        if not ConfidenceStore._thresholds:
            return None

        for ov in ConfidenceStore._thresholds:
            # Process must match (case-insensitive)
            ov_proc = ov.get("process", "")
            if ov_proc and ov_proc.lower() != (process or "").lower():
                continue

            # Check exclude_contains first — if the exclusion substring
            # is present, this override does NOT apply
            exclude = ov.get("exclude_contains")
            if exclude and exclude in norm_title:
                continue

            # Match pattern against normalized title
            pattern = ov.get("pattern", "")
            match_type = ov.get("match_type", "exact")

            matched = False
            if match_type == "exact":
                matched = (norm_title == pattern)
            elif match_type == "prefix":
                matched = norm_title.startswith(pattern)
            elif match_type == "contains":
                matched = (pattern in norm_title)
            elif match_type == "glob":
                import fnmatch
                matched = fnmatch.fnmatch(norm_title, pattern)

            if matched:
                return ov

        return None

    @staticmethod
    def _extract_account(activity):
        """Extract account prefix from task code in activity name."""
        code_match = re.search(r'\s([A-ZÄÖÜß]{4,6})\s*$', activity)
        if code_match:
            return code_match.group(1)[:2]
        return "_UNCLASSIFIABLE"

    def lookup(self, process, title):
        """Look up a normalized title in the confidence store.

        Returns (account, activity, confidence, is_durchreicher) or None.

        is_durchreicher=True means the title is noise and the previous
        activity should be continued rather than using this suggestion.
        """
        norm_title = self._normalize_title(process, title)

        # ── Per-title threshold overrides (Issue #25) ──────────────────
        override = self._match_threshold_override(process, norm_title)

        # force_activity: bypass the store entirely
        if override and "force_activity" in override:
            forced = override["force_activity"]
            account = self._extract_account(forced)
            return (account, forced, 1.0, False)

        # ── Normal store lookup ────────────────────────────────────────
        key = f"{process}||{norm_title}"

        entry = ConfidenceStore._data.get(key)
        if entry is None:
            return None

        confidences = entry.get("confidences", {})
        if not confidences:
            return None

        # Find top activity
        top_activity = max(confidences, key=confidences.get)
        top_conf = confidences[top_activity]

        # Check if this is a Durchreicher (noise title) BEFORE confidence cutoff.
        # A Durchreicher has high stability (same activity before and after)
        # regardless of how low its top confidence is — it's noise either way.
        p_before = entry.get("p_same_before", 1.0)
        p_after = entry.get("p_same_after", 1.0)
        is_durchreicher = (p_before >= self.DURCHREICHER_THRESHOLD and
                           p_after >= self.DURCHREICHER_THRESHOLD and
                           top_conf < 0.70)

        # Determine effective minimum confidence:
        # use per-title override if available, otherwise global MIN_CONFIDENCE
        has_override = override and "min_confidence" in override
        effective_min = override["min_confidence"] if has_override else self.MIN_CONFIDENCE

        # If confidence is too low and it's NOT a Durchreicher, reject
        if top_conf < effective_min and not is_durchreicher:
            return None

        # When a per-title override explicitly lowers the threshold and the
        # confidence passes that threshold, suppress Durchreicher status.
        # The override expresses that this title IS a real activity, not noise.
        if has_override and top_conf >= effective_min and is_durchreicher:
            is_durchreicher = False

        account = self._extract_account(top_activity)
        return (account, top_activity, top_conf, is_durchreicher)

    @staticmethod
    def _normalize_title(process, title):
        """Same normalization as confidence_learner.py."""
        # Remove zero-width spaces that Edge inserts between "Microsoft" and "Edge"
        result = title.replace("\u200b", "")

        if process and process.lower() == "msedge.exe":
            result = re.sub(
                r'\s+und\s+\d+\s+weitere\s+Seite[n]?\s+-\s+Pers\u00f6nlich\s+[\u2013-]\s+Microsoft\s*Edge\s*$',
                '', result, flags=re.IGNORECASE)
            result = re.sub(
                r'\s+-\s+Pers\u00f6nlich\s+[\u2013-]\s+Microsoft\s*Edge\s*$',
                '', result, flags=re.IGNORECASE)

        if process and process.lower() == "winamp.exe":
            result = "(Winamp playback)"

        result = re.sub(r'\s+\(Keine\s+R\u00fcckmeldung\)\s*$', '', result,
                        flags=re.IGNORECASE)
        result = result.rstrip()
        return result

    # ── Session-level learning ──────────────────────────────────────────

    # Processes/titles to skip (same as confidence_learner.py)
    _SKIP_TITLES    = {"", "Programmumschaltung"}
    _SKIP_PROCESSES = {"ShellExperienceHost.exe", "SearchApp.exe"}

    _EMA_OLD        = 0.80
    _EMA_NEW        = 0.20
    _PRUNE_THRESHOLD = 0.01

    @classmethod
    def update_from_import(cls, entries, blocks):
        """Update the confidence store from just-imported timeline blocks.

        Parameters
        ----------
        entries : list[TLEntry]
            All timeline entries (already filtered; planner_idle excluded by
            TimelineModel._rebuild).
        blocks : list[TLBlock]
            The importable blocks (same list iterated in _import()).
            Only blocks that were actually imported (account != "??"/"IDLE",
            not already logged) should be passed.
        """
        if cls._data is None:
            cls.get()  # trigger _load via __init__
        store = cls._data

        for b in blocks:
            activity = b.activity
            if not activity:
                continue

            # Collect (process, title, duration_seconds) for each entry in block
            title_secs: dict = {}  # key: (process, norm_title) → seconds

            for i in range(b.start_idx, min(b.end_idx + 1, len(entries))):
                e = entries[i]

                # Skip synthetic idle markers (planner_idle already excluded
                # by _rebuild, but guard against future changes)
                if not e.process and not e.title:
                    continue

                proc  = e.process or ""
                title = e.title  or ""

                # Skip list (mirrors confidence_learner.py)
                if title in cls._SKIP_TITLES:
                    continue
                if proc in cls._SKIP_PROCESSES:
                    continue

                norm_title = cls._normalize_title(proc, title)
                if not norm_title:
                    continue

                # Duration: difference to next entry timestamp (in same block)
                if i + 1 < len(entries):
                    dur = (entries[i + 1].ts - e.ts).total_seconds()
                else:
                    dur = 60.0  # last entry: assume 60 s
                if dur <= 0:
                    dur = 1.0

                key = (proc, norm_title)
                title_secs[key] = title_secs.get(key, 0.0) + dur

            if not title_secs:
                continue

            total_secs = sum(title_secs.values())
            if total_secs <= 0:
                continue

            # Build import_conf: time-weighted fraction per (process, title)
            import_conf: dict = {}  # store_key → fraction
            for (proc, norm_title), secs in title_secs.items():
                store_key = f"{proc}||{norm_title}"
                import_conf[store_key] = secs / total_secs

            # EMA-update each store key
            for store_key, imp_val in import_conf.items():
                if store_key in store:
                    entry = store[store_key]
                    old_conf = entry.get("confidences", {})

                    all_activities = set(old_conf.keys()) | {activity}
                    new_conf = {}
                    for act in all_activities:
                        old_val = old_conf.get(act, 0.0)
                        i_val   = imp_val if act == activity else 0.0
                        new_conf[act] = cls._EMA_OLD * old_val + cls._EMA_NEW * i_val

                    # Prune + normalize
                    new_conf = {a: v for a, v in new_conf.items()
                                if v >= cls._PRUNE_THRESHOLD}
                    conf_total = sum(new_conf.values())
                    if conf_total > 0:
                        new_conf = {a: v / conf_total for a, v in new_conf.items()}

                    entry["confidences"] = new_conf
                else:
                    # New entry: use import confidence directly
                    new_conf = {activity: imp_val}
                    conf_total = sum(new_conf.values())
                    if conf_total > 0:
                        new_conf = {a: v / conf_total for a, v in new_conf.items()}
                    store[store_key] = {
                        "confidences": new_conf,
                        "p_same_before": 1.0,
                        "p_same_after":  1.0,
                    }

    @classmethod
    def save(cls):
        """Persist the in-memory confidence store to confidence_store.json."""
        if cls._data is None:
            return  # nothing loaded, nothing to save
        store_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "confidence_store.json"
        )
        sorted_store = dict(sorted(cls._data.items()))
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(sorted_store, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════ #
#  Low-Accuracy Overridable Rules                                            #
#  For these (account, activity) pairs the confidence store is preferred     #
#  when it has a match.  Based on rule_accuracy.py analysis over             #
#  2026-03-03 to 2026-03-28.                                                 #
# ═══════════════════════════════════════════════════════════════════════════ #

LOW_ACCURACY_OVERRIDABLE = {
    ("KS", "Erfassung Ablauf KSPLEA"),           # 1.3% accuracy, 18h
    ("KS", "Diskussion OpenClaw KSPLEN"),         # 4.4% accuracy, 34h
    ("LE", "Bearb. Essensplan LEEPEP"),           # 6.0% accuracy, 16h
    ("IN", "div. Surfen INSUSU"),                 # 3.9% accuracy, 13h
    ("RA", "Surfen Andon FM RAAFSU"),             # 4.9% accuracy, 11h
    ("RA", "Ansehen YouTube-Videos RAYTYT"),       # 20.2% accuracy, 9.5h
    ("LE", "Bearb. Essensdatenbank (Access) LEEPEP"),  # generic Access
    ("RA", "Surfen X RAAFKO"),                    # generic X browsing
    ("IN", "Surfen X (Timeline) INSUXX"),         # 8.8% accuracy, 2.4h
    ("IN", "Analysen in Arena AI INSUAI"),        # 1.8% accuracy, 3.6h
    ("RW", "Anhören Musik (Winamp) RWMPMP"),      # 0% accuracy, 1.8h
    ("RW", "Andon FM Scraper RAAFAN"),            # 0% accuracy (background)
    ("RW", "Anhören Radiosender (Live365) RWMPMP"),  # generic Live365
    ("RW", "Anhören Thinking Frequencies (Live365) RAAFKO"),  # 0% accuracy
    ("PC", "Bearbeitung in VS Code PCOCIN"),      # 0% accuracy, 2.5h
    ("LE", "Bearb. Essensprotokoll LEEPEP"),      # 0% accuracy, 1h
    ("MU", "Bearb. Ohrwürmer-Listen RWOWTT"),     # 0% accuracy, 2.7h
    ("IN", "Bearbeitung Mails INMBMB"),           # 0.3% accuracy, 1.7h
    ("KS", "Nacherfassung (Windowlog) KSPLNA"),   # 0% accuracy, 2.4h
    ("RA", "Untersuchung AI DJ Breaks RAAFAN"),   # 0% accuracy
    ("IN", "Diskussion ChatGPT RAAFDI"),          # generic ChatGPT
    ("RA", "Bearb. Library Andon FM RAAFAN"),     # generic Excel rule
    ("RW", "Anhören Radiosender / Radio Würmchen / Tonträger / Ohrwürmer RWMPMP"),  # 3.5%
    ("RA", "Anhören Grok'n Roll (Live365) RAAFSU"),  # background
    ("LE", "Off-PC (unbekannt)"),                 # generic Off-PC
    ("RW", "Radio Würmchen (ngrok) RWMPMP"),      # background process
    ("IN", "Surfen Moltbook INOCMB"),             # sometimes background
    ("RW", "Bearb. Radio-Dateien RAAFSU"),        # generic notepad rule
    ("KS", "Bearb. Planer-Dateien KSPLEN"),       # 0% accuracy
    ("LE", "Bearb. Essensplan (gegessen, zu essen, Start Korrekturlauf) LEEPEP"),  # specific but wrong
    ("GE", "Blutdruck messen GEBMBM"),            # 32% (often left open)
    ("FI", "Bearbeitung Börsenkurse / Aktienhandel FIAKBK"),  # 31% (includes Fs.)
    ("RA", "Untersuchung Rotation Andon FM / OpenAIR RAAFAN"),  # 26%
}

# ═══════════════════════════════════════════════════════════════════════════ #
#  AutoDetect Rules                                                          #
#  Map window titles/processes to account codes + activity names.            #
#  Order matters: first match wins.                                          #
# ═══════════════════════════════════════════════════════════════════════════ #

def _title_contains(title: str, *keywords: str) -> bool:
    """Case-insensitive check if title contains ALL keywords."""
    tl = title.lower()
    return all(kw.lower() in tl for kw in keywords)


def _title_contains_any(title: str, *keywords: str) -> bool:
    """Case-insensitive check if title contains ANY keyword."""
    tl = title.lower()
    return any(kw.lower() in tl for kw in keywords)


# Each rule: (match_fn, account, activity)
# match_fn receives (title, process, browser)
# ── Radio Würmchen title parser ───────────────────────────────────────── #
# Radio Würmchen window titles encode scan targets like:
#   "Radio Würmchen 26.2.20 - Scan Kronehit 2024"
#   "Radio Würmchen 26.2.20 - Scan Radio Arabella 2023"
# Extract the scan target for precise classification.

_SCAN_PATTERNS = re.compile(
    r"(?:Radio\s+W[üu]rmchen[^-]*-\s*)(Scan\s+.+?)(?:\s+\d{4}\s*$|\s*$)",
    re.IGNORECASE,
)


def _parse_radio_wuermchen_title(title: str) -> Optional[str]:
    """Extract scan target from Radio Würmchen window title.

    Returns e.g. "Scan Kronehit" or None if no scan target found.
    """
    m = _SCAN_PATTERNS.search(title)
    if m:
        return m.group(1).strip()
    return None


# ── Explorer folder → account mapping ────────────────────────────────── #
# Folder names in Explorer titles that indicate a specific account.
# Used both as standalone classification and as confirmation signal
# for continuing the previous activity.

_EXPLORER_FOLDER_ACCOUNTS = {
    "kontensystem": "KS",
    "kontenverwaltung": "KS",
    "betrieb": "KS",
    "tagesplanung": "KS",
    "planner": "KS",
    "logs": "KS",
    "lebenserhaltung": "LE",
    "essensplan": "LE",
    "radio": "RW",
    "würmchen": "RW",
    "wuermchen": "RW",
    "radio fernsehen": "RA",
    "ohrwürmer": "MU",
    "ohrwuermer": "MU",
    "karaoke": "MU",
    "gesundheit": "GE",
    "papa": "PA",
    "finanzen": "FI",
    "wohnung": "WF",
}


def _explorer_folder_account(title: str) -> Optional[str]:
    """Derive account code from Explorer folder name in window title.

    Returns 2-char account code or None.
    """
    tl = title.lower()
    for folder, account in _EXPLORER_FOLDER_ACCOUNTS.items():
        if folder in tl:
            return account
    return None


AUTODETECT_RULES = [
    # ── Planner idle (Off-PC markers) ──────────────────────────────────
    (lambda t, p, b: p == "planner_idle",
     "IDLE", "Off-PC"),

    # ── Planner dialog with activity in title ──────────────────────────
    # When a dialog like "Aufgabe erledigt — WC LEMTWC" is left open
    # during Off-PC, extract the activity part after the em-dash.
    # This rule MUST come before the generic dialog rule below.
    (lambda t, p, b: p == "python.exe" and " \u2014 " in t and
     _title_contains_any(t, "Aufgabe erledigt", "Eintrag bearbeiten",
                         "Ungeplante Aktivit\u00e4t", "Vorgezogene Aktivit\u00e4t",
                         "Aufgabe unterbrechen"),
     "_PLANNER_DIALOG_ACTIVITY", ""),  # special: extract from title

    # ── Planner app — distinguish phantom vs real usage ────────────────
    # "Aufgabe erledigt" or "Eintrag bearbeiten" dialogs WITHOUT activity
    # in title (short focus = phantom click, or legacy title format)
    (lambda t, p, b: p == "python.exe" and
     _title_contains_any(t, "Aufgabe erledigt", "Eintrag bearbeiten",
                         "Ungeplante Aktivit\u00e4t"),
     "KS", "Erfassung Ablauf KSPLEA"),

    # Planner Off-PC title → use activity from title
    (lambda t, p, b: p == "python.exe" and "Off-PC" in t and
     "Tagesplanung" in t,
     "_PLANNER_OFFPC", ""),  # special: extract activity from title

    # Planner dialogs: Nacherfassung-specific → KSPLNA
    (lambda t, p, b: p == "python.exe" and
     _title_contains_any(t, "Nacherfassung aus windowmon",
                          "Timeline Nacherfassung",
                          "Vorschlag bearbeiten",
                          "Block reklassifizieren",
                          "Zusammengefasst",
                          "Import bestätigen", "Import abgeschlossen"),
     "KS", "Nacherfassung Ablauf KSPLNA"),

    # ── CMOL-FPGA Placer (Learner: 100%, 21x) ────────────────────────
    (lambda t, p, b: p == "python.exe" and
     _title_contains(t, "CMOL-FPGA Placer"),
     "CS", "Spielen Kreuzungs-FGPA CSEXKF"),

    # Planner dialogs: other (Tagesbericht, etc.) → KSPLEA
    (lambda t, p, b: p == "python.exe" and
     _title_contains_any(t, "Tagesbericht",
                          "Ungespeicherte", "windowmon "),
     "KS", "Erfassung Ablauf KSPLEA"),

    # Planner started from cmd
    (lambda t, p, b: p == "cmd.exe" and
     _title_contains(t, "main.py"),
     "KS", "Erfassung Ablauf KSPLEA"),

    # Planner main window
    (lambda t, p, b: p == "python.exe" and
     _title_contains_any(t, "Tagesplanung", "Reaktiver Planer"),
     "KS", "Erfassung Ablauf KSPLEA"),

    # ── Old Window Logger ──────────────────────────────────────────────
    # When Window Logger is in foreground, Kurt uses it as "idle" signal:
    # it means the PREVIOUS activity is still running (typically off-PC).
    # Short focus (< few seconds) = just selecting an activity.
    # Long focus = genuine off-PC / andere Aktivität.
    (lambda t, p, b: p == "Window logger.exe",
     "_WINLOGGER", "andere Aktivitaet (Window Logger idle)"),

    # ── Radio Würmchen — with scan target extraction ──────────────────
    # Parse "Scan Kronehit", "Scan Radio Arabella" etc. from window title.
    # Falls back to generic "Radio Würmchen" if no scan target found.
    (lambda t, p, b: p == "Radio Würmchen.exe" or
     _title_contains(t, "Radio Würmchen") or
     _title_contains(t, "Radio Wuermchen"),
     "_RADIO_WUERMCHEN", ""),  # special: extract scan target from title

    (lambda t, p, b: _title_contains(t, "Backlink Broadcast") or
     _title_contains(t, "Andon FM"),
     "RA", "Surfen Andon FM RAAFSU"),

    # ── Live365: specific stations before generic rule ────────────────
    (lambda t, p, b: b and _title_contains(t, "Grok'n Roll"),
     "RA", "Anhören Grok'n Roll (Live365) RAAFSU"),

    (lambda t, p, b: b and _title_contains(t, "Thinking Frequencies"),
     "RW", "Anhören Thinking Frequencies (Live365) RAAFKO"),

    (lambda t, p, b: _title_contains(t, "Live365") and
     p not in ("Live365Scraper.exe",),
     "RW", "Anhören Radiosender (Live365) RWMPMP"),

    (lambda t, p, b: p == "Live365Scraper.exe",
     "RW", "Andon FM Scraper RAAFAN"),

    (lambda t, p, b: p.lower() == "winamp.exe",
     "RW", "Anhören Musik (Winamp) RWMPMP"),

    # ── Arena AI ──────────────────────────────────────────────────────
    (lambda t, p, b: _title_contains_any(t, "Arena AI", "arena.ai",
                                          "artificialanalysis") or
     (b and _title_contains(t, "Arena") and
      _title_contains_any(t, "Benchmark", "Compare", "Leaderboard",
                           "LLM")),
     "IN", "Analysen in Arena AI INSUAI"),

    # ── AI Generated DJ Break (Grok'n Roll analysis page) ────────────
    (lambda t, p, b: b and _title_contains(t, "DJ Break"),
     "RA", "Untersuchung AI DJ Breaks RAAFAN"),

    # ── ChatGPT ───────────────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains_any(t, "ChatGPT", "chatgpt.com"),
     "IN", "Diskussion ChatGPT RAAFDI"),

    # ── YouTube ───────────────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains(t, "YouTube"),
     "RA", "Ansehen YouTube-Videos RAYTYT"),

    # ── Social Media / X — specific before generic ────────────────────
    # Tweet intents with specific recipients (from URL in title)
    (lambda t, p, b: b and _title_contains(t, "grok_androll"),
     "RA", "Tweet an Grok'n Roll RWMPAR"),

    (lambda t, p, b: b and _title_contains(t, "open_air_radio"),
     "RA", "Tweet an OpenAIR Radio RWMPAR"),

    (lambda t, p, b: b and _title_contains(t, "ThinkingFreq"),
     "RA", "Tweet an Thinking Frequencies RWMPAR"),

    (lambda t, p, b: b and _title_contains(t, "BacklinkRadio"),
     "RA", "Tweet an Backlink Broadcast RWMPAR"),

    # Generic tweet intent (unknown recipient)
    (lambda t, p, b: b and _title_contains(t, "x.com/intent"),
     "RA", "Tweet an Radiostation RWMPAR"),

    # X/Twitter: Home timeline → generic browsing
    (lambda t, p, b: b and _title_contains(t, "Home / X"),
     "IN", "Surfen X (Timeline) INSUXX"),

    # X/Twitter: everything else (DMs, notifications, profiles) →
    # primarily radio station conversations (Andrew Pappas etc.)
    (lambda t, p, b: b and _title_contains_any(t, "/ X", "twitter.com",
                                                 "x.com"),
     "RA", "Surfen X RAAFKO"),

    (lambda t, p, b: b and _title_contains(t, "moltbook"),
     "IN", "Surfen Moltbook INOCMB"),

    # ── OpenClaw ──────────────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains(t, "OpenClaw"),
     "KS", "Diskussion OpenClaw KSPLEN"),

    # ── Access DB — known vs unknown ──────────────────────────────────
    # Known: Essensplan, Kontensystem
    (lambda t, p, b: p.lower() == "msaccess.exe" and
     _title_contains_any(t, "Essensplan", "Speiseplan", "EP "),
     "LE", "Bearb. Essensdatenbank (Access) LEEPEP"),

    (lambda t, p, b: p.lower() == "msaccess.exe" and
     _title_contains_any(t, "Kontensystem", "Konten"),
     "KS", "Bearb. Kontensystem (Access) KSAAKO"),

    # Unknown Access DB → almost always Essensplan
    # Same name as Notepad Essensplan rule so adjacent blocks merge
    (lambda t, p, b: p.lower() == "msaccess.exe",
     "LE", "Bearb. Essensplan LEEPEP"),

    # ── Notepad — named vs unnamed ────────────────────────────────────
    (lambda t, p, b: p == "notepad.exe" and
     _title_contains_any(t, "Essensplan", "Speiseplan", "Einkaufsliste",
                          "Speisekarte", "offene Nachbearbeitung von Essensdatenbank"),
     "LE", "Bearb. Essensplan LEEPEP"),

    # Notepad: Windowlog.txt → Window Logger (= Nacherfassung context)
    (lambda t, p, b: p == "notepad.exe" and
     _title_contains(t, "Windowlog"),
     "KS", "Nacherfassung (Windowlog) KSPLNA"),

    # Notepad: Access DB temp files (~Versuch*, ~Auswertung*, ~Vergleich*)
    # These are auto-generated by the Essensplan Access tools
    (lambda t, p, b: p == "notepad.exe" and
     re.search(r"~(?:Versuch|Auswertung|Vergleich)", t) is not None,
     "LE", "Bearb. Essensplan LEEPEP"),

    # ── Notepad: Learner-derived rules (2026-03-28) ─────────────────────
    # Scan Grok'n Roll analysis files
    (lambda t, p, b: p == "notepad.exe" and
     _title_contains(t, "Scan Grok'n Roll"),
     "RA", "Analyse Grok'n Roll RWPLAF"),

    # Papa's Pflege task files
    (lambda t, p, b: p == "notepad.exe" and
     _title_contains(t, "Aufgaben zu Papa"),
     "PA", "Bearbeitung Aufgaben zu Papa's Pflege (10' +) PATATA"),

    # Notepad: Andon FM / Radio files
    (lambda t, p, b: p == "notepad.exe" and
     _title_contains_any(t, "Andon FM", "DJ Break", "Prompts for adjusting",
                          "charts_in_library", "wishlist"),
     "RW", "Bearb. Radio-Dateien RAAFSU"),

    # Notepad: Ohrwürmer / singbare Titel
    (lambda t, p, b: p == "notepad.exe" and
     _title_contains_any(t, "Ohrwürmer", "Ohrwuermer", "singbar"),
     "MU", "Bearb. Ohrwürmer-Listen RWOWTT"),

    # Notepad: Essensprotokoll / Kalkulation
    (lambda t, p, b: p == "notepad.exe" and
     _title_contains_any(t, "Protokoll", "Kalkulation", "Mohnnudeln",
                          "offene Nachbearbeitung"),
     "LE", "Bearb. Essensprotokoll LEEPEP"),

    # Notepad: Python/config/json files (planner development context)
    (lambda t, p, b: p == "notepad.exe" and
     re.search(r"\.(py|json|jsonl|bat)\s*-?\s*Editor", t) is not None,
     "KS", "Bearb. Planer-Dateien KSPLEN"),

    # Notepad: genuinely unnamed file (only "Unbenannt - Editor" or bare "Editor")
    (lambda t, p, b: p == "notepad.exe" and
     (t.strip() in ("Editor", "Suchen") or
      _title_contains_any(t, "Unbenannt", "Untitled")),
     "_UNCLASSIFIABLE", "Bearb. unbenannte Datei"),

    # ── VS Code / Code editing ────────────────────────────────────────
    (lambda t, p, b: p.lower() in ("code.exe", "code - insiders.exe") and
     _title_contains_any(t, "kontensystem", "planner", "Tagesplanung"),
     "KS", "Entwicklung Tagesplanung (VS Code) KSPLEN"),

    (lambda t, p, b: p.lower() in ("code.exe", "code - insiders.exe") and
     _title_contains_any(t, "radio", "würmchen", "wuermchen", "andon",
                          "scraper"),
     "RW", "Entwicklung Radio (VS Code) RWKIAN"),

    (lambda t, p, b: p.lower() in ("code.exe", "code - insiders.exe"),
     "PC", "Bearbeitung in VS Code PCOCIN"),

    # ── Excel — file-specific classification ─────────────────────────
    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "Library Andon FM"),
     "RA", "Bearb. Library Andon FM RAAFAN"),

    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "Statistik_heute"),
     "RA", "Untersuchung Rotation Andon FM / OpenAIR RAAFAN"),

    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "Blutdruck"),
     "GE", "Blutdruck messen GEBMBM"),

    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "Planungsaktivitaeten"),
     "KS", "Bearbeitung Planungsaktivitäten KSPLEN"),

    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "duplicate_codes"),
     "KS", "Review Duplicate Codes KSPLEN"),

    # ── Excel: Learner-derived rules (2026-03-28) ─────────────────────
    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "Aktienuntersuchung"),
     "FI", "Bearbeitung Börsenkurse / Aktienhandel FIAKBK"),

    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "Liste Fahrten mit E-Scootern"),
     "FZ", "Bearb. Liste Scooterfahrten FZSCLI"),

    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains_any(t, "Protokoll Geldbörse", "Protokoll Geldboerse"),
     "FI", "Bearb. Geldbörse FIBGGB"),

    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "Grok_n Roll"),
     "RA", "Analyse Grok'n Roll RWPLAF"),

    (lambda t, p, b: p == "EXCEL.EXE" and
     _title_contains(t, "Thinking Frequencies"),
     "RW", "Analyse Thinking Frequencies RWMPMP"),

    # Excel: generic fallback → continue previous activity
    (lambda t, p, b: p == "EXCEL.EXE",
     "_UNCLASSIFIABLE", "Bearb. Excel-Datei"),

    # ── Word — with document name classification ───────────────────────
    (lambda t, p, b: p == "WINWORD.EXE" and _title_contains(t, "BRZG"),
     "BR", "Bearb. Dokumentation BRZG KSBRDR"),

    # Known document patterns → specific tasks
    (lambda t, p, b: p == "WINWORD.EXE" and
     _title_contains_any(t, "Ohrwürmer", "Ohrwuermer", "Ohrwurm"),
     "RW", "Dokumentation Ohrwurm-Projekt RWOWDO"),

    (lambda t, p, b: p == "WINWORD.EXE" and
     _title_contains_any(t, "Erbschaft", "Patientenverfügung",
                          "Vorsorgevollmacht"),
     "PA", "Überlegungen Vorsorgevollmacht + Patientenverfügung PAWFAF"),

    (lambda t, p, b: p == "WINWORD.EXE" and
     _title_contains_any(t, "Ma at", "Ma'at", "Grundsätze"),
     "GE", "Dokumentation Grundsätze der Ma'at GEDOMA"),

    (lambda t, p, b: p == "WINWORD.EXE" and
     _title_contains_any(t, "Tagebuch", "schmerzhafte Situationen"),
     "GE", "Führung Tagebuch GELIFT"),

    (lambda t, p, b: p == "WINWORD.EXE" and
     _title_contains_any(t, "Champion's Mindset", "Champions Mindset",
                          "Champion"),
     "GE", "Bearbeitung Buch Champion's Mindset GELICM"),

    (lambda t, p, b: p == "WINWORD.EXE" and
     _title_contains_any(t, "Finanzkonzept", "Finanzanlage"),
     "FI", "Dokumentation Finanzanlagen FIDOAK"),

    (lambda t, p, b: p == "WINWORD.EXE" and
     _title_contains_any(t, "Prioritätenliste", "Prioritaetenliste"),
     "KS", "Untersuchung der Prioritätenliste KSDODO"),

    # Generic Word: try to derive account from document name keywords.
    # Uses _WORD_DOC_CLASSIFY special handler to extract doc name and
    # match against known account keywords.
    (lambda t, p, b: p == "WINWORD.EXE",
     "_WORD_DOC_CLASSIFY", ""),

    # ── KeePass — support activity, continue previous ────────────────
    (lambda t, p, b: p == "KeePass.exe",
     "_UNCLASSIFIABLE", "Bearb. Passwörter (KeePass)"),

    # ── git-credential-manager — support activity ────────────────────
    (lambda t, p, b: p == "git-credential-manager.exe",
     "_UNCLASSIFIABLE", "Git Authentifizierung"),

    # ── ngrok — used for Radio Würmchen streaming ────────────────────
    (lambda t, p, b: _title_contains(t, "ngrok"),
     "RW", "Radio Würmchen (ngrok) RWMPMP"),

    # ── BRZ / Work ────────────────────────────────────────────────────
    (lambda t, p, b: _title_contains_any(t, "BRZG", "BRZ"),
     "BR", "Arbeit BRZ BREPDZ"),

    # ── Email (Outlook) ──────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains_any(t, "Outlook", "outlook.live",
                                                 "outlook.office"),
     "IN", "Bearbeitung Mails INMBMB"),

    # ── Explorer — with folder→account confirmation ───────────────────
    # Specific folders that clearly indicate an account
    # Note: USB-STICK removed — it's not KS-specific, any project can be on USB
    (lambda t, p, b: p == "explorer.exe" and
     _title_contains_any(t, "Kontenverwaltung", "Betrieb"),
     "KS", "Dateiverwaltung (Kontensystem) KSPLEN"),

    # Explorer with a folder that hints at an account → mark for
    # confirmation logic in build_activity_blocks
    (lambda t, p, b: p == "explorer.exe" and
     _explorer_folder_account(t) is not None,
     "_EXPLORER_ACCOUNT_HINT", ""),  # special: resolved in block builder

    (lambda t, p, b: p == "explorer.exe",
     "_UNCLASSIFIABLE", "Dateiverwaltung (Explorer)"),

    # ── GitHub ────────────────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains_any(t, "github.com", "GitHub",
                                                 "Personal Access Token"),
     "PC", "Bearb. Github PCENGH"),

    # ── Google Übersetzer — support activity, continue previous ──────
    (lambda t, p, b: b and _title_contains_any(t, "Google Übersetzer",
                                                 "Google Translate",
                                                 "Google \u00dcbersetzer"),
     "_UNCLASSIFIABLE", "Google Übersetzer"),

    # ── General browsing ──────────────────────────────────────────────
    (lambda t, p, b: b and _title_contains_any(t, "orf.at"),
     "IN", "div. Surfen (News) INSUNE"),

    (lambda t, p, b: b,
     "IN", "div. Surfen INSUSU"),

    # ── Fallback — continue previous activity ─────────────────────────
    # Instead of "Sonstige PC-Nutzung", mark as unclassifiable.
    # build_activity_blocks will continue the previous activity.
    (lambda t, p, b: True,
     "_UNCLASSIFIABLE", "Sonstige PC-Nutzung"),
]


# ═══════════════════════════════════════════════════════════════════════════ #
#  Core Processing                                                           #
# ═══════════════════════════════════════════════════════════════════════════ #

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def load_windowmon(date_str: str) -> List[Dict]:
    """Load and parse a day's windowmon JSONL file."""
    path = os.path.join(LOG_DIR, f"windowmon-{date_str}.jsonl")
    if not os.path.exists(path):
        print(f"Datei nicht gefunden: {path}")
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry["_ts"] = datetime.strptime(entry["ts"],
                                                  "%Y-%m-%dT%H:%M:%S")
                entries.append(entry)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"  Warnung: Zeile {line_no} übersprungen: {e}")
    return entries


def load_planner_log(date_str: str) -> List[Dict]:
    """Load planner log for cross-referencing Off-PC activity names."""
    path = os.path.join(LOG_DIR, f"planner-log-{date_str}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_offpc_activity(title: str) -> Tuple[str, str]:
    """Extract account and activity from planner Off-PC title.

    Title format: 'Tagesplanung — Off-PC — Duschen LEMTDU'
    → account from task code (first 2 chars), activity = full name.
    """
    # Split on " — " (em-dash with spaces)
    parts = title.split(" — ")
    if len(parts) >= 3:
        activity = parts[2].strip()
    elif " - Off-PC - " in title:
        # Fallback: regular dashes
        parts = title.split(" - Off-PC - ")
        activity = parts[-1].strip() if len(parts) >= 2 else ""
    else:
        return "LE", "Off-PC (unbekannt)"

    if not activity:
        return "LE", "Off-PC (unbekannt)"

    # Try to extract task code (6 chars at end)
    task_code_match = re.search(r'\s([A-ZÄÖÜß]{6})$', activity)
    if task_code_match:
        code = task_code_match.group(1)
        account = code[:2]
        return account, activity

    # No task code → generic
    return "LE", f"Off-PC: {activity}"


# ── Word document name → account mapping ──────────────────────────── #
# Keywords in Word document titles that indicate a specific account.
# Reuses the same concept as _EXPLORER_FOLDER_ACCOUNTS.

_WORD_DOC_ACCOUNTS = {
    "radio": "RW",
    "würmchen": "RW",
    "wuermchen": "RW",
    "andon": "RA",
    "ohrwürmer": "RW",
    "ohrwuermer": "RW",
    "ohrwurm": "RW",
    "karaoke": "MU",
    "essensplan": "LE",
    "lebenserhaltung": "LE",
    "kontensystem": "KS",
    "planung": "KS",
    "finanz": "FI",       # prefix: matches Finanzen, Finanzkonzept, etc.
    "papa": "PA",
    "erbschaft": "PA",
    "wohnung": "WF",
    "gesundheit": "GE",
    "tagebuch": "GE",
    "champion": "GE",
}


def _classify_word_document(title: str) -> Tuple[str, str]:
    """Classify a Word document by extracting account from the doc name.

    Title format: 'Dokumentation Projekt Ohrwürmer 26.3.8.doc - Microsoft Word'
    → Extract 'Dokumentation Projekt Ohrwürmer 26.3.8' as doc name.
    → Match keywords to find account.
    → Return (account, 'Bearb. <doc_name> <ACCOUNT>DODO').

    Falls back to _UNCLASSIFIABLE if no account can be determined
    (so the block builder can continue the previous activity).
    """
    # Extract document name: everything before " - Microsoft Word"
    # or before ".doc" if that pattern isn't found
    doc_name = title
    for suffix in (" - Microsoft Word", " - Word"):
        if suffix in doc_name:
            doc_name = doc_name.split(suffix)[0].strip()
            break

    # Remove file extension
    doc_name = re.sub(r'\.docx?$', '', doc_name, flags=re.IGNORECASE).strip()

    if not doc_name:
        return "_UNCLASSIFIABLE", "Bearb. Word-Dokument"

    # Match against known account keywords
    tl = title.lower()
    for keyword, account in _WORD_DOC_ACCOUNTS.items():
        if keyword in tl:
            code = f"{account}DODO"
            return account, f"Bearb. {doc_name} {code}"

    # No account match → unclassifiable (continue previous activity)
    return "_UNCLASSIFIABLE", f"Bearb. Word-Dokument"


def _extract_dialog_activity(title: str) -> Tuple[str, str]:
    """Extract account and activity from planner dialog title.

    Title format: 'Aufgabe erledigt — WC LEMTWC'
                   'Eintrag bearbeiten — Bearb. Essensplan LEEPEP'
                   'Vorgezogene Aktivität erfassen — Zähne putzen GEMTZP'
                   'Vorgezogene Aktivität erfassen — Liste_Morgentoilette — Bearb. Essensplan LEEPUH'
                   'Ungeplante Aktivität erfassen — Off-PC — WC LEMTWC'

    The part after the em-dash is the actual activity the user is doing
    (typically Off-PC while the dialog is left open).

    Fix for Issue #26: Handle additional prefixes (Off-PC, list names)
    that appear between the dialog type and the actual activity.
    """
    # Split on " — " (em-dash with spaces)
    parts = title.split(" \u2014 ")
    if len(parts) < 2:
        # Fallback: shouldn't happen (rule only matches if " — " present)
        return "KS", "Erfassung Ablauf KSPLEA"

    # The first part is the dialog type (e.g. "Aufgabe erledigt").
    # The LAST part is the activity; intermediate parts are list names
    # or "Off-PC" markers that should be stripped.  (Issue #26)
    #
    # Examples with 3 parts:
    #   ["Vorgezogene Aktivität erfassen", "Liste_Morgentoilette", "Bearb. Essensplan LEEPUH"]
    #   ["Ungeplante Aktivität erfassen", "Off-PC", "WC LEMTWC"]
    activity = parts[-1].strip()

    if not activity:
        return "KS", "Erfassung Ablauf KSPLEA"

    # If the extracted activity looks incomplete (dialog was just opening,
    # e.g. title was "Ungeplante Aktivität erfassen — <e"),
    # treat as planner operation, not a real activity.
    if len(activity) <= 3 or activity.startswith("<"):
        return "KS", "Erfassung Ablauf KSPLEA"

    # Try to extract task code (6 chars at end, optionally with (Fs.))
    task_code_match = re.search(r'\s([A-ZÄÖÜß]{6})(?:\s*\(Fs\.\))?\s*$', activity)
    if task_code_match:
        code = task_code_match.group(1)
        account = code[:2]
        return account, activity

    # No task code → classify as KS/Erfassung with the activity as context
    return "KS", activity


def classify_entry(entry: Dict) -> Tuple[str, str]:
    """Apply AutoDetect rules to classify a windowmon entry.

    Returns (account, activity).

    Special return values for block-builder logic:
      ("_UNCLASSIFIABLE", fallback_name)  → continue previous activity
      ("_EXPLORER_ACCOUNT_HINT", "")      → explorer folder hints at account
      ("_RADIO_WUERMCHEN", "")            → parse scan target from title
      ("_WINLOGGER", ...)                 → Window Logger idle signal
      ("_PLANNER_OFFPC", "")              → extract activity from title
      ("_PLANNER_DIALOG_ACTIVITY", "")    → extract activity from dialog title
    """
    # Handle idle markers
    entry_type = entry.get("type", "")
    if entry_type in ("idle_start", "idle_end"):
        return "IDLE", "Off-PC"

    title = entry.get("title", "")
    process = entry.get("process", "")
    browser = entry.get("browser", "")

    for match_fn, account, activity in AUTODETECT_RULES:
        try:
            if match_fn(title, process, browser):
                # Special case: Planner Off-PC title → extract activity
                if account == "_PLANNER_OFFPC":
                    return _extract_offpc_activity(title)

                # Special case: Planner dialog with activity in title
                # e.g. "Aufgabe erledigt — WC LEMTWC"
                if account == "_PLANNER_DIALOG_ACTIVITY":
                    return _extract_dialog_activity(title)

                # Special case: Word document → extract account from doc name
                if account == "_WORD_DOC_CLASSIFY":
                    return _classify_word_document(title)

                # Special case: Radio Würmchen → extract scan target
                if account == "_RADIO_WUERMCHEN":
                    scan_target = _parse_radio_wuermchen_title(title)
                    if scan_target:
                        return "RW", scan_target
                    return "RW", "Radio Würmchen"

                # When a hardcoded rule yields _UNCLASSIFIABLE, try the
                # confidence store before giving up.
                # All other special accounts (_EXPLORER_ACCOUNT_HINT,
                # _WINLOGGER, etc.) pass through unchanged.
                if account == "_UNCLASSIFIABLE":
                    store_result = ConfidenceStore.get().lookup(process, title)
                    if store_result is not None:
                        s_account, s_activity, s_conf, s_durch = store_result
                        if s_durch:
                            # Durchreicher: still unclassifiable so block
                            # builder continues the previous activity.
                            return "_UNCLASSIFIABLE", activity
                        else:
                            return s_account, s_activity
                    return account, activity

                # For low-accuracy rules: prefer confidence store if available.
                if (account, activity) in LOW_ACCURACY_OVERRIDABLE:
                    store_result = ConfidenceStore.get().lookup(process, title)
                    if store_result is not None:
                        s_account, s_activity, s_conf, s_durch = store_result
                        if not s_durch:
                            # Store has a real suggestion — use it.
                            return s_account, s_activity
                        # Durchreicher: hardcoded rule is also low-accuracy,
                        # so signal block-builder to continue previous activity.
                        return "_UNCLASSIFIABLE", activity
                    # No store match — fall back to hardcoded rule.

                return account, activity
        except Exception:
            continue

    # Final fallback: try confidence store for completely unknown titles
    store_result = ConfidenceStore.get().lookup(process, title)
    if store_result is not None:
        s_account, s_activity, s_conf, s_durch = store_result
        if not s_durch:
            return s_account, s_activity

    return "_UNCLASSIFIABLE", "Sonstige PC-Nutzung"


def build_activity_blocks(entries: List[Dict],
                          planner_log: Optional[List[Dict]] = None
                          ) -> List[Dict]:
    """Convert raw windowmon entries into classified activity blocks.

    Each block: {account, activity, start, end, duration_s, entries}

    Adjacent entries with the same classification are merged.

    Key behavior (Window Logger philosophy):
      - _UNCLASSIFIABLE entries continue the previous activity instead of
        creating a new "Sonstige PC-Nutzung" block.
      - _EXPLORER_ACCOUNT_HINT entries check if the explorer folder's
        account matches the previous block's account. If yes, continue
        previous activity (confirmation signal). If not, create a
        "Dateiverwaltung (Konto)" block.
      - _WINLOGGER entries always continue the previous activity.
    """
    if not entries:
        return []

    # Ensure chronological order (idle markers may be backdated)
    entries = sorted(entries, key=lambda e: e["_ts"])

    blocks = []
    current_block = None

    for entry in entries:
        ts = entry["_ts"]
        account, activity = classify_entry(entry)
        title = entry.get("title", "")

        # Skip idle markers as separate entries (they're info-only)
        if entry.get("type") in ("idle_start", "idle_end"):
            continue

        # ── Special: Window Logger idle → continue previous ───────────
        if account == "_WINLOGGER" and current_block:
            current_block["end"] = ts
            current_block["entries"] += 1
            continue

        # ── Special: Unclassifiable → continue previous activity ──────
        # This is the core Window Logger philosophy: when something can't
        # be classified, assume the previous activity is still running.
        if account == "_UNCLASSIFIABLE" and current_block:
            current_block["end"] = ts
            current_block["entries"] += 1
            continue

        # ── Special: Explorer folder → account confirmation ───────────
        # If the folder's account matches the previous block's account,
        # this confirms the previous activity continues (e.g., opening
        # the "kontensystem" folder while working on the planner).
        # If different account, create a Dateiverwaltung block for that account.
        if account == "_EXPLORER_ACCOUNT_HINT":
            folder_account = _explorer_folder_account(title)
            if folder_account and current_block:
                if folder_account == current_block["account"]:
                    # Confirmation: same account → continue previous
                    current_block["end"] = ts
                    current_block["entries"] += 1
                    continue
                else:
                    # Different account → Dateiverwaltung for that account
                    account = folder_account
                    activity = f"Dateiverwaltung ({title.strip()})"
            else:
                # No account match or no previous block → generic explorer
                if current_block:
                    current_block["end"] = ts
                    current_block["entries"] += 1
                    continue
                account = "PC"
                activity = "Dateiverwaltung (Explorer)"

        # ── Normal classification: merge or create new block ──────────
        if (current_block and
                current_block["account"] == account and
                current_block["activity"] == activity and
                (ts - current_block["end"]).total_seconds() < 300):
            # Extend current block (< 5 min gap = same activity)
            current_block["end"] = ts
            current_block["entries"] += 1
        else:
            if current_block:
                blocks.append(current_block)
            current_block = {
                "account": account,
                "activity": activity,
                "start": ts,
                "end": ts,
                "entries": 1,
            }

    if current_block:
        blocks.append(current_block)

    # Set end times: each block ends when the next one starts,
    # BUT cap at a maximum gap to avoid inflating blocks across
    # long Off-PC periods (e.g., BRZ workday on company laptop).
    MAX_BLOCK_GAP_S = 600  # 10 minutes — beyond this, don't extend the block

    for i in range(len(blocks) - 1):
        gap_s = (blocks[i + 1]["start"] - blocks[i]["end"]).total_seconds()
        if gap_s <= MAX_BLOCK_GAP_S:
            blocks[i]["end"] = blocks[i + 1]["start"]
        else:
            # Cap: extend by at most 60 seconds past last entry
            blocks[i]["end"] = blocks[i]["end"] + timedelta(seconds=60)

    # Calculate durations
    for block in blocks:
        block["duration_s"] = max(0, (block["end"] - block["start"]).total_seconds())

    return blocks


def inject_idle_periods(blocks: List[Dict],
                        entries: List[Dict]) -> List[Dict]:
    """Insert Off-PC blocks based on idle markers from the planner.

    Idle markers: {type: "idle_start"} and {type: "idle_end", idle_start: ...}
    These override whatever windowmon saw during that period.
    """
    idle_periods = []
    for entry in entries:
        if entry.get("type") == "idle_end":
            idle_start_str = entry.get("idle_start")
            if idle_start_str:
                try:
                    idle_start = datetime.strptime(idle_start_str,
                                                    "%Y-%m-%dT%H:%M:%S")
                    idle_end = entry["_ts"]
                    idle_periods.append((idle_start, idle_end))
                except ValueError:
                    pass

    if not idle_periods:
        return blocks

    # For each idle period, find the planner Off-PC title if available
    # (from window entries during idle time)
    idle_activities = []
    for idle_start, idle_end in idle_periods:
        # Find the last Off-PC title entry before/during idle
        offpc_account, offpc_activity = "LE", "Off-PC"
        for entry in entries:
            if entry.get("type"):
                continue  # skip markers
            ts = entry["_ts"]
            title = entry.get("title", "")
            if ts <= idle_end and "Off-PC" in title and "Tagesplanung" in title:
                offpc_account, offpc_activity = _extract_offpc_activity(title)

        idle_activities.append({
            "account": offpc_account,
            "activity": offpc_activity,
            "start": idle_start,
            "end": idle_end,
            "duration_s": (idle_end - idle_start).total_seconds(),
            "entries": 0,
            "is_idle": True,
        })

    # Merge idle blocks into the block list, splitting overlapping blocks
    result = []
    idle_idx = 0
    for block in blocks:
        # Check if any idle period overlaps this block
        while idle_idx < len(idle_activities):
            idle = idle_activities[idle_idx]
            if idle["start"] >= block["end"]:
                break  # idle starts after this block
            if idle["end"] <= block["start"]:
                idle_idx += 1
                continue  # idle ended before this block

            # Overlap: idle period cuts into this block
            # Part before idle
            if block["start"] < idle["start"]:
                pre = dict(block)
                pre["end"] = idle["start"]
                pre["duration_s"] = (pre["end"] - pre["start"]).total_seconds()
                if pre["duration_s"] > 0:
                    result.append(pre)

            # The idle block itself
            result.append(idle)

            # Adjust block to start after idle
            block = dict(block)
            block["start"] = idle["end"]
            block["duration_s"] = (block["end"] - block["start"]).total_seconds()
            idle_idx += 1

        if block["duration_s"] > 0:
            result.append(block)

    return result


def aggregate_summary(blocks: List[Dict]) -> Dict[str, float]:
    """Aggregate blocks into total minutes per account/activity."""
    totals = defaultdict(float)
    for block in blocks:
        key = f'{block["account"]}/{block["activity"]}'
        totals[key] += block["duration_s"] / 60.0
    return dict(totals)


def detect_gaps(entries: List[Dict],
                min_gap_minutes: int = 5) -> List[Tuple[datetime, datetime, float]]:
    """Detect gaps in windowmon data (potential Off-PC periods).

    Returns list of (start, end, duration_minutes) for gaps >= min_gap_minutes.
    """
    gaps = []
    for i in range(1, len(entries)):
        if entries[i].get("type"):
            continue  # skip markers
        if entries[i - 1].get("type"):
            continue

        prev_ts = entries[i - 1]["_ts"]
        curr_ts = entries[i]["_ts"]
        gap_min = (curr_ts - prev_ts).total_seconds() / 60.0
        if gap_min >= min_gap_minutes:
            gaps.append((prev_ts, curr_ts, gap_min))
    return gaps


# ═══════════════════════════════════════════════════════════════════════════ #
#  Output Formatting                                                         #
# ═══════════════════════════════════════════════════════════════════════════ #

def print_summary(blocks: List[Dict], totals: Dict[str, float],
                  gaps: List, show_detail: bool, show_idle: bool):
    """Print the activity summary report."""

    print("=" * 76)
    print(f"  WINDOWMON TAGESZUSAMMENFASSUNG")
    if blocks:
        day = blocks[0]["start"].strftime("%d.%m.%Y")
        span = (f'{blocks[0]["start"].strftime("%H:%M")} – '
                f'{blocks[-1]["end"].strftime("%H:%M")}')
        print(f"  Datum: {day}    Zeitraum: {span}")
    print("=" * 76)

    # ── Totals by account ─────────────────────────────────────────────
    account_totals = defaultdict(float)
    for key, mins in totals.items():
        acct = key.split("/")[0]
        account_totals[acct] += mins

    print(f"\n{'KONTO':<6} {'MINUTEN':>8}  {'STUNDEN':>7}")
    print(f"{'-'*6} {'-'*8}  {'-'*7}")
    for acct, mins in sorted(account_totals.items(),
                              key=lambda x: -x[1]):
        if acct == "IDLE" and not show_idle:
            continue
        print(f"{acct:<6} {mins:8.1f}  {mins/60:7.2f}h")
    total_mins = sum(v for k, v in account_totals.items()
                     if k != "IDLE" or show_idle)
    print(f"{'------':6} {'--------':>8}  {'-------':>7}")
    print(f"{'TOTAL':<6} {total_mins:8.1f}  {total_mins/60:7.2f}h")

    # ── Totals by activity ────────────────────────────────────────────
    print(f"\n{'KONTO':<6} {'MIN':>6}  {'AKTIVITÄT'}")
    print(f"{'-'*6} {'-'*6}  {'-'*50}")
    for key, mins in sorted(totals.items(), key=lambda x: -x[1]):
        if mins < 1.0:
            continue
        acct = key.split("/")[0]
        activity = key.split("/", 1)[1]
        if acct == "IDLE" and not show_idle:
            continue
        print(f"{acct:<6} {mins:6.1f}  {activity}")

    # ── Gaps (potential undetected Off-PC) ─────────────────────────────
    if gaps:
        print(f"\n{'='*76}")
        print(f"  ERKANNTE LUECKEN (>= 5 Min. ohne windowmon-Eintraege)")
        print(f"{'='*76}")
        print(f"  {'VON':>8}  {'BIS':>8}  {'DAUER':>6}  MÖGLICHE BEDEUTUNG")
        print(f"  {'-'*8}  {'-'*8}  {'-'*6}  {'-'*40}")
        for start, end, dur in gaps:
            meaning = ""
            hour = start.hour
            if 7 <= hour <= 9:
                meaning = "Morgentoilette / Duschen?"
            elif 12 <= hour <= 13:
                meaning = "Mittagspause?"
            elif 20 <= hour <= 21:
                meaning = "Laufen / Spaziergang?"
            elif 22 <= hour <= 23:
                meaning = "Abendzeremonie?"
            print(f"  {start.strftime('%H:%M'):>8}  {end.strftime('%H:%M'):>8}"
                  f"  {dur:5.1f}m  {meaning}")

    # ── Detailed block view ───────────────────────────────────────────
    if show_detail:
        print(f"\n{'='*76}")
        print(f"  DETAILIERTE BLÖCKE")
        print(f"{'='*76}")
        print(f"  {'VON':>8}  {'BIS':>8}  {'MIN':>5}  {'KONTO':<6} "
              f"{'AKTIVITÄT'}")
        print(f"  {'-'*8}  {'-'*8}  {'-'*5}  {'-'*6} {'-'*44}")
        for block in blocks:
            dur = block["duration_s"] / 60.0
            if dur < 0.15:  # skip < 10 second blocks
                continue
            idle_mark = " [Off-PC]" if block.get("is_idle") else ""
            acct = block["account"]
            if acct == "IDLE" and not show_idle:
                continue
            print(f"  {block['start'].strftime('%H:%M'):>8}  "
                  f"{block['end'].strftime('%H:%M'):>8}  "
                  f"{dur:5.1f}  {acct:<6} "
                  f"{block['activity']}{idle_mark}")


# ═══════════════════════════════════════════════════════════════════════════ #
#  CLI                                                                       #
# ═══════════════════════════════════════════════════════════════════════════ #

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    show_detail = False
    show_idle = False
    planner_log_path = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            date_str = args[i + 1]
            i += 2
        elif args[i] == "--detail":
            show_detail = True
            i += 1
        elif args[i] == "--idle":
            show_idle = True
            i += 1
        elif args[i] == "--planner-log" and i + 1 < len(args):
            planner_log_path = args[i + 1]
            i += 2
        elif args[i] in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"Unbekannter Parameter: {args[i]}")
            sys.exit(1)

    print(f"Lade windowmon-Log für {date_str}...")
    entries = load_windowmon(date_str)
    if not entries:
        print("Keine Einträge gefunden.")
        sys.exit(0)

    # Filter out non-window entries for gap detection
    window_entries = [e for e in entries if not e.get("type")]
    print(f"  {len(window_entries)} Fenster-Einträge, "
          f"{len(entries) - len(window_entries)} Marker")

    # Build classified activity blocks
    blocks = build_activity_blocks(entries)
    print(f"  {len(blocks)} Aktivitätsblöcke erkannt")

    # Inject idle periods
    blocks = inject_idle_periods(blocks, entries)

    # Detect gaps
    gaps = detect_gaps(entries, min_gap_minutes=5)
    if gaps:
        print(f"  {len(gaps)} Luecken >= 5 Min. erkannt")

    # Aggregate
    totals = aggregate_summary(blocks)

    # Output
    print()
    print_summary(blocks, totals, gaps, show_detail, show_idle)


if __name__ == "__main__":
    main()
