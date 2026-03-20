# Tagesplanung — Reaktiver Planer

Reaktives Tagesplanungstool in Python/tkinter. Inspiriert vom Radio-Playout-System
bei 88.6 (2005/2006): Planung = Playlist am Tagesbeginn, Ablauf = Änderungen
während des Tages.

## Starten

```
cd C:\Users\kurt_\.openclaw\workspace\kontensystem
py planner/main.py
```

## Module

| Datei | Inhalt |
|---|---|
| `main.py` | Einstiegspunkt: Startup-Dialog → CSV → Engine → Projektion → Log laden → GUI |
| `engine.py` | Kern-Logik: Listen, Kandidaten, Scheduling, Log, Projektions-Simulation |
| `gui.py` | tkinter-GUI: Aktueller Task, Queue (Live + Restplan), Erledigt-Panel, Dialoge |
| `models.py` | Datenklassen: `CsvRow`, `ListState`, `CompletedItem`, `RowType` |
| `csv_parser.py` | Liest `Planungsaktivitaeten.csv` (Win-1252, Semikolon) |
| `startup_dialog.py` | Erster Dialog: Tagestyp, YAML-Overrides, Early Work |
| `day_context.py` | Tagestyp-Flags (Bürotag, Teleworking, etc.), Bedingungsauswertung |
| `code_suggest.py` | 6-stellige Task-Code-Vorschläge aus Master Task List |
| `automations.py` | Laden + Ausführen von Automationen (Shell/URL) per Aktivitäts-Match |
| `automation_editor.py` | tkinter-Editor für `automations.json` |
| `yaml_loader.py` | Lädt `schedule_exceptions.yaml` für datumsspezifische Overrides |
| `day_report.py` | Tagesbericht-Generierung (Projektion vs. Log) |
| `window_monitor.py` | Fenster-Überwachung: pollt aktives Fenster, schreibt JSONL-Log |
| `windowmon_import.py` | Nacherfassung: JSONL → AutoDetect → Block-Konsolidierung → Import-GUI |

## Ausgabedateien (in `logs/`)

| Datei | Inhalt |
|---|---|
| `planner-log-YYYY-MM-DD.json` | Tages-Log (Aktivitäten mit Start/End/Kommentar) |
| `projection-YYYY-MM-DD.json` | Tagesprojektion beim Start (geplanter Idealablauf) |
| `report-YYYY-MM-DD.txt` | Tagesbericht (Zusammenfassung, Drift, Übersprungene) |
| `windowmon-YYYY-MM-DD.jsonl` | Fenster-Events (Basis für Nacherfassung) |
| `autodetect-corrections-YYYY-MM-DD.json` | Manuelle Korrekturen der AutoDetect-Klassifikation |

## Dokumentation

| Dokument | Inhalt |
|---|---|
| `docs/planner-technik.md` | **Technische Referenz**: Architektur, Datenfluss, Engine-Logik, CSV-Format, Versionshistorie |
| `docs/planner-handbuch.md` | **Benutzerhandbuch**: Bedienung, Tagestyp, Buttons, Nacherfassung |
| `docs/nacherfassung-improvements.md` | Verbesserungsvorschläge V1-V10, Baseline-Daten, erledigte Fixes |
| `docs/feature-window-monitor.md` | WindowMon-Design (4 Phasen) |
| `docs/feature-log-editing.md` | Log-Bearbeitung (Delete/Edit/Duplicate) |
| `docs/planning-unified-vision.md` | Gesamtvision Kontensystem |
| `docs/planning-history.md` | Planungsgeschichte 2007-2026 |
| `docs/answers-to-open-questions.md` | Design-Entscheidungen (März 2026) |
| `docs/analysis-checklisten.md` | Analyse des alten VB5-Checklisten-Programms |
| `docs/analysis-tagesplanung-cs.md` | Analyse des C#-Planungstools |

## Aktuelle Version: v1.7 (20. März 2026)

Letzte Änderungen:
- **V8**: Out-of-Order-Logging (beliebige Aktivität aus Queue direkt loggen)
- **V9**: Restplan-Ansicht (originale Tagesprojektion minus Erledigtes)
- **V10**: Bulk-Complete ("Bis hierher erledigt" im Restplan)

Vollständige Versionshistorie: siehe `docs/planner-technik.md` Abschnitt 5.
