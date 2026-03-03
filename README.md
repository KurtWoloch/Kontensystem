# Kontensystem — Unified Planning & Accounting System

## What is this?

A project to unify Kurt's four separate life-management systems into one:
1. **C# Planning Tool** (daily schedule generation from CSV)
2. **Window Logger** (automatic PC activity tracking)
3. **Ablauf files** (manual plan-vs-reality reconciliation)
4. **Accounting system** (Access DB time/activity reporting)

The vision: a reactive, auto-logging, plan-aware system that eliminates manual Ablauf reconstruction (~36 min/day overhead) and bridges planning → tracking → accounting automatically.

## Repository structure

```
kontensystem/
├── docs/                    # Project documentation
│   ├── planning-unified-vision.md   # System vision & architecture
│   ├── planning-history.md          # History of all 4 legacy systems
│   ├── answers-to-open-questions.md # Kurt's design decisions
│   ├── analysis-checklisten.md      # Checklisten VB5 code analysis
│   └── analysis-tagesplanung-cs.md  # C# Planning Tool analysis
├── parsers/                 # Scripts to extract tasks from legacy sources
├── data/                    # Extracted data (task lists, mappings, etc.)
├── windowlog_corrector.py   # Existing: corrects Window Logger output
└── How to run it.txt        # Usage notes for windowlog_corrector
```

## Current phase: Task Master List (Phase A)

Building a comprehensive task inventory by parsing all legacy sources:
- CSV (Planungsaktivitaeten.csv)
- Window Logger mappings (VB5 code + windowlog_corrector.py)
- Access DB tables (Aufwandserfassung, Tab_Aktionen, Tab_Gewinnaktionen, Tab_Wuensche, Tab_Konten)
- Ablauf files (free-form logged activities)
- KURTDOKU.txt (life documentation checklists)
- Taskliste.txt
- YAML exceptions
- Old C# code (Tagesplanung_Global_Old.cs)

## Key references (external)

- **Legacy source code:** `C:\Users\kurt_\Betrieb\Kontenverwaltung\`
- **VB5 projects:** `...\Checklisten_Winlogger\`
- **C# project:** `...\Tagesplanung_AI\Tagesplanung\`
- **Access DB:** `...\Kontensystem 2021.mdb`
- **Ablauf/Planung files:** `C:\Users\kurt_\Betrieb\Kontenverwaltung\Ablauf *.txt` / `Planung *.txt`
