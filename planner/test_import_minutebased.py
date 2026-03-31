# -*- coding: utf-8 -*-
"""
Test: Minute-based import logic (Issues #2 and #3).

Tests the new _import() logic that:
  1. Truncates timestamps to whole minutes
  2. Skips sub-minute blocks (start_min == end_min)
  3. Merges adjacent same-activity segments after sub-minute filtering
  4. Prevents cascading extensions via original_completed_at snapshot

Run:  py test_import_minutebased.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

# ─── Minimal stubs to test the import algorithm in isolation ────────────

@dataclass
class FakeEntry:
    ts: datetime
    title: str = ""
    process: str = ""
    browser: str = ""
    block_id: int = 0
    logged_activity: str = ""

@dataclass
class FakeBlock:
    block_id: int
    activity: str
    account: str
    start_idx: int
    end_idx: int

    def is_logged(self, entries):
        return all(entries[i].logged_activity != "" 
                   for i in range(self.start_idx, self.end_idx + 1))

@dataclass
class FakeCompleted:
    activity: str
    started_at: datetime
    completed_at: datetime
    skipped: bool = False


def build_import_segments(entries, blocks, completed):
    """
    Replicate the core import logic from timeline_import.py::_import().
    Returns (merged_segments, extended_activities, new_imports).
    """
    # Step 1: Build minute-truncated segments
    raw_segments = []
    for b in blocks:
        if b.start_idx >= len(entries) or b.end_idx >= len(entries):
            continue
        if b.account in ("??", "IDLE"):
            continue
        if b.is_logged(entries):
            continue

        start_ts = entries[b.start_idx].ts.replace(second=0, microsecond=0)
        if b.end_idx + 1 < len(entries):
            end_ts = entries[b.end_idx + 1].ts.replace(second=0, microsecond=0)
        else:
            end_ts = (entries[b.end_idx].ts.replace(second=0, microsecond=0)
                      + timedelta(minutes=1))

        if end_ts <= start_ts:
            continue

        raw_segments.append({
            'activity': b.activity,
            'account': b.account,
            'start': start_ts,
            'end': end_ts,
        })

    # Step 2: Merge adjacent same-activity
    merged = []
    for seg in raw_segments:
        if (merged
                and merged[-1]['activity'] == seg['activity']
                and merged[-1]['end'] >= seg['start']):
            merged[-1]['end'] = max(merged[-1]['end'], seg['end'])
        else:
            merged.append(dict(seg))

    # Step 3: Import with anti-cascade extension
    original_completed_at = {id(c): c.completed_at for c in completed}
    extensions = []
    new_imports = []

    for seg in merged:
        matching = [
            c for c in completed
            if c.activity == seg['activity']
            and abs((original_completed_at[id(c)] - seg['start']).total_seconds()) < 300
        ]
        if matching:
            last_match = max(matching, key=lambda c: original_completed_at[id(c)])
            orig_end = original_completed_at[id(last_match)]
            intervening = [
                c for c in completed
                if c is not last_match
                and not c.skipped
                and c.started_at >= orig_end
                and c.started_at <= seg['start']
            ]
            if not intervening:
                last_match.completed_at = seg['end']
                extensions.append((seg['activity'], seg['start'], seg['end']))
                continue
        new_imports.append(seg)

    return merged, extensions, new_imports


# ═══════════════════════════════════════════════════════════════════════════
#  Test Cases
# ═══════════════════════════════════════════════════════════════════════════

def dt(h, m, s=0):
    return datetime(2026, 3, 27, h, m, s)


def test_issue2_interrupter_structure():
    """Issue #2: FGPA segments with interrupters should NOT merge into monolith."""
    print("Test Issue #2: Interrupter structure preserved...", end=" ")

    entries = [
        FakeEntry(ts=dt(21, 53, 0),  block_id=1),   # 0: FGPA
        FakeEntry(ts=dt(22, 2,  5),  block_id=2),   # 1: Surfen X (interrupter)
        FakeEntry(ts=dt(22, 4,  0),  block_id=3),   # 2: FGPA
        FakeEntry(ts=dt(22, 8, 15),  block_id=4),   # 3: Andon FM (interrupter)
        FakeEntry(ts=dt(22, 13, 0),  block_id=5),   # 4: FGPA
        FakeEntry(ts=dt(22, 42, 0),  block_id=5),   # 5: FGPA (end)
    ]
    blocks = [
        FakeBlock(1, "Spielen FGPA CSFGPA", "CS", 0, 0),
        FakeBlock(2, "Surfen X INSUSU",     "IN", 1, 1),
        FakeBlock(3, "Spielen FGPA CSFGPA", "CS", 2, 2),
        FakeBlock(4, "Analyse Andon FM RWPLAF", "RW", 3, 3),
        FakeBlock(5, "Spielen FGPA CSFGPA", "CS", 4, 5),
    ]

    merged, extensions, new_imports = build_import_segments(entries, blocks, [])

    # Surfen X: 22:02:05 → 22:04:00  truncated = 22:02 → 22:04  (2 min, kept)
    # Andon FM: 22:08:15 → 22:13:00  truncated = 22:08 → 22:13  (5 min, kept)
    # So FGPA should NOT merge into one monolith — there are real interrupters

    # Check that we have separate segments for FGPA
    fgpa_segs = [s for s in merged if "FGPA" in s['activity']]
    other_segs = [s for s in merged if "FGPA" not in s['activity']]

    assert len(fgpa_segs) == 3, f"Expected 3 FGPA segments, got {len(fgpa_segs)}: {fgpa_segs}"
    assert len(other_segs) == 2, f"Expected 2 interrupter segments, got {len(other_segs)}"
    print("OK ✓")


