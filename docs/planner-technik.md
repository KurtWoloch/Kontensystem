# Planungstool — Technische Referenz & Übergangsdokumentation

**Version:** v1.7.1 (Stand: 21. März 2026)

---

## 1. Architektur

### Modulübersicht

```
planner/
├── main.py              # Einstiegspunkt, Startup-Sequenz, Projektion speichern
├── engine.py            # Kern-Logik: Listen, Kandidaten, Scheduling, Log
├── gui.py               # tkinter-Benutzeroberfläche (inkl. Restplan-Ansicht)
├── models.py            # Datenklassen (CsvRow, ListState, CompletedItem, RowType)
├── csv_parser.py        # Liest und parst Planungsaktivitaeten.csv
├── startup_dialog.py    # Erster Dialog (Tagestyp-Konfiguration)
├── day_context.py       # Tagestyp-Logik, Bedingungsauswertung
├── code_suggest.py      # Code-Vorschläge aus Master Task List
├── automations.py       # Laden, Zuordnen, Ausführen von Automationen
├── automation_editor.py # tkinter-Editor für automations.json
├── yaml_loader.py       # Laden von schedule_exceptions.yaml
├── day_report.py        # Tagesbericht-Generierung (Projektion vs. Log)
├── window_monitor.py    # Fenster-Überwachung (aktives Fenster → JSONL-Log)
├── windowmon_import.py  # Nacherfassung: JSONL → Aktivitätsblöcke → GUI-Dialog
├── test_engine.py       # Unit-Tests für die Engine
└── test_parse.py        # Unit-Tests für den CSV-Parser
```

### Modulverantwortlichkeiten

| Modul | Verantwortung |
|---|---|
| `main.py` | Startet alles: Dialog → CSV → Engine → Projektion → Log laden → GUI |
| `engine.py` | Der eigentliche Planer: verwaltet Listen, wählt Kandidaten, schreibt Logs, simuliert Projektion |
| `gui.py` | Zeichnet die Oberfläche, ruft Engine-Methoden auf, öffnet Dialoge |
| `models.py` | Reine Datenstrukturen, keine Logik |
| `csv_parser.py` | Liest die CSV, erkennt Row-Typen, gibt Dict[ListName → [CsvRow]] zurück |
| `startup_dialog.py` | Zeigt den Startdialog, gibt `DayContext` + YAML-Overrides zurück |
| `day_context.py` | Berechnet alle Tagestyp-Flags (Bürotag, Teleworking, Putztag, …), wertet Bedingungen aus |
| `code_suggest.py` | Durchsucht Master Task List nach passenden 6-stelligen Codes |
| `automations.py` | Lädt `automations.json`, findet Automation für eine Aktivität, startet sie |
| `automation_editor.py` | CRUD-Editor für `automations.json` |
| `yaml_loader.py` | Lädt `schedule_exceptions.yaml`, gibt Overrides für ein Datum zurück |
| `day_report.py` | Vergleicht `projection-*.json` mit `planner-log-*.json`, erzeugt Bericht |
| `window_monitor.py` | Pollt alle 1s das aktive Fenster (Win32 API), schreibt JSONL-Log, erkennt Idle/Off-PC |
| `windowmon_import.py` | Liest windowmon-JSONL, klassifiziert Blöcke (AutoDetect), bietet Nacherfassungs-GUI |

### Datenfluss beim Start

```
main.py
  └── show_startup_dialog()          → DayContext, yaml_overrides
  └── parse_csv()                    → Dict[str, List[CsvRow]]
  └── PlannerEngine(raw_lists, ctx)  → Engine-Objekt
        └── _apply_yaml_overrides()  (earlyWorkStart, removeActivities, addEvents)
        └── Liste_Morgentoilette.active = True
        └── Auto-activate lists mit fixed-time rows
        └── _resolve() für jede aktive Liste
  └── save_initial_projection()      → logs/projection-YYYY-MM-DD.json
  └── engine.load_log()              → stellt Zustand aus Log wieder her
  └── PlannerGUI(root, engine)       → Hauptfenster
```

### Datenfluss im laufenden Betrieb

```
GUI-Tick (alle 10s): engine.tick() → entsperrt wartende Listen
GUI-Refresh (alle 15s): 
    engine.get_best_candidate()     → zeigt aktuelle Aufgabe
    engine.get_day_projection()     → zeigt Queue
    engine.get_completed_log()      → zeigt Erledigt-Panel

Nutzeraktion "Erledigt":
    engine.mark_done(ls, row, ...)  → schreibt CompletedItem ins Log
    engine._resolve(ls)             → setzt current_activity für nächste Aufgabe
    GUI-Refresh
```

---

## 2. Dateien und Verzeichnisse

### 2.1 Eingabedateien (gelesen, nicht geschrieben)

#### `Planungsaktivitaeten.csv`

```
Pfad: C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Planungsaktivitaeten.csv
Encoding: Windows-1252
Trennzeichen: Semikolon (;)
```

Die Hauptplanungsdatei. Jede Zeile ist eine Aktivität oder ein Steuerungs-Eintrag. Detailliertes Format: siehe Abschnitt 4.

#### `schedule_exceptions.yaml`

```
Pfad: C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\schedule_exceptions.yaml
```

Optionale Datei mit datumsspezifischen Überschreibungen (Feiertage, Urlaubstage, Sondertermine). Benötigt PyYAML. Format:

```yaml
exceptions:
  - date: "2026-12-25"
    dayTypeOverride: "Feiertag"
    specialNote: "Weihnachten"
    addEvents:
      - name: "Weihnachtsfeier"
        durationMinutes: 120
        startTime: "14:00"
    removeActivities:
      - "Schwimmbad"
  - date: "2026-04-14"
    earlyWorkStart: 2
    specialNote: "Frühschicht"
```

Felder:
- `dayTypeOverride`: `"Bürotag"`, `"Teleworking"`, `"Urlaubstag"`, `"Feiertag"`
- `specialNote`: Anzeigetext im Startup-Dialog
- `earlyWorkStart`: Stunden, um die `Liste_Arbeit` vorgezogen wird
- `addEvents`: Liste von Terminen (timed → `Liste_YAML`, untimed → an Stelle entfernter Aktivitäten eingefügt)
- `removeActivities`: Liste von Aktivitätsnamen, die aus der CSV entfernt werden

#### `data/master_task_list_v4.jsonl`

```
Pfad: C:\Users\kurt_\.openclaw\workspace\kontensystem\data\master_task_list_v4.jsonl
Format: JSON Lines (eine JSON-Objekt pro Zeile)
```

Die konsolidierte Liste aller bekannten Tasks (aus 9 Legacy-Quellen zusammengeführt). Jede Zeile:

