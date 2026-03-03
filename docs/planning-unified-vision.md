# Unified Planning System — Vision Document

Created: 2026-03-02, from conversation with Kurt.

## The Problem

Four separate systems that should be one:
1. **C# Planning Tool** — generates daily schedule from CSV, outputs static text file
2. **Window Logger** — tracks what actually happens on PC, but doesn't know the plan
3. **Ablauf files** — manual reconciliation of plan vs reality (36+ min/day overhead)
4. **Accounting system (Access DB)** — needs time data as input, currently fed manually

Each system has part of the picture. The human (Kurt) is the integration layer, manually bridging them all day long.

## The Vision: A Reactive, Auto-Logging, Plan-Aware System

### Core concept: Radio playout model applied to life

Like a radio station's playout system:
- **Hard anchors** (news, ads) have fixed times → ZiB 1 at 19:30, BRZ meetings, meals
- **Flexible fill** (music) flows around anchors → Ohrwürmer, Papiersortierung, etc.
- **DJ inserts** happen on the fly, system adapts → unplanned activities
- **Hourly clock resets** prevent drift from propagating → damage contained to current block
- **Logging is automatic** — the system knows what played because it played it

### Feature 1: Automatic activity detection (Window Logger integration)

When a window change is detected (or user returns to PC after away-from-PC activity):

```
1. Check: Does this match the NEXT planned item?
   → Yes: Log it as started, advance the plan
   
2. Check: Does this match ANY item planned for today?
   → Yes: Log that item as started now, mark as done (unless recurring/minimum-time)
   
3. Check: Does this match a GENERAL activity mapping?
   (e.g., editing "suggestion_pool_schlager.txt" → "Working on Radio Würmchen KI")
   → Yes: Log as unplanned item with the mapped activity name
   
4. No match found:
   → Log generic entry ("editing suggestion_pool_schlager.txt"), mark as NEEDS REVIEW
```

### Feature 2: Learnable activity mappings

- When user reviews unmatched items, they can create permanent mappings:
  - "Every time `suggestion_pool_schlager.txt` is edited → Radio Würmchen KI station"
  - "Every time `Kontensystem 2021.mdb` is active → Aufwandserfassung Kontensystem"
- These mappings are stored in a configuration file (not hardcoded)
- Mappings can use window title patterns, file names, application names, or combinations
- Over time, the system learns and fewer items need review

### Feature 3: Reactive "next item" guidance (Checklisten model)

- Multiple lists run concurrently with their own priorities (as defined in CSV)
- System always knows the current highest-priority doable item
- Presents it to the user: "Next: Bearb. Ohrwürmer (durchgenommen) — 3 min — Prio 1.84"
- When user completes it (or the system detects a matching window change), advances to next
- Handles timed items: if a hard anchor approaches, it interrupts/queues current flexible item
- Handles prerequisites: won't suggest an item whose dependencies aren't met

### Feature 4: Live re-planning (predictive view)

