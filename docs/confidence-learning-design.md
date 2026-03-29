# Confidence Learning Design — Fenstertitel → Aktivität

## Überblick

Ein EMA-basiertes (Exponential Moving Average) Lernsystem, das aus der Korrelation 
von Fenstertiteln und geloggten Aktivitäten automatisch Konfidenzen berechnet.

Zwei Ebenen:
1. **Session-Konfidenz** — wird bei jedem Timeline-Import aktualisiert (80/20 alt/neu)
2. **Globale/permanente Konfidenz** — wird am Tagesende über das volle windowmon-Log aktualisiert

## Ablauf

### Bei Timeline-Erfassung (Session-Level)
1. Für alle Fenstertitel im Zeitraum wird versucht, die passende Aktivität anhand 
   der gespeicherten Konfidenzen herauszufinden.
2. Bei jedem Import werden die Konfidenzen angepasst (wenn Checkbox gesetzt):
   - Matching aller Fenstertitel im Zeitraum gegen die importierte Aktivität
   - Bei gleichen Titeln in verschiedenen Aktivitäten: Konfidenz nach Zeitanteil verteilt
   - "Import-Konfidenz" wird mit bestehender verglichen: **80% alt + 20% neu**
   - Ergebnis wird gespeichert

### Am Tagesende (Globales Level)
- Gesamtes windowmon-Log wird mit allen geloggten Aktivitäten verglichen
- Permanente Konfidenz wird analog angepasst (80/20-Gewichtung)
- Alternativ: Konfidenz basierend auf letzten 5 Tagen berechnen
- Konfidenzen für nicht gesichtete Titel bleiben erhalten (kein Vergessen)

## Mehrfach-Konfidenzen

Jeder Fenstertitel kann mehrere Konfidenzen für verschiedene Aktivitäten haben:
- Nur die höchste zählt fürs Matching
- Niedrigere werden trotzdem gespeichert (können über Zeit aufholen)
- Unter 1% wird geprunt

## Titel-Normalisierung

Vor jeder Analyse werden hardcodierte Regeln angewendet:
- Edge: "und X weitere Seiten - Persönlich – Microsoft Edge" wird abgeschnitten
- Allgemein: "(Keine Rückmeldung)" wird entfernt
- Trailing whitespace entfernt
- Perspektivisch: Wildcard/Pattern-Matching (z.B. `*Andon FM*`)

## Störer-Behandlung

Titel mit niedriger Exklusivität (< 70%) und hoher Stabilität (> 70%) werden als 
"Störer" klassifiziert (siehe title_stability.py). Deren Konfidenz für jede Aktivität 
bleibt niedrig. Unter einer Matching-Schwelle sollte ein Titel als "unklassifizierbar" 
gelten statt mit z.B. 12% auf eine Aktivität zu matchen.

Zusätzlicher Faktor: Bei "drübergezogenen" Aktivitäten (User erweitert Block über 
kurzen Unterbrecher, weil Umbenennen aufwändiger als Erweitern) sorgt die 
zeitgewichtete Konfidenz dafür, dass der Störer-Titel nur minimal Gewicht bekommt 
(3 Sekunden Störer vs. 5 Minuten Hauptaktivität).

## Datenformat (confidence_store.json)

```json
{
  "msedge.exe||Andon FM | Andon Labs": {
    "confidences": {
      "Arbeitszeit absolvieren (Nachmittag) BREPDZ": 0.38,
      "Surfen Andon FM RAAFSU": 0.15,
      "Untersuchung Rotation Andon FM RAAFAN": 0.12
    },
    "total_secs": 13800,
    "last_seen": "2026-03-28"
  }
}
```

Schlüssel: `"process||normalized_title"` (doppelter Pipe-Separator)

## Kaltstart / Bootstrap

Beim ersten Lauf werden die Konfidenzen direkt aus dem windowtitle_learner-Output 
bootstrapped. Die historischen Daten (windowmon + planner-log) existieren bereits 
zurück bis mindestens 2026-03-03 und können rückwirkend verarbeitet werden.

## Verwandte Issues

- **Issue #21** — Überwachtes Lernen aus Korrekturdaten (Haupt-Issue)
- **Issue #10** — Regel-Editor (Pattern/Wildcard-Matching)
- **Issue #8** — Exklusivitätsanalyse (statistische Grundlage)
- **Issue #15** — Störer-Prozesse als transparent markieren
- **Issue #9** — Checkbox-Persistenz für Timeline-Reklassifizierung

## Tools

- `tools/windowtitle_learner.py` — Korrelationsanalyse (bestehend)
- `tools/title_stability.py` — Stabilitäts-/Störer-Klassifizierung (bestehend)
- `tools/confidence_learner.py` — EMA-Konfidenz-Berechnung (neu)

## Quelle
Konzept von Kurt Woloch, 2026-03-29, dokumentiert in OpenClaw-Session.