```json
{
  "name": "2 Mails an Verwandte",
  "code": "",
  "account_prefix": "VE",
  "parent": "",
  "list": "",
  "priority": 0,
  "fixed_time": "",
  "status": "active",
  "sources": "access_Tab_Aktionen, access_Tab_Aufwandserfassung",
  "source_count": 2,
  "variant_count": 0,
  "notes": "",
  "prefix": "2 Mails an Verwandte",
  "tier": 1,
  "in_planner_csv": false,
  "planner_match_method": "",
  "planner_activity": "",
  "doc_refs": [
    {"doc_id": "DOC042", "match_type": "named", "context": "...Snippet aus der Doku..."}
  ],
  "doc_status": "documented"
}
```

#### Vollständige Feldliste

| Feld | Typ | Beschreibung |
|---|---|---|
| `name` | string | Name der Aktivität/Aufgabe |
| `code` | string | 6-stelliger Task-Code (leer wenn keiner vorhanden) |
| `account_prefix` | string | 2-stelliges Konto-Kürzel (ableitbar aus den ersten 2 Zeichen des Codes) |
| `parent` | string | Übergeordnete Aufgabe (hierarchische Zuordnung) |
| `list` | string | Name der Planer-Liste (leer wenn nicht im Planer) |
| `priority` | float | Prioritätswert |
| `fixed_time` | string | Fixe Startzeit (HH:MM oder leer) |
| `status` | string | `"active"` oder `"inactive"` |
| `sources` | string | Kommagetrennte Liste der Legacy-Quellen, aus denen der Task stammt |
| `source_count` | int | Anzahl der Quellen |
| `variant_count` | int | Anzahl bekannter Varianten/Aliase |
| `notes` | string | Freitext-Notizen |
| `prefix` | string | Vollständiger Name (oft identisch mit `name`) |
| `tier` | int | Wichtigkeitsstufe (1 = höchste) |
| `in_planner_csv` | bool | Ob der Task in der aktuellen Planungsaktivitaeten.csv vorkommt |
| `planner_match_method` | string | Wie der Task zur CSV zugeordnet wurde (code, name, etc.) |
| `planner_activity` | string | Der CSV-Zeilentext, dem dieser Task zugeordnet ist |
| `doc_refs` | array | Verweise auf Dokumentations-Einträge (siehe unten) |
| `doc_status` | string | `"documented"`, `"mentioned"` oder `"undocumented"` |

#### Dokumentationsverweise (`doc_refs`)

Jeder Eintrag in `doc_refs` verweist auf ein Dokument in `documentation_index.jsonl`:

| Feld | Beschreibung |
|---|---|
| `doc_id` | ID des Dokuments (z.B. `"DOC042"`) |
| `match_type` | Art der Zuordnung: `"named"` (Name im Dokument gefunden), `"coded"` (Code gefunden), `"account"` (nur auf Account-Ebene) |
| `context` | Textausschnitt aus dem Dokument, der den Match zeigt |

`doc_status` wird daraus abgeleitet:
- `"documented"` = mindestens ein `named` oder `coded` Match
- `"mentioned"` = nur `account`-Level Matches (das Konto wird erwähnt, aber nicht dieser spezifische Task)
- `"undocumented"` = keine Matches

#### Dokumentations-Index (`documentation_index.jsonl`)

Separate JSONL-Datei, die alle bekannten Dokumentationsdateien katalogisiert:

```
Pfad: C:\Users\kurt_\.openclaw\workspace\kontensystem\data\documentation_index.jsonl
```

Jede Zeile beschreibt ein Dokument mit Feldern wie `doc_id`, `title`, `path`, `format`, `account_prefix`, `last_modified`, `txt_path` (extrahierte Textversion für die Volltextsuche durch `build_doc_refs.py`).

Die Zuordnung zwischen Tasks und Dokumenten wird durch `build_doc_refs.py` hergestellt, das alle Dokumenttexte nach Task-Namen und -Codes durchsucht.

Wird von `code_suggest.py` und `automation_editor.py` verwendet. Fallback auf `v3`-Datei falls `v4` nicht existiert.

### 2.2 Ausgabedateien (geschrieben)

Alle Ausgabedateien landen in:
```
C:\Users\kurt_\.openclaw\workspace\kontensystem\logs\
```

#### `planner-log-YYYY-MM-DD.json`

Das zentrale Ergebnis-Log. Wird manuell über **💾 Log speichern** geschrieben (und beim Schließen des Fensters angeboten). Format:

```json
[
  {
    "activity": "Frühstück LEMTFS",
    "list": "Liste_Morgentoilette",
    "priority": 2.1,
    "minutes": 25,
    "started_at": "07:38:00",
    "completed_at": "08:05:00",
    "skipped": false,
    "original_activity": "",
    "comment": ""
  },
  {
    "activity": "Medikamente",
    "list": "Liste_Morgentoilette",
    "priority": 2.5,
    "minutes": 5,
    "started_at": "08:05:00",
    "completed_at": "08:09:00",
    "skipped": true,
    "original_activity": "",
    "comment": "kein Bedarf heute"
  },
  {
    "activity": "E-Mails checken",
    "list": "ungeplant",
    "priority": 0.0,
    "minutes": 12,
    "started_at": "09:15:00",
    "completed_at": "09:27:00",
    "skipped": false,
    "original_activity": "",
    "comment": "dringend"
  }
]
```

Felder:
| Feld | Typ | Beschreibung |
|---|---|---|
| `activity` | string | Aktivitätsname (ggf. vom Benutzer bearbeitet) |
| `list` | string | Name der Liste (`"ungeplant"` für Adhoc-Einträge) |
| `priority` | float | Prioritätswert aus der CSV (0.0 für ungeplante) |
| `minutes` | int | Geplante Dauer in Minuten |
| `started_at` | string HH:MM:SS | Tatsächliche Startzeit |
| `completed_at` | string HH:MM:SS | Tatsächliche Endzeit |
| `skipped` | bool | `true` wenn übersprungen |
| `original_activity` | string | Original-CSV-Name, falls Benutzer die Bezeichnung geändert hat |
| `comment` | string | Optionaler Kommentar (Begründung, Notiz) |

Sortierung: chronologisch nach `started_at`. Einträge nach Mitternacht (Stunde < 5) werden auf den nächsten Kalendertag referenziert.

#### `projection-YYYY-MM-DD.json`

Einmalig beim Start gespeichert: die ideale Tagesplanung, als ob alle Aktivitäten exakt nach Plan abgearbeitet würden. Äquivalent zur alten Planung-Datei. Wird **nicht** überschrieben, wenn die Datei bereits existiert (Neustart-Schutz).

```json
[
  {
    "activity": "Frühstück",
    "list_name": "Liste_Morgentoilette",
    "minutes": 25,
    "priority": 2.1,
    "fixed_time": null,
    "est_start": "07:30",
    "est_end": "07:55",
    "state": "upcoming"
  },
  {
    "activity": "ZiB 1",
    "list_name": "Liste_Abend",
    "minutes": 30,
    "priority": 3.5,
    "fixed_time": "19:30",
    "est_start": "19:30",
    "est_end": "20:00",
    "state": "scheduled"
  }
]
```

