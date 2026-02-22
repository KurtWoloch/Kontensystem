# -*- coding: latin-1 -*-
"""
Windowlog Corrector - Iteratively improved auto-correction for Kurt's Windowlog files.

Usage:
    python windowlog_corrector.py <windowlog_file> [--date YYYY-MM-DD] [--summary]

Reads a Windowlog file, applies correction rules, and outputs a corrected version.
With --date, only processes that specific date.
With --summary, shows a per-activity time summary after corrections.

Rules are accumulated over time by reviewing days with Kurt.
Each rule has an optional valid_from/valid_to date range.
"""

import sys
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================================================
# CORRECTION RULES
# Each rule is a dict with:
#   'match': function(account, activity, window_title, timestamp) -> bool
#   'new_account': new account code (or None to keep)
#   'new_activity': new activity name (or None to keep)
#   'description': human-readable explanation
#   'valid_from': optional datetime (rule only applies from this date)
#   'valid_to': optional datetime (rule only applies until this date)
#   'keep_previous': if True, don't create new activity - keep whatever was before
# ============================================================================

RULES = [
    # --- Kahoot/Doggo stream corrections ---
    # When browsing YouTube or Streamlabs showing Kahoot stream, it's actually
    # "Scan Doggo live" (monitoring a music request stream), not YouTube/Surfen.
    # Kurt monitored this stream regularly. It eventually died when YouTube
    # kept shutting it down for copyright, and they switched to NCS-only music.
    {
        'match': lambda acc, act, title, ts: (
            act in ('Ansehen YouTube-Videos', 'div. Surfen') and
            'kahoot' in title.lower()
        ),
        'new_account': 'RA',
        'new_activity': 'Scan Doggo live',
        'description': 'Kahoot live stream -> Scan Doggo live',
        # TODO: determine valid_to date when Kurt lost interest
    },
    {
        'match': lambda acc, act, title, ts: (
            act == 'div. Surfen' and
            'streamlabs' in title.lower() and
            'stevehainesfib' in title.lower()
        ),
        'new_account': 'RA',
        'new_activity': 'Scan Doggo live',
        'description': 'stevehainesfib/Streamlabs -> Scan Doggo live',
    },

    # --- Erwachsenenvertretung (father's legal guardianship) ---
    # Any browsing related to ERWANTST documents is work for Papa's account.
    # Valid until father's death (TODO: get exact date).
    {
        'match': lambda acc, act, title, ts: (
            act == 'div. Surfen' and
            'erwantst' in title.lower()
        ),
        'new_account': 'PA',
        'new_activity': 'Bearb. Antrittsbericht Erw.vertretung Papa',
        'description': 'ERWANTST documents -> Papa Erwachsenenvertretung',
    },

    # --- Corona tracking ---
    # Checking daily Corona infection numbers on ORF
    {
        'match': lambda acc, act, title, ts: (
            act == 'div. Surfen' and
            'coronavirus' in title.lower() and
            'orf' in title.lower()
        ),
        'new_account': 'IN',
        'new_activity': 'Surfen Corona-Infektionen',
        'description': 'ORF Corona stats -> Corona tracking',
        # TODO: determine valid_to when daily reporting stopped
    },

    # --- Food/nutrition database ---
    # Browsing for food prices or ordering food items is Essensdatenbank work
    {
        'match': lambda acc, act, title, ts: (
            act == 'div. Surfen' and
            any(kw in title.lower() for kw in [
                'bestellen', 'birnen', 'obst', 'lebensmittel',
                'spar.at', 'billa.at', 'hofer.at', 'interspar',
            ]) and
            any(kw in title.lower() for kw in [
                'kaufen', 'bestellen', 'preis', 'online',
                'spar', 'billa', 'hofer', 'interspar',
                'birnen', 'obst', 'gemüse',
            ])
        ),
        'new_account': 'LE',
        'new_activity': 'Bearb. Essensdatenbank',
        'description': 'Food shopping/prices browsing -> Essensdatenbank',
    },

    # --- Forced prices correction run files stealing focus ---
    # When "KorrekturForciertePreise" or "AuswertungGegessen" files appear briefly
    # (1-2 seconds) between other activities, they're just output files stealing focus.
    # Handled specially in contextual processing (keep_previous logic).
    # But when they appear for longer with Essens* context, they're Essensplan work.
    # This is handled in the contextual pass, not here.

    # --- Bumper Car XL research ---
    # Flybar Bumper Car XL - a toy Kurt researches occasionally
    {
        'match': lambda acc, act, title, ts: (
            'bumper car' in title.lower() or
            'flybar' in title.lower()
        ),
        'new_account': 'FZ',
        'new_activity': 'Surfen Bumper Car XL',
        'description': 'Bumper Car XL research -> FZ/Surfen Bumper Car XL',
    },

    # --- running_chat.txt belongs to Scan Doggo live ---
    {
        'match': lambda acc, act, title, ts: (
            'running_chat.txt' in title
        ),
        'new_account': 'RA',
        'new_activity': 'Scan Doggo live',
        'description': 'running_chat.txt -> Scan Doggo live',
    },

    # --- Rechnung Ersoy -> Papa Erwachsenenvertretung ---
    {
        'match': lambda acc, act, title, ts: (
            'rechnung ersoy' in title.lower() or
            'rechnung ersoy' in act.lower()
        ),
        'new_account': 'PA',
        'new_activity': 'Bearb. Antrittsbericht Erw.vertretung Papa',
        'description': 'Rechnung Ersoy (maiden bill) -> Papa Erwachsenenvertretung',
    },

    # --- "Dokumente für Antrittsbericht Papa" unnamed file ---
    {
        'match': lambda acc, act, title, ts: (
            'antrittsbericht papa' in title.lower() or
            'dokumente f' in title.lower() and 'antrittsbericht' in title.lower()
        ),
        'new_account': 'PA',
        'new_activity': 'Bearb. Antrittsbericht Erw.vertretung Papa',
        'description': 'Dokumente fuer Antrittsbericht Papa -> PA',
    },

    # --- JS99'er (TI-99/4A emulator) ---
    # Online emulator for Kurt's first home computer. Usually playing "The mine".
    {
        'match': lambda acc, act, title, ts: (
            'js99' in title.lower() or
            "js99'er" in title.lower() or
            'js99er' in title.lower()
        ),
        'new_account': 'CS',
        'new_activity': "JS99'er The mine",
        'description': "JS99'er TI-99/4A emulator -> Computerspiele",
    },

    # --- Unknown Access database ---
    # When Access doesn't report which DB is open, look at the NEXT entry to
    # determine which database it is. This is handled specially in apply_rules_contextual().
    # Fallback: Essensdatenbank (most common case).
    # NOTE: This rule is the fallback; contextual lookahead is applied first.
    {
        'match': lambda acc, act, title, ts: (
            act.startswith('unbekannte Datenbank') or
            (acc == '??' and 'Microsoft Access' in title) or
            (acc == '??' and 'Sprungliste' in title)
        ),
        'new_account': 'LE',
        'new_activity': 'Bearb. Essensdatenbank',
        'description': '?? Access database -> Essensdatenbank (fallback)',
        '_is_unknown_db_fallback': True,
    },
]


