# Analysis of C# Tagesplanung Architecture

## 1. CSV Parsing (Activity Definitions)
*   **Module:** `CsvConverter.cs`
*   **Mechanism:** Reads `Planungsaktivitaeten.csv`.
*   **Format:** Semicolon-separated values.
*   **Columns:** `Activity`, `Minutes`, `List`, `Priority`, `Weekdays`, `Starting time`, `Dependencies`, `Preceding_Activity`.
*   **Logic:**
    *   Handles quoted fields via `SplitCsvLine`.
    *   Detects encoding (UTF-8 BOM or Windows-1252).
    *   Parses numbers (`Minutes`, `Priority`) using invariant culture (dots/commas handled).
    *   Parses `Starting time` as `DateTime` or `TimeSpan` (combined with the planning date).
    *   Returns a `List<Planungsaktivitaet>`.

## 2. List Handling & Interactions
*   **Modules:** `InputProcessing.cs`, `ListTransformer.cs`, `Models.cs`.
*   **Structure:** Activities are grouped by their `Liste` field into `Liste_Planungsaktivitaet` objects.
*   **State Tracking:** A `ListState` struct tracks:
    *   `CurrentIndex`: The next activity to consider in that list.
    *   `Status`: `Started` or `Stopped`.
    *   `WaitTime`: A blocking timestamp (list cannot schedule until this time).
*   **Interactions (Start/Stop/Restart):**
    *   Handled in `ListTransformer.HandleSpecialActivities`.
    *   **"Start list X":** Sets list X status to `Started` and resets `CurrentIndex` to 0.
    *   **"Stop list X":** Sets list X status to `Stopped`.
    *   **"Restart list X":** Sets list X status to `Started` (maintains current index).

## 3. Priority Sorting & Scheduling
*   **Modules:** `CandidateSelector.cs`, `ListTransformer.cs`.
*   **Algorithm:**
    *   The scheduler runs a simulation loop, advancing `currentTime`.
    *   In each step, `CandidateSelector.SelectNextCandidates` identifies the *one* valid next activity from each *Started* list.
    *   **Validation:** Checks `Weekdays`, `Dependencies`, and `WaitTime`.
    *   **Selection:** Candidates are ordered by **Priority (Descending)**.
    *   **Tie-Breaker:** If priorities match, the `SourceListOriginalIndex` (order of lists in input) is used.
    *   The winner is scheduled, `currentTime` advances by its duration, and its list's `CurrentIndex` increments.

## 4. Dependencies & Conditions
*   **Module:** `ActivityValidator.cs`.
*   **Mechanism:** Parses the `Dependencies` and `Weekdays` strings.
*   **Keywords:** `Wochenende`, `Feiertag`, `Urlaubstag`, `BRZ_geplant`, `Teleworking`, `Putztag`.
*   **Logic:**
    *   **Weekdays:** Supports positive ("Montag,Dienstag") and negative ("nicht Wochenende") conditions.
    *   **Dependencies:** Evaluates simple expressions like `Planungsvariablen.Wochenende` or `!Planungsvariablen.Teleworking`.
    *   Also checks fixed start date consistency.

## 5. Timed Items & "Wait"
*   **Modules:** `ListTransformer.cs`, `CandidateSelector.cs`.
*   **Fixed Start Time:**
    *   If `Anfangszeit_festgelegt` is true: The activity is *deferred* (skipped) until `currentTime >= Anfangszeit`.
    *   Once time is reached, it competes normally via priority (or triggers a conflict resolution if it *must* happen now).
*   **Wait Commands:**
    *   **"Wait":** Adds the activity's duration to the list's `WaitTime`. The list is blocked until then.
    *   **"Wait until top of hour":** Calculates the next full hour and sets `WaitTime`.
    *   These "Wait" activities are *not* added to the final schedule output; they just modify the state.

## 6. Interruptions & Splitting (Fs.)
*   **Module:** `FixedTimeConflictHandler.cs`.
*   **Trigger:** A fixed-time activity (higher priority) needs to start *during* an already scheduled activity.
*   **Mechanism:**
    1.  **Shorten:** The current activity is truncated to end at the fixed start time.
    2.  **Calculate Remainder:** `continuation_duration = original - shortened`.
    3.  **Create Continuation:** A new activity named `Original (Fs.)` is created with the remaining duration.
    4.  **Insert:** This continuation is inserted back into the source list at the *current* index (replacing the original).
    5.  **Result:** The scheduler picks up the "(Fs.)" part immediately after the interruption (unless displaced by even higher priorities).

## 7. Final Output Generation
*   **Modules:** `ListTransformer.GenerateFinalScheduleOutput`, `ConflictResolver`.
*   **Process:**
    *   `GeplanteAktivitaeten` list is populated during the simulation.
    *   **Gap Filling:** `ConflictResolver.FillScheduleGaps` inserts generic activities into empty time slots.
    *   **Formatting:** Iterates through the list, printing `HH:mm ActivityName (Dauer: X, Prio: Y)`.
    *   **Unplanned:** Appends a list of activities that were never scheduled (e.g., list stopped, conditions not met).
    *   **Output:** Writes to `Planung dd.MM.yyyy.txt`.

## 8. Comparison: C# vs. VB5 Checklisten
*   **Architecture Shift:**
    *   **VB5 (Inferred):** Likely a **runtime execution** system. It showed valid items *now* from multiple lists concurrently. "Reactive" means the UI updated in real-time as you checked things off. "Interrupt-driven" meant high-priority items popped up the moment they became valid.
    *   **C# (Current):** A **static planner**. It simulates the day *in advance*.
*   **Lost Capabilities:**
    *   **Concurrent List Execution:** The C# app linearizes everything into a single timeline. You cannot easily "pick" from multiple valid options during the day; you strictly follow the pre-calculated text file.
    *   **Reactive Next-Item:** If you are faster/slower than the plan, the static text file becomes inaccurate. The VB5 system likely adjusted dynamically.
    *   **True Interrupts:** In C#, interrupts are calculated during planning. In a runtime system, an interrupt (e.g., "Phone rings") can happen anytime.