def test_issue3_subminute_filtered():
    """Issue #3: Sub-minute interrupter should be filtered, neighbors merged."""
    print("Test Issue #3: Sub-minute blocks filtered...", end=" ")

    entries = [
        FakeEntry(ts=dt(22, 1, 0),   block_id=1),   # 0: FGPA
        FakeEntry(ts=dt(22, 8, 5),   block_id=2),   # 1: Quick interrupter
        FakeEntry(ts=dt(22, 8, 55),  block_id=3),   # 2: FGPA again
        FakeEntry(ts=dt(22, 15, 0),  block_id=3),   # 3: FGPA (end)
    ]
    blocks = [
        FakeBlock(1, "Spielen FGPA CSFGPA", "CS", 0, 0),
        FakeBlock(2, "Surfen X INSUSU",     "IN", 1, 1),  # 22:08:05-22:08:55 = sub-minute!
        FakeBlock(3, "Spielen FGPA CSFGPA", "CS", 2, 3),
    ]

    merged, extensions, new_imports = build_import_segments(entries, blocks, [])

    # Surfen X: 22:08:05 → 22:08:55  truncated = 22:08 → 22:08 (0 min, FILTERED)
    # FGPA segments: 22:01→22:08, 22:08→22:15+1 = should merge to 22:01→22:16
    assert len(merged) == 1, f"Expected 1 merged segment (sub-minute filtered), got {len(merged)}: {merged}"
    assert "FGPA" in merged[0]['activity']
    assert merged[0]['start'] == dt(22, 1, 0), f"Start should be 22:01, got {merged[0]['start']}"
    print("OK ✓")


def test_issue2_cascade_prevention():
    """Issue #2: Extension must use ORIGINAL completed_at, not cascaded values."""
    print("Test Issue #2: Cascade extension prevented...", end=" ")

    # Scenario: Two FGPA blocks with a real interrupter between them.
    # Both are near an existing completed FGPA activity.
    # Without the fix, extending block 1 would move completed_at forward,
    # causing block 2 to also match and extend — creating a monolith.

    completed = [
        FakeCompleted("Spielen FGPA CSFGPA", dt(21, 30, 0), dt(21, 50, 0))
    ]

    entries = [
        FakeEntry(ts=dt(21, 53, 0),  block_id=1),   # 0: FGPA
        FakeEntry(ts=dt(22, 2, 0),   block_id=2),   # 1: Surfen X
        FakeEntry(ts=dt(22, 5, 0),   block_id=3),   # 2: FGPA
        FakeEntry(ts=dt(22, 15, 0),  block_id=3),   # 3: FGPA end
    ]
    blocks = [
        FakeBlock(1, "Spielen FGPA CSFGPA", "CS", 0, 0),
        FakeBlock(2, "Surfen X INSUSU",     "IN", 1, 1),
        FakeBlock(3, "Spielen FGPA CSFGPA", "CS", 2, 3),
    ]

    merged, extensions, new_imports = build_import_segments(entries, blocks, completed)

    # The first FGPA (21:53-22:02) is within 300s of completed (21:50) → extend
    # The second FGPA (22:05-22:16) should NOT match the original completed_at
    # (21:50, >300s gap) — it should be a NEW import, not an extension
    assert len(extensions) == 1, f"Expected 1 extension, got {len(extensions)}"
    assert len(new_imports) >= 1, f"Expected at least 1 new import, got {len(new_imports)}"
    
    # Verify the completed activity was extended to 22:02 (first FGPA end),
    # NOT to 22:16 (cascaded through second FGPA)
    assert completed[0].completed_at == dt(22, 2, 0), \
        f"Expected extension to 22:02, got {completed[0].completed_at}"
    print("OK ✓")


