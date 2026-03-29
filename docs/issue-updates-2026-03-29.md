# Issue-Kommentare für 2026-03-29

Folgende Kommentare sind in den GitHub-Issues zu hinterlegen.

## Issue #8 — Statistische Fenster-Aktivitäts-Profile (Exklusivitätsanalyse)

### Kommentar:
Neues Tool `tools/title_stability.py` implementiert (Commit 95afaf0).

**Was es macht:** Berechnet für jeden Fenstertitel zwei Metriken:
- **Exklusivität:** Wie stark ist ein Titel an eine bestimmte Aktivität gebunden?
- **Transitions-Stabilität:** Wie oft bewirkt das Auftauchen des Titels einen Aktivitätswechsel?

**Klassifiziert in 4 Kategorien:**
- STÖRER (niedrige Exkl. + hohe Stab.) → z.B. "Live365 Scraper", "Microsoft Access" generisch
- MARKER (hohe Exkl. + niedrige Stab.) → z.B. "Aufgabe erledigt — Zähne putzen"
- KONSISTENT (hohe Exkl. + hohe Stab.) → z.B. "Timeline Nacherfassung"
- AMBIG (niedrige Exkl. + niedrige Stab.)

**Ergebnisse über 26 Tage:** 375 Störer (235h), 441 Konsistente (98h), 43 Marker (4h), 8 Ambige (34m).

Wird als Grundlage für Issue #15 (transparente Störer) und Issue #21 (Confidence Learning) verwendet.

---

## Issue #15 — Störer-Prozesse als transparent markieren

### Kommentar:
Indirekt über den Confidence Store adressiert (Commits 14a7a84, dcedcb7).

**Was umgesetzt wurde:**
- `title_stability.py` identifiziert Störer-Titel quantitativ (Issue #8)
- Der `confidence_learner.py` berechnet `p_same_before` und `p_same_after` für jeden Titel (Commit b62351e)
- Titel mit p_same_before >= 85% UND p_same_after >= 85% UND top_confidence < 70% werden als **Durchreicher** klassifiziert
- `classify_entry()` in `windowmon_summary.py` gibt für Durchreicher `_UNCLASSIFIABLE` zurück → `build_activity_blocks()` übernimmt die vorige Aktivität

**Ergebnis:** Fragmentierung von 1470 auf 705 Blöcke (-52%) am Testtag 2026-03-28.

**Noch offen:** Explizite Transparenz-Liste für Prozesse (Live365Scraper.exe, etc.) statt nur über Durchreicher-Logik.

---

## Issue #21 — Überwachtes Lernen aus Korrekturdaten (Feedback-Loop für AutoDetect)

### Kommentar:
Kernimplementierung abgeschlossen. Mehrere Commits:

**1. `confidence_learner.py` (cd1343d):**
- EMA-basiertes Lernsystem (80% alt / 20% neu)
- Verarbeitet windowmon-Logs + planner-log, baut confidence_store.json
- Über 26 Tage: 2.904 Einträge (nach Normalisierung) mit Konfidenzen

**2. Transition-Wahrscheinlichkeiten (b62351e):**
- `p_same_before` und `p_same_after` pro Titel
- Ermöglicht Durchreicher/Marker-Erkennung (←hoch →hoch = Noise)

**3. Titel-Normalisierung:**
- Edge: "und X weitere Seiten" abgeschnitten + Zero-Width-Space (U+200B) entfernt (3f63454)
- Winamp: Alle Songtitel → "(Winamp playback)" (cae116a)
- Teleworking-Filter: 12 BRZ-Task-Codes ausgefiltert (dbe70c7)

**4. Integration in AutoDetect (c49d53b, dcedcb7):**
- Confidence Store als Fallback wenn hardcodierte Regeln _UNCLASSIFIABLE liefern
- 33 niedrig-akkurate Regeln (gemessen mit rule_accuracy.py, 072e597) werden vom Store überstimmt
- Durchreicher-Erkennung VOR Konfidenz-Cutoff (14a7a84)

**5. Design-Dokumente:**
- `docs/confidence-learning-design.md` — Gesamtkonzept
- `docs/known-classification-issues.md` — Bekannte verbleibende Probleme

**Noch offen:** 
- Session-Level-Konfidenz (Update bei jedem Timeline-Import, nicht nur am Tagesende)
- Issue #22 (Off-PC-Erkennung) für korrekte Pop-Up-Klassifizierung
- MIN_CONFIDENCE-Tuning für Planer-eigene Fenster
