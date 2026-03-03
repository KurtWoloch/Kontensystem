# Analysis of VB5 Checklisten System

## 1. Data Structure & Definition

The system logic is defined in `KURTDOKU.txt`, a hybrid "Life Documentation" and source code file. The VB program parses this file to generate the runtime checklist structure.

### Source File (`KURTDOKU.txt`)
- **Hybrid Format:** The file contains pages of prose (philosophy, instructions on how to eat/sleep) mixed with structured checklist definitions.
- **Parser Logic:** The program scans for lines starting with specific keywords (like `Checkliste ...:`) to extract the "code" from the "comments".
- **Definition Syntax:**
  - **Header:** `Checkliste [Name]:` or `Checkliste bei [Event]:`
  - **Body:** Indented lines (tabs or spaces) or lines starting with `-`.
  - **Priority:** `Priorität=[Integer]` (usually the first item).
  - **Items:** Plain text (e.g., `- Zähne putzen`).
  - **Logic:** Conditional items start with `Wenn ...`.

### Runtime State (`laufende Checklisten.txt`)
The system persists its *current state* in a separate flat text file. This allows the program to be closed and reopened without losing the exact position in a day's routine.
- **Structure:** Serializes the array of active `Checkliste` objects.
- **Fields per List:** Name, Priority, Entry Count, Current Index.
- **Fields per Item:** Text description, Status code, Timestamp (if completed).

## 2. Priority & Selection Logic

The system is a **preemptive multitasking operating system for human life**. It doesn't just show a list; it dynamically decides what the user *should* be doing right now.

### The Algorithm (`Suche_aktuelle_Checkliste`)
1. **Pool:** Looks at all active checklists.
2. **Urgency Calculation:**
   - **Running (10):** Task is already started (`laeuft`, `eingetretenes_wenn`). Sticky focus.
   - **Waiting (5):** Planned (`geplant`) or Waiting (`wartet`).
   - **Done (3):** Completed items (`beendet`) have low urgency.
3. **Selection:**
   - Primary Sort: **Priority** (defined in `KURTDOKU.txt`, e.g., "Lebenserhaltung" = 70).
   - Secondary Sort: **Urgency** (Running > Planned).
4. **Result:** The highest-score list "interrupts" the user. If "Hunger" (Prio 70) triggers while "Cleaning" (Prio 50) is running, the system switches context to "Hunger".

## 3. Control Flow & Branching

The "language" in `KURTDOKU.txt` supports sophisticated control flow, parsed via string matching.

### A. Events & Interrupts ("Checkliste bei...")
- **Definition:** `Checkliste bei [Eventname]:`
- **Trigger:** The user clicks "Ereignis eingetreten" in the UI and selects `[Eventname]`.
- **Behavior:** This spawns a new active checklist instance.
- **Example:** `Checkliste bei Aufstehen` spawns the morning routine.

### B. Conditionals ("Wenn...")
- **Syntax:** `Wenn [Condition], [Action]`
- **Auto-Evaluation:**
  - `Wochentag = Sonntag`: Checks system date.
  - `Monat = 1`: Checks system date.
  - `Uhrzeit`: (Implicit in some logic).
- **Manual Evaluation:**
  - If the code doesn't recognize the condition (e.g., `Wenn Nasenbohren weh tut`), it presents a **Yes/No Dialog** to the user.
  - **Yes:** Item becomes active; Action is executed.
  - **No:** Item is marked `nicht durchgefuehrt` (skipped).

### C. Subroutines ("Checkliste X" vs "Start Checkliste X")
- **Call (Blocking):** `- Checkliste Morgen`
  - Parent waits (`status_wartet`).
  - Child list (`Morgen`) starts.
  - Parent resumes only when Child finishes (or priority shifts).
- **Spawn (Non-Blocking):** `- Start Checkliste Lebenserhaltung`
  - Fires off the new list.
  - Parent continues immediately to its next line.
  - Used for "background processes" like "Ensure I eat today" while the main thread continues.

### D. Timers ("Warten auf...")
- **Syntax:** `- Warten auf 13:00`
- **Behavior:**
  - Item blocks. Status becomes `status_Timer`.
  - System polls every 5 seconds.
  - When time is reached -> Item completes -> List reactivates (interrupts other lower-priority tasks).

## 4. Key Checklists & Priorities (from `KURTDOKU.txt`)

- **High Priority (75):** `Checkliste bei Fortgehen` (Leaving house - money/keys check), `Checkliste Geldprüfung`.
- **High Priority (70):** `Checkliste Lebenserhaltung` (Eating/Drinking schedule), `Checkliste Morgen` (Hygiene).
- **Medium Priority (65):** `Checkliste BRZG` (Work routine).
- **Low Priority (50):** `Checkliste Hausarbeit`.
- **Lowest Priority (30):** `Checkliste Freizeit` (Only when nothing else is pressing).

## 5. UI & User Interaction

- **Visual:** A single large text label showing the **Current Step**.
- **Context:** User sees "Priorität: 70" but not the full queue.
- **Interaction:**
  - **OK:** "I did it." (Next item)
  - **Ja/Nein:** Answers "Wenn..." questions.
  - **Ereignis:** "Something happened" (Trigger a `Checkliste bei...`).

## 6. Migration & Reconstruction Notes

To rebuild this in a modern stack (OpenClaw/Web), we must preserve the **Cybernetic Loop**:
1.  **State is External:** The system holds the state, not the user's brain.
2.  **Interrupts are Key:** The value is not the list, but the *interruption* when a higher-priority need arises (e.g., "Stop working, eat lunch").
3.  **Parsable Prose:** The user maintains logic in a readable text document. We should keep a way to define logic in text/markdown, perhaps translating it to a structured format (JSON/YAML) behind the scenes.

### Limitations in VB5 to Overcome
- **Hardcoded Paths:** Needs config.
- **Fragile Parsing:** `Mid(..., 11)` is dangerous. Needs a real parser.
- **Opaque Queue:** User can't see "What's next?". A sidebar showing the priority tree would be a massive UX upgrade.
- **Manual Sync:** Timer is dumb polling. Modern event loop is needed.
