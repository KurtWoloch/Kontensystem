# Verbesserungen Nacherfassung / Ablauf-Erfassung

Stand: 2026-03-20
Quelle: Analyse der Tagesberichte 2026-03-13, 2026-03-19 + Diskussion der Schmerzpunkte

---

## ⚠️ PRIORITÄT: Planer-Desynchronisation und Angstblockade (2026-03-20)

### Hintergrund: Das eigentliche Problem

Am 19.03.2026 und 18.03.2026 trat ein wiederkehrendes Muster auf, das Kurt als
"sinnloses Tun" beschreibt — eine Art Handlungsblockade, bei der zwar Aktivität
stattfindet, aber ohne erkennbaren Zweck. Dieses Muster (in der Literatur als
"autistic inertia" bekannt) tritt bei Kurt primär in zwei Situationen auf:

1. **Der Planer zeigt einen Zustand, der nicht zur Realität passt** — nach einem
   BRZ-Tag steht noch "Anziehen für Bürofahrt" als aktuelle Aktivität, darauf
   folgen Items aus verschiedenen Listen in schwer nachvollziehbarer Reihenfolge.
2. **Eine unerwartete Aufgabe muss in den Plan eingeschoben werden** — z.B. eine
   dringende Mail, deren Einordnung in den Tagesablauf eine Meta-Entscheidung
   erfordert, die das Arbeitsgedächtnis blockiert.

In beiden Fällen entsteht eine Dreifachbelastung:
- Gegenwart leben (essen, trinken, aktuelle Aufgaben)
- Vergangenheit rekonstruieren (Nacherfassung)
- System synchronisieren (Planer auf aktuellen Stand bringen)

Die Nacherfassung wird dabei zum **Angst-Auslöser**: Sie erfordert, Lücken in
nicht-chronologischer Reihenfolge zu füllen, vergangene und aktuelle Aktivitäten
zu mischen, in einem System, das gerade "falsch" aussieht. Die Angst führt zu
Vermeidung, die Vermeidung frisst Zeit, das Ergebnis sind Tage, die 1-2 Stunden
länger dauern als nötig.

**Kernproblem:** Der Planer ist als Queue gebaut (immer das nächste Item aus der
Liste). Das funktioniert im Live-Modus (Morgentoilette, Abendzeremonie). Aber
sobald Plan und Realität auseinanderdriften (BRZ-Rückkehr, unerwartete Aufgabe),
wird die Queue selbst zum Blocker.