Felder `state`: `"current"` | `"upcoming"` | `"scheduled"` (fixzeitlich).

#### `report-YYYY-MM-DD.txt`

Menschenlesbarer Tagesbericht (Plaintext). Enthält Zusammenfassung, Drift-Analyse, Übersprungene/Ungeplante/Nicht-erreichte Aktivitäten. Wird über den **📊 Tagesbericht**-Button erzeugt.

#### `windowmon-YYYY-MM-DD.jsonl`

Fenster-Überwachungs-Log (JSON Lines). Wird von `window_monitor.py` kontinuierlich geschrieben (alle 1s bei Fensterwechsel). Enthält normale Fenster-Events und Idle-Marker:

```jsonl
{"ts": "2026-03-19T09:25:31", "hwnd": 67226, "title": "OpenClaw Control ...", "process": "msedge.exe", "browser": "Edge"}
{"ts": "2026-03-19T09:26:23", "type": "idle_start", "hwnd": 0, "title": "", "process": "planner_idle", "browser": ""}
{"ts": "2026-03-19T10:24:17", "type": "idle_end", "hwnd": 0, "title": "", "process": "planner_idle", "browser": "", "idle_duration_s": 3473, "idle_start": "2026-03-19T09:26:23"}
```

Wird von `windowmon_import.py` für die Nacherfassung gelesen. Typische Größe: 100-300 KB pro Tag.

#### `autodetect-corrections-YYYY-MM-DD.json`

Manuelle Korrekturen aus der Nacherfassungs-GUI. Jede Korrektur speichert Original-Klassifikation und korrigierten Wert:

```json
[
  {"ts": "2026-03-19T07:53:52", "start": "07:15", "end": "07:17",
   "original": "Bearb. Essensplan LEEPEP",
   "corrected": "Bearb. Essensplan (gegessen) LEEPEP"}
]
```

Dient als Lernbasis für zukünftige AutoDetect-Verbesserungen. Wird nur bei Korrekturen geschrieben (nicht bei bestätigten Vorschlägen).

#### `planner-state-YYYY-MM-DD.json`

*Hinweis:* Diese Datei ist im Code referenziert, wird aber aktuell nicht aktiv verwendet. Der Zustand wird stattdessen aus dem Log rekonstruiert.

### 2.3 Weitere Dateien

#### `data/automations.json`

```json
{
  "_comment": "...",
  "automations": [
    {
      "match": "RWMPMP",
      "match_type": "code",
      "type": "shell",
      "command": "C:\\Users\\kurt_\\Musikprogramm\\Radio Würmchen.exe",
      "label": "Radio Würmchen starten"
    }
  ]
}
```

Felder:
- `match`: der Match-Wert (Code, Prefix oder Substring)
- `match_type`: `"code"` | `"prefix"` | `"contains"`
- `type`: `"shell"` | `"url"`
- `command`: Befehl/Pfad (für shell)
- `url`: URL (für url)
- `label`: optionaler Button-Text (wird als `"▶ [label]"` angezeigt)

#### `data/learned_codes.csv`

Automatisch angelegt und gepflegt von `code_suggest.py`. Speichert Codes, die beim manuellen Eingeben gelernt wurden:

```
CODE;Aktivitätsname
LEMTFS;Frühstück
KSPLPL;Tagesplanung OpenClaw
```

---

## 3. Engine-Logik

### 3.1 Listen und Aktivierung

Die Engine verwaltet mehrere `ListState`-Objekte, je eine pro Liste aus der CSV. Jede Liste hat:
- `rows`: alle CSV-Zeilen dieser Liste (in CSV-Reihenfolge)
- `current_index`: wie weit die Liste schon abgearbeitet wurde
- `active`: ob die Liste gerade Kandidaten liefert
- `wait_until`: bis wann die Liste blockiert ist (WAIT-Timer)
- `current_activity`: die aktuell vorderste Aktivität (None = erschöpft oder blockiert)

**Aktivierung beim Start:**
- `Liste_Morgentoilette` → immer automatisch aktiv
- `Liste_YAML` → aktiv, falls YAML-Overrides mit `addEvents` vorhanden
- Jede Liste mit mindestens einer ACTIVITY-Zeile mit Fixzeit → automatisch aktiv

**Aktivierung während des Tages:**
- Über `Start list X`-Steuerzeilen in der CSV (eine Liste aktiviert eine andere)
- Über CONDITION-Antworten (Ja/Nein → `start list X`)

### 3.2 Kandidatenauswahl

Jede Iteration:
1. Alle aktiven, nicht blockierten Listen liefern ihre `current_activity`.
2. Fixzeit-Aktivitäten: erst bereit, wenn `datetime.now() >= starting_time`.
3. Alle Kandidaten werden nach Priorität absteigend sortiert. Bei Gleichstand: Fixzeit vor freier Zeit; freie Aktivitäten vor Fortsetzungen.
4. Der beste Kandidat wird **gesperrt** (`_locked_task`).

### 3.3 Task-Sperre (Lock)

Die Sperre verhindert, dass das Tool still zur nächsthöheren Priorität wechselt, während der Benutzer noch arbeitet. Solange eine Aufgabe gesperrt ist:
- Erscheint sie immer als `get_best_candidate()`, auch wenn zwischenzeitlich eine höherpriore Aktivität erscheint.
- Die höherpriore Aktivität taucht stattdessen im **Preemption-Banner** auf.
- Die Sperre wird aufgehoben durch: Erledigt / Überspringen / Unterbrechen / Ende der Liste.

### 3.4 Preemption

`get_preemption_candidate()` sucht nach einem Kandidaten mit **höherer** Priorität als die gesperrte Aufgabe. Falls gefunden:
- Roter Banner erscheint in der GUI.
- Benutzer kann unterbrechen oder „Später" wählen.
- Bei „Später" wird der Banner bis zur nächsten Änderung ausgeblendet.

### 3.5 WAIT-Timer

WAIT-Zeilen in der CSV blockieren eine Liste für eine definierte Zeit:
- `Wait` (Minuten aus der CSV): Liste blockiert für N Minuten ab der letzten abgeschlossenen Aktivität.
- `Wait until top of hour`: Liste blockiert bis zur nächsten vollen Stunde.

Der Engine-Tick (`tick()`) prüft alle 10 Sekunden, ob Wartezeiten abgelaufen sind. Beim Neuladen des Logs werden WAIT-Timer relativ zur rückdatierten Abschlusszeit berechnet — nicht relativ zu `datetime.now()`.

### 3.6 Resolve