def parse_line(line):
    """Parse a Windowlog line into (timestamp, account, activity, window_title, raw).
    Returns None for unparseable lines."""
    line = line.rstrip()
    if len(line) < 29:
        return None

    ts_str = line[:19].strip()
    try:
        ts = datetime.strptime(ts_str, '%d.%m.%Y %H:%M:%S')
    except ValueError:
        return None

    rest = line[28:] if len(line) > 28 else ''

    # Check for special markers
    if 'gleichzeitige Aktion' in rest:
        return {'timestamp': ts, 'type': 'marker', 'text': rest.strip(), 'raw': line}

    # Parse "ACCOUNT - ACTIVITY: WINDOW_TITLE"
    colon_pos = rest.find(':')
    if colon_pos < 0:
        return {'timestamp': ts, 'type': 'activity', 'account': '', 'activity': rest.strip(),
                'title': '', 'raw': line}

    before_colon = rest[:colon_pos].strip()
    title = rest[colon_pos + 1:].strip()

    dash_pos = before_colon.find(' - ')
    if dash_pos > 0:
        account = before_colon[:dash_pos].strip()
        activity = before_colon[dash_pos + 3:].strip()
    else:
        account = ''
        activity = before_colon

    # Apply VBA-style account remaps
    if account == 'EL':
        account = 'PA'
    elif account == 'ES':
        account = 'VE'
    elif account == 'TV':
        account = 'RA'

    return {'timestamp': ts, 'type': 'activity', 'account': account,
            'activity': activity, 'title': title, 'raw': line}