**Vergleich mit dem alten Textdatei-System:** Im alten System konnte Kurt den
BRZ-Block als Ganzes in den "erledigt"-Bereich verschieben, dann frei an
beliebiger Stelle Zeiten eintragen — rückwärts von Ankerpunkten aus ("Ich war
um 17:22 am ZET, also davor WC um 17:13, davor Einpacken um 17:07..."). Die
Textdatei war ein räumliches Medium. Der neue Planer erzwingt dagegen eine
sequentielle Logik, die mit nicht-sequentieller Erinnerung inkompatibel ist.

### V8. Beliebige Aktivität aus "Geplant" direkt loggen

**Priorität:** HOCH — adressiert direkt die Angstblockade
**Aufwand:** niedrig-mittel (GUI-Änderung + Engine-Check)

**Beschreibung:** Doppelklick auf einen beliebigen Eintrag in der "Geplant"-Liste
öffnet den Log-Dialog (Start-/Endzeit, Kommentar). Die Aktivität wird ins Log
geschrieben und intern als erledigt markiert. Wenn sie später in der Queue an die
Reihe käme, wird sie automatisch übersprungen — kein Skip-Dialog, kein Duplikat.

**Technisch:**
- `gui.py`: Doppelklick-Handler auf Geplant-Einträge → bestehender Log-Dialog
- `engine.py`: Beim Queue-Advance prüfen, ob Aktivität bereits im Log existiert
  (Match auf Aktivitätsname). Falls ja: stillschweigend überspringen.
- Log-Eintrag bekommt kein spezielles Flag — er sieht aus wie jeder andere Eintrag.

**Löst:** Das "5 Listen dazwischen"-Problem. Statt sich durch die Queue zu kämpfen,
klickt Kurt direkt das Item an, das er loggen will.

### V9. Bereinigte Projektion als alternative Ansicht

**Priorität:** HOCH — gibt Überblick bei desynchronisiertem Planer
**Aufwand:** mittel (neue Ansicht in GUI, liest bestehende Projektionsdatei)

**Beschreibung:** Toggle-Button oder Tab "Restplan", der die originale Tagesprojektion
anzeigt, aber ohne bereits erledigte/übersprungene Aktivitäten. Zeigt den Tag in
chronologischer Reihenfolge mit den geplanten Zeiten.

**Technisch:**
- `projection-YYYY-MM-DD.json` laden (existiert bereits)
- Gegen aktuelles Log filtern (Name-Match → ausblenden)
- Anzeige als scrollbare Liste mit est_start/est_end
- Doppelklick → Log-Dialog (wie V8)

**Löst:** Die Orientierungslosigkeit nach BRZ-Rückkehr. Statt "wilde Mischung aus
5 Listen" sieht Kurt: "Das steht noch aus, in dieser Reihenfolge".

**Verhältnis zu V5:** Erweitert V5 um die Integration mit V8 (direktes Loggen aus
der Projektionsansicht) und löst damit das dort als "offener Punkt" genannte
Verdopplungs-Problem, weil V8 die automatische Skip-Logik liefert.

### V10. "Bis hierher erledigt" — Bulk-Complete

**Priorität:** HOCH — eliminiert die Desynchronisation in Sekunden statt Minuten
**Aufwand:** mittel (Bulk-Operation auf Projection-Daten)

**Beschreibung:** In der bereinigten Projektion (V9) kann Kurt eine Aktivität
auswählen und "Bis hierher erledigt" klicken. Alle Aktivitäten von der aktuellen
Position bis zum gewählten Punkt werden ins Log geschrieben.

**Zeitenfrage:** Die geplanten Zeiten aus der Projektion werden als vorläufige
Zeiten übernommen. Sie können später korrigiert werden (Nacherfassung als separate
Aufgabe), aber der Planer ist sofort synchron.

**Trennung der Probleme:**
- **Planer synchronisieren** → sofort, mit Projektions-Zeiten → 10 Sekunden
- **Zeiten korrigieren** → später, in Ruhe, als eigene Aufgabe → ankerbassierte
  Rekonstruktion in beliebiger Reihenfolge

**Technisch:**
- Iteriert über Projektion bis zum gewählten Item
- Für jedes Item: Log-Eintrag mit `started_at`/`completed_at` aus Projektion
- Optional: `estimated: true`-Flag für spätere Korrektur-Erkennung
- Queue springt zum nächsten nicht-erledigten Item

**Löst:** Den "Ich muss erst 30 Minuten nacherfassen, bevor der Planer wieder
richtig funktioniert"-Blocker. Der Planer ist in 10 Sekunden synchron.

### Zusammenwirken der drei Features

**Szenario: Heimkehr vom BRZ (bisher):**
1. Planer zeigt "Anziehen" → Chaos
2. Nacherfassung nötig, bevor weitermachen → Angst → Vermeidung
3. Sinnloses Tun → 1-2h Verzögerung

**Szenario: Heimkehr vom BRZ (mit V8/V9/V10):**
1. "Restplan" öffnen → chronologische Liste → "bis hierher erledigt" bis
   zum letzten BRZ-Punkt → Planer zeigt sofort die aktuelle Aktivität
2. Normal weiterarbeiten im Live-Modus
3. Am Abend, als eigene Aufgabe: BRZ-Zeiten korrigieren (rückwärts von
   Ankerpunkten, in beliebiger Reihenfolge via V8/V9)

**Geschätzte Wirkung:** 30-60 Minuten Zeitersparnis pro BRZ-Tag, plus
Vermeidung der Angstblockade und des daraus folgenden "sinnlosen Tuns".

### Architektur-Warnung: Komplexitätsgrenze windowmon_import.py

Stand 2026-03-20 hat `_consolidate_blocks` in `windowmon_import.py` 6 Passes
(0a, 0b, 1, 1.5, 2, plus implizite Vor-/Nachbearbeitung). Jeder Fix fügt
Komplexität hinzu, die beim nächsten Fix schwer zu überblicken ist.

Die Features V1-V3a aus diesem Dokument (windowmon-Analyse-Verbesserungen) sollten
**nicht** auf die aktuelle Architektur draufgepackt werden. Stattdessen wäre ein
Refactoring-Schritt sinnvoll, bei dem Kurt selbst die Grundlogik vereinfacht —
analog zu den Architektur-Entscheidungen beim Radio-Würmchen-Projekt (z.B.
DJ Brain als eigenständiges Python-Skript statt OpenClaw-Cron-Job).

**Konkretes Beispiel für Vereinfachungspotential:** Das Lücken-Problem (Zeitblöcke
ohne Window-Events werden nicht in der Nacherfassung angeboten) wird aktuell durch
synthetische Events + Consolidation gelöst. Kurts Vorschlag: stattdessen einfach
auf das letzte Event vor der Lücke und das erste Event danach schauen und an
Minutengrenzen abschneiden — konzeptuell simpler, weniger Passes nötig.

Die V8/V9/V10-Features betreffen dagegen die **GUI und Queue-Logik**, nicht die
windowmon-Analyse, und sind daher ohne Komplexitätsrisiko umsetzbar.

---

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

#### V3a. Arbeitskontext-Erkennung (konkrete Implementierung)

**Status:** Konzept, 2026-03-16  
**Anlass:** Analyse Zeitraum 18:54–20:48 am 15.03.2026 — 911 rohe Window-Events, die manuell auf 22 Log-Einträge konsolidiert werden mussten (17 Min. Aufwand für knapp 2 Stunden).

##### Das Problem im Detail

Bei der Aktivität "Bearb.Ohrwürmer (Nachfassen aus alten Charts) RWOWTT" wechselt der User ständig zwischen zwei Werkzeugen:
1. **Notepad** — `*Ohrwürmer 12.3.2023-.txt` (Suchen-Dialog, Eintragen)
2. **Edge** — austriancharts.at (Charts-Seiten durchblättern, Alben anklicken)

Der Zyklus dauert ~30 Sekunden: Chart in Edge nachschlagen → Ctrl+Tab zu Notepad → Suchen → Eintragen → zurück zu Edge → nächster Chart-Eintrag. In 20 Minuten entstehen so ~40+ Fensterwechsel.

Der Window Monitor sieht jeden Wechsel als potenziellen Aktivitätswechsel und erzeugt separate Blöcke für "Bearb. Ohrwürmer-Listen" (Notepad) und "Surfen austriancharts.at" (Edge). Bei der Nacherfassung muss jeder dieser Blöcke manuell beurteilt und die meisten verworfen oder zusammengefasst werden.

##### Grundprinzip: Geplante Aktivität ist im Zweifelsfall richtig

Erweitert das am 13.03.2026 etablierte Kernprinzip der "Window-Logger-Philosophie" (→ `memory/2026-03-13.md`):

> **Alt (13.03.):** Im Zweifelsfall läuft die *vorherige* Aktivität weiter.  
> **Neu (V3a):** Im Zweifelsfall läuft die *geplante* Aktivität weiter — nur **echte Abweichungen** werden als Kontextwechsel identifiziert.

Die Frage ist nicht mehr "Was macht der User gerade?" (→ Fenster analysieren), sondern: **"Macht der User etwas anderes als geplant?"** (→ Abweichungen erkennen).

**Beispiel RWOWTT (Ohrwürmer Nachfassen aus Charts):**
- ✅ Kein Kontextwechsel: austriancharts.at, Ohrwürmer-Datei in Notepad, Suchen-Dialog, `officialcharts.com`, `chartsurfer.de`, `playback.fm`, `bravo-archiv.de` — das ist alles *erwartetes Verhalten* für diese Aufgabe
- ❌ Kontextwechsel: YouTube-Videos (Rosin's), Google Übersetzer, Arena AI, Essensplan-Dateien, unbenannte Datei im Editor, Nachsurfen "Win the tiger" / "Theme from the Exorcist", Surfen Andon FM / Andon Labs, News-Seiten — das sind echte Abweichungen

##### Zwei konvergente Signale zur Umsetzung

**Signal 1 — Aktive Planer-Aufgabe:**  
Der Planer weiß, welche Aufgabe gerade läuft (z.B. RWOWTT). Fensterwechsel, die zum erwarteten Workflow dieser Aufgabe passen, sind keine Unterbrechungen, sondern normales Arbeitsverhalten.

**Signal 2 — Anker-Datei/Anker-Fenster:**  
Bestimmte Fenster sind der stabile "Anker" einer Aktivität. Solange dieser Anker aktiv bleibt (Datei geöffnet, modifiziert — erkennbar am `*` im Titel), gehören alle Browser-Ausflüge zum selben Arbeitskontext.

##### Regel-Format (Arbeitskontext-Definitionen)

```yaml
work_contexts:
  - task_code: "RWOWTT"
    name: "Ohrwürmer Nachfassen aus Charts"
    anchor:
      process: "notepad.exe"
      title_contains: "Ohrwürmer"
    companion_patterns:
      - process: "msedge.exe"
        title_contains_any:
          - "austriancharts.at"
          - "officialcharts.com"
          - "chartsurfer.de"
          - "playback.fm"
          - "bravo-archiv.de"
          - "Bravo-Jahrescharts"
          - "wikipedia.org"  # für Bravo-Charts, Zertifizierungslisten etc.
          - "discogs.com"    # Titellisten nachschlagen (v.a. bei UK-Charts, wo keine Albumseiten existieren; bei AT-Charts gelegentlich für Alben ohne Titelliste)
    max_interruption_sec: 120  # Seitenblicke < 2 Min. werden absorbiert

  - task_code: "LEEPEP"
    name: "Bearb. Essensplan"
    anchor:
      process: "notepad.exe"
      title_contains_any: ["Essensplan", "AuswertungGegessen", "VersuchEssensplan", "Vergleich forcierter Preise"]
    companion_patterns:
      - process: "MSACCESS.EXE"
        title_contains: "Microsoft Access"  # Essensplan-DB
      - process: "ApplicationFram"
        title_contains: "Rechner"  # Taschenrechner für Nährwerte
    max_interruption_sec: 120

  - task_code: "KSPLEN"
    name: "Arbeit an Tagesplanung / Planer-Entwicklung mit OpenClaw"
    anchor:
      process: "msedge.exe"
      title_contains: "OpenClaw Control"
    companion_patterns:
      - process: "python.exe"
        title_contains_any: ["Tagesplanung", "Reaktiver Planer", "Tagesbericht", "Nacherfassung"]
        # Planer-GUI selbst — wird häufig kurz aufgerufen während der Diskussion
      - process: "explorer.exe"
        title_contains_any: ["kontensystem", "logs", "planner", "docs", "data"]
      - process: "notepad.exe"
        title_contains_any: ["planner", "report", "projection", "nacherfassung", "feature-", "planning-", ".json", ".md", ".py"]
        # Kontensystem-Dateien aller Art: Docs, Logs, Code
      - process: "cmd.exe"
        title_contains: "python"  # Planer starten/testen
    max_interruption_sec: 180

  - task_code: "RWOWDO"
    name: "Dokumentation Ohrwurm-Projekt"
    anchor:
      process: "notepad.exe"
      title_contains: "Ohrwürmer"
    companion_patterns:
      - process: "msedge.exe"
        # keine spezifische URL — Recherche kann alles sein
    max_interruption_sec: 120
```

##### Was ist die "aktuelle Aktivität"?

Wichtig: Die aktuelle Aktivität ist **nicht** unbedingt das, was der Planer als nächstes in der Queue vorschlägt. Kurt klickt oft eine andere Aktivität im Planer an und lässt sie offen, während er am PC daran arbeitet. Der Planer-Fenstertitel zeigt dann diese manuell gewählte Aktivität an (z.B. `Tagesplanung — Reaktiver Planer — Bearb.Ohrwürmer(Nachfassen aus alten Charts) RWOWTT`).

**Drei Ebenen von "aktueller Aktivität" (Priorität absteigend):**

1. **Manuell im Planer gewählt** — erkennbar am letzten Planer-Fenstertitel, bevor der Fokus auf ein anderes Fenster wechselt. Dies hat Vorrang. (Wird vom WindowMon bereits für Off-PC-Erkennung gelesen.)
2. **Queue-Vorschlag des Planers** — was aufgrund von Listen/Prioritäten als nächstes dran wäre. Fallback, wenn nichts manuell angeklickt wurde.
3. **Fenster-Aktivität** — was der WindowMon auf dem Bildschirm sieht. Wird gegen den Arbeitskontext (1 oder 2) geprüft: passt es zur aktuellen Aufgabe, oder ist es eine Abweichung?

**Implementierung:** Der WindowMon merkt sich bei jedem Fensterwechsel den **letzten Planer-Titel** (aus `python.exe` mit Titel `Tagesplanung — ...`). Dieser bleibt der aktive Arbeitskontext, bis:
- Ein neuer Planer-Titel erscheint (Aufgabe gewechselt)
- Die Aufgabe als erledigt/übersprungen markiert wird (→ nächste Queue-Aufgabe wird Kontext)
- Eine Unterbrechung durch den Planer erfolgt (z.B. fällige fixe Aufgabe "verdrängt" die aktuelle)

Das ist konsistent mit der bereits funktionierenden Off-PC-Erkennung: dort liest der WindowMon `Tagesplanung — Off-PC — [Aktivität]` aus dem Fenstertitel. Für die Arbeitskontext-Erkennung wird dasselbe Signal genutzt, nur eben für On-PC-Zeiträume.

##### Algorithmus

```
INITIALISIERUNG:
  aktiver_kontext = letzter Planer-Fenstertitel (Task-Code extrahieren)

FÜR jeden WindowMon-Zeitraum:
  1. Prüfe, ob ein Planer-Fenstertitel im Zeitraum vorkommt
     → WENN JA: aktiver_kontext aktualisieren (manuell gewählte Aufgabe hat Vorrang)
  2. Bestimme Task-Code aus aktiver_kontext
  3. Prüfe, ob ein definierter Arbeitskontext für diesen Task-Code existiert
  4. WENN JA:
     a. Suche den Anker (anchor) in den Fensterereignissen
     b. Solange der Anker regelmäßig aktiv ist (Rückkehr innerhalb max_interruption_sec):
        - Companion-Fenster → absorbieren (kein eigener Block)
        - Andere Fenster < max_interruption_sec → absorbieren
        - Andere Fenster ≥ max_interruption_sec → neuer Block (echte Abweichung)
     c. Ergebnis: ein einziger Block mit dem Namen des Arbeitskontexts
  5. WENN NEIN (kein Arbeitskontext definiert):
     → Bisherige Logik (Fenster-basierte Einzelerkennung)
     → Aber: Grundprinzip gilt weiterhin — geplante Aktivität ist Default,
        nur klare Abweichungen erzeugen neue Blöcke
```

##### Erwartete Wirkung (Beispiel 15.03.2026, 18:54–20:48)

| | Ohne Kontext-Erkennung | Mit Kontext-Erkennung |
|---|---|---|
| Vorgeschlagene Blöcke | ~25-30+ | ~12-15 |
| Davon korrekt | ~50% | ~80-90% |
| Manuelle Korrekturen | ~15+ | ~3-5 |
| Nacherfassungszeit | ~17 Min. | ~5-7 Min. (geschätzt) |

##### Erkannte Abweichungen im Beispiel-Zeitraum (15.03., 18:54–20:48)

**Keine Abweichung** (alles Teil von RWOWTT, wird NICHT als Kontextwechsel gewertet):
- Notepad `*Ohrwürmer 12.3.2023-.txt` + Suchen-Dialog
- Edge auf `austriancharts.at` (Austria Top 40, Alben Top 75 — alle Daten)
- Kurze Album-Detailseiten (Wilfried, McCartney II, ZZ Top, Joan Armatrading, KISS, Queen, Peter Gabriel, ABBA, Dire Straits, AC/DC, Bob Dylan, Rolling Stones, Roxy Music, etc.)
- Discogs/Vinyl-Seiten zur Verifizierung (z.B. Sulmtaler Dirndln, Bert Kaempfert)
- Explorer-Wechsel zum Programmumschalten zwischen Notepad und Edge

**Echte Abweichungen** (werden als separate Blöcke erkannt):
- 19:05–19:08 — Bearb. Essensplan (Essensplan-Dateien + Access + Rechner → eigener Arbeitskontext LEEPEP)
- 19:17–19:45 — Analyse DJ Breaks Grok'n Roll + Arena AI + Google Übersetzer + YouTube + Nachsurfen "Win the tiger"/"Theme from the Exorcist" (alles NICHT auf Charts-Seiten → klar anderer Kontext)
- 19:45–19:51 — Bearb. Essensplan (Essensplan-Dateien + Access → LEEPEP)
- 19:51–19:52 — Transkript DJ Break abspeichern (`*Unbenannt - Editor` → Speichern als)
- 19:52–19:54 — YouTube Rosin's Restaurants (YouTube ≠ Charts-Seite → Abweichung)
- 19:54–19:56 — div. Surfen News (Amazon-Preisänderung → weder Charts noch Ohrwürmer)
- 20:03–20:04 — YouTube Rosin's Restaurants
- 20:17–20:25 — YouTube Rosin's Restaurants (längerer Block)
- 20:25–20:28 — Surfen Andon Labs/Publications + YouTube
- 20:29–20:35 — Nachtmahl fassen (Off-PC, idle-Erkennung)

**Warum die Erkennung funktioniert:**
- Die Ohrwürmer-Arbeit nutzt spezifische Charts-Domains → über `companion_patterns` abgedeckt
- Der Essensplan hat einen eigenen Arbeitskontext (LEEPEP) mit eigenen Anker-Dateien → Wechsel erkennbar
- YouTube (Rosin's), Google Übersetzer, Arena AI, News-Seiten matchen weder den RWOWTT- noch den LEEPEP-Kontext → werden als Abweichungen erkannt
- Die "unbenannte Datei" im Editor (`*Unbenannt`) ist kein Match für den Ohrwürmer-Anker (`Ohrwürmer*.txt`) → Abweichung

##### Chart-Quellen für RWOWTT (vollständige Liste)

Beim Nachfassen aus alten Charts werden folgende Quellen durchgearbeitet:
- **Österreichische Charts:** austriancharts.at (Singles, LPs, Ö3-Hitparade, Neuvorstellungen)
- **UK Charts:** officialcharts.com (Albums Top 75, Singles)
- **Deutsche Charts:** chartsurfer.de (Jahrescharts)
- **Internationale Charts:** playback.fm (Top-100-Jahrescharts zurück bis 1900, Brazil, R&B, Country, Rock)
- **Bravo-Charts:** wikipedia.org (Bravo-Jahrescharts), bravo-archiv.de
- **Zertifizierungslisten:** wikipedia.org (meistverkaufte deutschsprachige Schlager)
- **Titellisten-Recherche:** discogs.com (Tracklists von Alben nachschlagen — bei UK LP-Charts regelmäßig, da officialcharts.com keine Album-Unterseiten mit Titellisten hat; bei AT-Charts gelegentlich für Alben ohne Titelliste auf austriancharts.at, z.B. Bert Kaempfert, Sulmtaler Dirndln)

Alle diese Domains sollten als `companion_patterns` für den RWOWTT-Kontext definiert sein.

##### Weiteres Beispiel: KSPLEN-Fragmentierung (16.03.2026, Morgen)

Bei der Nacherfassung der Morgen-Session erscheinen **drei aufeinanderfolgende Segmente** mit identischem erkannten Aktivitätsnamen:

| # | Zeitraum | Erkannter Titel | Zugeordnetes Fenster |
|---|----------|----------------|---------------------|
| 1 | Segment A | Diskussion Tagesplanung mit OpenClaw KSPLEN | OpenClaw Control (Edge) |
| 2 | Segment B | Diskussion Tagesplanung mit OpenClaw KSPLEN | Nacherfassung aus windowmon (python.exe) |
| 3 | Segment C | Diskussion Tagesplanung mit OpenClaw KSPLEN | OpenClaw Control (Edge) |

**Ursache:** Während der Diskussion im OpenClaw Webchat wurde kurz zur Nacherfassungs-GUI gewechselt (um das besprochene Muster live zu sehen), dann wieder zurück. Der WindowMon sieht zwei verschiedene Fenster/Prozesse und macht drei Blöcke daraus.

**Ohne Arbeitskontext:** Drei separate Segmente, die alle dreimal einzeln bestätigt werden müssen — obwohl es inhaltlich eine einzige ununterbrochene Aktivität ist.

**Mit Arbeitskontext KSPLEN:** "OpenClaw Control" ist der Anker, "Nacherfassung aus windowmon" (python.exe, Planer-bezogen) ist ein definierter Companion → **ein einziger Block**, keine manuelle Bestätigung nötig.

Dieses Beispiel zeigt, dass die Fragmentierung nicht nur bei Multi-Tool-Workflows wie Ohrwürmer+Charts auftritt, sondern auch bei der alltäglichen Planer-Arbeit, wo das Wechseln zwischen Diskussion und Planer-GUI ein natürlicher Teil der Tätigkeit ist.

##### Weitere Arbeitskontexte (noch zu definieren)

Die obigen vier Kontexte (RWOWTT, LEEPEP, KSPLEN, RWOWDO) decken die Hauptaktivitäten der letzten Wochen ab, die durch die intensive Planer-Entwicklung dominiert waren. Im Normalbetrieb gibt es weitere Aktivitäten mit Multi-Fenster-Workflows, z.B.:

- **FIAKBK** — Bearbeitung Börsenkurse / Aktienhandel (Broker-Seiten + Tabellen)
- **CSAAZE** — Eintragen Zeiten Atariage (Atariage-Forum + Tabelle)
- **CSGAUM** — Analyse Disassembly Astro Bomber (Disassembly-Tools + Referenz)
- **RWMPMP/RWMPAR** — Anhören Radio / Scan Radiosender (Radio-Würmchen-App + Live365 Scraper + Statistik-CSVs + Edge)
- **FZSCLI** — Bearb. Liste Scooterfahrten (Lime/Voi-App-Daten + Tabelle)
- **GELICM** — Bearbeitung Buch Champion's Mindset (PDF/Reader + Notizen)

Diese werden schrittweise definiert, sobald sie im täglichen Betrieb wieder regelmäßig vorkommen. Die Lernfähigkeit (s.u.) kann dabei helfen, neue Kontexte automatisch vorzuschlagen.

##### Lernfähigkeit

Neue Arbeitskontexte können hinzugefügt werden, wenn ein Muster erkannt wird:
- User korrigiert wiederholt Blöcke derselben Art (z.B. immer "Surfen X" → "Bearb. Y")
- System schlägt neuen Arbeitskontext vor: "Soll ich [Anker] + [Companion] als Kontext für [Task] definieren?"
- Bestätigung → neue Regel wird gespeichert

Das ist eine natürliche Erweiterung von Phase 4 (Regellernen) aus `feature-window-monitor.md`.

##### V3b. Statistische Fenster-Aktivitäts-Profile (Exklusivitätsanalyse)

**Status:** Idee, 2026-03-16  
**Anlass:** Beobachtung, dass manche Fenster/Dateien fast exklusiv bei einer Aktivität auftreten, andere in vielen verschiedenen Kontexten.

###### Konzept

Für jeden Fenstertitel / jede Datei wird aus den historischen Logs ein **Exklusivitäts-Score** berechnet: Wie stark ist die Zuordnung zu einer bestimmten Aktivität?

```
exklusivität(fenster, aktivität) = zeit_bei_aktivität / zeit_gesamt
```

###### Beispiele (geschätzt aus bisherigen Logs)

| Fenster / Datei | Hauptaktivität | Exklusivität | Signalstärke |
|---|---|---|---|
| `austriancharts.at` | RWOWTT | ~95% | ★★★ sehr stark |
| `*Ohrwürmer*.txt` | RWOWTT / RWOWDO | ~98% | ★★★ fast exklusiv |
| `~Vergleich forcierter Preise.txt` | LEEPEP | ~100% | ★★★ exklusiv |
| `~AuswertungGegessen*.txt` | LEEPEP | ~100% | ★★★ exklusiv |
| `OpenClaw Control` | KSPLEN | ~90% | ★★☆ stark |
| `officialcharts.com` | RWOWTT | ~95% | ★★★ sehr stark |
| `discogs.com` | RWOWTT | ~80% | ★★☆ stark (gelegentlich auch für Radio-Recherche) |
| `Microsoft Access` (generisch) | LEEPEP / KSAAKO / RW | ~40% LEEPEP | ☆☆☆ schwach allein — aber: valider Companion in *jedem* passenden Kontext (s.u.) |
| `YouTube` | diverse | ~30% max | ☆☆☆ schwach (RAYTRR, RAYTYT, RWMPMP...) |
| `Rechner` (Taschenrechner) | diverse | ~40% LEEPEP | ☆☆☆ schwach |
| `div. Surfen / News` | diverse | ~0% | ☆☆☆ kein Signal |

###### Nutzen für die Erkennung

**1. Stärkung der Arbeitskontext-Erkennung (V3a):**
- Fenster mit hoher Exklusivität für die aktuelle Planer-Aufgabe → automatisch als Companion absorbieren, auch wenn sie nicht explizit in den `companion_patterns` definiert sind
- Fenster mit hoher Exklusivität für eine *andere* Aktivität → starkes Abweichungssignal (z.B. `~AuswertungGegessen*.txt` während RWOWTT → ziemlich sicher LEEPEP-Unterbrechung)

**2. Automatische Erkennung bei fehlendem Arbeitskontext:**
- Wenn keine Arbeitskontext-Definition für den aktuellen Task existiert (Schritt 5 im Algorithmus), können Fenster mit hoher Exklusivität trotzdem Hinweise liefern
- Z.B.: Kein Arbeitskontext für FIAKBK definiert, aber `flatex.at` erscheint zu 99% bei FIAKBK → System kann trotzdem erkennen, dass die Aktivität passt

**3. Erkennung neuer Arbeitskontexte:**
- Wenn ein Cluster von Fenstern (A, B, C) regelmäßig bei derselben Aktivität zusammen auftritt → automatischer Vorschlag: "A+B+C scheinen ein Arbeitskontext für [Aktivität] zu sein"
- Schwellenwert: Mindestens 3 gemeinsame Vorkommen, Exklusivität > 70%

**4. Abweichungs-Confidence:**
- Fenster mit niedriger Exklusivität (YouTube, Rechner, Explorer) sind allein kein starkes Abweichungssignal → brauchen Dauer oder zusätzlichen Kontext
- Fenster mit hoher Exklusivität für eine andere Aktivität → sofort als Abweichung melden

**5. Multi-Kontext-Companions (wichtig!):**
Manche Programme — insbesondere `Microsoft Access` — haben niedrige Gesamt-Exklusivität, weil sie in mehreren Aktivitäten vorkommen (LEEPEP, KSAAKO, Radio-Würmchen). Das bedeutet aber **nicht**, dass sie schlechte Signale sind. Im Gegenteil: Access ist in *jedem* dieser Kontexte ein valider Companion.

Die Exklusivität wird deshalb **kontextbezogen** ausgewertet, nicht isoliert:
- Access allein → schwaches Signal (welche Aktivität?)
- Access **während LEEPEP aktiv** → passt, absorbieren
- Access **während KSAAKO aktiv** → passt, absorbieren  
- Access **während RWOWTT aktiv** → eher Abweichung (Access gehört nicht zum Charts-Workflow)

Zusätzlich kann das **nachfolgende Fenster** die Zuordnung bestätigen. Bei der Nacherfassung ist bereits bekannt, was als nächstes kam:
- Access → dann `~AuswertungGegessen*.txt` → sicher LEEPEP
- Access → dann `Kontensystem.mdb` → sicher KSAAKO
- Access → dann Radio-Würmchen-Dateien → sicher RW-Kontext

Dieses Vorwärts-Signal (was kommt nach Access?) ist bei der Nacherfassung immer verfügbar, da alle Events bereits vorliegen. Es ergänzt das Rückwärts-Signal (welche Aktivität war vorher/ist geplant?) und ermöglicht sichere Zuordnung auch bei niedrig-exklusiven Programmen.

**6. Titel-Flicker bei Access (und ähnlichen Programmen):**
Microsoft Access zeigt den Datenbanknamen im Fenstertitel, aber **nicht immer**: Pop-up-Dialoge (Find and Replace, Eingabemasken, Fehlermeldungen) haben als Titel nur "Microsoft Access" ohne DB-Namen. Im WindowMon-Log wechselt der Titel dadurch ständig zwischen z.B. `Microsoft Access - Essensplan.mdb` und generischem `Microsoft Access` — obwohl durchgehend in derselben Datenbank gearbeitet wird.

Folge ohne Kontext-Erkennung:
1. WindowMon sieht Titelwechsel → neues Segment "Microsoft Access" (generisch)
2. AutoDetect ordnet generisches Segment z.B. als "Bearb. unbekannte Datenbank" ein
3. Nächster Titelwechsel zurück zu `Essensplan.mdb` → neues Segment "Bearb. Essensplan"
4. Ergebnis: mehrere aufeinanderfolgende Essensplan-Segmente, die alle dasselbe sind

Auch nachdem die globale Regel "generisches Access → wahrscheinlich Essensplan" eingeführt wurde, bleibt das Fragmentierungsproblem: es entstehen trotzdem mehrere aufeinanderfolgende LEEPEP-Blöcke, die manuell zusammengefasst werden müssen.

**Lösung:** Innerhalb eines aktiven Arbeitskontexts (z.B. LEEPEP) werden Access-Fensterwechsel zwischen spezifischem Titel (`Essensplan.mdb`) und generischem Titel (`Microsoft Access`) als **dasselbe Fenster** behandelt. Regel:

> Wenn `MSACCESS.EXE` mit spezifischem DB-Titel und `MSACCESS.EXE` mit generischem Titel innerhalb desselben Arbeitskontexts alternieren → die spezifische DB "klebt" am Kontext, generische Titel erben die letzte bekannte DB.

Das gilt analog für andere Programme mit Pop-up-bedingtem Titel-Flicker (z.B. Notepad mit "Suchen"-Dialog vs. Dateititel, Excel mit "Sort"-Dialog vs. Tabellenname).

**Besonders ausgeprägt bei Ohrwürmer-Arbeit (RWOWTT):** Beim Durchgehen der Titelliste eines Albums werden für jeden einzelnen Titel eine oder mehrere Suchen in der Ohrwürmer-Datei durchgeführt — Suchen-Dialog öffnen, suchen, Suchen-Dialog schließen, Ergebnis prüfen, nächster Titel. Pro Album mit ~10 Titeln entstehen so ~20-30 Fensterwechsel allein zwischen `*Ohrwürmer*.txt - Editor` und `Suchen`, und das für jedes der ~15-20 Alben pro Chartseite. Im Rohdaten-Log vom 15.03. (18:54–20:48) waren Hunderte solcher Notepad↔Suchen-Wechsel sichtbar — allesamt Teil eines einzigen, durchgehenden Arbeitsvorgangs.

###### Datenquelle

Die historischen Daten liegen bereits vor:
- `windowmon-YYYY-MM-DD.jsonl` (rohe Fensterereignisse mit Zeitstempeln)
- `planner-log-YYYY-MM-DD.json` (welche Aktivität war zu welcher Zeit aktiv)
- `autodetect-corrections-YYYY-MM-DD.json` (manuell bestätigte Zuordnungen)

Durch Kreuzanalyse (Fensterereignis zum Zeitpunkt X → welche Aktivität war im Log zu diesem Zeitpunkt?) lässt sich die Exklusivitäts-Tabelle automatisch aufbauen und laufend aktualisieren.

###### Verhältnis zu V3a

V3a (Arbeitskontext-Erkennung) definiert Kontexte **manuell** über explizite Regeln. V3b ergänzt das durch **statistische Auswertung** der tatsächlichen Nutzung:
- V3a = "austriancharts.at gehört zu RWOWTT, weil wir das so definiert haben"
- V3b = "austriancharts.at gehört zu RWOWTT, weil es in 95% der Fälle dort vorkommt"

Langfristig kann V3b die manuelle Definition in V3a teilweise ersetzen: Statt jeden Companion einzeln zu definieren, lernt das System die Zuordnungen aus den Daten. Die manuellen Definitionen dienen dann als Startwert und als Override für Sonderfälle.

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

### V7. "AutoDetect wiederherstellen" bei falscher Korrektur

**Status:** Idee, 2026-03-16  
**Anlass:** Nacherfassung vom 16.03.2026 — wiederkehrendes Problem bei Batch-Korrekturen

#### Das Problem

Bei der Nacherfassung ersetzt manchmal eine Regel (z.B. aus windowmon_summary) den AutoDetect-Vorschlag durch einen falschen. Konkretes Beispiel:

1. AutoDetect erkennt korrekt: **"Ansehen Youtube-Videos RAYTYT"**
2. Eine Regel überschreibt das zu: **"RA / Surfen Andon FM RASUAF"**
3. In der Nacherfassungs-GUI steht: `RA / Surfen Andon FM RASUAF` (Hauptzeile) mit `5 Einträge (AutoDetect: Ansehen Youtube-Videos RAYTYT)` (Unterzeile)

Das Original (AutoDetect) stimmt, aber es gibt keinen schnellen Weg, die falsche Korrektur rückgängig zu machen. Der User muss:
1. "Bearbeiten" klicken
2. "Ansehen Youtube-Videos" händisch eintippen (kürzer → falsche Vorschläge)
3. "Name übernehmen" klicken (damit das Kürzel RAYTYT ergänzt wird)
4. Segment übernehmen

Und: Wenn mehrere aufeinanderfolgende Segmente denselben Fehler haben, wird die Rückkorrektur erst nach Schließen und Wiederöffnen der Nacherfassung auf die noch nicht übernommenen Segmente angewendet — jedes Segment muss also einzeln korrigiert werden, obwohl der Fehler systematisch ist.

#### Vorgeschlagene Lösung: "AutoDetect wiederherstellen"-Button

Wenn ein Segment angezeigt wird, dessen aktuelle Zuordnung vom AutoDetect-Original abweicht:
- **Sichtbar:** Anzeige des AutoDetect-Originals (existiert bereits als Unterzeile)
- **Neu:** Ein Button/Shortcut "AutoDetect übernehmen" oder "Korrektur löschen", der die falsche Überschreibung entfernt und den AutoDetect-Wert wiederherstellt
- **Für noch nicht übernommene Segmente:** Möglichkeit, die fehlerhafte Regel für alle verbleibenden Segmente in dieser Nacherfassungs-Session zurückzusetzen (Batch-Reset)

#### Ursache des Problems: Zu breite Regel-Generalisierung

Konkretes Beispiel vom 16.03.2026 (Nacherfassung):

1. Um 19:20 wurden `Library Andon FM.xls` und `Statistik_heute.csv` in Excel bearbeitet
2. AutoDetect erkennt das nicht als Andon-FM-Arbeit (die Excel-Dateien haben keine passende Regel)
3. Stattdessen wird die Planer-Aktivität "Ansehen Youtube-Videos RAYTYT" vorgeschlagen (weil YouTube vorher/nachher lief)
4. User korrigiert: "Youtube" → "Surfen Andon FM RASUAF" (weil die Excel-Dateien klar Andon FM sind)
5. **Fehler:** Der Planer interpretiert die Korrektur als "alles, was als Youtube erkannt wurde, soll generell auf Andon FM umbenannt werden" — statt zu verstehen, dass sich die Korrektur auf die spezifischen Excel-Fenster bezieht
6. **Folge:** Nachfolgende echte Youtube-Segmente werden fälschlicherweise auch zu "Surfen Andon FM" umbenannt

**Kernproblem:** Die Korrektur wird am **AutoDetect-Label** festgemacht ("Youtube" → "Andon FM"), nicht an den **zugrundeliegenden Fenstern** (`Library Andon FM.xls` in Excel). Das System lernt die falsche Lektion: nicht "Excel mit Andon-FM-Dateien = Andon FM", sondern "Youtube = Andon FM".

#### Vorgeschlagene Lösung: Korrektur-Scope begrenzen

Wenn eine Korrektur durchgeführt wird, muss das System unterscheiden:

**a) Korrektur bezieht sich auf die Fenster (häufiger Fall):**
- User korrigiert ein Segment, dessen Fenster `Library Andon FM.xls` zeigen
- → Neue Regel: "Excel mit `Library Andon FM` / `Statistik` = Andon FM"
- → AutoDetect-Label "Youtube" für andere Segmente bleibt unbeeinflusst

**b) Korrektur bezieht sich tatsächlich auf das AutoDetect-Label (seltener):**
- User sagt explizit "alle Youtube-Segmente in diesem Zeitraum sind eigentlich X"
- → Globale Umbenennung nur auf expliziten Wunsch

**Implementierungsidee:** Bei einer Korrektur zeigt das System, *warum* der AutoDetect diesen Vorschlag gemacht hat (welche Fenster), und fragt: "Korrektur gilt für: [○ diese Fenster] [○ alle mit diesem AutoDetect-Label]". Default: "diese Fenster".

#### Fehlende AutoDetect-Regel

Zusätzlich zum Scope-Problem fehlt eine Regel für die Andon-FM-Excel-Dateien:
- `Library Andon FM.xls` → RA / Bearb. Andon FM Playlist RAAFAN (oder RASUAF)
- `Statistik_heute.csv` (im Andon-FM-Kontext) → RA / Bearb. Andon FM Statistik

Wenn diese Regel existiert hätte, wäre der AutoDetect korrekt gewesen, die manuelle Korrektur wäre nicht nötig gewesen, und die Fehl-Generalisierung hätte nicht stattgefunden.

---

## Analyse: Wo liegt der größte Hebel?

| Verbesserung | Aufwand | Erwartete Zeiteinsparung pro Tag |
|-------------|---------|----------------------------------|
| V1. Synthetische corrections | mittel | ~10–15m (weniger Angst vor Ausdehnung → schnellere Nacherfassung) |
| V2. Priorisierte Vorschläge | niedrig | ~10–20m (weniger Copy-Paste-Zyklen) |
| V3. Mini-Segment-Zusammenfassung | mittel | ~15–25m (weniger Einzelentscheidungen) |
| V3a. Arbeitskontext-Erkennung | mittel-hoch | ~20–30m (drastische Reduktion bei Multi-Fenster-Workflows wie RWOWTT) |
| V4. Reihenfolge-Flexibilität | hoch | ~10–15m (weniger mentales Jonglieren) |
| V5. Originale Projektion | mittel | ~5–10m (bessere Orientierung beim Nacherfassen) |
| V6. Besserer Tagesbericht | niedrig | 0m (kein direkter Zeitgewinn, aber bessere Transparenz) |
| V7. "AutoDetect wiederherstellen" | niedrig | ~5–10m (weniger Tipp-Arbeit bei falschen Regel-Überschreibungen) |

V2 und V3 zusammen hätten vermutlich den größten Effekt bei überschaubarem Aufwand.

---

## Changelog (erledigte Fixes)

### ✅ Fix: Planner Context überschreibt spezifische AutoDetect-Klassifikation (2026-03-17)

**Commit:** `4179314` — `windowmon_import.py`

**Problem:** Der Planner-Context-Mechanismus verglich nur den 2-Buchstaben Account-Code.
Wenn ein Windowmon-Block bereits durch AutoDetect spezifisch klassifiziert war (z.B.
`Statistik_heute.csv` → `Untersuchung Rotation Andon FM / OpenAIR RAAFAN`, Account `RA`),
wurde diese Klassifikation trotzdem überschrieben, sobald eine Planer-Aktivität mit
demselben Account aktiv war (z.B. ein vorher importiertes `Ansehen Youtube-Videos RAYTYT`,
ebenfalls Account `RA`).

**Auslöser für Entdeckung:** Nacherfassung vom 16.03.2026 — Segmente mit Excel/Statistik_heute.csv
zeigten "Ansehen Youtube-Videos RAYTYT ← aus Planer-Aktivität", obwohl kein YouTube-Fenster
im Segment vorkam.

**Fix:** Planner Context greift nur noch, wenn der AutoDetect-Block **keinen spezifischen
6-Buchstaben Task-Code** enthält. Blöcke mit spezifischer Klassifikation (z.B. RAAFAN)
bleiben unangetastet.

**Abgrenzung zu V7:** V7 beschreibt ein verwandtes, aber separates Problem — die
Day-Override-Generalisierung (Korrektur am Label statt an den Fenstern). Der hier
gefixte Bug war eine Vorstufe: selbst ohne Day-Override-Problem wurde die AutoDetect-
Klassifikation durch den Planner Context zerstört. V7 bleibt offen.

### ✅ Fix: Noise-Absorption verschluckt kurze Same-Account-Runs (2026-03-17)

**Commit:** `6f45d09` — `windowmon_import.py`

**Problem:** `_consolidate_blocks` Pass 1 (Noise-Absorption) behandelte jeden Block einzeln.
Eine Sequenz aus mehreren kurzen Blocks desselben Accounts (z.B. RA: Andon FM Edge 12s →
LE: Explorer "Lebenserhaltung" 18s → RA: Excel Statistik_heute 86s) wurde blockweise
absorbiert: die kurzen Einzelblöcke (12s, 18s) fielen unter den `noise_threshold_s` von
30s und wurden vom langen KS-Nachbarn aufgesogen. Ergebnis: der gesamte ~2-Minuten
Andon-FM-Block verschwand, und zwei KS-Blöcke erschienen direkt hintereinander ohne
erkennbare Unterbrechung.

**Fix:** Neuer Pass 0 mit zwei Sub-Passes:
- **0a:** Direkt benachbarte Blocks mit demselben Account werden vor der Noise-Absorption
  zusammengeführt (z.B. RA+RA → ein längerer RA-Block).
- **0b:** Kurze Fremd-Blocks (< noise_threshold) zwischen zwei Blocks desselben Accounts
  werden als "Brücke" absorbiert (z.B. RA → short LE → RA → ein RA-Block). Typischer
  Fall: Explorer-Ordner öffnen auf dem Weg zur nächsten Excel-Datei.

### Beobachtung: Nacherfassung vs. manuelle Erfassung (2026-03-17)

**Quelle:** Feedback von Kurt bei Nutzung der Nacherfassung am 17.03.2026

Kurt stellt fest, dass er bei der Abwägung "Nacherfassungs-Dialog vs. manuell als ungeplante
Aktivitäten erfassen" häufig den manuellen Weg wählt, wenn:

1. **Zu viele Segmente:** Der Window Monitor schlägt deutlich mehr Segmente vor als logisch
   sinnvolle Aktivitäten. Jedes Segment muss einzeln beurteilt werden.
2. **Unlogische Vorschläge:** Segmente erscheinen, die nicht zur Erinnerung passen →
   Verifikationsaufwand (Segment öffnen, Window-Events prüfen, rekonstruieren).
3. **Wechsel zwischen geplant/ungeplant:** Wenn sich nacherfasste Segmente mit regulären
   Planer-Aktivitäten abwechseln, muss die Nacherfassung importiert/verlassen werden,
   die geplante Aktivität abgehakt, und dann erneut in die Nacherfassung eingestiegen
   werden. Der manuelle Weg (ungeplante Aktivität + Abhaken) ist in diesem Fall
   durchgängiger.

**Implikation für V3/V3a:** Diese Beobachtung bestätigt, dass die Nacherfassung nur dann
schneller ist als der manuelle Workflow, wenn die Vorschläge weitgehend stimmen und wenige
sind. V3a (Arbeitskontext-Erkennung) adressiert genau diesen Punkt: weniger, bessere
Vorschläge → weniger Verifikation → Nacherfassung wird tatsächlich schneller als der
manuelle Weg.