- At day start: generate full-day view with timestamps (like current C# tool)
- But this view is **continuously recalculated** as the day progresses
- When unplanned items are inserted or planned items take longer: remaining schedule adjusts
- Items that can no longer fit move to "won't fit today" section automatically
- No manual Ablauf reconstruction needed — the system IS the Ablauf

### Feature 5: Accounting system output

- At end of day (or on demand): export a log compatible with the accounting system
- Each activity has: start time, end time, activity code, planned/unplanned flag
- Can be imported into the Access DB or used as input for Aufwandserfassung
- Eliminates the manual "Ermittlung Gesamtzeiten" step

### Feature 6: Away-from-PC tracking

- The 4 combo boxes from Window Logger are preserved but populated dynamically from the day's plan
- User can select "Besuch Schwimmbad" when leaving → system logs it and continues plan from there when user returns
- Could also integrate with phone location/calendar for automatic away-activity detection (future)

## What This Eliminates

| Current overhead | How it's eliminated |
|---|---|
| Manual Ablauf reconstruction (36+ min/day) | Automatic logging from window detection |
| Window Logger → Ablauf matching (manual) | Activity mappings do this automatically |
| Manual priority scanning in backlog zone | Reactive "next item" presentation |
| Blank-line bookmark management | System tracks current position |
| Plan-vs-reality drift accumulation | Live re-planning with clock resets |
| Nacherfassung from Window Logger | Window Logger IS the logging system |
| Separate Planung and Ablauf files | One living document, continuously updated |
| Manual accounting system input | Auto-generated export |

## Technical Considerations

- **Current Window Logger:** Self-written, tracks every window change. Has 4 combo boxes with hardcoded activities, hardcoded window-to-activity logic
- **Current CSV format:** 332 lines, semicolon-delimited, with lists, priorities, day types, dependencies, starting times — this can be preserved as input
- **Current accounting system:** Access 2000 (.mdb), needs activity codes and times
- **Platform:** Windows, Kurt uses VS Code + RooCode for C# development
- **Code size consideration:** Kurt's experience with AI-assisted coding shows models struggle beyond ~500 lines per module. System should be modular (≤500 lines / ≤20 kB per module, as with current C# tool)

## Module Architecture

```
┌─────────────────┐     ┌──────────────────┐
│  Window Monitor  │────▶│ Activity Mapper   │
│    (Module 4)    │     │    (Module 1)     │
└─────────────────┘     └────────┬─────────┘
                                 │ matched activity
                                 ▼
┌─────────────────┐     ┌──────────────────┐
│   Plan Engine   │◀───▶│   Day Tracker    │
│   (Module 2)    │     │    (Module 3)    │
└────────┬────────┘     └────────┬─────────┘
         │ next item,            │ live state
         │ projected schedule    │
         ▼                       ▼
┌─────────────────┐     ┌──────────────────┐
│    Presenter    │     │    Exporter       │
│   (Module 5)    │     │    (Module 6)     │
└─────────────────┘     └──────────────────┘
```

### Module 1: Activity Mapper
- Owns learnable mappings: window title / file name / app → activity code
- Input: window change event (title, process, file path)
- Output: matched activity (code, name, confidence) or "needs review"
- Stores mappings in config file (JSON/CSV), not hardcoded
- Review UI for unmatched items → user confirms → mapping saved permanently

### Module 2: Plan Engine
- Reads existing CSV (Planungsaktivitaeten.csv) + day type parameters
- Maintains concurrent lists with priorities (Checklisten model internally)
- Tracks: done, pending, blocked by prerequisites
- Answers: "What's the highest-priority doable item right now?"
- Recalculates projected schedule on demand (live re-planning)
- Handles hard anchors (fixed-time) vs flexible fill

### Module 3: Day Tracker
- Central state: what happened today, what's planned, what's open
- Receives events from Activity Mapper ("user started X at 14:23")
- Tells Plan Engine "item done" or "unplanned item inserted"
- Maintains live Ablauf — no manual reconstruction needed
- Handles away-from-PC entries (manual activity selection)

### Module 4: Window Monitor
- Window change detection (replacing/wrapping current Window Logger)
- Fires events on active window change
- Feeds raw events to Activity Mapper
- Could initially be an adapter reading Window Logger output

### Module 5: Presenter
- UI: current item, next item, projected schedule
- Small always-on widget (like Checklisten's one-item view)
- Shows "needs review" items for quick mapping
- Combo boxes for away-from-PC activities (populated from today's plan)

### Module 6: Exporter
- End-of-day or on-demand export
- Generates Ablauf-format text file (backward compatible)
- Generates accounting system input (activity codes + times for Access DB)
- Auto-generates "noch offen" section

### Design constraints
- Target ≤500 lines per module (may need more modules if complex — that's fine)
- Existing CSV format preserved as input to Module 2
- Must be able to read existing Planungsaktivitaeten.csv without changes

## Source Code Locations

### Existing systems to analyze:
- **Window Logger (VB5):** `C:\Users\kurt_\Betrieb\Kontenverwaltung\Checklisten_Winlogger\Window logger.vbp`
- **Checklisten (VB5):** `C:\Users\kurt_\Betrieb\Kontenverwaltung\Checklisten_Winlogger\Checklisten.vbp`
- **Tagesplanung (C#):** `C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\` (20 modules)
- **Planungsaktivitaeten.csv:** `C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Planungsaktivitaeten.csv`
- **schedule_exceptions.yaml:** same directory

### Next step: Read existing source code, then define inter-module interfaces based on actual data formats.

## Key Insight About the Ablauf

The Ablauf file's current form is most useful for:
1. **Finding the next activity to do** (primary use during the day)
2. **Reconciling against planning + window log** for Aufwandserfassung (when behind on accounting)

But: maintaining the Ablauf currently takes MORE time than generating the Aufwandserfassung from window logs. The unified system should make both functions automatic.

## Open Questions

1. Should this be a rewrite of the C# tool, the Window Logger, or a new unified application?
2. GUI: Always-visible small widget (like Checklisten's one-item-at-a-time), system tray, or full window?
3. How to handle the transition period — can it read existing CSV and gradually learn mappings?
4. Should the accounting export format match the current Access DB structure exactly?
5. What about the YAML exceptions — are they still needed, or does the reactive model handle deviations naturally?
6. Phone/away-from-PC: manual selection only, or integrate with calendar/location?

---

*This is a vision document. Implementation decisions and architecture to be discussed separately.*
