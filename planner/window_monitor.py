"""
window_monitor.py — Background window monitor for the reactive planner.

Tracks the active foreground window on Windows, modeled after Kurt's
existing VB5 Window Logger. Polls every 1 second, detects window changes,
and logs them to a JSONL file.

Key behaviors (matching VB5 Timer1 logic):
  1. Poll every 1 second
  2. Double check: compare hwnd first; if same hwnd AND not a browser/Excel
     window, skip reading the title. If different hwnd OR browser/Excel,
     re-read the window title (tab changes don't change hwnd).
  3. Compare title text: only log when title actually changes.
  4. Browser detection: Chrome, Firefox, Edge, and Excel always get
     title re-read even with the same hwnd.

Public API:
  - start()          → launch the daemon thread
  - stop()           → signal the thread to stop
  - get_current()    → current window info dict or None
  - get_history(since=datetime) → list of recent changes
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional


# ── Windows API via ctypes ─────────────────────────────────────────────── #

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH = 260


def _get_foreground_hwnd() -> int:
    """Return the handle of the foreground window."""
    return user32.GetForegroundWindow()


def _get_window_title(hwnd: int) -> str:
    """Read the title text of a window by handle."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _get_process_name(hwnd: int) -> str:
    """Get the executable name for the process owning the window.

    Uses GetWindowThreadProcessId + OpenProcess + QueryFullProcessImageNameW.
    Returns just the filename (e.g. 'chrome.exe') or '' on failure.
    """
    try:
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return ""

        hProcess = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not hProcess:
            return ""

        try:
            buf = ctypes.create_unicode_buffer(MAX_PATH)
            size = ctypes.wintypes.DWORD(MAX_PATH)
            result = kernel32.QueryFullProcessImageNameW(
                hProcess, 0, buf, ctypes.byref(size))
            if result:
                # Extract just the filename from the full path
                return os.path.basename(buf.value)
            return ""
        finally:
            kernel32.CloseHandle(hProcess)
    except Exception:
        return ""


# ── Browser / special app detection ───────────────────────────────────── #

# These apps can change content without changing hwnd (tab switches, etc.)
# so we always re-read the title even if the hwnd is the same.
_ALWAYS_REREAD_PROCESSES = {
    "chrome.exe", "firefox.exe", "msedge.exe",
    "opera.exe", "brave.exe",
    "excel.exe",
}

# Map process names to friendly browser labels
_BROWSER_MAP = {
    "chrome.exe": "Chrome",
    "firefox.exe": "Firefox",
    "msedge.exe": "Edge",
    "opera.exe": "Opera",
    "brave.exe": "Brave",
}

# Fallback: detect browser from window title if process name unavailable
_TITLE_BROWSER_PATTERNS = [
    ("Google Chrome", "Chrome"),
    ("Mozilla Firefox", "Firefox"),
    ("Microsoft Edge", "Edge"),
    ("Opera", "Opera"),
    ("Brave", "Brave"),
    ("Microsoft Excel", "Excel"),
]


def _detect_browser(process_name: str, title: str) -> str:
    """Return a browser/app label or empty string."""
    pname = process_name.lower()
    if pname in _BROWSER_MAP:
        return _BROWSER_MAP[pname]
    if pname == "excel.exe":
        return "Excel"
    # Fallback to title-based detection
    for pattern, label in _TITLE_BROWSER_PATTERNS:
        if pattern.lower() in title.lower():
            return label
    return ""


def _should_always_reread(process_name: str, title: str) -> bool:
    """Return True if this window type requires re-reading title every poll."""
    if process_name.lower() in _ALWAYS_REREAD_PROCESSES:
        return True
    # Fallback: check title for browser/Excel keywords
    for pattern, _label in _TITLE_BROWSER_PATTERNS:
        if pattern.lower() in title.lower():
            return True
    return False


# ── Data model ─────────────────────────────────────────────────────────── #

@dataclass
class WindowEvent:
    """A single window change event."""
    ts: str           # ISO timestamp (no timezone)
    hwnd: int         # window handle
    title: str        # window title text
    process: str      # executable name (e.g. 'chrome.exe')
    browser: str      # browser label or '' for non-browsers