`_resolve(ls)` scannt ab `ls.current_index` vorwärts durch die CSV-Zeilen der Liste:
- `WAIT` / `WAIT_UNTIL_TOP_OF_HOUR`: setzt `wait_until`, stoppt
- `START_LIST` / `STOP_LIST` / `RESTART_LIST`: führt die List-Management-Aktion aus, geht weiter
- `CONDITION`: setzt `current_activity` auf die Bedingungszeile, stoppt
- `ACTIVITY`: setzt `current_activity`, stoppt
- Nicht-anwendbare Zeilen (Wochentag/Dependency): überspringen

### 3.7 Projektionssimulation

`get_day_projection()` simuliert den gesamten restlichen Tag vorwärts:
- Erzeugt interne `_SimList`-Objekte (Snapshots der aktuellen Listen-Zustände)
- Iteriert: wähle den besten Kandidaten, prüfe ob ein höherpriores Item während der Ausführung „aufwacht" (Preemption-Check), emittiere entweder den vollen Eintrag oder splitte ihn
- Unterbrechungen erzeugen `(Fs.)`-Fortsetzungseinträge
- Stoppt bei „Im Bett"-Aktivität oder nach 500 Items

Die Projektion wird live bei jedem GUI-Refresh neu berechnet (schnell genug für die 15-Sekunden-Rate).

### 3.8 Log-Replay beim Start

`load_log()` stellt den Zustand aus einer JSON-Log-Datei wieder her:
- Läuft durch jede Liste sequenziell (CSV-Reihenfolge)
- Verarbeitet Steuerzeilen inline (WAITs, Start/Stop/Restart)
- Matched ACTIVITY-Zeilen gegen Log-Einträge (Name oder `original_activity`)
- Rückdatierte WAIT-Timer: werden relativ zur `completed_at`-Zeit des letzten Eintrags berechnet
- Nicht-Engine-Listen-Einträge (`"ungeplant"`, Unterbrechungen) werden direkt ins Log übernommen
- Am Ende: `_resolve()` für alle aktiven, nicht-blockierten Listen

---

## 4. CSV-Format

### Grundstruktur

```
Encoding: Windows-1252
Trennzeichen: Semikolon (;)
Dezimaltrennzeichen: Komma (Priorität wird als "2,100" geschrieben)
Erste Zeile: Header (wird übersprungen)
```

### Spalten

| Spalte | Feld | Beschreibung |
|---|---|---|
| 1 | `Activity` | Bezeichnung der Aktivität (oder Steueranweisung) |
| 2 | `Minutes` | Geplante Dauer in Minuten |
| 3 | `List` | Name der Liste (z.B. `Liste_Morgentoilette`) |
| 4 | `Priority` | Prioritätswert (Komma als Dezimaltrennzeichen, z.B. `2,100`) |
| 5 | `Weekdays` | Wochentag-Filter (kommagetrennte Bedingungen, leer = immer) |
| 6 | `Starting time` | Fixe Startzeit `HH:MM` (leer = keine Fixzeit) |
| 7 | `Dependencies` | Planungsvariablen-Bedingungen (kommagetrennt, AND-Logik) |
| 8 | `Preceding_Activity` | Muss zuerst erledigt sein (derzeit nicht ausgewertet) |

### Row-Typen

Der Row-Typ wird automatisch aus dem `Activity`-Feld erkannt:

| Activity-Wert | Row-Typ | Beschreibung |
|---|---|---|
| Normaler Text | `ACTIVITY` | Reguläre Aktivität |
| `Wait` | `WAIT` | Liste blockieren für N Minuten (aus Minutes-Feld) |
| `Wait until top of hour` | `WAIT_UNTIL_TOP_OF_HOUR` | Warten bis zur nächsten vollen Stunde |
| `Start list X` | `START_LIST` | Liste X aktivieren (aus Inaktivität) |
| `Stop list X` | `STOP_LIST` | Liste X deaktivieren |
| `Restart list X` | `RESTART_LIST` | Liste X reaktivieren (ohne Index-Reset) |
| `Wenn "Frage?", Aktion` | `CONDITION` | Wenn-Bedingung mit optionaler `sonst`-Alternative |

### Wochentag-Filter (Weekdays-Feld)

Kommagetrennte Bedingungen, die mit ODER verknüpft sind. Eine Zeile wird eingeschlossen, wenn **mindestens eine** Bedingung zutrifft. Leeres Feld = immer eingeschlossen.

| Token | Bedeutung |
|---|---|
| `Montag` … `Sonntag` | Spezifischer Wochentag |
| `Wochenende` | Samstag oder Sonntag |
| `Bürotag` | Wenn der Tag als Bürotag konfiguriert ist |
| `Teleworking` | Wenn der Tag als Teleworking konfiguriert ist |
| `Putztag` | Dienstag oder Freitag |
| `Feiertag` | Wenn als Feiertag markiert |
| `Urlaubstag` | Wenn als Urlaubstag markiert |
| `nicht X` oder `!X` | Negierung |

Beispiele:
```
Montag,Mittwoch          → Mo oder Mi
nicht Wochenende         → Mo bis Fr
Bürotag,Teleworking      → jeder Werktag (außer Feiertag/Urlaub)
```

### Dependencies-Feld

Kommagetrennte Planungsvariablen-Bedingungen. **Alle** müssen zutreffen (AND-Logik).

Bekannte Variablen:
- `Planungsvariablen.Jause_zu_Hause` — Mittagessen zu Hause (Urlaubstag/Feiertag oder nicht Mo/Di)
- `Planungsvariablen.BRZ_geplant` — gleich Bürotag
- `Planungsvariablen.Bürotag`, `Planungsvariablen.Teleworking`, etc.

Mit `!` negierbar: `!Planungsvariablen.Jause_zu_Hause` = nur wenn auswärts zu Mittag.

### CONDITION-Format

```
Wenn "Frage?", Ja-Aktion
Wenn "Frage?", Ja-Aktion, sonst Nein-Aktion
Wenn ("Frage?"), Ja-Aktion   ← Klammern optional
```

Aktionen können sein:
- Ein Aktivitätsname (wird als synthetische ACTIVITY in die Liste eingefügt)
- `start list X` (aktiviert Liste X)
- Leer (entsprechende Antwort = einfach weiterspringen)

Beispiele:
```
Wenn "Bist du heute zu Hause zu Mittag?", Mittagessen vorbereiten, sonst start list Liste_Arbeit
Wenn "Hast du Jause mitgenommen?", , sonst Jause kaufen
```

---

## 5. Versionshistorie

### v1.0 — 3. März 2026 (Grundgerüst)

*Erstellt von einem Sub-Agenten basierend auf dem CSV-Format.*

- Grundlegende reaktive Engine mit mehreren Listen und Prioritäten
- Einfache tkinter-GUI mit aktuellem Task und Queue
- CSV-Parser für `Planungsaktivitaeten.csv`
- `DayContext` für Tagestyp-Erkennung (Bürotag, Teleworking, Wochenende, etc.)
- Erledigt-Dialog mit anpassbarer Endzeit

