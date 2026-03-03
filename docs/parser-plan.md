# Task Master List — Parser Plan

## Target output format (per parser)
Each parser produces a JSON lines file in `data/` with this structure:
```json
{"name": "Task name", "code": "ABCDEF", "parent": "", "list": "Liste_Morgentoilette", "priority": 1.84, "fixed_time": "", "source": "csv", "status": "active", "notes": ""}
```

## Parsers needed

### 1. `parse_csv.py` — Planungsaktivitaeten.csv
- Source: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Planungsaktivitaeten.csv`
- Extract: task name, 6-char code (at end of name), list, priority, weekday conditions, starting time, dependencies
- Note: Same task can appear multiple times with different weekday/time variants — deduplicate by (name, code) but preserve variants as notes

### 2. `parse_old_cs.py` — Tagesplanung_Global_Old.cs
- Source: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Tagesplanung\Tagesplanung_Global_Old.cs`
- Extract: hardcoded Planungsaktivitaet_hinzufuegen() calls — task name, code, duration, list, priority, weekday conditions
- Also extract: commented-out tasks (prefixed with //) as status="retired"
- Also extract: ExtractAndCondenseLogLines logic for activity mapping patterns

### 3. `parse_windowlog_corrector.py` — windowlog_corrector.py
- Source: `C:\Users\kurt_\.openclaw\workspace\kontensystem\windowlog_corrector.py`
- Extract: window-title-to-activity mappings (regex patterns → activity names)

### 4. `parse_taskliste.py` — Taskliste.txt
- Source: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Taskliste.txt`
- Extract: task names with 2-letter account prefixes, categorized by priority tier (periodisch/kurzfristig/mittelfristig/etc.)

### 5. `parse_yaml_exceptions.py` — schedule_exceptions.yaml
- Source: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\schedule_exceptions.yaml`
- Extract: any added events not already in CSV (unique task names from addEvents)

### 6. `parse_access_db.py` — Kontensystem 2021.mdb tables
- Source: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Kontensystem 2021.mdb`
- Tables: Aufwandserfassung, Tab_Aktionen, Tab_Gewinnaktionen, Tab_Wuensche, Tab_Konten
- Needs: pyodbc or pypyodbc with Access ODBC driver, or mdbtools
- Extract: activity names, account codes, any additional metadata

### 7. `parse_kurtdoku.py` — KURTDOKU.txt
- Source: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Checklisten_Winlogger\KURTDOKU.txt`
- Extract: checklist items and control structures (this is the Checklisten program's data file)
- Complex format with priority commands — needs careful parsing

### 8. `parse_window_logger_vb5.py` — Window logger.frm
- Source: `C:\Users\kurt_\Betrieb\Kontenverwaltung\Checklisten_Winlogger\Window logger.frm`
- Extract: combo box items (hardcoded activities), window-to-activity mappings

## Merge step
After all parsers run, `merge_tasks.py` combines all JSON lines files into a single master task list, deduplicating by code+name, tracking sources, and flagging conflicts.

## Execution order
Parsers 1-5, 7-8 can run in parallel (text file parsing). Parser 6 (Access DB) may need special setup.