def test_subminute_youtube_across_minute_boundary():
    """Kurt's example from Issue #3 comment: 22:01:57-22:02:15 should import as 22:01-22:02."""
    print("Test: Activity crossing minute boundary imports correctly...", end=" ")

    entries = [
        FakeEntry(ts=dt(22, 0, 0),   block_id=1),   # 0: Something before
        FakeEntry(ts=dt(22, 1, 57),  block_id=2),   # 1: YouTube
        FakeEntry(ts=dt(22, 2, 15),  block_id=3),   # 2: Something after
        FakeEntry(ts=dt(22, 10, 0),  block_id=3),   # 3: end
    ]
    blocks = [
        FakeBlock(1, "Arbeitszeit BREPDZ", "BR", 0, 0),
        FakeBlock(2, "Ansehen Youtube RAYTYT", "RA", 1, 1),
        FakeBlock(3, "Arbeitszeit BREPDZ", "BR", 2, 3),
    ]

    merged, _, _ = build_import_segments(entries, blocks, [])

    # YouTube: 22:01:57 → 22:02:15  truncated = 22:01 → 22:02  (1 min, KEPT)
    yt_segs = [s for s in merged if "Youtube" in s['activity']]
    assert len(yt_segs) == 1, f"Expected 1 YouTube segment, got {len(yt_segs)}"
    assert yt_segs[0]['start'] == dt(22, 1, 0)
    assert yt_segs[0]['end'] == dt(22, 2, 0)
    print("OK ✓")


def test_subminute_youtube_same_minute():
    """Kurt's example: 22:02:05-22:02:59 should NOT import (sub-minute)."""
    print("Test: Same-minute activity filtered out...", end=" ")

    entries = [
        FakeEntry(ts=dt(22, 0, 0),   block_id=1),
        FakeEntry(ts=dt(22, 2, 5),   block_id=2),   # YouTube same-minute
        FakeEntry(ts=dt(22, 2, 59),  block_id=3),
        FakeEntry(ts=dt(22, 10, 0),  block_id=3),
    ]
    blocks = [
        FakeBlock(1, "Arbeitszeit BREPDZ", "BR", 0, 0),
        FakeBlock(2, "Ansehen Youtube RAYTYT", "RA", 1, 1),  # 22:02:05-22:02:59 → same minute
        FakeBlock(3, "Arbeitszeit BREPDZ", "BR", 2, 3),
    ]

    merged, _, _ = build_import_segments(entries, blocks, [])

    yt_segs = [s for s in merged if "Youtube" in s['activity']]
    assert len(yt_segs) == 0, f"Sub-minute YouTube should be filtered, got {yt_segs}"

    # The two Arbeitszeit blocks should merge since the interrupter was filtered
    br_segs = [s for s in merged if "Arbeitszeit" in s['activity']]
    assert len(br_segs) == 1, f"Expected 1 merged Arbeitszeit, got {len(br_segs)}"
    print("OK ✓")


# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Timeline Import — Minute-Based Logic Tests")
    print("  (Issues #2 and #3)")
    print("=" * 60)
    print()
    test_issue2_interrupter_structure()
    test_issue3_subminute_filtered()
    test_issue2_cascade_prevention()
    test_subminute_youtube_across_minute_boundary()
    test_subminute_youtube_same_minute()
    print()
    print("All tests passed! ✓")
