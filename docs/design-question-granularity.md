# Design-Frage: Welche Granularität braucht die Erfassung?

Entstanden am 14.3.2026 aus einer Reflexion über den Nacherfassungsaufwand.

## Ausgangslage

- Jänner 2026 (manuell): ~53-103 Minuten/Tag für Nacherfassung Ablauf
- März 2026 (neuer Planer): ~87-107 Minuten/Tag für Nacherfassung
- AutoDetect-Match-Rate (Name + Task-Code): ~4% am 13.3.2026
- Messung verbraucht ~11% der Wachzeit → Beobachter dominiert das Experiment

## Historische Granularitätsstufen

| Stufe | Segmente/Tag | Aufwand | Zeitraum |
|-------|-------------|---------|----------|
| Taschenkalender | max. ~14 | minimal | bis ~2021 |
| Handgeschriebene Planung | ~40-60 | ~15-20m | ab ~2021 (Ablauf vom Vortag kopiert + angepasst) |
| C#-Planungstool | ~60-130+ | wachsend | ab 17.3.2024 (inkl. Checklisten-Inhalte) |
| C#-Planung + Window Logger | ~100-200 Fenster | ~30-60m Korrektur + Zusammenfassung | Window Logger ab ~2007, parallel zur Planung |
| Ablauf-Datei (minutengenau) | ~60-150 Zeilen | ~1-2h/Tag | Drift über Zeit |
| Neuer Planer + Windowmon | ~100-180 Einträge | ~1-2h/Tag | ab März 2026 |

## Mögliche Zwecke der Erfassung

1. **Aufwandserfassung** (Kontensystem): Wieviel Zeit geht auf welches Konto?
   - Braucht: ~10-20 Blöcke/Tag, Konto-Zuordnung, Stunden
   - Braucht NICHT: Minutengenauigkeit, jeder Fensterwechsel

2. **Selbstoptimierung**: Wo verschwende ich Zeit? Wo gibt es Drift?
   - Braucht: Muster über Wochen (z.B. "Nacherfassung frisst 10% der Zeit")
   - Braucht NICHT: tägliches Minutenprotokoll

3. **Kontrolle/Beweis**: "Ich habe den Tag sinnvoll verbracht"
   - Historisch verwurzelt (50-Seiten-Dokumentation 2000, Helicopter-Mother)
   - Frage: Für wen wird das heute noch bewiesen?

4. **Tagesrückblick / Tagebuch**: Was habe ich heute gemacht?
   - Braucht: ~20-30 narrative Blöcke
   - Braucht NICHT: Sekundengenauigkeit

5. **Gewohnheit**: "So mache ich das halt"
   - Kein Zweck, aber reale Ursache für Drift in Richtung Übergenauigkeit

## Frühere Pragmatismen (die funktioniert haben)

- **Morgenroutine als ein Block**: Surfen währenddessen wurde nicht extra erfasst
- **Radio-Pauschale**: 8 min/Stunde pauschal abgezogen, nicht jeder Fensterwechsel
- **Window Logger Matching**: ~1h Mismatch pro Tag, Korrektur + Zusammenfassung ~30-60 Min
  - Davon 40-50% für Zusammenfassung (= Reduktion der Segment-Anzahl für Abrechnung)
  - Das hat für die Aufwandserfassung ausgereicht
- **Vor dem Window Logger**: Aufwandserfassung händisch aus Erinnerung oder
  Adaption der (damals kurzen) Planung → wesentlich schneller erledigt
- **Sprunghafte Aufwandssteigerung** mit Einführung des Window Loggers:
  Auslöser war der Beginn von Onlinespielen (z.B. Chefville), wo ständig
  zwischen Spiel und anderen Tätigkeiten hin- und hergesprungen wurde →
  der Window Logger machte diese Fragmentierung erstmals sichtbar, und die
  Aufwandserfassung musste nun jedes Fragment einzeln verarbeiten

## Der vergessene Zweck: "Was soll ich jetzt tun?"

6. **Echtzeit-Steuerung**: Was hat gerade die höchste Priorität?
   - Diesen Zweck erfüllten früher: Checklisten (teilweise), Planungs-/Aufwandsfiles (Suche nach höchster Prio), geplanter Ablauf (solange kein Rückstand)
   - Diesen Zweck erfüllt der neue Planer **gut** (Queue mit Prioritäten)
   - Problem: Ausgelassene Aktivitäten blockieren die Queue ("Warst Du heute schon draußen?")
   - **Das ist ein Queue-Management-Problem, kein Erfassungsproblem**