### v1.1 — 3. März 2026 (nachmittags)

*Erste User-Feedback-Iteration.*

- `Jause_zu_Hause` aus C#-Logik übernommen (automatisch berechnet)
- Erledigt-Dialog: Aktivitätsname editierbar
- Start- und Endzeit in Erledigt-Dialog (Rückdatierung möglich)

### v1.2 — 3. März 2026 (abends)

*State Persistence und Timeline-Logging.*

- `CompletedItem.started_at` (Startzeit im Log-Eintrag)
- Log-Replay beim Start (`load_log()`)
- WAIT-Timer werden relativ zur rückdatierten Abschlusszeit berechnet (`reference_time`)
- **📝 Ungeplant**-Button (früher „Pause") für Adhoc-Aktivitäten
- Bugfix: Doppelter `load_log()`-Aufruf entfernt
- Bugfix: Kein Auto-Save beim Schließen (zerstörte Daten bei Neustart)

*Commit: `3253e00`*

### v1.3 — 5.–6. März 2026 (Projektion und Preemption)

*Tagesplanung-Simulation und Gap-Erkennung.*

- `get_day_projection()` mit Preemption-Simulation
- `save_initial_projection()` speichert den Tagesplan beim Start
- `day_report.py` — Tagesbericht (Projektion vs. Log)
- Preemption-Banner in der GUI
- Queue-Panel zeigt projizierte Zeiten

### v1.4 — 6. März 2026 (UI-Überarbeitung)

*GUI-Redesign inspiriert von Radio-Playout-Systemen.*

- Neues **Erledigt-Panel** (oben): zeigt abgeschlossene Aktivitäten sortiert nach Startzeit
- **Geplant-Panel** (unten): umbenannt von „Tagesplan"
- Layout: Vergangenheit ↑, Gegenwart mitte, Zukunft ↓ (wie bei 88.6)
- **Statusleiste** mit Lückenwarnung (⚠ bei >30 min ohne Eintrag)
- Log sortiert nach `started_at` (Rückdatierungen füllen Lücken korrekt)
- Doppelklick / Rechtsklick auf Queue-Einträge
- **Automationen**: `automations.py`, `automation_editor.py`, `automations.json`
- **„Name übernehmen"-Button** in Erledigt/Adhoc-Dialogen

### v1.5 — 7. März 2026 (Conditions und YAML)

*Bedingte Steuerung und Ausnahmen-Management.*

- **CONDITION-Zeilen**: CSV erkennt `Wenn "Frage?", Aktion, sonst Alternative`
- GUI-Konditionsmodus: Ja/Nein-Buttons ersetzen normale Buttons
- `engine.answer_condition()` verarbeitet Antworten
- **YAML-Exceptions** (`yaml_loader.py`): per-Datum Overrides aus `schedule_exceptions.yaml`
- Startup-Dialog: vorausgefüllte Tagestypen aus YAML, Sonderbemerkungen, `earlyWorkStart`
- **Code-Vorschläge** (`code_suggest.py`): fuzzy matching gegen Master Task List
- Task-Sperre (`lock_current()`) verhindert stillen Kandidatenwechsel
- 4 Matching-Strategien: exakt, Prefix, Keyword-Alias, Containment

*Commit: diverse März 2026*

### v1.6 — 12.–17. März 2026 (Window Monitor & Nacherfassung)

*Automatische Fenster-Überwachung und halbautomatische Nacherfassung.*

- **`window_monitor.py`**: Pollt aktives Fenster alle 1s über Win32 API, schreibt `windowmon-YYYY-MM-DD.jsonl`
- **`windowmon_import.py`**: Nacherfassungs-Workflow — JSONL → Blockbildung → AutoDetect → GUI-Dialog
  - AutoDetect: Regelbasierte Klassifikation von Fenster-Events zu Aktivitäten (per `windowmon_summary.yaml`)
  - Block-Konsolidierung: 6-Pass-Algorithmus (Pass 0a/0b → 1 → 1.5 → 2) für Noise-Absorption und Bridging
  - GUI: Zeigt vorgeschlagene Blöcke, erlaubt Korrektur, Import in den Planner-Log
  - autodetect-corrections-YYYY-MM-DD.json: Speichert manuelle Korrekturen als Lernbasis
- **Idle/Off-PC-Erkennung**: 30s ohne Input → „Off-PC"-Modus, backdated um 20s, Marker in JSONL
- **Window-Titel im Planer**: Zeigt aktuelle Aktivität für WindowMon-Klassifikation (`Tagesplanung — Off-PC — [Aktivität]`)
- **Log-Bearbeitung**: Doppelklick auf Erledigt-Einträge → Ändern/Löschen/Duplizieren
- **Drift-Anzeige**: Vergleich aktuelle vs. geplante Zeit (aus Projektion) mit farblicher Warnung

*Commits: `ae75cef` und Vorgänger*

### v1.7 — 20. März 2026 (Restplan & Out-of-Order-Logging)

*Adressiert das Desynchronisations-Problem: Wenn Plan und Realität auseinanderdriften
(z.B. nach BRZ-Rückkehr), war der Planer bisher unbrauchbar, bis die Nacherfassung
abgeschlossen war. Drei Features lösen das:*

- **V8 — Out-of-Order-Logging**: Doppelklick auf beliebiges Queue-Item loggt es unter
  der richtigen Liste. Engine überspringt bereits geloggte Items automatisch
  (`_is_already_logged()` in `_resolve()` und `get_day_projection()`). Kein manuelles
  Überspringen mehr, keine Duplikate.
- **V9 — Restplan-Ansicht**: Toggle-Button „📋 Restplan" im Queue-Panel zeigt die
  originale Tagesprojektion (aus `projection-*.json`) minus Erledigtes. Chronologisch,
  mit „── jetzt ──"-Marker, gedimmte vergangene Items, grüne Kandidaten.
- **V10 — Bulk-Complete**: Rechtsklick im Restplan → „Bis hierher erledigt" markiert
  alle Items bis zum gewählten Punkt als erledigt (mit Projektions-Zeiten als Platzhalter).
  Synchronisiert den Planer in Sekunden statt Minuten.

*Hintergrund: Analyse des 19.03.2026 zeigte, dass die Nacherfassungs-Angst
(Desynchronisation → Vermeidung → „sinnloses Tun" → Tage 1-2h zu lang) das
Kernproblem war. Details in `docs/nacherfassung-improvements.md` (V8/V9/V10-Abschnitt).*

*Commit: `d0e7c94`*

---

## 6. Übergang von den alten Planungs-/Ablauf-Dateien

Dieser Abschnitt dokumentiert, wie das Planungstool die bisherigen manuellen Dateien ablöst und wo die Daten jetzt liegen.

### 6.1 Die alten Dateiformate

**Planung-Datei (alt)**
- Format: Klartext (`.txt`)
- Ort: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Planung DD.MM.YYYY.txt`
- Inhalt: Tagesplanung mit geplanten Zeiten und Prioritäten, erzeugt vom C#-Tool
- Letzte Datei: **5.3.2026** (Planung mit Unterbrechung am 3.3.)

**Ablauf-Datei (alt)**
- Format: Klartext (`.txt`)
- Ort: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Ablauf DD.MM.YYYY.txt`
- Inhalt: manuelle Nacherfassung was tatsächlich passiert ist
- Letzte vollständig abgeschlossene Datei: **26.1.2026**
- Letzte Datei überhaupt: **2.3.2026** (unvollständig)

Seit 26.1.2026 gibt es keine vollständig abgeschlossenen Ablauf-Dateien mehr. Es existieren zwar Ablauf-Dateien für spätere Tage, in denen die tatsächliche Erfassung begonnen wurde, aber sie erreichen nie das Tagesende — die Nacherfassung bricht immer irgendwo mittendrin ab.

### 6.2 Das neue Format

**JSON-Log** (neu, ab 3.3.2026)
- Format: JSON (`.json`)
- Ort: `C:\Users\kurt_\.openclaw\workspace\kontensystem\logs\planner-log-YYYY-MM-DD.json`
- Inhalt: automatisch während des Tages aufgebaut, erfordert kein manuelles Nacherfassen

**Projektion** (neu, entspricht der Planung-Datei)
- Format: JSON (`.json`)
- Ort: `C:\Users\kurt_\.openclaw\workspace\kontensystem\logs\projection-YYYY-MM-DD.json`
- Inhalt: ideale Tagesplanung, beim Start automatisch gespeichert

### 6.3 Vergleich der Informationen

| Information | Ablauf-Datei (alt) | JSON-Log (neu) |
|---|---|---|
| Aktivitätsname | ✓ | ✓ `activity` |
| Startzeit | ✓ | ✓ `started_at` |
| Endzeit | ✓ | ✓ `completed_at` |
| Dauer | ✓ | ✓ `minutes` |
| Übersprungen | ✓ (manuell) | ✓ `skipped: true` |
| Begründung | manchmal | ✓ `comment` |
| Konto/Liste | implizit | ✓ `list` |
| Priorität | nein | ✓ `priority` |
| Original-Name | nein | ✓ `original_activity` |
| Ungeplante Aktivitäten | manuell eingetragen | ✓ `list: "ungeplant"` |
| Unterbrechungen | manuell | ✓ als separate Einträge |

Das JSON-Format enthält also **dieselben** Kerninformationen wie die alten Ablauf-Dateien, plus zusätzliche maschinenlesbare Felder.

### 6.4 Wie es zum Umstieg kam

Der Umstieg war **nicht geplant**. Er ergab sich aus der Entwicklung des Planungstools ab 3. März 2026:

1. Das Planungstool wurde entwickelt, um die laufende Ablauf-Erstellung zu automatisieren.
2. Beim ersten produktiven Einsatz (3. März) entstanden direkt JSON-Logs.
3. Seitdem werden keine Ablauf-Textdateien mehr manuell erstellt.
4. Das C#-Tool kann weiterhin Planung-Textdateien erzeugen, wird aber seit dem 3. März nicht mehr gestartet. Die Funktion der Planungsdateien wird jetzt von den Projektion-JSON-Dateien des Python-Tools übernommen.

### 6.5 Parallelbetrieb

Das **Window Logger**-System läuft weiterhin parallel und erzeugt seine eigenen Logs (separate Dateien, anderes Format). Der Window Logger erfasst Fensteränderungen auf dem PC — das Planungstool erfasst den *geplanten* Ablauf. Beide ergänzen sich.

### 6.6 Offene Punkte zur Aufwandserfassung

**Geplant, aber noch nicht implementiert:**
- Export der JSON-Logs in ein besser menschenlesbares Format (das aktuelle JSON-Format mit jedem Feld in einer eigenen Zeile ist für händische Konsultation unpraktisch)
- Automatische Zuordnung von Aktivitäten zu Konten (derzeit manuell über die Access-Datenbank)
- Automatische Feiertags-Erkennung (im C#-Tool vorhanden als `Feiertag.cs` unter `C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Tagesplanung\Feiertag.cs` — berechnet österreichische Feiertage inkl. beweglicher Feiertage über einen Oster-Algorithmus; im Python-Tool bisher nur manuell über Startup-Dialog oder YAML-Exception)

**Kontext zur Aufwandserfassung:** Die Aufwandserfassung liegt seit ca. 3 Jahren im Rückstand (letzter vollständiger Stand: ~2023). Die Aufwandserfassung basiert primär auf den **Window Logger**-Logs, die automatisch eingelesen werden. Die Ablauf-Dateien (alt) und nun die Planner-Logs (neu) dienen als **ergänzende Quelle**, die händisch konsultiert wird, wenn aus dem Window Log unklar ist, was passiert ist, oder Lücken darin gefüllt werden müssen (z.B. Aktivitäten abseits des PC wie Bürotage, Einkäufe, Schwimmbadbesuche). Da die Datenstruktur sich voraussichtlich noch mehrfach ändern wird, bevor die Aufarbeitung beginnt, ist ein stabiler Export-Konverter zum jetzigen Zeitpunkt noch nicht sinnvoll.

**Window Logger** läuft eigenständig weiter und liefert eine zeitliche Übersicht der Fensteraktivitäten. Er bleibt die primäre Datenquelle für die Aufwandserfassung.

---

## 7. Nacherfassung: Code-Flow-Analyse

*Stand: 20. März 2026. Beschreibt den tatsächlichen Ablauf vom Klick auf
"📥 Nacherfassung" bis zur Anzeige der Vorschläge.*

### 7.1 Beteiligte Module

| Modul | Ort | Größe | Rolle |
|---|---|---|---|
| `windowmon_import.py` | `planner/` | 55 KB, ~1300 Zeilen | Hauptlogik: Lücken finden, Vorschläge erzeugen, GUI |
| `windowmon_summary.py` | **Repo-Root** (Anomalie!) | 44 KB, ~1000 Zeilen | Klassifikationsregeln, Block-Bildung, JSONL-Laden |

**Anomalie:** `windowmon_summary.py` liegt im Repo-Root statt in `planner/`.
Es wird von `windowmon_import.py` importiert (`from windowmon_summary import ...`).
Das funktioniert, weil `main.py` das Repo-Root zum `sys.path` hinzufügt. Sollte
bei einem Refactoring nach `planner/` verschoben werden.

### 7.2 Funktionsübersicht

```
windowmon_import.py:
  find_planner_gaps()          — Lücken im Planer-Log finden
  _consolidate_blocks()        — 6-Pass Block-Konsolidierung (228 Zeilen)
  _load_day_overrides()        — Korrektur-Overrides aus corrections.json
  _find_planner_context()      — Welche Planer-Aktivität lief zur Lückenzeit?
  get_windowmon_proposals()    — HAUPTFUNKTION: Gaps → Proposals (260 Zeilen)
  log_correction()             — Korrektur in corrections.json speichern
  show_raw_windowmon()         — Debug: Roh-Events anzeigen
  edit_proposal()              — Einzelvorschlag bearbeiten (GUI-Dialog)
  open_import_dialog()         — Einstiegspunkt: baut die Nacherfassungs-GUI

windowmon_summary.py:
  classify_entry()             — Einzelnes Fenster-Event → (account, activity)
  build_activity_blocks()      — Sequenz von Events → Blöcke gleicher Aktivität
  load_windowmon()             — JSONL-Datei lesen und parsen
  load_planner_log()           — Planer-Log lesen (für standalone-Nutzung)
  inject_idle_periods()        — Idle-Marker in Block-Liste einfügen
  aggregate_summary()          — Zeitsummen pro Account
  detect_gaps()                — Lücken in Event-Sequenz
  print_summary()              — Terminal-Ausgabe (standalone-Modus)
  main()                       — Standalone CLI-Einstieg
```

### 7.3 Der Flow: Klick → Vorschläge

```
gui.py: _on_windowmon_import()
  │
  └→ windowmon_import.open_import_dialog(root, engine, code_suggestor)
       │
       │  ═══ SCHRITT 1: Lücken finden ═══════════════════════════════
       │
       ├→ find_planner_gaps(completed, day_start, day_end)
       │    • Sortiert Log nach started_at
       │    • Findet Zeiträume ≥ 2 Min. ohne Log-Eintrag
       │    • Berechnet day_start (erster Log-Eintrag) und day_end (jetzt)
       │    → Liste von (gap_start, gap_end) Tupeln
       │
       │  ═══ SCHRITT 2: Vorschläge erzeugen ════════════════════════
       │
       ├→ get_windowmon_proposals(date_str, gaps, completed)
       │    │
       │    │  2a: JSONL laden
       │    ├→ windowmon_summary.load_windowmon(date_str)
       │    │    • Liest windowmon-YYYY-MM-DD.jsonl
       │    │    • Parst Timestamps, filtert defekte Zeilen
       │    │    → Liste von Event-Dicts mit _ts (datetime)
       │    │
       │    │  2b: Tages-Overrides laden
       │    ├→ _load_day_overrides(date_str)
       │    │    • Liest autodetect-corrections-*.json
       │    │    • Baut Map: {original_activity → corrected_activity}
       │    │    • Letzter Override gewinnt bei Mehrfachkorrekturen
       │    │
       │    │  ═══ FÜR JEDE LÜCKE: ═══════════════════════════════════
       │    │
       │    │  2c: Fenster-Events filtern
       │    │    • Events innerhalb [gap_start, gap_end]
       │    │
       │    │  2d: Sonderfall: keine Events in Lücke
       │    │    • Letztes Event VOR der Lücke suchen
       │    │    • Synthetischen Vorschlag erzeugen
       │    │      ("kein Fensterwechsel — letztes Fenster fortgesetzt")
       │    │    → weiter zur nächsten Lücke
       │    │
       │    │  2e: Events klassifizieren
       │    ├→ windowmon_summary.classify_entry(entry)     [pro Event]
       │    │    • ~300 Zeilen Regelwerk: Prozess + Titel → (account, activity)
       │    │    • Erkennt: Browser-URLs, Access-DBs, Notepad-Dateien,
       │    │      Planer-Dialoge, Radio Würmchen, Excel, Word, etc.
       │    │
       │    │  2f: Events zu Blöcken gruppieren
       │    ├→ windowmon_summary.build_activity_blocks(gap_entries)
       │    │    • Aufeinanderfolgende Events gleicher Klassifikation
       │    │      → ein Block mit start/end/Dauer
       │    │
       │    │  2g: Planner-Context anwenden [pro Block]
       │    ├→ _find_planner_context(completed, gap_start)
       │    │    • Sucht im Log: welche Aktivität lief vor/nach der Lücke?
       │    │    • Wenn Block-Account == Planer-Aktivitäts-Account UND
       │    │      Block hat keinen spezifischen 6-Buchstaben-Code:
       │    │      → Aktivitätsname wird durch Planer-Aktivität ersetzt
       │    │    • Beispiel: Access-Event (Account LE) während LEEPEP
       │    │      → wird zu "Bearb. Essensplan LEEPEP" statt
       │    │        "Bearb. unbekannte Datenbank"
       │    │
       │    │  2h: Day-Overrides anwenden [pro Block]
       │    │    • Wenn Aktivitätsname in Override-Map vorhanden UND
       │    │      kein Planner-Context greift:
       │    │      → Name wird durch korrigierten Namen ersetzt
       │    │
       │    │  2i: Blöcke konsolidieren  ← KOMPLEXESTES STÜCK
       │    ├→ _consolidate_blocks(blocks)
       │    │    • Pass 0a: Direkt benachbarte Same-Account → merge
       │    │    • Pass 0b: Kurze Fremd-Blöcke (< 30s) zwischen
       │    │               gleichen Accounts → bridge
       │    │    • Pass 1:  Noise-Absorption (Blöcke < 30s werden
       │    │               vom längeren Nachbarn verschluckt)
       │    │    • Pass 1.5: Re-run Bridging (Noise-Absorption kann
       │    │                neue Bridge-Möglichkeiten erzeugt haben)
       │    │    • Pass 2:  Finale Zusammenführung gleicher Klassifikation
       │    │    → Reduzierte Block-Liste
       │    │
       │    │  2j: Clamping + Sub-Gap-Erkennung
       │    │    • Blöcke auf Lücken-Grenzen zuschneiden
       │    │    • Blöcke < 1 Minute verwerfen
       │    │    • Lücken ZWISCHEN Blöcken füllen:
       │    │      - Vor erstem Block: letztes Event vor Lücke
       │    │      - Zwischen Blöcken: vorherigen Block verlängern
       │    │      - Nach letztem Block: letzten Block verlängern
       │    │
       │    └→ Liste von Proposal-Dicts, sortiert nach Startzeit
       │
       │  ═══ SCHRITT 3: GUI aufbauen ═══════════════════════════════
       │
       └→ Dialog mit Canvas, Scroll-Frame, Proposal-Karten
            • Pro Vorschlag: Zeitraum, Aktivitätsname, Dauer, Buttons
            • Buttons: Übernehmen / Bearbeiten / Raw-Events / Ignorieren
            • Import-Button: akzeptierte Vorschläge ins Planer-Log schreiben
```

### 7.4 Bekannte Schwachstellen

**1. `get_windowmon_proposals()` — 260 Zeilen Monolith**

Die Schritte 2a–2j laufen alle innerhalb einer einzigen Funktion ab. Die Schleife
`for gap_start, gap_end in gaps:` enthält Klassifikation, Context, Overrides,
Konsolidierung und Sub-Gap-Erkennung. Das macht Debugging und gezielte Änderungen
schwierig — man muss den gesamten Flow verstehen, um eine einzelne Stelle zu ändern.

**2. `_consolidate_blocks()` — 228 Zeilen, 6 Passes**

Die Pass-Kaskade (0a → 0b → 1 → 1.5 → 2) ist historisch gewachsen: jeder Pass
wurde eingeführt, um ein spezifisches Symptom zu beheben. Die Interaktion zwischen
den Passes ist schwer vorhersagbar. Kurts Vereinfachungsvorschlag (20.03.2026):
"Letztes Event vor der Lücke und erstes Event danach anschauen, an Minutengrenzen
abschneiden" — konzeptuell simpler, weniger Passes nötig.

**3. "Letztes Fenster fortgesetzt" — 3× dupliziert**

Die Logik "kein Fensterwechsel → letztes Fenster weiterhin aktiv" erscheint an
drei Stellen leicht abgewandelt:
- Schritt 2d: Leere Lücke (kein einziges Event)
- Schritt 2j: Bereich vor dem ersten Block innerhalb einer Lücke
- Schritt 2j: Block-Verlängerung nach dem letzten Block

Gleiche Grundlogik, drei separate Implementierungen.

**4. Reihenfolge-Abhängigkeit: Overrides vor Konsolidierung**

Day-Overrides (2h) werden pro Block angewendet, BEVOR die Konsolidierung (2i)
Blöcke zusammenführt. Wenn Block A (Override "X") und Block B (kein Override)
zusammengeführt werden, bestimmt die Merge-Logik, welcher Name überlebt — das
hängt von der Blockdauer ab (längerer Block gewinnt), nicht vom Override-Status.

**5. `windowmon_summary.py` im Repo-Root**

Sollte unter `planner/` liegen. Der aktuelle Import funktioniert nur, weil
`main.py` das Repo-Root zu `sys.path` hinzufügt. Bei Refactoring verschieben.

**6. `classify_entry()` — ~300 Zeilen hart kodierte Regeln**

Jede Regel ist eine if/elif-Kette. Neue Regeln werden am Ende angehängt.
Das Improvements-Dokument (V3a/V3b) beschreibt ein YAML-basiertes Regelsystem
als Alternative, aber das erfordert ein Refactoring der Grundarchitektur.

### 7.5 Verbesserungspotential (Refactoring-Ideen)

Diese Ideen sind **nicht** als nächste Features gedacht, sondern als Orientierung
für den Fall, dass Kurt selbst in den Code einsteigt:

1. **`get_windowmon_proposals()` aufteilen:** Die Schritte 2c-2j könnten in eine
   eigene Funktion `_process_gap(gap_start, gap_end, entries, ...)` ausgelagert
   werden. Das reduziert die Hauptfunktion auf eine Schleife über Gaps.

2. **"Letztes Fenster"-Logik zentralisieren:** Eine Hilfsfunktion
   `_get_preceding_activity(entries, before_ts)` eliminiert die Dreifach-Duplizierung.

3. **`_consolidate_blocks()` vereinfachen:** Statt 6 Passes möglicherweise ein
   einziger Durchlauf, der Blöcke gleichen Accounts zusammenführt, wenn die
   Zwischenblöcke unter einem Schwellenwert liegen. Kurts Ansatz (Minutengrenzen
   + Blick auf letztes/nächstes Event) als Alternative evaluieren.

4. **`windowmon_summary.py` verschieben:** Nach `planner/windowmon_summary.py`,
   Import-Pfade anpassen.

---

## 8. Known Limitations

### 8.1 "Unterbrechen" während Nacherfassungs-Rückstand

Wenn der Planer aufgrund eines Nacherfassungs-Rückstands eine veraltete Aktivität
anzeigt (z.B. "Anhören Radiosender" von heute früh, obwohl es schon Mittag ist),
bezieht sich die Funktion "Aufgabe unterbrechen" auf diese veraltete Aktivität —
nicht auf das, was man gerade tatsächlich tut. Das Bestätigen der Unterbrechung
würde die veraltete Aktivität als "Teil 1 bis jetzt" loggen, was zeitlich falsch
wäre.

**Workaround:** Für kurze Zwischenaktivitäten (WC, Getränk holen) während eines
Nacherfassungs-Rückstands den "Ungeplant"-Button verwenden oder die Aktivität
per Doppelklick aus der Queue vorziehen (V8 Out-of-Order-Logging).

### 8.2 Rechtsklick-Verhalten in der Live-Ansicht ist inkonsistent

In der Live-Queue-Ansicht:
- **Doppelklick** funktioniert auf jede Aktivität (aktuelle Kandidaten → normaler
  Erledigt-Dialog; zukünftige → Ad-hoc-Dialog mit vorausgefülltem Namen).
- **Rechtsklick** (Überspringen) funktioniert nur auf aktuelle Kandidaten, also
  Aktivitäten die `current_activity` ihrer jeweiligen Liste sind. Für andere
  Einträge erscheint die Meldung "ist noch nicht an der Reihe".

Visuell ist nicht erkennbar, welche Einträge Kandidaten sind und welche nicht —
beide haben dieselbe Farbe (hellgrau). Das führt zu Verwirrung, wenn manche
Rechtsklicks funktionieren und andere nicht.

In der **Restplan-Ansicht** hingegen öffnet Rechtsklick immer ein Kontextmenü
mit "Bis hierher erledigt" und "Einzeln loggen".

**Mögliche Verbesserung:** Kandidaten visuell hervorheben (z.B. fettgedruckt oder
mit einem Marker), oder Rechtsklick in der Live-Ansicht ebenfalls ein Kontextmenü
mit "Überspringen" + "Vorziehen" anbieten — unabhängig vom Kandidaten-Status.

---

## Anhang: DayContext-Variablen

Vollständige Liste der Planungsvariablen, die in `day_context.py` definiert sind:

| Variable | Wert = True wenn... |
|---|---|
| `Bürotag` | Mo oder Mi, nicht Feiertag/Urlaubstag, nicht Wochenende |
| `Teleworking` | Di, Do oder Fr, nicht Feiertag/Urlaubstag |
| `Wochenende` | Sa oder So |
| `Putztag` | Di oder Fr |
| `Feiertag` | Im Startup-Dialog als Feiertag markiert (oder per YAML) |
| `Urlaubstag` | Im Startup-Dialog als Urlaubstag markiert (oder per YAML) |
| `BRZ_geplant` | Gleich wie Bürotag |
| `Jause_zu_Hause` | Urlaubstag ODER Feiertag ODER (nicht Mo UND nicht Di) |

Unbekannte Variablen werden als `True` ausgewertet (permissiv — damit neue CSV-Variablen das Tool nicht blockieren).
