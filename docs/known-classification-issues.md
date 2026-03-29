# Known Classification Issues (Stand: 2026-03-29)

Gesammelt aus der heutigen Session. Zu fixen in zukünftigen Iterationen.

## 1. Planer-eigene Fenstertitel unter 50% Konfidenz
- Viele Planer-Fenster (Reaktiver Planer, Aufgabe erledigt, etc.) haben 
  "Nacherfassung Ablauf" als höchste Konfidenz, aber unter 50%
- Werden daher nicht vom Store erkannt und fallen auf hardcodierte Regeln zurück
- **Möglicher Fix:** MIN_CONFIDENCE für Durchreicher separat senken, oder 
  Planer-eigene Fenster generell als transparent behandeln (Issue #15)

## 2. Pop-Up-Fenster setzen fälschlich die Off-PC-Aktivität
- "Aufgabe erledigt — X" und "Eintrag bearbeiten — X" werden von 
  `_PLANNER_DIALOG_ACTIVITY` erfasst und geben die Aktivität X zurück
- Problem: Wenn der User nur kurz das Pop-Up sieht (11 Sekunden) und dann 
  weiterarbeitet, wechselt die erkannte Aktivität zu X obwohl X gar nicht 
  stattfindet
- Das ist Issue #22 (Off-PC-Erkennung) — die Pop-Ups sollten als "Planer-Bedienung"
  klassifiziert werden, nicht als die genannte Aktivität

## 3. "Vorgezogene Aktivität erfassen" lernt falsche Konfidenz
- "Vorgezogene Aktivität erfassen — Einkauf LEEKBI" wurde als tatsächliche 
  Einkaufs-Aktivität gelernt, weil der User das regulär erfasst hat UND 
  danach tatsächlich einkaufen war
- Aber bei der Nacherfassung erscheint das gleiche Fenster nur 11 Sekunden →
  trotzdem wird die Einkaufs-Aktivität gesetzt
- **Ursache:** Es gibt kein Off-PC im Titel bei "Vorgezogene Aktivität", daher
  wird die Aktivität direkt extrahiert statt als Off-PC behandelt
- **Zusammenhang mit Issue #22:** Wenn Off-PC korrekt gesetzt würde, wäre das Problem gelöst

## 4. Fragmentation bei Planer-Fenstern
- Schneller Wechsel zwischen "Erfassung Ablauf" und "Nacherfassung Ablauf" 
  bei Planer-Fenstern
- Deutlich verbessert durch Durchreicher-Fix (1470→705 Blöcke), aber noch 
  nicht vollständig gelöst
- Restproblem: Planer-Fenster, die NICHT als Durchreicher erkannt werden 
  (weil p_same_before/after zu niedrig oder nicht im Store)

## Priorisierung
- Issue #22 (Off-PC-Erkennung) würde #2 und #3 gleichzeitig lösen
- Issue #15 (Störer als transparent) würde #1 und #4 verbessern
- Beide sind im GitHub-Backlog dokumentiert
