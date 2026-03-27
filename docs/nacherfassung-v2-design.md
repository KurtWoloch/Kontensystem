# Nacherfassung v2 — Timeline-basiertes Redesign

**Status:** Konzept (2026-03-27, beschrieben von Kurt)
**Problem:** Die aktuelle Nacherfassung arbeitet mit vorklassifizierten Segmenten, die schwer zu teilen, zusammenzulegen oder umzuklassifizieren sind. Bei unbekannten Aktivitäten und paralleler Hintergrundarbeit (z.B. TF-Analyse) entstehen viele Kurzsegmente, die manuell zusammengeführt werden müssen.

---

## 1. Grundkonzept: Timeline mit Merge-Conflict-Metapher

**Visuelles Vorbild:** Git Merge Conflicts in Visual Studio

### Layout
- **Links:** Alle Fensterwechsel-Events aus dem Window Monitor (Rohdaten)
  - Zeitstempel + Fenstertitel
- **Rechts:** Vorläufige Klassifizierung / für bereits geloggte Segmente: geloggte Aktivität + Task-Code

### Kern-Unterschied zum Status quo
Aktuell: Segmente sind an Klassifizierungsgrenzen gebunden. Ein als eine Aktivität klassifiziertes Segment bleibt ein Segment — Teilen/Zusammenlegen erfordert Workarounds (Zeitdauer ändern, im Hauptfenster kopieren, importieren, Nacherfassung neu öffnen).

Neu: Die **Begrenzungslinien zwischen Klassifizierungsblöcken sind ziehbar**.

---

## 2. Interaktion: Ziehbare Begrenzungslinien

### Ziehen nach oben (Zeile in nächsten Block einschließen)
- Die Zeile direkt über der Begrenzungslinie wechselt die Klassifizierung zum Block darunter.
- Visuell: Die Linie bewegt sich eine Zeile nach oben.

### Ziehen nach unten (Zeile in vorigen Block einschließen)
- Die "übersprungene" Zeile wechselt in die Klassifizierung des Blocks darüber.

### Eliminierung eines Blocks
- Wenn eine Begrenzungslinie auf die nächste Begrenzungslinie (oben oder unten) gezogen wird:
  - Der Klassifizierungsblock dazwischen wird eliminiert
  - Falls die beiden verbleibenden Nachbar-Blöcke die gleiche Klassifizierung haben → **automatisches Zusammenlegen**
  - Beide Begrenzungslinien (die gezogene und die Ziel-Linie) verschwinden

### Beispiel: Phantom-Segment-Behebung
```
Block A: Nacherfassung Ablauf KSPLNA     [15 min]
────────── Begrenzungslinie 1 ──────────
Block B: Dokumentation Ohrwürmer RWOWDO  [1 min]    ← Phantom
────────── Begrenzungslinie 2 ──────────
Block C: Nacherfassung Ablauf KSPLNA     [8 min]

→ Ziehe Begrenzungslinie 1 auf Begrenzungslinie 2
→ Block B wird eliminiert
→ Block A + C haben gleiche Klassifizierung → zusammenlegen
→ Ergebnis: ein Block "Nacherfassung Ablauf KSPLNA" [24 min]
```

---

## 3. Interaktion: Doppelklick-Reklassifizierung

- Doppelklick neben einem Fenstertitel → Klassifizierung ändern
- Erstellt ein neues, separates Klassifizierungssegment (1 Zeile)
- Kann danach durch Ziehen der Begrenzungslinien erweitert werden
- Auch möglich: nur den Aktivitätsnamen herauskopieren (ohne Reklassifizierung)

---

## 4. Checkbox: "Änderungen auf gleiche Fenstertitel anwenden"

### Geltungsbereich der Propagation

**Nicht der gesamte Tag** — nur das aktuell angezeigte Zeitintervall.
- Das Fenster hat (wie bisher) ein einstellbares Zeitintervall mit Spinnern
- Alle Propagationseffekte (Checkbox aktiv) wirken nur innerhalb dieses Intervalls
- Bereits geloggte Zeilen außerhalb/vor dem Intervall bleiben unverändert