### Kernspannung im Tool

Der Planer vereint zwei Funktionen mit unterschiedlichen Anforderungen:

| Funktion | Zeitpunkt | Anforderung | Aufwand |
|----------|-----------|-------------|---------|
| Steuerung ("Was jetzt?") | Echtzeit | Schnell, klar, keine Ablenkung | Gering |
| Nacherfassung (Aufwandserfassung) | Nachträglich | Genauigkeit, Konto-Zuordnung | 1-2h/Tag |

Die Nacherfassung im Planer belastet den Echtzeit-Workflow.
Frage: Sollte die Nacherfassung ein separater Workflow sein (wie früher beim Window Logger)?

## Offene Fragen (noch zu beantworten)

- Was ist das primäre Ziel des neuen Planers?
- Welche Granularität ist für dieses Ziel *ausreichend*?
- Lohnt sich die minutengenaue Erfassung, oder reichen grobe Blöcke + Pauschalen?
- Soll die Ablauf-Datei in der bisherigen Form weitergeführt werden?
- Wie war das Kosten-Nutzen-Verhältnis des Window Loggers (der über Jahre funktioniert hat)?
- Was wäre ein realistisches Ziel für den täglichen Erfassungsaufwand? (10 Min? 20 Min? 30 Min?)

## Meta-Reflexion: Die Schachtelung (14.3.2026)

### "Wie meta wird das noch alles?"

Beobachtung beim Schwimmen: Fast alle Aktivitäten im Plan sind selbst
Meta-Aktivitäten — Vorbereitungen für etwas "Wirkliches", das irgendwann
passieren soll:

- Planer-Design → um den Planer zu bauen → um Aktivitäten zu verwalten →
  die selbst Vorbereitungen sind → für etwas "Wirkliches"
- Ohrwürmer katalogisieren → statt tatsächlich singen
- Psychologie-Bücher lesen → statt die Erkenntnisse zu leben
- Kommunikation mit Judith → Konzepte verteidigen, sich validieren
- Planung planen → statt tun

25 Jahre schleichende Drift in Richtung Meta-Aktivitäten.

### Warum: Die Funktion des Systems

Das Kontensystem und die Aufwandserfassung sind nicht nur Planungstools —
sie sind ein **Schutzschild**. Ihre tiefere Funktion:

**Beweisen, dass alles, was ich tue, gut überlegt ist und sich "rechnet".**

Herkunft: Eltern haben Eigenständigkeit systematisch verunsichert.
- Mutter: Eigenständiges Handeln → "Du kannst nicht alleine leben" →
  Drohung mit Psychologin / "Irrenhaus"
- Vater: Anforderungen an Form der Dokumentation, Geld ausgeben war
  emotional verboten, Pläne wurden angezweifelt → "überleg dir das
  erst einmal genauer"
- Effekt: Solange man zu Hause sitzt und plant, bleibt man bei den
  Eltern, gibt kein Geld aus, und macht nichts "Falsches"
- Internalisierte Botschaft: **Eigenständigkeit ist gefährlich,
  Planung ist sicher.**

Konsequenz heute:
- Einfache Handlungen ("ich kaufe mir ein Kebap") fühlen sich nicht
  "gut genug überlegt" an
- Permanentes Gefühl, dass jemand Vorwürfe machen könnte
- Das Kontensystem als permanenter Verteidigungsbrief an Eltern,
  die gar nicht mehr fragen
- Gehorsamkeit möglicherweise übertrieben — das System, das beweisen
  soll, dass man alleine leben kann, verhindert genau das

### Was folgt daraus für das Tool-Design?

Noch offen. Aber die Erkenntnis ist:
Die Frage "welche Granularität braucht die Erfassung?" ist nicht nur
eine technische Frage. Sie hängt daran, wie viel "Beweis" man braucht —
und ob man diesen Beweis überhaupt noch schuldig ist.

## Historische Aufwandszahlen

**Budget:** 1 Stunde/Tag für Planung + Nacherfassung + Aufwandserfassung + Kontensystem-Abrechnung.

