# Tagesplanung — Reaktiver Planer (Iteration 1)

Reaktives Tagesplanungstool nach dem Vorbild des alten VB5 Checklisten-Programms.

## Starten

```
cd C:\Users\kurt_\.openclaw\workspace\kontensystem
py planner/main.py
```

## Funktionsumfang (Iteration 1)

- **Startup-Dialog:** Tagestyp automatisch erkannt (Wochentag), optional Feiertag/Urlaubstag/Jause
- **CSV-Parsing:** `Planungsaktivitaeten.csv` (Windows-1252, Semikolon, deutsche Dezimalzahlen)
- **Reaktive Listen:** 13 Listen, sequenziell, gleichzeitig aktiv
- **Start mit** `Liste_Morgentoilette`; weitere Listen werden per `Start list X`-Befehlen aktiviert
- **Prioritätsauswahl:** Höchste Priorität aus allen aktiven Listen wird angezeigt
- **Buttons:** Erledigt / Überspringen / Pause
- **Wait-Handling:** `Wait N` blockiert Liste für N Minuten; `Wait until top of hour` bis zur vollen Stunde
- **Fixzeit-Items:** Werden zurückgestellt bis die Uhrzeit erreicht ist
- **Log:** JSON-Protokoll in `logs/planner-log-YYYY-MM-DD.json`

## Module

| Datei              | Inhalt                                          |
|--------------------|------------------------------------------------|
| `main.py`          | Einstiegspunkt, Fenster-Init                   |
| `startup_dialog.py`| Startup-Konfigurationsdialog                   |
| `gui.py`           | tkinter-GUI                                    |
| `engine.py`        | Reaktive Planungs-Engine                       |
| `csv_parser.py`    | CSV-Parser                                     |
| `day_context.py`   | Tagestyp-Logik & Bedingungsauswertung          |
| `models.py`        | Datenklassen                                   |

## Geplant für Iteration 2

- Manuelle Listenaktivierung im UI
- Estimated end-time Berechnung
- Ablauf-Export (TXT-Format wie C#-Planung)
- Springen zu einer bestimmten Uhrzeit / vorspulen
- Konfigurationsdatei für den CSV-Pfad
