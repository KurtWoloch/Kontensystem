# Planning System Genealogy

This document traces the evolution of Kurt's planning and life management systems, from their origins to the current C# planning tool. Created 2026-03-02 as groundwork for documenting the full planning process.

---

## Layer 1: Life Documentation (~2000)

- ~50-page document proving to Kurt's parents he understood everything needed to live independently
- Written before parents moved out of the shared flat
- Morning routine broken into 14+ steps, daily checklists for all essential life tasks
- **Approved by mother** — effectively a contract proving competence
- Origin: mother was self-admitted "helicopter mother"; Kurt internalized need to prove he could manage alone
- These checklists defined the granularity of daily routines that persist to this day (the 15 morning routine items in current planning trace directly back here)

## Layer 2: Accounting System / Priority List (1991–ongoing)

- **Origin:** 1991, tracking money owed by classmates in school
- **Expanded 1992:** to meet perceived parental expectations (karaoke profitability)
- **Modeled after:** BRZ cost accounting (Kurt's workplace, introduced 1991)
- **Database:** Access 2000 (.mdb format), still in use
- **Core concept:** Spasspunkte × EUR 11/point = revenue; labor at BRZ hourly rate = cost
- **Priority list:** Tab_Gewinnaktionen (131 items), ranks activities by ROI + time since last execution
- **Planning role:** Generated daily plans with priority-weighted tasks; morning and evening routines were **single blocks** each
- **Radio metaphor:** Planning system was conceptualized as a radio DJ playout system (activities = songs, priorities = rotation rules)
- **Location:** `C:\Users\kurt_\Betrieb\Kontenverwaltung`

## Layer 3: Checklisten Software (VB5, date unknown)

- Written in Visual Basic 5
- **Modeled after radio station playout systems** (but less flexible)
- Worked from checklists extracted from the Life Documentation (Layer 1)
- **Behavior:**
  - Served one item at a time
  - Item stayed on screen until "Done" (or German equivalent) was clicked
  - Supported yes/no branching → conditional sub-lists
  - Timed lists triggered at specific times of day
  - Items followed priority ordering defined in the lists
  - Morning routine was broken into the same ~15 detailed items from the Life Documentation
- **Limitations:**
  - No arbitrary item insertion (couldn't add ad-hoc tasks like "chatting with OpenClaw")
  - No reordering beyond built-in priorities
  - No deviation from predefined routines
  - When important fixed items were done, displayed: "Further actions according to priority list" → handoff to accounting system's priority list (Layer 2)
- **Relationship to Layer 2:** Complementary. Checklisten handled the *fixed daily must-dos*; the accounting system handled the *flexible priority-based work* in between
- **Usage:** Not used much (Kurt's own assessment)

## Layer 4: C# Planning Tool (2007–present, current system)

### Two iterations:

**Iteration 1 (hand-written, no AI):**
- All activities hardcoded in C# source
- Generated daily plan based on day of week
- No external data files

**Iteration 2 (adapted with RooCode):**
- Activities moved from hardcoded lines → CSV file (`Planungsaktivitaeten.csv`)
- CSV was then adapted and expanded
- Added YAML file for planned deviations (one-off changes to specific days)
- **YAML abandoned in practice** — easier to edit each day's plan output than to maintain the YAML
- Original vision: use RooCode conversationally ("I need to do X on Tuesday") → RooCode would update YAML
- **Failed because:** RooCode is task-oriented; couldn't interpret planning intent naturally; came up with "creative" solutions (modifying the software itself) instead of updating the YAML
- **Result:** Planning is now effectively monolithic — CSV rarely changes, plans are hand-edited after generation

### CSV structure (Planungsaktivitaeten.csv):
- **332 lines**, semicolon-delimited
- **Columns:** Activity;Minutes;List;Priority;Weekdays;Starting time;Dependencies;Preceding_Activity
- **Lists** (sequence groups): Liste_Morgentoilette, Nach_Fruehstueck, Liste_Schwimmbad, Radio, Liste_Spiele, Liste_untertags, Liste_Arbeit, Lebenserhaltung, Liste_mittags, Liste_nachmittags, Liste_Putzen, Liste_ZiB, Liste_Abendzeremonie
- **Day types:** Weekday names, Wochenende, Feiertag, Urlaubstag, Bürotag, Teleworking, Putztag (cleaning day = Tue/Fri)
- **Dependencies:** Reference `Planungsvariablen.*` (BRZ_geplant, Teleworking, Feiertag, Jause_zu_Hause, Putztag) with `!` for negation
- **Priority values:** Range from ~2.407 (ZiB 1 news) down to ~1.645 (exercise, messages to friends/family, buffer time)
- **"Wait" entries:** Spacers — either fixed minutes or "Wait until top of hour" (for radio listening alignment)
- **"Start/Stop/Restart list" entries:** Control flow between list sequences
- **Game entries (Liste_Spiele):** Scattered throughout the day with 60-min waits between them (mobile game check-ins)

### Key observations from the CSV:
1. **Covers ~06:00 to ~23:15** — every minute accounted for
2. **Heavy conditional logic** — same activity appears multiple times for different day types (e.g., breakfast has BRZ/non-BRZ/Sunday variants)
3. **The "tail" problem:** After ~line 200, activities become increasingly aspirational — Papiersortierung (60 min), Mailbearbeitung (60 min), multiple voice messages to Judith, estate tasks, stretching, yoga, "buffer time" — these are the items that never get reached
4. **Radio playout DNA visible:** "Wait until top of hour", "Start/Stop/Restart list", activities scheduled to clock positions — this is literally a broadcast schedule for a human life
5. **Morning routine = Life Documentation items:** The 15+ items in Liste_Morgentoilette trace directly back to the ~2000 life documentation

### General:
- **Started:** Pfingsten 2007, originally ~10 elements/day
- **Morning routine expansion:** March 2021 ("Neuer Tagesplan") — expanded from 1 block to 14+ elements
- **Task format:** 6-character codes (e.g. LEMTAU), priority scores
- **Outputs:** Planung (plan) and Ablauf (what actually happened) files
- **Development:** VS Code + RooCode, refactored into 20 modules of ≤500 lines / ≤20 kB each
- **Current state:** Daily overload of 21+ hours (unreachable items per day, not accumulated backlog)

---

## Key Tensions / Dilemmas

1. **Rigidity vs. flexibility:** Checklisten were completely rigid; accounting system was flexible; C# tool tries to be both but may satisfy neither
2. **"Proving competence" origin:** Much of the routine granularity comes from the Life Documentation's purpose (proving to parents), not necessarily from operational need
3. **Radio playout metaphor:** Both accounting system and Checklisten drew on this metaphor; the C# tool inherits it — but real life isn't a broadcast schedule
4. **Authority figure replacement:** The planning system may function as a replacement authority figure (post-parents), perpetuating the same dynamic of external control (insight from 2026-02-21 session)
5. **The broken loop:** Since Dec 2022 (father becoming care patient), Kurt's healthy analysis-judgment-consensus cycle for evaluating activities stopped and hasn't restarted
6. **21-hour daily overload:** The system generates plans that are physically impossible to complete, creating perpetual failure

## The Manual Editing Process (post-generation)

After the C# tool generates the raw plan, Kurt manually edits it:

1. **Open previous day's planning file** (as template, since it contains the Ungeplant section)
2. **Paste new plan output** into it
3. **Strip leading zeros** from times 05:xx–09:xx (cosmetic, matching hand-written convention; the AI rewrite reintroduced them)
4. **Fix scheduling errors:**
   - Items displaced by list-start timing (e.g., "Fahrt BRZG" appears at 09:03 instead of 08:59 because earlier items pushed it 4 minutes)
   - Items placed at impossible times (e.g., "Blutdruck messen" placed after commute — should be 1hr after breakfast but by then Kurt's traveling)
   - Resolution: move item forward, push to evening, or delete entirely
   - Similar with "Bearbeitung Aufgaben zu Papa's Pflege" — placed where it can't practically happen
5. **Merge Ungeplant section:** Delete the "Ungeplant:" header, copy items below it, paste into the pre-existing Ungeplant section from the template file
6. **Add overflow items:** If editing caused more items to become unplanned, add those too
7. **Clean up:** Delete remnants of old plan

**Key insight:** The tool's output requires *human judgment* to be usable. The scheduling algorithm doesn't understand physical constraints (you can't measure blood pressure while commuting) or temporal dependencies that cross list boundaries.

## Comparison: Bürotag vs. Sunday

| Metric | Monday (Bürotag) 2026-03-02 | Sunday 2026-03-01 |
|--------|------------------------------|---------------------|
| Wake time | 06:12 | 05:55 |
| Bedtime | 23:18 | 23:16 |
| Planned items | ~90 | ~107 |
| Ungeplant items | 60 | 51 |
| Ungeplant total | 1,468 min (24.5h) | 1,233 min (20.6h) |
| Work block | 08:59–18:13 (≈9h) | — |
| Games in plan | 0 | 3 (Kreuzungs-FGPA, Astro Bomber, Grindy Adventure) |
| Games in Ungeplant | 7 | 6 |
| Kontensystem bookkeeping | Ungeplant (68 min) | Planned at 16:21 (68 min) |

**Sunday observations:**
- Earlier start (05:55 vs 06:12) — still fills to 23:16
- Swimming pool block (08:01–09:01) replaces commute
- More activities fit: games, Papiersortierung (42+18 min!), Dokumentation Ma'at, Senderwertungen
- Kontensystem bookkeeping (68 min) actually fits on Sundays
- ZiB 1 at 19:30 with priority 2.407 — the highest-priority item in the entire system, anchored to broadcast time
- Still 20.5 hours of overflow — even "the most relaxed day" can't fit everything
- Sunday has extra items: Nägel schneiden, Zähne fluoridieren, Eintragen Zeiten Atariage, Scan Museumsradio (×4!)

**The Ungeplant tail is nearly identical** between both days — the bottom ~40 items (Judith messages, estate tasks, stretching, yoga, friends, family) are the same eternal backlog regardless of day type.

## The Daily Workflow (How the Plan Is Actually Used)

### Morning setup
1. Save Planung file as `Planung d.m.yyyy`
2. Replace "Planung" in heading with "Ablauf", save as `Ablauf d.m.yyyy`
3. The Ablauf file starts as an exact copy of the Planung

### During the day: line-by-line execution with manual priority scheduling
1. Go through the Ablauf file line-by-line, tracking the current item
2. Insert a blank line above or below the current item as a visual marker (deleted as progress advances)
3. **Do what's currently on** — execute the activity
4. **Unplanned items appear** → insert with `*` prefix. These often cause falling behind.
5. **When behind:** consult the Window Logger file to reconstruct what actually happened between the last recorded entry and current time
   - This can take a long time if many activities were interleaved
   - Creates fragmented entries when reality involved switching back and forth
   - Check which Window Logger activities match planned items
6. **Arrive at current time** with a backlog block of undone planned items
7. Insert blank line before the first item planned *after* current time — creating a visible "backlog zone"
8. **Priority scanning:** In the backlog zone, find the item with highest priority, check if it can be done (prerequisites met?), and if so, do it
9. Move completed items from the backlog zone to the bottom of the recorded activities list
10. **Activity renaming:** Generic planned activities often get renamed to what actually happened (e.g., "Anhören Radiosender / Radio Würmchen / Tonträger / Ohrwürmer RWMPMP" → "Scan Radio Würmchen KI" with a different activity code), but the source time from the planning is preserved
11. As time advances, more items fall into the backlog zone (their planned time passes while working on other things)
12. **Day ends** with: a full recorded list + a "noch offen" section of items that didn't make the cut

### What the Checklisten software did better
- **Automatic priority selection:** The program found the highest-priority item and served it up — Kurt didn't have to scan the list manually
- **Concurrent lists:** Multiple lists ran simultaneously with their own priorities, naturally handling interruptions (e.g., a timed item from Liste_Schwimmbad could interrupt Liste_Morgentoilette)
- **No time pressure:** Items didn't have explicit timestamps — the program just ensured everything got executed, in priority order

### What the Checklisten software couldn't do
- No ad-hoc items (couldn't add "chatting with OpenClaw" or "Scan Radio Würmchen KI")
- No reordering beyond built-in priorities
- No deviation from predefined checklists
- When fixed items were done: "Further actions according to priority list" → handoff to accounting system

### What was lost in the C# transition
- **List identity:** The CSV has 13 separate lists, but they get "baked into one continuous activity stream" — the output loses which list each item belongs to
- **Automatic next-item selection:** Kurt now manually scans for the highest-priority item in a flat list, checking prerequisites mentally
- **The Window Logger dependency:** Because the Ablauf file needs to reconstruct what actually happened (not just what was planned), Kurt relies on the Window Logger to fill gaps — this creates the "Nacherfassung Ablauf" overhead (36+ min/day)

### The fundamental tension
The Checklisten software was a **reactive system** (serve the next item, wait for completion, repeat). The C# planning tool produces a **predictive schedule** (here's your entire day, minute by minute). Reality follows neither model perfectly, but the reactive model required less overhead to maintain because it didn't need to reconcile predictions with reality.

---

## The Ablauf (What Actually Happens)

### Format
The Ablauf file records what actually happened, using:
- `planned_time -> actual_time Activity` — for planned items that were done (shows drift)
- `*time Activity` — for unplanned activities (asterisk prefix)
- `(planned_time Activity ... nicht durchgeführt/nichts offen)` — for skipped items
- `(Fs.)` — Fortsetzung, continuation of a split item
- **"noch offen" section** with `(geplant)` and `(ungeplant)` subsections — planned items not done + the carried-forward backlog

### Analysis: Completed Ablauf Jan 26, 2026 (Teleworking Monday)

**The morning (06:15–10:30): Constant context-switching.**
Between 06:15 and 10:30, alongside the planned morning routine items, there are **~80 asterisk entries** — unplanned activities that interrupt. The dominant ones:
- "Notizen OpenAIR (Scan, Programm, Rotationsirrtümer)" — appears ~20 times
- "Surfen Andon FM" — appears ~15 times
- "Bearb. Essensplan" — appears ~20 times (food plan corrections triggered by what's on screen)
- "Konversation mit Andrew Pappas" — ~7 times
- "Nacherfassung Ablauf" — ~8 times (recording the Ablauf itself takes significant time!)

**Time drift is severe.** Examples:
- "Abwiegen" planned 07:04 → actual 07:27 (+23 min)
- "Duschen" planned 07:07 → actual 07:31 (+24 min)
- "Frühstücken" planned 07:41 → actual 08:02 (+21 min)
- "Wohnung lüften" planned 08:06 → actual 09:03 (+57 min)
- "Blutdruck messen" planned 09:20 → actual 10:13 (+53 min)

**The evening (19:30–00:00): Radio stations take over completely.**
From ~19:30 onward, the Ablauf becomes almost entirely asterisk entries:
- Scanning/monitoring radio stations (OpenAIR, Andon FM, Backlink Broadcast, Grok'n Roll, Thinking Frequencies)
- Playing LM Arena (song ratings)
- Messaging/conversations
- The evening routine (Zähne putzen etc.) gets pushed ~30 minutes late
- "im Bett" planned 23:18 → actual 00:00 (42 minutes late)

**The "Nacherfassung Ablauf" feedback loop:** Recording what you're doing takes time, which creates more things to record, which takes more time. This is a meta-overhead problem — the accounting system's own accounting cost.

**"noch offen" (geplant) section:** 27 planned items totaling 175 minutes were cut ("175' an Aktivitäten gestrichen"). These include:
- Work admin (Zeiten sammeln, SAP entries — teleworking bookkeeping skipped)
- Self-care items (Tagebuch, Champion's Mindset)
- Routine maintenance (Wohnung lüften, Papiersortierung, Ohrwürmer)
- Papa-related tasks

**"noch offen" (ungeplant) section:** The eternal tail — identical to all other days.

### Comparison: Ablauf Mar 1 vs Jan 26

Both days show the same pattern:
- Morning routine takes 2–3× longer than planned due to constant micro-interruptions
- Unplanned "scanning" activities (radio stations, websites) fill every gap
- Essensplan corrections are triggered constantly by context switches
- The Ablauf recording itself is a significant time sink
- Evening routine drifts 30–45 min past target
- The same ~50 items remain eternally in "noch offen (ungeplant)"

**Key difference:** Jan 26 was dominated by OpenAIR/Andon FM radio scanning. Mar 1 was dominated by Radio Würmchen KI work. The *specific* rabbit hole changes; the *pattern* of rabbit holes doesn't.

## The Drift Pattern — A Universal Problem

The same scope-drift and ballooning pattern appears in both Kurt's planning and Sidestepper's heartbeat system. Documented 2026-03-02 after Kurt noticed the parallel.

### Kurt's drift examples:
- **Andon FM scanning:** Started as "just a few more stations to check out" → grew to tracking 160 songs with budget for 4 more, constant scanning throughout the day
- **Ablauf recording:** A meta-task that consumes 36+ min/day of the time it's supposed to track
- **Morning routine interruptions:** What should be sequential execution becomes constant context-switching between the planned item, Essensplan corrections, radio scanning, and Ablauf recording
- **Radio Würmchen:** Absorbed Feb 9-20 entirely, continued pulling attention through March

### Sidestepper's drift examples:
- **Heartbeat bloat:** Chess and Moltbook checks were already automated via Python scripts running as Windows Scheduled Tasks (every 10 and 30 min respectively). The heartbeat *duplicated* this work, making redundant API calls on Opus pricing (~$50/day)
- **API fumbling:** A single Moltbook "nothing to report" check required 8 API calls because endpoints weren't cached — trying wrong auth formats, wrong URLs, fetching documentation mid-check
- **Chess self-commentary:** Generated move analysis and regret ("I should have played...") that burned tokens with no actionable outcome
- **Forgotten automation:** Built Python scripts specifically to handle chess/Moltbook, then forgot they existed and re-implemented the checks in heartbeats

### The shared pattern:
1. **A task starts small** ("check this," "track that")
2. **Scope creeps** (more stations to scan, more analysis to do, more endpoints to verify)
3. **Meta-overhead grows** (recording takes time, checking the checks takes tokens)
4. **The system forgets its own automation** (Kurt's Checklisten → C# tool lost the handoff logic; Sidestepper's heartbeat duplicated scheduled tasks)
5. **Cost becomes disproportionate** to value ($50/day for "nothing needs attention"; 36 min/day for Ablauf that's months behind)

### Fixes applied (2026-03-02):
- Heartbeat switched to Gemini (free) instead of Opus
- Frequency reduced from ~30 min to 60 min
- Active hours restricted to 07:00–23:30 Vienna time
- HEARTBEAT.md stripped to bare minimum — explicitly says "do NOT duplicate scheduled task work"
- Chess and Moltbook checking removed from heartbeat entirely (handled by scheduled tasks)

---

## What's Documented Where

- **"Untersuchung der Prioritätenliste"** — Kurt's own analysis document (~20+ pages, first 20 read in prior session). Covers problems with the priority system.
- **This file** — System genealogy and evolution
- **Next step:** Document the actual planning *process* (how a plan gets generated, what decisions are made, how it's followed or deviated from)

---

*This is a living document. Update as more layers are uncovered.*