| Zeitraum | Aufwandserfassung | Abrechnung | Planung/Ablauf | Total |
|----------|------------------|------------|----------------|-------|
| 1990er (Papier) | ~12m | ~48m | minimal | ~60m |
| ~2023 (konsolidierte Blöcke) | deutlich länger | ~10m | nicht berücksichtigt | >60m |
| Jän 2023 (Aufwandserfassung-Backlog-Stand) | — | — | 22-30m | 22-30m |
| Jän 2026 (manuell, verifiziert) | — | — | 53-103m | 53-103m |
| März 2026 (neuer Planer) | — | — | 87-107m | 87-107m |

**Beobachtung:** Die Aufwands-Drift ist klar sichtbar:
- Jänner 2023: ~22-30 Minuten für Planung/Ablauf, aber Korrekturen brechen oft
  mitten im Tag ab, Blöcke wesentlich ungenauer, Detailaktivitäten nicht erkennbar
- Jänner 2026: ~53-103 Minuten, minutengenaue Erfassung
- März 2026: ~87-107 Minuten, noch genauer durch Windowmon

**Wichtig:** Die niedrigen Zahlen von 2023 sind kein Zeichen von Effizienz.
Die Aufwandserfassung hatte schon am 6.12.2022 abgebrochen (da bereits einige
Tage im Rückstand). Völliger Abbruch am Tag, als Papa vom Pflegeheim zurückkam
und die 24-Stunden-Betreuung begann (~2h/Tag zusätzliche Bindung).

Chronologie des Verdrängungseffekts:
- 6.12.2022: Aufwandserfassung bricht ab (Papa wird Pflegefall)
- 1.1.2023: Aufwandserfassung noch für 21:08 eingeplant, aber nicht erreicht
- 8.1.2023: Erster Tag, an dem Aufwandserfassung nicht einmal mehr eingeplant
  ist (erster Arbeitstag nach Weihnachtsurlaub; Erwachsenenvertretung für Papa
  übernommen, Antrittsbericht hatte Vorrang)
- Ab ~23.1.2023: KS-Aktivitäten komplett aus Planung verschwunden
- Dez 2025 / Jän 2026: Versuch, Aufwandserfassungs-Backlog aufzuholen (bis
  23.1.2023 geschafft), dann erneuter Abbruch wegen Andon FM, Radio Würmchen
  und neuem Tagesplaner-Tool

Die Papa-Pflege hat nicht unmittelbar alles verdrängt, aber so viele ungeplante
Aktivitäten erzeugt, dass die geplanten KS-Aktivitäten schrittweise verdrängt
wurden. Die 22-30 Minuten waren also nur der Planungs-/Ablauf-Teil, ohne den
KS-Rest, der eigentlich noch ~60 Min/Tag hätte kosten sollen.

Die Genauigkeit ist über die Jahre gestiegen, der Aufwand ist mitgestiegen,
aber der Nutzen der zusätzlichen Genauigkeit ist unklar.

### Der Anti-Verzettelungs-Effekt

Die ausführlichere Planung war eine **bewusste Gegenmaßnahme**: In den
Jahren 2006-2010 (mit nur ~14 Punkten im Taschenkalender) lag die
produktive Arbeitszeit außerhalb des BRZ bei nur ~1 Stunde pro Tag —
der Rest ging durch Verzettelung verloren. Die detailliertere
handgeschriebene Planung ab ~2021 (~40-60 Punkte, täglich vom Vortags-
Ablauf kopiert und angepasst) brachte deutlich mehr Disziplin.

Ab 17.3.2024 begann die Arbeit am C#-Planungstool. Damit einher ging eine
deutliche Erhöhung der täglich geplanten Aktivitäten, weil versucht wurde,
alles aus den Checklisten einzubauen. Aus dieser Zeit stammen auch erste
erkennbare minutengenaue Nacherfassungen (z.B. 17.3.2024: ständiger Wechsel
zwischen "Scan Radio Plattenkiste" und "Debugging Tasklistebearbeitung (C#)"
im 2-3-Minuten-Takt, 132 geloggte Aktivitäten bis 21:34).

Aber: Die Steigerung von ~60 auf ~130-150 Punkte (minutengenaue Erfassung)
bringt möglicherweise keinen zusätzlichen Disziplin-Effekt mehr — nur
zusätzlichen Erfassungsaufwand. Der Sweet Spot liegt vermutlich irgendwo
dazwischen.