**Schutz durch Intervall-Verschiebung:**
- Wenn bestimmte Änderungen "fix" sind → Startzeitpunkt des Intervalls nach hinten schieben
- Alles vor dem Startpunkt ist geschützt und wird nicht mehr durch Propagation verändert
- Erlaubt schrittweises Abarbeiten: vorne fixieren, Intervall weiterrücken, hinteren Teil bearbeiten

### Verhalten bei aktivierter Checkbox:

#### Bei manueller Reklassifizierung (Doppelklick)
- Alle anderen Zeilen **im aktuellen Intervall** mit demselben Fenstertitel werden automatisch auf die neue Aktivität geändert
- Beispiel: `AG_26_03_2026_AG-133244.pdf - Adobe Acrobat Reader (64-bit)` → "Begutachtung Angebote Bepflanzung Friedhof VEGPBA"
  - Alle Zeilen mit diesem Fenstertitel **im Intervall** werden sofort umklassifiziert

#### Bei Ziehen einer Begrenzungslinie
- Falls dadurch eine Zeile ihre Klassifizierung wechselt, werden alle Zeilen mit demselben Fenstertitel **im Intervall** ebenfalls geändert

#### Bei Import/Übernahme (Checkbox aktiv)
- Die Zuordnungen werden **permanent gespeichert**
- Beim nächsten Öffnen der Nacherfassung wird der gleiche Fenstertitel automatisch korrekt erkannt

---

## 5. Zukunft: Regel-Editor

### Funktionalität (spätere Version)
- Verwaltung der permanent gespeicherten Regeln aus Schritt 4
- **Verfeinerung der Matching-Logik:**
  - Exakter Fenstertitel (default, entsteht aus dem Checkbox-Modus)
  - **Substring-Match:** z.B. "Thinking Frequencies" im Titel → "RA - Analyse Thinking Frequencies RWANTF"
  - Evtl. Regex oder Pattern-Match
- **Suchfunktion:** In bestehenden Regeln nach Texten suchen
- **Confidence Level:** Wenn mehrere Regeln auf einen Fenstertitel zutreffen, gewinnt die mit höherem Confidence
- **Kontext-Erweiterung:** (Details noch offen)

### Geklärt (2026-03-27)
- **Spezialregeln** (Access-DB, Planer) → migrieren in Regel-Editor als vordefinierte Regeln mit hohem Confidence (Confidence ist editierbar)
- **Confidence-Auflösung:** Höherer Confidence gewinnt immer. Bei gleichem Confidence und direkt nachfolgendem Fenstertitel: bestehende Klassifizierung bleibt (Kontinuitätsprinzip)
- **Exakte vs. Substring-Regeln:** Koexistieren im gleichen System, Confidence entscheidet bei Konflikten

### Noch offen
- Kontext-Erweiterung: Kurt hatte das in der ursprünglichen Beschreibung erwähnt ("Das ließe sich dann noch mit dem Kontext ausweiten"), aber keine Details spezifiziert. Bleibt als Platzhalter für spätere Ideen.

### Festgelegt
- **Confidence-Skala:** Ganzzahlen 0–100

---

## 6. Konkretes Beispiel: 26. März — Sozialbau + Friedhof

### Problem
1. Unbekannte Aktivität (Brief, Formular, Scan, PDF, Mail) → Planer kennt sie nicht
2. TF-Analyse läuft nebenher → Fragmentierung in Kurzsegmente
3. Nacherfassung selbst erzeugt Phantom-Segmente

### Mit der neuen Timeline:
- Alle Fensterwechsel-Events sichtbar (links)
- Unerkannte PDF-Titel → Doppelklick → "Sozialbau PV WFSBAD" → Checkbox "auf alle anwenden" → alle PDFs/Mails dieser Session werden umklassifiziert
- TF-Kurzsegmente dazwischen → Begrenzungslinien ziehen, um sie in den Sozialbau-Block einzugliedern ODER als separate TF-Segmente stehen zu lassen
- Nacherfassungs-Phantom-Segmente → durch Ziehen eliminieren

