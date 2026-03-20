"""
andon_fm_match.py — Match Andon FM played songs against RW database.
"""
import csv
import io
import os
from difflib import SequenceMatcher

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "Library_Andon_FM.csv")

# Load with encoding fallback
for enc in ['utf-8', 'latin-1', 'cp1252']:
    try:
        with open(CSV_PATH, 'r', encoding=enc) as f:
            content = f.read()
        break
    except UnicodeDecodeError:
        continue

played = []
rw_songs = []
reader = csv.reader(io.StringIO(content), delimiter=';')
header = next(reader)
for row in reader:
    if len(row) >= 1 and row[0].strip():
        times = 0
        if len(row) > 1 and row[1].strip():
            try:
                times = int(row[1].strip())
            except ValueError:
                pass
        played.append((row[0].strip(), times))
    if len(row) >= 3 and row[2].strip():
        rw_songs.append(row[2].strip())

print(f"Played songs (Andon FM): {len(played)}")
print(f"RW database songs: {len(rw_songs)}")
print()


def normalize(s):
    s = s.lower().strip()
    # Remove common parenthetical suffixes
    removals = [
        "(remastered 2011)", "(remastered 2009)", "(remastered)",
        "(remaster)", "(2004 remaster)", "(2008 remaster)",
        "(2012 remaster)", "(2013 remaster)", "(2018 remastered)",
        "(2019 mix)", "(2001 remaster)", "(2007 remastered)",
        "(remastered 2010)", "(remastered 1999)", "(remastered 2019)",
        "(2021 remaster)", "(album version)", "(single edit)",
        "(single version)", "(stereo/remastered 2012)",
        "(2015 remaster)", "(2018 bob ludwig remastering)",
        "(live on mtv, 1994)", "(live from joshua tree)",
        "(original)", "(explicit)", "(studio)", "(live)",
        "(lp version)",
    ]
    for rem in removals:
        s = s.replace(rem, "")
    s = s.replace("&", "and").replace("!", "").replace(",", "").replace(".", "")
    s = s.replace("  ", " ").strip()
    return s


def flip_played(s):
    """Convert 'Artist - Title' to normalized 'title-artist'."""
    parts = s.split(" - ", 1)
    if len(parts) == 2:
        return normalize(parts[1]) + "-" + normalize(parts[0])
    return normalize(s)


def normalize_rw(s):
    """RW format is already 'Title-Artist'."""
    return normalize(s)


played_norm = {}
for p in played:
    k = flip_played(p[0])
    played_norm[k] = p

rw_norm = {}
for r in rw_songs:
    k = normalize_rw(r)
    rw_norm[k] = r


def best_match(needle, haystack_keys, threshold=0.70):
    best_score = 0
    best_key = None
    for hk in haystack_keys:
        score = SequenceMatcher(None, needle, hk).ratio()
        if score > best_score:
            best_score = score
            best_key = hk
    if best_score >= threshold:
        return best_key, best_score
    return None, best_score


# ── 1. Played on Andon FM but NOT in RW ──────────────────────────────
print("=" * 70)
print("  PLAYED ON ANDON FM but NOT in RW database")
print("=" * 70)
print()
not_in_rw = []
matched_rw_keys = set()
for pnorm, (pname, times) in played_norm.items():
    match, score = best_match(pnorm, rw_norm.keys(), threshold=0.60)
    if match is None:
        not_in_rw.append((pname, times, score))
    else:
        matched_rw_keys.add(match)

not_in_rw.sort(key=lambda x: -x[1])
for name, times, score in not_in_rw:
    print(f"  [{times:3d}x] {name}")
print()
print(f"Total: {len(not_in_rw)} songs on Andon FM not found in RW database")


# ── 2. In RW but NOT played on Andon FM ──────────────────────────────
print()
print("=" * 70)
print("  IN RW DATABASE but NOT played on Andon FM (= missing songs?)")
print("=" * 70)
print()
not_played = []
for rnorm, rname in rw_norm.items():
    match, score = best_match(rnorm, played_norm.keys(), threshold=0.60)
    if match is None:
        not_played.append((rname, score))

for name, score in sorted(not_played):
    print(f"  {name}")
print()
print(f"Total: {len(not_played)} RW songs not matched on Andon FM")


# ── 3. Uncertain matches ─────────────────────────────────────────────
print()
print("=" * 70)
print("  UNCERTAIN MATCHES (0.45-0.60) -- manual check needed")
print("=" * 70)
print()
seen = set()
for pnorm, (pname, times) in played_norm.items():
    match, score = best_match(pnorm, rw_norm.keys(), threshold=0.45)
    if match and score < 0.60:
        key = f"{pname}|{rw_norm[match]}"
        if key not in seen:
            seen.add(key)
            print(f"  Played: {pname}")
            print(f"  RW:     {rw_norm[match]}")
            print(f"  Score:  {score:.2f}")
            print()
for rnorm, rname in rw_norm.items():
    match, score = best_match(rnorm, played_norm.keys(), threshold=0.45)
    if match and score < 0.60:
        key = f"{played_norm[match][0]}|{rname}"
        if key not in seen:
            seen.add(key)
            print(f"  RW:     {rname}")
            print(f"  Played: {played_norm[match][0]}")
            print(f"  Score:  {score:.2f}")
            print()
