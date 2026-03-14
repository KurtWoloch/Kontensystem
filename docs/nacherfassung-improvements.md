# Verbesserungen Nacherfassung / Ablauf-Erfassung

Stand: 2026-03-14
Quelle: Analyse des Tagesberichts 2026-03-13 + Diskussion der Schmerzpunkte

## Kontext

Am 13.03.2026 wurden **~107 Minuten (~1h 47m)** für Nacherfassung des Ablaufs aufgewendet — bei 0 Minuten geplant. Das sind ~10% der gesamten Tagesarbeitszeit. Der offizielle Tagesbericht wies nur 22 Minuten "ungeplante Aktivitäten" aus, obwohl ~6h 40m an `windowmon_import`-Aktivitäten nicht im Plan standen.

## Identifizierte Probleme

### 1. Mini-Segment-Granularität
Der Window Monitor zerlegt zusammenhängende Arbeit in viele kleine Segmente (1–3 Minuten), die jeweils einzeln beurteilt werden müssen. Alternieren zwischen z.B. Edge und Explorer erzeugt mehrere Segmente für eine einzige Aktivität.

### 2. Umständlicher Korrektur-Workflow (Copy-Paste)
Wenn ein Segment falsch erkannt wird und keine passenden Vorschläge erscheinen:
1. Nacherfassung schließen
2. Ins Log gehen
3. Richtige Aktivität suchen
4. Doppelklick → Name+Kürzel kopieren
5. Nacherfassung wieder öffnen
6. Segment wiederfinden
7. Kopierten Aktivitätsnamen einfügen
8. Übernehmen

~8 Schritte für eine einzige Korrektur. Am 13.03. gab es 80+ autodetect-corrections.

### 3. Zusammenfassungs-Problem
Versuch, kleine gleichartige Segmente zu einem großen zu vereinen → Überschneidungen mit bereits geloggten Segmenten → alles löschen → nochmal nacherfassen. Doppelte Arbeit.

### 4. Reihenfolge-Zwänge des Planers
Aktivitäten müssen in der Reihenfolge ihrer Liste abgeschlossen werden. Probleme:
- Bedingte Aktivitäten ("Warst Du heute schon draußen?") blockieren nachfolgende
- BRZ-Dokumentation musste nach 37m echter Arbeit vorzeitig als "abgeschlossen" markiert werden, weil sie sonst die Arbeitszeit-Kette blockiert hätte
- Beim Nacherfassen am Abend: Aktivitäten werden in falscher Reihenfolge präsentiert

### 5. Akkumulation durch Verzögerung
Je länger nicht nacherfasst wird, desto größer der Berg. Am 13.03. entstand ein großer Block nach 22:00 mit 3+ Stunden Rückstand. Größerer Rückstand = schwierigere Zuordnung (Erinnerung verblasst).

### 6. Doppelt-Logging
Aktivitäten werden sowohl ungeplant eingefügt als auch als geplante übersprungen → Duplikate → manuelles Löschen nötig. Das System hat zwei parallele Erfassungswege (Planer-Queue vs. Windowmon-Import), die nicht wissen, dass sie über dieselbe Aktivität reden.

### 7. Verlust von autodetect-corrections bei Zeitraum-Ausdehnung
Workaround "Segment zeitlich ausdehnen, um benachbarte Fehlerkennungen mit abzudecken" ist effizient, wird aber vermieden, weil dadurch keine autodetect-corrections für die überdeckten Segmente entstehen → die Lernbasis für bessere Erkennung geht verloren.

## Verbesserungsvorschläge

### V1. Synthetische autodetect-corrections bei Zeitraum-Ausdehnung
Wenn ein Segment zeitlich ausgedehnt wird und dabei andere (nicht übernommene) Segmente überdeckt: automatisch synthetische corrections generieren für die überdeckten Segmente.

Beispiel: Segment A (10:04–10:08, "Andon FM / Backlink Broadcast") wird ausgedehnt zu 10:04–10:15. Die überdeckten Segmente B (10:08–10:11, "div. Surfen") und C (10:11–10:15, "Ansehen YouTube-Videos") bekommen automatisch corrections: B.original → A.corrected, C.original → A.corrected.

**Status:** Von Kurt als "sehr gut" bewertet. Eliminiert den Trade-off zwischen schneller Nacherfassung und Erhalt der Corrections-Lernbasis.

### V2. Priorisierte Vorschläge beim Eintippen
Aktuell: Vorschläge aus gesamtem historischen Pool ("WC" → "WC / Windeltest" statt "WC BREPWC").

Vorgeschlagene Priorisierung:
1. Heute geplante Aktivitäten (aus Projektion)
2. Bereits im heutigen Log vorhandene Aktivitäten
3. Häufig verwendete Aktivitäten der letzten Wochen (Recency-Faktor)
4. Historische Aktivitäten

Alte, selten genutzte Aktivitäten wie "WC / Windeltest" sollten niedrigeren Score bekommen als "WC BREPWC", das täglich vorkommt.

### V3. Zusammenfassung gleichartiger Mini-Segmente
Heuristik: Wenn aufeinanderfolgende Window-Monitor-Segmente denselben erkannten Aktivitätsnamen erhalten (oder wenn dasselbe Fensterpaar alterniert), vor der Nacherfassung automatisch zu einem Block zusammenfassen.

### V4. Reihenfolge-Flexibilität erhöhen
Mechanismen finden, um Aktivitäten out-of-order nachzuerfassen, ohne dass die Planer-Queue blockiert. Details noch zu klären — das Vorziehen erzeugt derzeit potenzielle Verdopplungen.