# ── Log directory ──────────────────────────────────────────────────────── #

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


# ── Monitor class ──────────────────────────────────────────────────────── #

class WindowMonitor:
    """Background thread that tracks the active foreground window.

    Usage:
        monitor = WindowMonitor()
        monitor.start()
        ...
        info = monitor.get_current()
        history = monitor.get_history(since=some_datetime)
        ...
        monitor.stop()
    """

    def __init__(self, poll_interval: float = 1.0):
        self._poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # State
        self._last_hwnd: int = 0
        self._last_title: str = ""
        self._last_process: str = ""
        self._current: Optional[WindowEvent] = None
        self._history: List[WindowEvent] = []

        # JSONL log file handle (opened on first write each day)
        self._log_file = None
        self._log_date: Optional[str] = None

    def start(self):
        """Start the monitor daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return  # already running

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="WindowMonitor", daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the monitor thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._close_log_file()

    def get_current(self) -> Optional[dict]:
        """Return the current window info as a dict, or None."""
        with self._lock:
            if self._current is None:
                return None
            return asdict(self._current)

    def get_history(self, since: Optional[datetime] = None) -> List[dict]:
        """Return recent window changes as a list of dicts.

        Args:
            since: If provided, only return events after this time.
        """
        with self._lock:
            if since is None:
                return [asdict(e) for e in self._history]
            since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
            return [asdict(e) for e in self._history if e.ts >= since_str]

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── Internal polling loop ──────────────────────────────────────── #

    def _run(self):
        """Main polling loop — runs in a daemon thread."""
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as e:
                # Don't crash the thread on transient errors
                print(f"[WindowMonitor] Error in poll: {e}")
            self._stop_event.wait(self._poll_interval)

        self._close_log_file()

    def _poll_once(self):
        """Single poll iteration — the core VB5-style logic."""
        hwnd = _get_foreground_hwnd()
        if hwnd == 0:
            return  # no foreground window (locked screen, etc.)

        same_hwnd = (hwnd == self._last_hwnd)

        if same_hwnd:
            # Same handle — only re-read title for browsers/Excel
            if not _should_always_reread(self._last_process, self._last_title):
                return  # skip — nothing changed
            # Browser/Excel: re-read title (tab might have changed)
            title = _get_window_title(hwnd)
            if title == self._last_title:
                return  # title unchanged
            process = self._last_process  # process hasn't changed
        else:
            # Different handle — new window
            title = _get_window_title(hwnd)
            process = _get_process_name(hwnd)

        # Check if title actually changed
        if title == self._last_title and same_hwnd:
            return

        # Detect browser
        browser = _detect_browser(process, title)

        # Build event
        now = datetime.now()
        event = WindowEvent(
            ts=now.strftime("%Y-%m-%dT%H:%M:%S"),
            hwnd=hwnd,
            title=title,
            process=process,
            browser=browser,
        )

        # Update state
        with self._lock:
            self._last_hwnd = hwnd
            self._last_title = title
            self._last_process = process
            self._current = event
            self._history.append(event)

            # Keep history bounded (last 1000 events)
            if len(self._history) > 1000:
                self._history = self._history[-500:]

        # Write to JSONL log
        self._write_log(event)

    # ── JSONL file logging ─────────────────────────────────────────── #

    def _write_log(self, event: WindowEvent):
        """Append one JSON line to the daily log file."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            # Rotate log file at midnight
            if self._log_date != today:
                self._close_log_file()
                self._log_date = today

            if self._log_file is None:
                os.makedirs(LOG_DIR, exist_ok=True)
                path = os.path.join(LOG_DIR, f"windowmon-{today}.jsonl")
                self._log_file = open(path, "a", encoding="utf-8")

            line = json.dumps(asdict(event), ensure_ascii=False)
            self._log_file.write(line + "\n")
            self._log_file.flush()
        except Exception as e:
            print(f"[WindowMonitor] Log write error: {e}")

    def _close_log_file(self):
        """Close the current log file handle."""
        if self._log_file is not None:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
