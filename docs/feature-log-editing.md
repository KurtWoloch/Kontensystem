# Feature: Log-Einträge bearbeiten, löschen & duplizieren

**Status:** Spezifikation  
**Datum:** 2026-03-09  
**Anlass:** Ghost Entries vom 08.03 (versehentlich abgeschlossene Eingaben, die sich nicht korrigieren ließen)

---

## Problem

Einmal geloggte Einträge im Planner können derzeit weder bearbeitet noch gelöscht werden. Fehlerhafte Einträge (abgeschnittene Namen, falsche Zeiten) bleiben dauerhaft im Log und können nur durch "drüber loggen" kaschiert werden — was die Datenqualität verschlechtert und zusätzliche Zeit kostet.

Zusätzlich: Bei der Nacherfassung wiederholen sich gleichartige Einträge häufig (z.B. "Scan Thinking Frequencies" alle paar Minuten im Wechsel mit anderen Aktivitäten). Jedes Mal alles neu einzutippen ist unnötig aufwendig.

## Lösung: Zwei Zugangswege

### 1. Schnelllöschung (Entf/Backspace)

- **Auslöser:** Eintrag in der Log-Liste anklicken (selektieren) → Entf oder Backspace drücken
- **Verhalten:** Bestätigungsdialog ("Eintrag '[Name]' [HH:MM–HH:MM] wirklich löschen?") → Ja/Nein
- **Ergebnis:** Eintrag wird aus dem Log entfernt
- **Zweck:** Schnelles Entfernen offensichtlicher Fehleinträge (Ghost Entries, versehentliche Absendungen)

### 2. Bearbeitung per Doppelklick

- **Auslöser:** Doppelklick auf einen Eintrag in der Log-Liste
- **Verhalten:** Eingabeformular öffnet sich mit den bestehenden Werten vorausgefüllt (Aktivitätsname, Code, Startzeit, Endzeit, Kommentar)
- **Aktionen im Formular:**

| Button | Verhalten |
|--------|-----------|
| **Ändern** | Überschreibt den bestehenden Eintrag mit den neuen Werten |
| **Löschen** | Entfernt den Eintrag komplett (wie Schnelllöschung) |
| **Duplizieren** | Speichert die (geänderten) Werte als **neuen** Eintrag; der ursprüngliche Eintrag bleibt unverändert erhalten |
| **Abbrechen** | Formular schließt sich, nichts passiert |

### Hauptanwendungsfälle

1. **Fehleinträge korrigieren:** Ghost Entry mit abgeschnittenem Namen → Doppelklick → Löschen (oder Ändern mit korrektem Namen)
2. **Falsche Zeiten korrigieren:** "Versehentlich falsche Endzeit übernommen" → Doppelklick → Ändern
3. **Wiederkehrende Aktivitäten schnell nacherfassen:** "Scan Thinking Frequencies" kam 10x vor → ersten Eintrag doppelklicken → nur Zeiten anpassen → Duplizieren → wiederholen. Spart das erneute Eintippen/Auswählen des Aktivitätsnamens und Codes.

## Technische Hinweise

- Die Log-Datei (`planner-log-YYYY-MM-DD.json`) muss für In-Place-Updates unterstützt werden (bisher nur Append)
- Beim Ändern/Löschen: Eintrag über Index oder Zeitstempel identifizieren
- Beim Duplizieren: Neuer Eintrag bekommt eigenen Zeitstempel, wird am Ende der Liste angefügt (chronologisch sortiert)
- Bestätigungsdialog bei Löschen ist wichtig — kein versehentliches Entfernen valider Einträge

## Priorisierung

Hoch — reduziert direkt die Zeit für Nacherfassung und verbessert Datenqualität. Hätte am 08.03 mindestens 10–15 Minuten gespart (Ghost Entries + wiederholte Einträge).