def apply_rules(entry):
    """Apply correction rules to a parsed entry. Returns (new_account, new_activity, rule_desc) or None."""
    if entry.get('type') != 'activity':
        return None

    for rule in RULES:
        # Check date bounds
        if 'valid_from' in rule and rule['valid_from'] and entry['timestamp'] < rule['valid_from']:
            continue
        if 'valid_to' in rule and rule['valid_to'] and entry['timestamp'] > rule['valid_to']:
            continue

        try:
            if rule['match'](entry['account'], entry['activity'], entry['title'], entry['timestamp']):
                new_acc = rule.get('new_account') or entry['account']
                new_act = rule.get('new_activity') or entry['activity']
                return (new_acc, new_act, rule['description'])
        except Exception:
            continue

    return None


def rebuild_line(entry, new_account, new_activity):
    """Rebuild a Windowlog line with corrected account/activity."""
    ts_str = entry['timestamp'].strftime('%d.%m.%Y %H:%M:%S')
    # Pad to match original format (28 chars before content)
    prefix = f'{ts_str}         '
    return f'{prefix}{new_account} - {new_activity}: {entry["title"]}'


def process_file(filepath, target_date=None, show_summary=False):
    """Process a Windowlog file and output corrected version."""
    corrections = defaultdict(int)
    activity_times = defaultdict(lambda: timedelta())

    entries = []
    with open(filepath, encoding='latin-1') as f:
        for line in f:
            entry = parse_line(line)
            if entry is None:
                continue
            if target_date and entry['timestamp'].date() != target_date:
                continue
            entries.append(entry)

    # ======================================================================
    # CONTEXTUAL PRE-PASS: Fix entries that depend on surrounding context
    # ======================================================================
    correction_log_pre = []

    # 1. "no_activity: idle" -> attribute to previous activity
    for i, entry in enumerate(entries):
        if (entry.get('type') == 'activity' and
            (entry.get('activity') == 'no_activity' or
             (entry.get('account', '') == '' and 'no_activity' in entry.get('raw', '')))):
            # Find previous real activity
            for j in range(i - 1, -1, -1):
                prev = entries[j]
                if prev.get('type') == 'activity' and prev.get('account', '') not in ('', '??'):
                    entry['account'] = prev['account']
                    entry['activity'] = prev['activity']
                    entry['raw'] = rebuild_line(entry, prev['account'], prev['activity'])
                    correction_log_pre.append(
                        f'  {entry["timestamp"].strftime("%H:%M:%S")} no_activity -> {prev["account"]}/{prev["activity"]} [attributed to previous activity]')
                    break

    # 2. KorrekturForciertePreise / AuswertungGegessen focus-stealing:
    #    PAIRED (both files within 2 seconds of each other) = focus steal -> keep previous
    #    SINGLE (one file alone, followed by different activity within ~60s) = actual work -> Essensdatenbank
    #    The paired pattern typically looks like:
    #      ~AuswertungGegessen...txt - Editor
    #      ~KorrekturForciertePreise...txt - Editor  (within 1-2 seconds)
    #    Then nothing Essens-related for minutes = correction run output stealing focus.
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        title = entry.get('title', '')
        is_korrektur = 'KorrekturForciertePreise' in title
        is_auswertung = 'AuswertungGegessen' in title
        if not (is_korrektur or is_auswertung):
            continue
        # Don't skip Essens* classified entries - they might be paired focus-steals
        # that happened to be classified as Essensplan by the Windowlogger

        # Check if this is PAIRED: is there another KorrekturForciertePreise/AuswertungGegessen
        # within 3 seconds in either direction?
        is_paired = False
        for j in range(max(0, i - 3), min(len(entries), i + 4)):
            if j == i:
                continue
            ne = entries[j]
            if ne.get('type') != 'activity':
                continue
            if abs((ne['timestamp'] - entry['timestamp']).total_seconds()) > 3:
                continue
            ne_title = ne.get('title', '')
            if (('KorrekturForciertePreise' in ne_title or 'AuswertungGegessen' in ne_title) and
                ne_title != title):  # different file = pair
                is_paired = True
                break

        if is_paired:
            # Paired = focus steal -> revert to previous activity
            for j in range(i - 1, -1, -1):
                prev = entries[j]
                if (prev.get('type') == 'activity' and
                    'KorrekturForciertePreise' not in prev.get('title', '') and
                    'AuswertungGegessen' not in prev.get('title', '')):
                    entry['account'] = prev['account']
                    entry['activity'] = prev['activity']
                    entry['raw'] = rebuild_line(entry, prev['account'], prev['activity'])
                    correction_log_pre.append(
                        f'  {entry["timestamp"].strftime("%H:%M:%S")} Paired focus-steal reverted to {prev["account"]}/{prev["activity"]}')
                    break
        else:
            # Single = actual work on the file -> Essensdatenbank
            entry['account'] = 'LE'
            entry['activity'] = 'Bearb. Essensdatenbank'
            entry['raw'] = rebuild_line(entry, 'LE', 'Bearb. Essensdatenbank')
            correction_log_pre.append(
                f'  {entry["timestamp"].strftime("%H:%M:%S")} Single KorrekturForciertePreise -> LE/Bearb. Essensdatenbank')

    # 3. "Bearb. unbenannte Datei" / "*Unbenannt - Editor" interspersed with Papa entries:
    #    NOTE: This is also run as a POST-pass after main rules, since many PA entries
    #    are only identified during the main pass (e.g., ERWANTST pattern matching).
    #    If unnamed file entries are near PA entries (within 8 entries each direction),
    #    attribute to PA as well. Wider radius because there may be intervening entries.
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        if not ('unbenannte Datei' in entry.get('activity', '') or
                'Unbenannt - Editor' in entry.get('title', '')):
            continue

        # Check surrounding entries for PA (within 5 minutes in either direction)
        pa_nearby = False
        for j in range(max(0, i - 20), min(len(entries), i + 21)):
            if j == i:
                continue
            ne = entries[j]
            if ne.get('type') != 'activity':
                continue
            if abs((ne['timestamp'] - entry['timestamp']).total_seconds()) > 300:
                continue  # more than 5 minutes away
            if ne.get('account') == 'PA':
                pa_nearby = True
                break
        if pa_nearby:
            entry['account'] = 'PA'
            entry['activity'] = 'Bearb. Antrittsbericht Erw.vertretung Papa'
            entry['raw'] = rebuild_line(entry, 'PA', 'Bearb. Antrittsbericht Erw.vertretung Papa')
            correction_log_pre.append(
                f'  {entry["timestamp"].strftime("%H:%M:%S")} Unbenannte Datei near PA -> PA/Bearb. Antrittsbericht')

    # 4. "Rechner" (Windows Calculator) keeping previous activity classification:
    #    If "Rechner" appears in title and the entry is "div. Surfen" but previous
    #    entry was something specific (PA, LE, etc.), revert to previous.
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        if entry.get('title', '').strip() != 'Rechner':
            continue
        if entry.get('activity') != 'div. Surfen':
            continue
        # Revert to previous real activity
        for j in range(i - 1, -1, -1):
            prev = entries[j]
            if (prev.get('type') == 'activity' and
                prev.get('account', '') not in ('', '??') and
                prev.get('activity', '') != 'div. Surfen'):
                entry['account'] = prev['account']
                entry['activity'] = prev['activity']
                entry['raw'] = rebuild_line(entry, prev['account'], prev['activity'])
                correction_log_pre.append(
                    f'  {entry["timestamp"].strftime("%H:%M:%S")} Rechner (div. Surfen) -> {prev["account"]}/{prev["activity"]}')
                break

    # 5. "Feiertage" / holiday research near Papa entries -> attribute to Papa
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        title_lower = entry.get('title', '').lower()
        if not ('feiertag' in title_lower):
            continue
        # Check if near PA entries
        pa_nearby = False
        for j in range(max(0, i - 10), min(len(entries), i + 10)):
            if j == i:
                continue
            ne = entries[j]
            if ne.get('type') == 'activity' and ne.get('account') == 'PA':
                pa_nearby = True
                break
        if pa_nearby:
            entry['account'] = 'PA'
            entry['activity'] = 'Bearb. Antrittsbericht Erw.vertretung Papa'
            entry['raw'] = rebuild_line(entry, 'PA', 'Bearb. Antrittsbericht Erw.vertretung Papa')
            correction_log_pre.append(
                f'  {entry["timestamp"].strftime("%H:%M:%S")} Feiertage research near PA -> PA/Bearb. Antrittsbericht')

    # 6. "Neuer Tab" / generic browsing near PA entries -> attribute to Papa
    #    When opening new tabs or doing Google searches near Papa work, it's research for that.
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        if entry.get('activity') != 'div. Surfen':
            continue
        title = entry.get('title', '')
        # Only match generic browsing patterns (new tab, Google search without specific terms)
        is_generic = any(p in title for p in ['Neuer Tab', 'Google und', 'Google Search und'])
        if not is_generic:
            continue
        # Check if surrounded by PA entries (within 5 entries each direction)
        pa_before = False
        pa_after = False
        for j in range(max(0, i - 5), i):
            ne = entries[j]
            if ne.get('type') == 'activity' and ne.get('account') == 'PA':
                pa_before = True
                break
        for j in range(i + 1, min(len(entries), i + 6)):
            ne = entries[j]
            if ne.get('type') == 'activity' and ne.get('account') == 'PA':
                pa_after = True
                break
        if pa_before and pa_after:
            entry['account'] = 'PA'
            entry['activity'] = 'Bearb. Antrittsbericht Erw.vertretung Papa'
            entry['raw'] = rebuild_line(entry, 'PA', 'Bearb. Antrittsbericht Erw.vertretung Papa')
            correction_log_pre.append(
                f'  {entry["timestamp"].strftime("%H:%M:%S")} Generic browsing between PA entries -> PA')

    # 7. Non-significant window titles should not change activity.
    #    Lines where the title is empty, a folder name, cmd.exe, "Programmumschaltung",
    #    or "Suche" (Windows search) should carry forward the previous activity.
    NON_SIGNIFICANT_TITLES = {'', 'Programmumschaltung', 'Suche',
                              'C:\\WINDOWS\\system32\\cmd.exe', 'Program Manager',
                              'Papa', 'Musiker', 'Explorer'}
    NON_SIGNIFICANT_PATTERNS = []  # moved to titles set
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        title = entry.get('title', '').strip()
        is_nonsig = (title in NON_SIGNIFICANT_TITLES or
                     title.endswith('\\'))
        if not is_nonsig:
            continue
        # Only override if the activity would CHANGE from previous
        if i > 0:
            prev = None
            for j in range(i - 1, -1, -1):
                if entries[j].get('type') == 'activity' and entries[j].get('title', '').strip() not in NON_SIGNIFICANT_TITLES:
                    prev = entries[j]
                    break
            if prev and (prev['account'] != entry['account'] or prev['activity'] != entry['activity']):
                old_acc, old_act = entry['account'], entry['activity']
                entry['account'] = prev['account']
                entry['activity'] = prev['activity']
                entry['raw'] = rebuild_line(entry, prev['account'], prev['activity'])
                # Don't log trivial ones to avoid noise

    # 8. TikTok continuation: if previous entry's title contained bumper car / flybar keywords
    #    and current is TikTok -> keep Bumper Car (the main rule hasn't run yet, so check title)
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        title_lower = entry.get('title', '').lower()
        if 'tiktok' not in title_lower:
            continue
        # Check if previous significant entry was about Bumper Car (by title or already corrected)
        for j in range(i - 1, max(0, i - 5) - 1, -1):
            prev = entries[j]
            if prev.get('type') != 'activity':
                continue
            prev_title = prev.get('title', '').lower()
            prev_is_bumper = (prev.get('account') == 'FZ' or
                              'bumper car' in prev_title or
                              'flybar' in prev_title)
            if prev_is_bumper:
                entry['account'] = 'FZ'
                entry['activity'] = 'Surfen Bumper Car XL'
                entry['raw'] = rebuild_line(entry, 'FZ', 'Surfen Bumper Car XL')
                correction_log_pre.append(
                    f'  {entry["timestamp"].strftime("%H:%M:%S")} TikTok after Bumper Car -> FZ/Surfen Bumper Car XL')
                break
            elif prev.get('title', '').strip() not in NON_SIGNIFICANT_TITLES:
                break  # different activity in between

    # ======================================================================
    # MAIN PASS: Apply pattern-matching rules
    # ======================================================================
    corrected_lines = []
    correction_log = correction_log_pre  # merge pre-pass log

    for i, entry in enumerate(entries):
        if entry.get('type') == 'marker':
            corrected_lines.append(entry['raw'])
            continue

        # Contextual lookahead for ?? (unknown database) entries:
        # If next Access-related entry identifies a specific database, use that instead.
        result = None
        is_unknown_db = (entry.get('type') == 'activity' and
                         (entry.get('activity', '').startswith('unbekannte Datenbank') or
                          (entry.get('account') == '??' and 'Access' in entry.get('title', ''))))
        if is_unknown_db:
            # Look ahead for the next entry that identifies a specific Access database
            for j in range(i + 1, min(i + 5, len(entries))):
                next_e = entries[j]
                if next_e.get('type') != 'activity':
                    continue
                if 'Microsoft Access' in next_e.get('title', '') and next_e.get('account', '') != '??':
                    result = (next_e['account'], next_e['activity'],
                              f'?? Access -> next DB: {next_e["account"]}/{next_e["activity"]}')
                    break
                # Stop looking if we hit a non-Access entry
                if next_e.get('account', '') not in ('??', '') and 'Access' not in next_e.get('title', ''):
                    break

        if not result:
            result = apply_rules(entry)
        if result:
            new_acc, new_act, desc = result
            new_line = rebuild_line(entry, new_acc, new_act)
            corrected_lines.append(new_line)
            key = f'{entry["account"]}/{entry["activity"]} -> {new_acc}/{new_act}'
            corrections[key] += 1
            correction_log.append(
                f'  {entry["timestamp"].strftime("%H:%M:%S")} {key} [{desc}]'
            )
            # Update entry for time tracking
            entry['account'] = new_acc
            entry['activity'] = new_act
        else:
            corrected_lines.append(entry['raw'])

        # Calculate time to next entry for summary
        if show_summary and i + 1 < len(entries):
            next_ts = entries[i + 1]['timestamp']
            duration = next_ts - entry['timestamp']
            if timedelta(0) < duration < timedelta(hours=2):  # skip unreasonable gaps
                act_key = f'{entry["account"]} - {entry["activity"]}'
                activity_times[act_key] += duration

    # ======================================================================
    # POST-PASS: Rules that need to run after main pass corrections
    # ======================================================================

    # Re-run unbenannte Datei check now that PA entries are identified
    post_corrections = 0
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        if not ('unbenannte Datei' in entry.get('activity', '') or
                'Unbenannt - Editor' in entry.get('title', '')):
            continue
        if entry.get('account') == 'PA':
            continue  # already corrected
        # Check surrounding entries for PA (within 5 minutes, using corrected data)
        pa_nearby = False
        for j in range(max(0, i - 20), min(len(entries), i + 21)):
            if j == i:
                continue
            ne = entries[j]
            if ne.get('type') != 'activity':
                continue
            if abs((ne['timestamp'] - entry['timestamp']).total_seconds()) > 300:
                continue
            if ne.get('account') == 'PA':
                pa_nearby = True
                break
        if pa_nearby:
            old_key = f'{entry["account"]}/{entry["activity"]}'
            entry['account'] = 'PA'
            entry['activity'] = 'Bearb. Antrittsbericht Erw.vertretung Papa'
            entry['raw'] = rebuild_line(entry, 'PA', 'Bearb. Antrittsbericht Erw.vertretung Papa')
            # Update the corrected_lines array too
            for ci, cl in enumerate(corrected_lines):
                if entry['timestamp'].strftime('%d.%m.%Y %H:%M:%S') in cl and 'nbenannt' in cl:
                    corrected_lines[ci] = entry['raw']
                    break
            key = f'{old_key} -> PA/Bearb. Antrittsbericht Erw.vertretung Papa'
            corrections[key] += 1
            post_corrections += 1
            correction_log.append(
                f'  {entry["timestamp"].strftime("%H:%M:%S")} {old_key} -> PA (post-pass: unbenannte Datei near PA)')

    # Re-run "Neuer Tab between PA" check with corrected data
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        if entry.get('activity') != 'div. Surfen':
            continue
        if entry.get('account') == 'PA':
            continue
        title = entry.get('title', '')
        is_generic = any(p in title for p in ['Neuer Tab', 'Google und', 'Google Search und'])
        if not is_generic:
            continue
        pa_before = False
        pa_after = False
        for j in range(max(0, i - 5), i):
            ne = entries[j]
            if ne.get('type') == 'activity' and ne.get('account') == 'PA':
                pa_before = True
                break
        for j in range(i + 1, min(len(entries), i + 6)):
            ne = entries[j]
            if ne.get('type') == 'activity' and ne.get('account') == 'PA':
                pa_after = True
                break
        if pa_before and pa_after:
            old_key = f'{entry["account"]}/{entry["activity"]}'
            entry['account'] = 'PA'
            entry['activity'] = 'Bearb. Antrittsbericht Erw.vertretung Papa'
            entry['raw'] = rebuild_line(entry, 'PA', 'Bearb. Antrittsbericht Erw.vertretung Papa')
            for ci, cl in enumerate(corrected_lines):
                if entry['timestamp'].strftime('%d.%m.%Y %H:%M:%S') in cl and any(p in cl for p in ['Neuer Tab', 'Google und', 'Google Search']):
                    corrected_lines[ci] = entry['raw']
                    break
            key = f'{old_key} -> PA/Bearb. Antrittsbericht Erw.vertretung Papa'
            corrections[key] += 1
            post_corrections += 1
            correction_log.append(
                f'  {entry["timestamp"].strftime("%H:%M:%S")} {old_key} -> PA (post-pass: generic browsing between PA)')

    # Re-run non-significant title handling with corrected data
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        title = entry.get('title', '').strip()
        is_nonsig = (title in NON_SIGNIFICANT_TITLES or title.endswith('\\'))
        if not is_nonsig:
            continue
        if i > 0:
            prev = None
            for j in range(i - 1, -1, -1):
                if entries[j].get('type') == 'activity' and entries[j].get('title', '').strip() not in NON_SIGNIFICANT_TITLES:
                    prev = entries[j]
                    break
            if prev and (prev['account'] != entry['account'] or prev['activity'] != entry['activity']):
                old_key = f'{entry["account"]}/{entry["activity"]}'
                entry['account'] = prev['account']
                entry['activity'] = prev['activity']
                entry['raw'] = rebuild_line(entry, prev['account'], prev['activity'])
                for ci, cl in enumerate(corrected_lines):
                    if entry['timestamp'].strftime('%d.%m.%Y %H:%M:%S') in cl:
                        corrected_lines[ci] = entry['raw']
                        break
                key = f'{old_key} -> {prev["account"]}/{prev["activity"]}'
                corrections[key] += 1
                post_corrections += 1

    # Re-run Feiertage near PA with corrected data
    for i, entry in enumerate(entries):
        if entry.get('type') != 'activity':
            continue
        if entry.get('account') == 'PA':
            continue
        title_lower = entry.get('title', '').lower()
        if 'feiertag' not in title_lower:
            continue
        pa_nearby = False
        for j in range(max(0, i - 10), min(len(entries), i + 11)):
            if j == i:
                continue
            ne = entries[j]
            if ne.get('type') == 'activity' and ne.get('account') == 'PA':
                pa_nearby = True
                break
        if pa_nearby:
            old_key = f'{entry["account"]}/{entry["activity"]}'
            entry['account'] = 'PA'
            entry['activity'] = 'Bearb. Antrittsbericht Erw.vertretung Papa'
            entry['raw'] = rebuild_line(entry, 'PA', 'Bearb. Antrittsbericht Erw.vertretung Papa')
            for ci, cl in enumerate(corrected_lines):
                if entry['timestamp'].strftime('%d.%m.%Y %H:%M:%S') in cl and 'feiertag' in cl.lower():
                    corrected_lines[ci] = entry['raw']
                    break
            key = f'{old_key} -> PA/Bearb. Antrittsbericht Erw.vertretung Papa'
            corrections[key] += 1
            post_corrections += 1

    if post_corrections:
        print(f'Post-pass corrections: {post_corrections}')

    # Output corrected file (drop lines with empty title after colon)
    date_str = target_date.strftime('%Y-%m-%d') if target_date else 'all'
    out_path = filepath.replace('.txt', f'_corrected_{date_str}.txt')
    dropped_empty = 0
    with open(out_path, 'w', encoding='latin-1', errors='replace') as f:
        for line in corrected_lines:
            # Drop lines where there's nothing meaningful after the colon
            colon_pos = line.find(':', 20)  # skip timestamp colon
            if colon_pos > 0:
                after_colon = line[colon_pos + 1:].strip()
                if after_colon == '' and 'gleichzeitige Aktion' not in line:
                    dropped_empty += 1
                    continue
            f.write(line + '\n')
    if dropped_empty:
        print(f'Dropped {dropped_empty} empty-title lines')

    # Print report
    print(f'Processed {len(entries)} entries for {date_str}')
    print(f'Output: {out_path}')
    print(f'\nCorrections applied: {sum(corrections.values())}')
    for key, count in sorted(corrections.items(), key=lambda x: -x[1]):
        print(f'  {count:4d}x  {key}')

    if correction_log:
        print(f'\nDetailed correction log:')
        for line in correction_log[:50]:  # limit output
            print(line)
        if len(correction_log) > 50:
            print(f'  ... and {len(correction_log) - 50} more')

    if show_summary:
        print(f'\nTime summary (after corrections):')
        for key, duration in sorted(activity_times.items(), key=lambda x: -x[1].total_seconds()):
            mins = duration.total_seconds() / 60
            if mins >= 1:
                print(f'  {mins:6.1f} min  {key}')

    # Print condensed daily view (like Aufwandserfassung)
    if show_summary and entries:
        print(f'\n{"="*80}')
        print(f'CONDENSED DAILY VIEW (Aufwandserfassung-style):')
        print(f'{"="*80}')
        print(f'{"Start":>19}  {"End":>8}  {"Dur":>6}  {"Acct":<4} {"Activity"}')
        print(f'{"-"*19}  {"-"*8}  {"-"*6}  {"-"*4} {"-"*40}')

        # Build activity blocks: merge consecutive same-account+activity entries
        blocks = []
        current_block = None
        for i, entry in enumerate(entries):
            if entry.get('type') != 'activity':
                continue
            acc = entry['account']
            act = entry['activity']

            if (current_block and
                current_block['account'] == acc and
                current_block['activity'] == act and
                (entry['timestamp'] - current_block['end']) < timedelta(hours=1)):
                current_block['end'] = entry['timestamp']
            else:
                if current_block:
                    blocks.append(current_block)
                current_block = {
                    'account': acc,
                    'activity': act,
                    'start': entry['timestamp'],
                    'end': entry['timestamp'],
                }
        if current_block:
            blocks.append(current_block)

        # Set end times: each block ends when the next begins
        for i in range(len(blocks) - 1):
            blocks[i]['end'] = blocks[i + 1]['start']

        for block in blocks:
            dur = (block['end'] - block['start']).total_seconds() / 3600
            if dur < 0.005:  # skip sub-20-second blocks
                continue
            start_str = block['start'].strftime('%d.%m.%Y %H:%M:%S')
            end_str = block['end'].strftime('%H:%M:%S')
            print(f'{start_str}  {end_str}  {dur:5.2f}h  {block["account"]:<4} {block["activity"]}')

    return corrections


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Windowlog Corrector - Auto-correct Windowlog entries')
        print()
        print('Usage: python windowlog_corrector.py <windowlog_file> [--date DD.MM.YYYY] [--summary]')
        print()
        print(f'Current rules: {len(RULES)}')
        for i, rule in enumerate(RULES):
            vf = rule.get('valid_from', '')
            vt = rule.get('valid_to', '')
            bounds = ''
            if vf or vt:
                bounds = f' [{vf or "..."} - {vt or "..."}]'
            print(f'  {i+1}. {rule["description"]}{bounds}')
        sys.exit(0)

    filepath = sys.argv[1]
    target_date = None
    show_summary = '--summary' in sys.argv

    for i, arg in enumerate(sys.argv):
        if arg == '--date' and i + 1 < len(sys.argv):
            try:
                target_date = datetime.strptime(sys.argv[i + 1], '%d.%m.%Y').date()
            except ValueError:
                try:
                    target_date = datetime.strptime(sys.argv[i + 1], '%Y-%m-%d').date()
                except ValueError:
                    print(f'Cannot parse date: {sys.argv[i + 1]}')
                    sys.exit(1)

    process_file(filepath, target_date, show_summary)