### V5. Originale Projektion als alternative Sortierordnung
**Idee:** Toggle-Button in der GUI ("Sortierung: Aktuell / Original"), der die Geplant-Liste nach der **Tagesanfangs-Projektion** sortiert statt nach der aktuellen Queue.

- Zeigt geplante Aktivitäten in der **ursprünglichen Reihenfolge** mit den **ursprünglich geplanten Zeiten**
- Filtert heraus, was bereits im Log steht (gleiche Logik wie beim Programmstart-Abstreichen)
- Vorteil: Die Originalreihenfolge entspricht oft besser der tatsächlichen Abfolge des Tages

Technisch: `projection-YYYY-MM-DD.json` existiert bereits. Beim Umschalten:
- Projektion laden
- Gegen aktuelles Log filtern (bereits erledigte/übersprungene ausblenden)
- est_start/est_end aus Projektion als Orientierung anzeigen

**Offener Punkt:** Interaktion mit Abschluss-Mechanik. Beim Markieren als erledigt aus der Originalprojektion-Ansicht: Aktivität muss trotzdem in der Queue vorgezogen werden, was Verdopplungs-Probleme verursachen kann (dasselbe Problem wie V4). Die Projektionsansicht hilft primär bei der **Orientierung** (was kommt als nächstes?), löst aber nicht automatisch das Reihenfolge-Problem.

### V6. Verbesserung des Tagesberichts
Neue Kategorie im Report: **"Nacherfasst (nicht im Plan)"** für `windowmon_import`-Aktivitäten, die keiner geplanten Aktivität zugeordnet werden konnten. Zusätzlich: Überzeit-Analyse pro Aktivitätskategorie (geplante vs. tatsächliche Zeit).

## Baseline-Referenz: Nacherfassungsaufwand Jänner 2026

Quelle: Ablauf-Dateien 20.–26.1.2026 (manueller Window-Logger-Workflow, vor dem neuen Planer).
Ohne BRZ-Planung und SAP-Zeiterfassung.

### Verifiziert vollständig (24.–26.1.)

| Datum | Tag | BRZ | Planung | Nacherfassung | TOTAL |
|-------|-----|-----|---------|---------------|-------|
| 24.1. | Sa | – | 1m | 77m | 78m |
| 25.1. | So | – | 3m | 69m | 72m |
| 26.1. | Mo | ✓ | 18m | 13m | 31m |
| | | | **Ø 7m** | **Ø 53m** | **Ø 60m** |

### Vollständig, aber teils mit Nacherfassung von Vortagen (20.–23.1.)

| Datum | Tag | BRZ | Planung | Nacherfassung | TOTAL | Hinweis |
|-------|-----|-----|---------|---------------|-------|---------|
| 20.1. | Di | ✓ | 23m | 52m | 75m | davon 25m Nacherfassung 19.1. |
| 21.1. | Mi | ✓ | 18m | 86m | 104m | davon ~50m Nacherfassung Aufwand 20.1. |
| 22.1. | Do | ✓ | 27m | 82m | 109m | Nacherfassung 21.1. + eigener Tag |
| 23.1. | Fr | ✓ | 27m | 122m | 149m | Nacherfassung 21.+22.+23.1. |
| | | | | | **Ø 109m** | (20.–23.1., ~103m/Tag reine Eigenleistung) |

### Erkenntnisse

- **Fragmentierung verschleiert den Aufwand:** Am So 25.1. gab es 56 einzelne Nacherfassungs-Einträge à 1–2 Min. = 69m, aber es fühlt sich nicht nach über einer Stunde an.
- **BRZ-Tage = weniger Nacherfassung:** Arbeitszeit ist ein großer Block → weniger zu dokumentieren. Mo 26.1. hatte nur 13m.
- **Rückstau-Muster existierte schon:** Fr 23.1. musste 3 Tage nachholen (122m).
- **Ab ~26.1. rissen unvollständige Abläufe ein:** Tage wurden nicht mehr bis zum Ende nacherfasst, Nacherfassung wurde irgendwann aufgegeben.
- **Der neue Planer hat das Problem nicht verursacht**, sondern sichtbar gemacht (Tagesbericht-Funktion + strukturiertes Log statt verstreute `*`-Zeilen).

### Vergleichswert 13.3.2026 (neuer Planer)

- Nacherfassung: **107m** (ganzer Tag, fragmentierter Tag mit Grok'n Roll-Rabbit-Hole)
- Am 14.3.2026 nach Einbau der neuen AutoDetect-Regeln: **17m für 3h** Zeitraum

## Analyse: Wo liegt der größte Hebel?

| Verbesserung | Aufwand | Erwartete Zeiteinsparung pro Tag |
|-------------|---------|----------------------------------|
| V1. Synthetische corrections | mittel | ~10–15m (weniger Angst vor Ausdehnung → schnellere Nacherfassung) |
| V2. Priorisierte Vorschläge | niedrig | ~10–20m (weniger Copy-Paste-Zyklen) |
| V3. Mini-Segment-Zusammenfassung | mittel | ~15–25m (weniger Einzelentscheidungen) |
| V4. Reihenfolge-Flexibilität | hoch | ~10–15m (weniger mentales Jonglieren) |
| V5. Originale Projektion | mittel | ~5–10m (bessere Orientierung beim Nacherfassen) |
| V6. Besserer Tagesbericht | niedrig | 0m (kein direkter Zeitgewinn, aber bessere Transparenz) |

V2 und V3 zusammen hätten vermutlich den größten Effekt bei überschaubarem Aufwand.
