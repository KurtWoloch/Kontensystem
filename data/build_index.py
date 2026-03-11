#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build documentation index from scanned files."""

import json
import os
from datetime import datetime

# All found documents (path, size_bytes, last_modified, account_prefix, notes)
docs_raw = [
    # I:\Daten\ - Dokumentation*.doc
    (r"I:\Daten\Amiga\Dokumentation des Amiga-Kontos 11.1.26.doc", 49664, "2011-01-27", "AM", ""),
    (r"I:\Daten\Ausfluege\Dokumentation des Ausflugskontos 10.8.27.doc", 68608, "2010-08-28", "AF", ""),
    (r"I:\Daten\Ausfluege\Dokumentation des Ausflugskontos Entwicklungsdokument.doc", 125440, "2010-08-27", "AF", "Entwicklungsdokument"),
    (r"I:\Daten\Ausfluege\Dokumentation des Ausflugskontos Status Quo.doc", 86528, "2010-08-21", "AF", "Status Quo"),
    (r"I:\Daten\Ausfluege\Dokumentation des Ausflugskontos.doc", 115200, "2007-04-06", "AF", "Original version"),
    (r"I:\Daten\Ausflüge\Dokumentation des Ausflugskontos.doc", 115200, "2007-04-07", "AF", "Duplicate folder (encoding variant)"),
    (r"I:\Daten\Ausflüge\Dokumentation Karaoke-Lokalbesuche Kurt - Elfi.doc", 26112, "2006-09-27", "AF", "Karaoke-Lokalbesuche"),
    (r"I:\Daten\BRZ\Dokumentation BRZG 11.11.9.doc", 47616, "2011-11-09", "BR", ""),
    (r"I:\Daten\BRZ\Dokumentation BRZG 7.6.16.doc", 50176, "2007-06-28", "BR", ""),
    (r"I:\Daten\cdg\Dokumentation CD+G-Konto 10.9.16.doc", 47104, "2012-07-21", "CG", ""),
    (r"I:\Daten\cdg\Dokumentation CD+G-Konto 15.1.3.doc", 47104, "2015-01-03", "CG", ""),
    (r"I:\Daten\Computerspiele\Dokumentation Computerspiele 10.9.15.doc", 57344, "2010-09-17", "CS", ""),
    (r"I:\Daten\Computerspiele\Dokumentation zu Gate-Empire.doc", 98304, "2008-11-06", "CS", "Game-specific doc"),
    (r"I:\Daten\Eltern\Bilder+Dokumente\Dokumentation des Eltern-Kontos 10.10.30.doc", 54272, "2010-10-30", "EL", "Duplicate in subfolder"),
    (r"I:\Daten\Eltern\Dokumentation des Eltern-Kontos 10.10.30.doc", 54272, "2010-10-30", "EL", ""),
    (r"I:\Daten\Erwins Schwestern\Dokumentation des Kontos Erwins Schwestern 11.1.1.doc", 35840, "2010-11-01", "ES", ""),
    (r"I:\Daten\Fahrzeug\Dokumentation Fahrzeug 10.9.22.doc", 156160, "2010-10-09", "FA", ""),
    (r"I:\Daten\Fahrzeug\Dokumentation Fahrzeug 11.11.9.doc", 79872, "2011-11-13", "FA", ""),
    (r"I:\Daten\Finanz\Berechnungen\Dokumentation der Veranlagung vom Juli 2011.doc", 30720, "2011-08-02", "FI", "Duplicate in Berechnungen subfolder"),
    (r"I:\Daten\Finanz\Dokumente\Dokumentation der Veranlagung vom Juli 2011.doc", 30720, "2011-08-02", "FI", ""),
    (r"I:\Daten\Finanz\Dokumente\Dokumentation der Veranlagung vom Oktober 2009.doc", 32768, "2009-10-05", "FI", ""),
    (r"I:\Daten\Finanz\Dokumente\Dokumentation Finanzverwaltung 13.5.18.doc", 89600, "2013-05-20", "FI", ""),
    (r"I:\Daten\Finanz\Dokumente\Dokumentation Finanzverwaltung 14.12.26.doc", 85504, "2014-12-30", "FI", ""),
    (r"I:\Daten\Finanz\Dokumente\Dokumentation Finanzverwaltung 7.5.29.doc", 90624, "2007-06-01", "FI", ""),
    (r"I:\Daten\Finanz\Dokumente\Dokumentation Finanzverwaltung.doc", 112128, "2007-04-09", "FI", "Original version"),
    (r"I:\Daten\Finanz\Dokumentation der Veranlagung vom Oktober 2009.doc", 32768, "2009-10-05", "FI", "Duplicate in root Finanz"),
    (r"I:\Daten\Geräteversicherung\Dokumentation des Geräteversicherungskontos 11.1.27.doc", 46080, "2011-01-28", "GV", ""),
    (r"I:\Daten\Gesundheit\Dokumentation aktueller Probleme 10.10.2.doc", 45056, "2010-10-03", "GE", ""),
    (r"I:\Daten\Gesundheit\Dokumentation aktueller Probleme 11.7.29.doc", 64000, "2011-07-31", "GE", ""),
    (r"I:\Daten\Gesundheit\Dokumentation der Psychotherapie von Kurt Woloch ab 31.doc", 95744, "2010-09-25", "GE", "Psychotherapy documentation"),
    (r"I:\Daten\Gesundheit\Dokumentation Gesundheitskonto 11.11.9.doc", 40448, "2011-11-09", "GE", ""),
    (r"I:\Daten\historische Aufnahmen\Dokumentation historische Aufnahmen 10.10.26.doc", 55296, "2010-10-29", "HA", ""),
    (r"I:\Daten\Hitparadenlistung\Dokumentation des Hitparadenlistungskontos 11.1.23.doc", 43520, "2011-01-26", "HL", ""),
    (r"I:\Daten\Internet\Dokumentation Internet 9.5.17.doc", 46592, "2009-05-18", "IN", ""),
    (r"I:\Daten\Karaoke-Sänger\Dokumentation des Karaoke-Sänger-Kontos 10.10.30.doc", 68608, "2010-11-01", "KS", ""),
    (r"I:\Daten\Karaoke-Videos\Dokumentation Karaoke-Videos 10.10.9.doc", 156160, "2010-10-24", "KV", ""),
    (r"I:\Daten\Keyboard Funkmikrofon\Dokumentation Kauf eines Funkmikrofons.doc", 56320, "2015-03-06", "KF", ""),
    (r"I:\Daten\Kontensystem\Dokumentation des Kontensystems 8.9.27.doc", 80384, "2008-09-27", "KO", ""),
    (r"I:\Daten\Kontenverwaltung\Dokumentation des Kontensystems 14.8.6.doc", 75776, "2014-08-07", "KO", ""),
    (r"I:\Daten\Kontenverwaltung\Dokumentation des Kontensystems 8.9.27.doc", 80384, "2008-09-27", "KO", "Duplicate in Kontenverwaltung"),
    # Lebenserhaltung docs
    (r"I:\Daten\Lebenserhaltung\Dokumentation der Wohnungsverwaltung 13.7.28.doc", 99328, "2013-07-28", "LE", "Wohnungsverwaltung sub-doc"),
    (r"I:\Daten\Lebenserhaltung\Dokumentation des Mittagessens am Arbeitsplatz (Kurzfassung).doc", 29184, "2008-04-30", "LE", "Kurzfassung"),
    (r"I:\Daten\Lebenserhaltung\Dokumentation des Mittagessens an Arbeitstagen 11.11.18.doc", 38912, "2011-11-18", "LE", ""),
    (r"I:\Daten\Lebenserhaltung\Dokumentation des Mittagessens an Arbeitstagen 8.10.23.doc", 49152, "2008-11-02", "LE", ""),
    (r"I:\Daten\Lebenserhaltung\Dokumentation des Mittagessens an Arbeitstagen 8.10.5.doc", 37888, "2008-10-08", "LE", ""),
    (r"I:\Daten\Lebenserhaltung\Dokumentation Lebenserhaltung (Abrechnung) 10.08.6.doc", 136192, "2010-08-06", "LE", "Abrechnung version"),
    (r"I:\Daten\Lebenserhaltung\Dokumentation Lebenserhaltung (Abrechnung) 7.09.28.doc", 128512, "2008-10-09", "LE", "Abrechnung version"),
    # Literatur
    (r"I:\Daten\Literatur\Dokumentation Literatur 10.8.28.doc", 52224, "2010-08-28", "LI", ""),
    (r"I:\Daten\Literatur\Dokumentation Literatur 11.10.19.doc", 55296, "2011-11-12", "LI", ""),
    (r"I:\Daten\Literatur\Dokumentation Literatur 11.11.12.doc", 55296, "2011-11-12", "LI", ""),
    (r"I:\Daten\Literatur\Dokumentation Literatur 11.6.19.doc", 55808, "2011-06-19", "LI", ""),
    (r"I:\Daten\Literatur\Dokumentation Literatur 11.6.4.doc", 54784, "2011-06-04", "LI", ""),
    (r"I:\Daten\Literatur\Dokumentation Literatur 11.8.3.doc", 54784, "2011-08-04", "LI", ""),
    (r"I:\Daten\Literatur\Dokumentation Literatur 8.10.24.doc", 60416, "2009-08-09", "LI", ""),
    (r"I:\Daten\Literatur\Dokumentation Literatur 9.8.14.doc", 50688, "2009-08-15", "LI", ""),
    # Musiker
    (r"I:\Daten\Musiker\Dokumentation Kauf neues Keyboard und Funkmikrofone.doc", 100864, "2015-02-03", "MU", "Purchase doc"),
    (r"I:\Daten\Musiker\Dokumentation Musiker 10.8.29.doc", 83456, "2010-09-11", "MU", ""),
    (r"I:\Daten\Musiker\Dokumentation Musiker.doc", 80896, "2010-08-28", "MU", "Original version"),
    # Others
    (r"I:\Daten\Musiktexte\Dokumentation des Musiktexte-Kontos 10.11.1.doc", 44544, "2010-11-01", "MT", ""),
    (r"I:\Daten\Myslik\Dokumentation des Myslik-Kontos 11.1.1.doc", 36352, "2011-01-23", "MY", ""),
    (r"I:\Daten\Orange\Dokumentation Orange 94.0 10.9.19.doc", 67072, "2010-09-19", "OR", "Radio Orange"),
    (r"I:\Daten\PC\Dokumentation PC 10.12.28.doc", 90624, "2010-12-28", "PC", ""),
    (r"I:\Daten\PC\Dokumentation PC 10.9.11.doc", 92160, "2010-09-12", "PC", ""),
    (r"I:\Daten\PC\Dokumentation PC 11.7.18.doc", 95232, "2011-07-18", "PC", ""),
    (r"I:\Daten\PC\Dokumentation zum Kauf eines tragbaren PC's Nov.2011.doc", 94208, "2013-09-26", "PC", "Laptop purchase"),
    (r"I:\Daten\PC\Dokumentation zum PC-Kauf Nov.2007 7.12.25.doc", 131072, "2007-12-25", "PC", ""),
    (r"I:\Daten\PC\Dokumentation zum PC-Kauf Nov.2007.doc", 165376, "2008-01-04", "PC", "Original"),
    # Radio Würmchen
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Chattertreffen JBH Sommer 2010.doc", 30720, "2010-08-04", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Datenbank Radio Würmchen 10.9.25.doc", 284672, "2010-09-25", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Datenbank Radio Würmchen 7.10.1.doc", 286720, "2010-08-13", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Datenbank Radio Würmchen Status Quo.doc", 54784, "2009-10-01", "RW", "Status Quo"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Lebensbereich Radio Würmchen 7.9.28.doc", 398848, "2008-09-28", "RW", "Largest RW doc"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Lebensbereich Radio Würmchen 8.10.18.doc", 50688, "2009-09-21", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Lebensbereich Radio Würmchen 9.9.21.doc", 48128, "2009-10-01", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Musikversorgung Radio Würmchen Hauptaktivitäten 9.1.2.doc", 61440, "2009-09-17", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Musikversorgung Radio Würmchen Hauptaktivitäten 9.9.21.doc", 61952, "2009-09-21", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Musikversorgung Radio Würmchen Hauptaktivitäten Entwicklungsdokument 9.9.20.doc", 150016, "2009-09-21", "RW", "Entwicklungsdokument"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Musikversorgung Radio Würmchen Hauptaktivitäten Entwicklungsdokument 9.9.26.doc", 60928, "2009-09-27", "RW", "Entwicklungsdokument"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Musikversorgung Radio Würmchen Hauptaktivitäten Entwicklungsdokument.doc", 151040, "2009-09-19", "RW", "Entwicklungsdokument original"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Musikversorgung Radio Würmchen Hauptaktivitäten Status Quo.doc", 45568, "2008-12-29", "RW", "Status Quo"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Musikversorgung Radio Würmchen unterstützende Aktivitäten Status Quo.doc", 61440, "2009-09-23", "RW", "Status Quo"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Radio Würmchen Karaoke 10.8.14.doc", 53760, "2010-08-14", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Radio Würmchen Karaoke Entwicklungsdokument 10.8.14.doc", 78336, "2010-08-14", "RW", "Entwicklungsdokument"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Radio Würmchen Karaoke Status Quo.doc", 48640, "2010-08-14", "RW", "Status Quo"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Radio Würmchen weitere Aktivitäten 10.8.18.doc", 41984, "2010-08-18", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Radio Würmchen weitere Aktivitäten Entwicklungsdokument 10.8.15.doc", 49664, "2010-08-18", "RW", "Entwicklungsdokument"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation Radio Würmchen weitere Aktivitäten Status Quo.doc", 45568, "2010-08-15", "RW", "Status Quo"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation unterstützende Aktivitäten Radio Würmchen 9.9.28.doc", 73728, "2009-09-30", "RW", ""),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation unterstützende Aktivitäten Radio Würmchen Entwicklungsdokument 9.9.24.doc", 137216, "2009-09-26", "RW", "Entwicklungsdokument"),
    (r"I:\Daten\Radio Würmchen\Dokumentationen\Dokumentation unterstützende Aktivitäten Radio Würmchen Entwicklungsdokument.doc", 294400, "2009-09-24", "RW", "Entwicklungsdokument original"),
    # Radio & Fernsehen
    (r"I:\Daten\Radio & Fernsehen\Radio hören\Dokumentation Radio hören 11.11.9.doc", 35328, "2011-11-09", "RF", "Duplicate in subfolder"),
    (r"I:\Daten\Radio & Fernsehen\Dokumentation Fernsehen 10.10.9.doc", 41984, "2010-10-09", "RF", ""),
    (r"I:\Daten\Radio & Fernsehen\Dokumentation Radio hören 11.11.9.doc", 35328, "2011-11-09", "RF", ""),
    # Tonträger
    (r"I:\Daten\Tonträger\Dokumentation Tonträger 10.9.19.doc", 42496, "2010-09-20", "TT", ""),
    # Wohnungsverwaltung
    (r"I:\Daten\Wohnungsverwaltung\Dokumentation der Hausratverwaltung 21.7.2025.doc", 44544, "2025-07-21", "WV", "Recent 2025"),
    (r"I:\Daten\Wohnungsverwaltung\Dokumentation der Papier- und Datenverwaltung 21.7.2025.doc", 38400, "2025-07-21", "WV", "Recent 2025"),
    (r"I:\Daten\Wohnungsverwaltung\Dokumentation der Wohnungsverwaltung 8.9.28.doc", 101376, "2008-09-28", "WV", ""),
    (r"I:\Daten\Wohnungsverwaltung\Dokumentation zur Papiersortierung November 2007.doc", 25088, "2007-11-17", "WV", "SMALLEST file"),
    # Lebensdokumentation (Lebenserhaltung)
    (r"I:\Daten\Lebenserhaltung\Lebensdokumentation 8.9.27.doc", 179200, "2008-09-27", "LE", "Life documentation"),
    # Betrieb files
    (r"C:\Users\kurt_\Betrieb\Papa\Dokumentation des Todes von Erwin Woloch (V2).doc", 416768, "2025-04-21", "PA", "Death documentation for Papa"),
    (r"C:\Users\kurt_\Betrieb\Gesundheit\Untersuchung der Prioritätenliste.doc", 2373120, "2026-01-18", "GE", "Priority list analysis (Gesundheit copy)"),
    (r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Untersuchung der Prioritätenliste 5.4.2023.pdf", 1167907, "2023-04-05", "KW", "PDF version 2023-04-05"),
    (r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Untersuchung der Prioritätenliste.doc", 2373120, "2026-03-01", "KW", "Priority list analysis - current"),
    (r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Untersuchung der Prioritätenliste.pdf", 1167987, "2023-05-13", "KW", "PDF version"),
    (r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Untersuchung der Prioritätenliste.txt", 460295, "2024-10-02", "KW", "TXT version"),
    (r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Daten Mitte 2022-1.4.2023\Untersuchung der Prioritätenliste.doc", 2675200, "2023-03-21", "KW", "Historical version 2022-2023"),
    (r"C:\Users\kurt_\Betrieb\Kontenverwaltung\Checklisten_Winlogger\KURTDOKU.txt", 109625, "2006-04-12", "KW", "Kurt's personal documentation checklist"),
]

# Build JSONL
output_dir = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\data"
jsonl_path = os.path.join(output_dir, "documentation_index.jsonl")
txt_path = os.path.join(output_dir, "documentation_index.txt")

entries = []
for i, (path, size_bytes, last_mod, prefix, notes) in enumerate(docs_raw, 1):
    filename = os.path.basename(path)
    # Determine title (filename without extension)
    title = os.path.splitext(filename)[0]
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    fmt = ext if ext else "unknown"
    
    entry = {
        "doc_id": f"DOC{i:03d}",
        "title": title,
        "path": path,
        "format": fmt,
        "size_kb": round(size_bytes / 1024, 1),
        "last_modified": last_mod,
        "account_prefix": prefix,
        "status": "found",
        "notes": notes
    }
    entries.append(entry)

# Write JSONL
with open(jsonl_path, "w", encoding="utf-8") as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

print(f"Written {len(entries)} entries to {jsonl_path}")

# Write human-readable TXT
with open(txt_path, "w", encoding="utf-8") as f:
    f.write("DOCUMENTATION INDEX\n")
    f.write("===================\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"Total documents: {len(entries)}\n\n")
    
    # Group by account_prefix
    from collections import defaultdict
    by_prefix = defaultdict(list)
    for e in entries:
        by_prefix[e['account_prefix']].append(e)
    
    prefix_names = {
        "AM": "Amiga", "AF": "Ausflüge", "BR": "BRZ", "CG": "CD+G",
        "CS": "Computerspiele", "EL": "Eltern", "ES": "Erwins Schwestern",
        "FA": "Fahrzeug", "FI": "Finanz", "GV": "Geräteversicherung",
        "GE": "Gesundheit", "HA": "Historische Aufnahmen", "HL": "Hitparadenlistung",
        "IN": "Internet", "KS": "Karaoke-Sänger", "KV": "Karaoke-Videos",
        "KF": "Keyboard/Funkmikrofon", "KO": "Kontensystem", "KW": "Kontenverwaltung/Betrieb",
        "LE": "Lebenserhaltung", "LI": "Literatur", "MU": "Musiker",
        "MT": "Musiktexte", "MY": "Myslik", "OR": "Orange Radio",
        "PA": "Papa", "PC": "PC", "RF": "Radio & Fernsehen",
        "RW": "Radio Würmchen", "TT": "Tonträger", "WV": "Wohnungsverwaltung"
    }
    
    for prefix in sorted(by_prefix.keys()):
        area_name = prefix_names.get(prefix, prefix)
        docs = by_prefix[prefix]
        f.write(f"\n[{prefix}] {area_name} ({len(docs)} docs)\n")
        f.write("-" * 60 + "\n")
        for e in sorted(docs, key=lambda x: x['last_modified']):
            f.write(f"  {e['doc_id']}  {e['size_kb']:>8.1f} KB  {e['last_modified']}  {e['title'][:60]}\n")
            if e['notes']:
                f.write(f"         NOTE: {e['notes']}\n")

    f.write("\n\n--- ACCOUNT PREFIX SUMMARY ---\n")
    for prefix in sorted(by_prefix.keys()):
        area_name = prefix_names.get(prefix, prefix)
        count = len(by_prefix[prefix])
        f.write(f"  {prefix}  {area_name:<35}  {count} docs\n")

print(f"Written summary to {txt_path}")
print("\n--- STATISTICS ---")
print(f"Total documents: {len(entries)}")
by_fmt = defaultdict(int)
for e in entries:
    by_fmt[e['format']] += 1
for fmt, cnt in sorted(by_fmt.items()):
    print(f"  .{fmt}: {cnt}")
print(f"\nSmallest file: {min(entries, key=lambda x: x['size_kb'])['path']} ({min(entries, key=lambda x: x['size_kb'])['size_kb']} KB)")
print(f"Largest file: {max(entries, key=lambda x: x['size_kb'])['path']} ({max(entries, key=lambda x: x['size_kb'])['size_kb']} KB)")