Das 1-Stunden-Budget hat funktioniert, als es nur Aufwandserfassung +
Abrechnung gab (12m + 48m in den 90ern). Der wachsende Planungs-/Ablauf-
Aufwand hat das Budget gesprengt, ohne dass klar ist, ob der zusätzliche
Nutzen den Aufwand rechtfertigt.

## Idee: Top-down statt Bottom-up (14.3.2026)

Grundlegender Paradigmenwechsel für die Nacherfassung:

### Aktuelles Modell (Bottom-up)
Window Monitor liefert Mikro-Segmente → User korrigiert jedes einzelne →
mühsame Rekonstruktion von unten nach oben. ~80-100 Korrekturen pro Tag.

### Neues Modell (Top-down mit Plausibilitätsprüfung)
User sagt grob, was er gemacht hat → Window Monitor **validiert** im
Hintergrund und warnt nur bei groben Abweichungen.

### Zwei Modi je nach Kontext

**Modus 1: Geplante Blöcke (z.B. BRZ)**
- User hakt nur ab: ✓ gemacht / ✗ nicht gemacht
- Keine Zeitprüfung, keine Fenstertitel-Analyse
- Zweck: Abhaken, nicht rekonstruieren

**Modus 2: Freie Blöcke am PC**
- User beschreibt grob: "Habe Essensplan bearbeitet, dann gesurft, dann Radio"
- Window Monitor prüft im Hintergrund auf Plausibilität
- Warnung NUR bei groben Mismatches, z.B.:
  - "Du hast 50 Min Essensplan geloggt, aber dazwischen 20 Min gesurft"
  - NICHT: "Du hast 'Bearb. Essensplan' geloggt, aber es waren 2 Min
    Notepad + 2 Min Access"
- Fenstertitel-Details werden gespeichert, aber nicht zur Korrektur vorgelegt

### Erwarteter Aufwand
~5 Minuten statt 60-120 Minuten. Die Genauigkeit sinkt auf Konto-Level
(statt Minuten-Level), was für die Aufwandserfassung ausreicht.

### Beispiel: Essensplan — Checklist vs. Zeiterfassung

Die verschiedenen Essensplan-Varianten (LEEPEP, LEEPVO, LEEPGE, LEEPKO...)
existieren, um zu erinnern, was alles getan werden sollte — sie variieren
je nach Tageszeit und Planungsabschnitt. Das sind zwei verschiedene
Informationsbedürfnisse, die im aktuellen System vermischt werden:

**1. Checklist-Funktion:** "Welche Essensplan-Schritte habe ich heute erledigt?"
   - Braucht: Abhaken der spezifischen Varianten (LEEPEP ✓, LEEPVO ✗)
   - Braucht NICHT: Zeiterfassung pro Variante
   - Gehört in den **Echtzeit-Planer** (beim Tun abhaken)

**2. Aufwandserfassung:** "Wieviel Zeit ging heute für Essensplan drauf?"
   - Braucht: Gesamtzeit auf Konto LE
   - Braucht NICHT: Unterscheidung ob LEEPEP oder LEEPVO
   - Gehört in die **Nacherfassung** (automatisch per Window Monitor)

**Aktuell:** Window Monitor erkennt "Bearb. Essensplan" → User korrigiert
auf "Bearb. Essensplan (gegessen, zu essen) LEEPEP" → erfüllt beides,
aber zum Preis einzelner Segment-Korrekturen.

**Top-down:** Planer-Queue zeigt spezifische Variante → User hakt beim
Tun ab (Checklist erledigt) → Window Monitor sieht "irgendwas Essensplan"
→ bucht automatisch auf LE (Zeiterfassung erledigt) → keine Korrektur nötig.

**Prinzip:** Wenn IRGENDEINE Essensplan-Aktivität laut Planung läuft und
der Window Monitor IRGENDEINE Essensplan-Aktivität feststellt, passen die
zusammen. Die Checklist-Details (welche Variante?) werden beim Abhaken im
Planer festgehalten, nicht bei der Nacherfassung.

### Offene Frage
Reicht die gröbere Erfassung für alle Zwecke? Oder gibt es Fälle, wo
die Minutengenauigkeit tatsächlich gebraucht wird?

## Nächster Schritt

Kurt überlegt sich in Ruhe, wozu das alles eigentlich gut sein soll.
Erst danach: Design-Entscheidung über Granularität → daraus folgt, was der Planer können muss.