### Ergebnis
- Statt 89 Einzelkorrekturen: eine Handvoll Drag-Operationen + ein paar Doppelklick-Reklassifizierungen
- Regeln werden gespeichert → beim nächsten Mal erkennt der Logger ähnliche Fenstertitel automatisch

---

## 7. Phantom-Segment-Problem (Detail)

**Konkretes Beispiel vom 26.3.:** Um 16:51:12 wurde die Aktivität "Mund spülen LEMTMS" vorgeschlagen, die dann manuell auf "Nacherfassung Ablauf KSPLNA" geändert wurde. Ursprünglicher Vorschlag war "Vorschlag bearbeiten" (Fenstertitel unklar). Die Fehlklassifizierung entstand vermutlich, weil Kurt zuvor eine andere Aktivität auf "Mund spülen LEMTMS" geändert hatte und die Checkbox/Propagation das auf dieses Segment übertragen hat.

**Grundproblem:** Während der Nacherfassung sieht der Logger die Fenster der Aktivitäten, die gerade nacherfasst werden. Er kann nicht zwischen "ich schaue mir das Fenster an, um die Nacherfassung zu prüfen" und "ich mache gerade diese Aktivität" unterscheiden.

**Lösungsansatz in v2:** Die Timeline-Ansicht eliminiert dieses Problem nicht an der Quelle, aber macht die Korrektur trivial — Phantom-Segmente werden durch eine einzige Zieh-Operation mit dem umgebenden Nacherfassungs-Block verschmolzen.

---

## 8. Persistenz der Regeln

### Aktueller Zustand
- `autodetect-corrections-*.json` ist tagesspezifisch → System "vergisst" nach einigen Tagen
- Window Logger dagegen: Regeln bleiben permanent, bis manuell geändert

### Design-Entscheidung
Die neuen Regeln ersetzen perspektivisch die autodetect-corrections-Dateien, haben aber eine **flexible Lebensdauer:**
- **Permanente Regeln:** Wie im Window Logger — bleiben bis manuell gelöscht (z.B. "Thinking Frequencies" → RWANTF)
- **Temporäre Regeln:** Gültigkeitsdauer einstellbar oder manuell löschbar (z.B. spezifische PDF-Fenstertitel, die nur an einem Tag relevant sind)
- **Im Regel-Editor:** Jede Regel hat ein Gültigkeitsfeld (permanent / bis Datum / manuell) und kann dort gelöscht werden

### Format
- Könnte die tagesspezifischen autodetect-corrections-*.json ersetzen
- Genaues Dateiformat noch offen (eigene JSON-Datei? In Access-DB?)

---

## 9. Dauerthema: Radio-Monitoring als wiederkehrender Fragmentierungs-Treiber

Die TF-Analyse ist ein Spezialfall eines allgemeinen Musters:
- Kurt hört Radiosender und wechselt regelmäßig ins RW-Programm, um mitzuschreiben, was gerade läuft
- Das ist **Normalzustand** (ca. 8 Min/Stunde geplant), nicht Ausnahme
- Fragmentierung variiert nach Sender: Online-Titelliste vorhanden → wenig Aufwand; keine Liste + unbekannte Titel → häufiges Shazamen → mehr Fragmentierung
- Die Timeline-Lösung muss diesen Normalfall effizient abbilden, nicht nur den Extremfall TF-Analyse

---

## Implementierungs-Notizen

**Komplexität:** Hoch. Erfordert:
- Neues UI-Widget (Timeline mit ziehbaren Grenzen)
- Persistenz-Schicht für Klassifizierungsregeln (mit Lebensdauer)
- Integration mit bestehendem WindowMon-Import
- Migration der Spezialregeln (Access-DB, Planer) in den Regel-Editor

**Möglicher Stufenplan:**
- **v1:** Timeline-Widget + ziehbare Grenzen + Doppelklick + Propagations-Checkbox (innerhalb Intervall)
- **v2:** Permanente Regelspeicherung bei Import + Regel-Editor (Substring-Match, Confidence, Suche, Gültigkeit)
- **v3:** Migration der Spezialregeln, Kontext-Erweiterung

**Priorität:** Noch nicht festgelegt. Konzept wird festgehalten für spätere Umsetzung.
