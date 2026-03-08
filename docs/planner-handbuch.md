# Planungstool — Benutzerhandbuch

**Version:** v1.5 (Stand: März 2026)

---

## 1. Was ist das Planungstool?

Das Planungstool ist ein reaktiver Tagesplaner, der in Python/tkinter läuft. Es nimmt die Aktivitätenliste aus der bestehenden `Planungsaktivitaeten.csv` entgegen und führt dich in Echtzeit durch den Tag — ähnlich wie ein Radio-Playout-System (inspiriert von 88.6), das immer den nächsten Titel parat hat und nichts dem Zufall überlässt.

### Philosophie

Statt eine statische Liste abzuarbeiten, die sofort veraltet, sobald etwas dazwischenkommt, funktioniert das Tool **reaktiv**:

- Es kennt mehrere parallele Aktivitätenlisten mit unterschiedlichen Prioritäten.
- Es wählt immer die nächstbeste, gerade verfügbare Aufgabe aus.
- Unterbrechungen, ungeplante Aktivitäten und Verspätungen können direkt erfasst und rückdatiert werden.
- Das Ergebnis ist ein vollständiges JSON-Log — das Äquivalent der bisherigen Ablauf-Dateien, aber maschinenlesbar und mit Zusatzfeldern.

Das Tool **ersetzt** die bisherige C#-Planung. Die Projektion (beim Start erzeugt) übernimmt die Funktion der alten Planung-Textdateien, der JSON-Log ersetzt die Ablauf-Dateien. Seit dem 3. März 2026 werden keine Planung- und Ablauf-Textdateien mehr erstellt. Das C#-Tool kann weiterhin Planungsdateien erzeugen, wird aber aktuell nicht mehr gestartet.

---

## 2. Voraussetzungen

| Anforderung | Details |
|---|---|
| Python | 3.10 oder neuer (getestet mit 3.11). Python ist **nicht** standardmäßig in Windows enthalten — es muss separat installiert werden. Auf diesem System installiert unter `C:\Program Files\Python311\python.exe`. |
| tkinter | In der Standard-Python-Distribution enthalten (bei der Windows-Installation von python.org ist tkinter standardmäßig dabei) |
| PyYAML | Optional — nur für YAML-Exceptions nötig (`pip install pyyaml`) |
| CSV-Datei | `Planungsaktivitaeten.csv` im C#-Projektordner (Pfad in `csv_parser.py` eingetragen) |
| Master Task List | `kontensystem/data/master_task_list_v4.jsonl` — für Code-Vorschläge |

**Wichtig:** Das Tool liest die CSV direkt von ihrem angestammten Ort:
```
C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Planungsaktivitaeten.csv
```
Dieser Pfad ist in `planner/csv_parser.py` fest eingetragen. Wenn sich die Datei woanders befindet, muss der Pfad dort angepasst werden.

---

## 3. Start

### Aufrufen

```
cd C:\Users\kurt_\.openclaw\workspace\kontensystem
py planner/main.py
```

Oder aus dem `kontensystem`-Verzeichnis:
```
py planner\main.py
```

### Der Startup-Dialog

Bevor das Hauptfenster erscheint, öffnet sich ein Konfigurationsdialog. Hier wird der Tagestyp festgelegt — das steuert, welche CSV-Zeilen aktiv sind.

**Felder im Startup-Dialog:**

- **Datum & Wochentag** — automatisch ermittelt, nur zur Anzeige.
- **Arbeitstyp** (Dropdown):
  - `auto` — leitet den Typ aus dem Wochentag ab (Mo/Mi = Bürotag, Di/Do/Fr = Teleworking)
  - `Bürotag` — erzwingt Bürotag-Logik unabhängig vom Wochentag
  - `Teleworking` — erzwingt Teleworking-Logik
  - An Wochenenden ist das Feld deaktiviert.
- **Feiertag** — Checkbox; unterdrückt Büro/Teleworking-Aktivitäten
- **Urlaubstag** — Checkbox; gleiche Wirkung wie Feiertag
- **Tagestyp-Vorschau** — zeigt an, wie der Tag klassifiziert wird (z.B. `Mi | Bürotag | Putztag`)

**YAML-Overrides:** Falls für heute eine Ausnahme in `schedule_exceptions.yaml` definiert ist, wird diese automatisch angezeigt (gelber Hinweistext) und vorausgefüllt. Zum Beispiel: Urlaubstag, Feiertag, früherer Arbeitsbeginn oder Sonderbemerkungen.

Auf **„Starten"** klicken (oder Enter drücken) startet das Tool. **„Abbrechen"** beendet es.

---

## 4. Die Benutzeroberfläche

Das Hauptfenster besteht von oben nach unten aus:

```
┌─────────────────────────────────────────────────────────────┐
│  HH:MM                               Tagestyp-Info          │
├─────────────────────────────────────────────────────────────┤
│  Erledigt-Panel (abgeschlossene/übersprungene Aktivitäten)  │
├─────────────────────────────────────────────────────────────┤
│  Aktuelle Aktivität (Name, Liste, Priorität, Dauer)         │
│  [Preemption-Banner — optional]                             │
├─────────────────────────────────────────────────────────────┤
│  Geplant-Panel (kommende Aktivitäten mit Zeitprojektion)    │
├─────────────────────────────────────────────────────────────┤
│  [✓ Erledigt]  [⏭ Überspringen]  [⏸ Unterbrechen]  [📝 Ungeplant] │
│  [💾 Log speichern]  [📊 Tagesbericht]  [⚡ Automationen]  │
├─────────────────────────────────────────────────────────────┤
│  Statusleiste                                               │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Uhr und Tagestyp-Info

Oben links: die aktuelle Uhrzeit (aktualisiert alle 15 Sekunden).  
Oben rechts: der ermittelte Tagestyp (z.B. `Sa | Wochenende`).

### 4.2 Erledigt-Panel (oben)

Zeigt alle bereits abgeschlossenen und übersprungenen Aktivitäten des Tages, sortiert nach Startzeit:

```
  07:12–07:38  Morgentoilette  (26')
  07:38–08:05  Frühstück  (27')
  08:05–08:09  Medikamente  (4')  ⏭
```

- Erledigte Einträge: helles Blau-Grau
- Übersprungene Einträge (⏭): gedimmteres Grau
- Scrollbar vorhanden, neue Einträge werden automatisch ans Ende gescrollt.

**Zweck:** Man sieht auf einen Blick, was bereits im Log steht — keine Notwendigkeit, die JSON-Datei manuell zu prüfen.

### 4.3 Aktuelle Aktivität (Mitte)

Das Herzstück des Fensters. Zeigt immer die aktuell anstehende Aufgabe:

- **Großer Name** — die Bezeichnung der Aufgabe (6-stelliger Task-Code am Ende wird automatisch ausgeblendet)
- **Listenname** — z.B. `Liste_Morgentoilette` (türkis)
- **Metadaten** — `Prio 2.100 • 25 Min.`
- **Fixzeit-Anzeige** — `⏰ ab 07:00` (falls die Aufgabe eine feste Startzeit hat, gelb)
- **▶ Starten-Button** — erscheint, wenn für diese Aufgabe eine Automation definiert ist (grüner Button mit konfigurierbarem Label)

Bei einer **Wenn-Bedingung** (CONDITION-Zeile): Der Name der Aktivität wird durch die Frage ersetzt (`❓ Bist du zu Hause zu Mittag?`). Statt der normalen Buttons erscheinen **Ja** und **Nein**.

Bei einer **Wartezeit**: Anzeige `⏳ Warte … (Liste_Schwimmbad)` mit verbleibender Wartezeit.

### 4.4 Preemption-Banner

Wenn eine Aufgabe mit **höherer Priorität** bereit wird, während du an einer anderen arbeitest, erscheint ein roter Banner zwischen dem Aufgabenbereich und dem Geplant-Panel:

```
⚠ ZiB 1 (⏰ 19:30) — Liste_Abend — Prio 3.500 wartet   [⏸ Unterbrechen]  [Später]
```

- **⏸ Unterbrechen** — öffnet den Unterbrechungs-Dialog mit der wartenden Aufgabe vorausgefüllt
- **Später** — blendet den Banner aus, bis sich die Situation ändert

Das Tool wechselt **nie automatisch** zur höherprioren Aufgabe — du entscheidest immer.

### 4.5 Geplant-Panel (unten)

Zeigt die geplanten Aktivitäten für den Rest des Tages mit **projizierter Startzeit**:

```
  [Liste_Arbeit]
▶ 09:00–09:45  ⏰  Standup Meeting  (45')
    10:00–10:30     Dokumentation  (30') 🖱
  [Liste_Freizeit]
    19:30–20:00  ⏰  ZiB 1  (30')
```

- **▶** = aktuelle Aufgabe (blau)
- **⏰** = fixe Startzeit (die Uhrzeit-Angabe in der Projektion ist dann die Fixzeit, nicht die Schätzung)
- **🖱** = diese Aufgabe ist gerade bereit (klickbar → Doppelklick zum Loggen)
- Grüne Einträge = aktuelle Kandidaten (können jetzt gestartet werden)
- Gelbe Einträge = fixzeitlich, noch nicht bereit
- Listen-Trennzeilen ([Listenname]) für Übersichtlichkeit

**Interaktion mit der Queue:**
- **Doppelklick** auf einen aktuellen Kandidaten → öffnet den Erledigt-Dialog für diesen Eintrag
- **Doppelklick** auf einen zukünftigen Eintrag → öffnet den Adhoc-Dialog mit vorausgefülltem Namen (zum Vorziehen; der Eintrag muss später beim regulären Durchlauf übersprungen werden)
- **Rechtsklick** auf einen aktuellen Kandidaten → öffnet den Überspringen-Dialog

### 4.6 Statusleiste

Ganz unten, zeigt auf einen Blick den Tagesstand:

```
  Erledigt: 12  |  Übersprungen: 3  |  Offen: 28  |  Aktive Listen: 4  |  Wartend: 1  |  Letzter Eintrag: 10:42  ⚠ Lücke: 47m
```

- **Lückenwarnung** (⚠): erscheint, wenn der letzte Log-Eintrag mehr als 30 Minuten zurückliegt — Hinweis, dass etwas nicht erfasst wurde.

---

## 5. Arbeitsablauf

### Typischer Tagesstart

1. **Planer öffnen:** `py planner/main.py`
2. **Startup-Dialog ausfüllen:** Tagestyp prüfen/bestätigen, auf „Starten" klicken.
3. Das Tool prüft, ob für heute bereits ein Log existiert (Neustart nach Absturz/Unterbrechung) und stellt den Zustand wieder her.
4. Die erste Aktivität erscheint im Mittelpanel.

### Tasks abarbeiten

Für jede Aktivität:
1. Die Aufgabe ausführen.
2. Auf **✓ Erledigt** klicken.
3. Im Dialog Startzeit prüfen (Vorgabe: Ende der vorherigen Aufgabe), Endzeit anpassen falls nötig, optionalen Kommentar eintragen.
4. Auf **✓ Erledigt** im Dialog klicken.

Die Aktivität wandert ins Erledigt-Panel, die nächste erscheint.

### Aufgabe überspringen

- Auf **⏭ Überspringen** klicken.
- Optional eine Begründung eintragen.
- Die Aufgabe erscheint im Erledigt-Panel mit ⏭-Markierung.

### Ungeplante Aktivitäten erfassen

Wenn zwischendurch etwas passiert, das nicht in der Planung steht:
1. Auf **📝 Ungeplant** klicken.
2. Bezeichnung eingeben (Code-Vorschlag erscheint automatisch).
3. Start- und Endzeit anpassen.
4. Bestätigen.

Die aktuelle geplante Aufgabe wird **nicht** abgehakt — sie bleibt offen.

### Unterbrechung

Wenn die aktuelle Aufgabe unterbrochen wird (Telefon, unerwarteter Besucher, etc.):
1. Auf **⏸ Unterbrechen** klicken.
2. Bezeichnung der unterbrechenden Aktivität eingeben.
3. Zeitraum der Unterbrechung eintragen.
4. Bestätigen.

Das Tool schreibt zwei Log-Einträge: das bisherige Segment der unterbrochenen Aufgabe + die Unterbrechung. Die ursprüngliche Aufgabe erscheint danach als **„(Fs.)"** (Fortsetzung).

### Tag beenden

- Auf **💾 Log speichern** klicken, um den Log-Stand zu sichern.
- Das Fenster schließen — falls ungespeicherte Änderungen vorhanden sind, kommt eine Rückfrage.

**Hinweis:** Beim Schließen des Fensters fragt das Tool nach, ob gespeichert werden soll — es speichert aber nicht stillschweigend von selbst. So wird kein versehentliches Überschreiben von Daten verursacht.

---

## 6. Dialoge

### 6.1 Erledigt-Dialog

Öffnet sich bei **✓ Erledigt**.

| Feld | Beschreibung |
|---|---|
| **Bezeichnung** | Name der Aufgabe, editierbar. Änderungen werden im Log als `activity` gespeichert, der Originalname als `original_activity`. |
| **Code-Vorschlag** | Sucht automatisch in der Master Task List nach einem passenden 6-stelligen Code. Zeigt Treffer mit Qualitätsstufe (✓ exakt, ≈ ähnlich, ? enthalten). |
| **„Name übernehmen"** (blauer Button) | Ersetzt den gesamten Text durch den vollen Task-Namen aus der Master Task List + Code. |
| **„Code anfügen"** (grauer Button) | Hängt den vorgeschlagenen Code an den aktuellen Text an. |
| **Begonnen um** | Startzeit (Vorgabe: Ende der vorherigen Aufgabe, oder nach Unterbrechung: Ende der Unterbrechung). |
| **Erledigt um** | Endzeit (Vorgabe: jetzt). |
| **Kommentar** | Optionales Freitext-Feld. |

Validierung: Ende darf nicht vor Beginn liegen.

### 6.2 Überspringen-Dialog

Öffnet sich bei **⏭ Überspringen** oder Rechtsklick in der Queue.

Zeigt den Aufgabennamen und ein Freitext-Feld für eine Begründung. Kein Zeitstempel-Eintrag (der Zeitpunkt des Überspringens wird nicht erfasst).

### 6.3 Ungeplant-Dialog

Öffnet sich bei **📝 Ungeplant**.

Wie der Erledigt-Dialog, aber ohne Referenz auf eine geplante Aufgabe. Die Aktivität wird im Log mit `"list": "ungeplant"` gespeichert. Enthält ebenfalls den Code-Vorschlag.

### 6.4 Unterbrechungs-Dialog

Öffnet sich bei **⏸ Unterbrechen** oder über den Preemption-Banner.

| Feld | Beschreibung |
|---|---|
| **Unterbrechung durch** | Name der unterbrechenden Aktivität (bei Preemption vorausgefüllt). |
| **Unterbrochen um** | Zeitpunkt der Unterbrechung (Vorgabe: jetzt). |
| **Fortgesetzt um** | Zeitpunkt der Wiederaufnahme (Vorgabe: jetzt — muss manuell auf das tatsächliche Ende der Unterbrechung geändert werden). |
| **Kommentar** | Optional. |

### 6.5 Konditions-Modus (Wenn-Bedingungen)

Wenn die aktuelle Aufgabe eine Wenn-Bedingung aus der CSV ist, zeigt das Mittelpanel die Frage an (`❓ ...`). Die normalen Buttons werden durch **✓ Ja** und **✗ Nein** ersetzt.

- **Ja** → führt die in der CSV definierte Aktion aus (z.B. eine andere Liste starten)
- **Nein** → führt die Alternativaktion aus (oder überspringt die Bedingung, falls keine definiert)

Die Antwort wird im Log mit einem `"Entscheidung: Ja/Nein"`-Kommentar gespeichert.

---

## 7. Automationen

Automationen sind vordefinierte Aktionen, die mit einer Aufgabe verknüpft sind. Wenn eine Aufgabe mit einer Automation erkannt wird, erscheint ein grüner **▶ Starten**-Button neben den Metadaten.

### Typen

| Typ | Beschreibung |
|---|---|
| `shell` | Startet ein Programm oder einen Shell-Befehl (z.B. `.exe`, `.bat`) |
| `url` | Öffnet eine URL im Standardbrowser |

Beide Typen werden **nicht-blockierend** ausgeführt — das Tool bleibt offen und bedienbar.

### Zuordnung (Match-Typen)

| Match-Typ | Beschreibung | Beispiel |
|---|---|---|
| `code` | Passt, wenn der 6-stellige Task-Code am Ende der Aktivität übereinstimmt | `RWMPMP` |
| `prefix` | Passt, wenn der Aktivitätsname mit dem Wert **beginnt** | `Radio Würmchen` |
| `contains` | Passt, wenn der Wert **irgendwo** im Aktivitätsnamen vorkommt | `Musik` |

### Automationen verwalten

Über den Button **⚡ Automationen** in der unteren Button-Leiste öffnet sich der Editor.

**Im Editor:**
- Übersichtstabelle mit allen vorhandenen Automationen
- **➕ Neu** — neuen Eintrag anlegen
- **✏️ Bearbeiten** — ausgewählten Eintrag bearbeiten (auch per Doppelklick)
- **🗑️ Löschen** — ausgewählten Eintrag löschen (mit Bestätigung)
- **💾 Speichern** — Änderungen in `data/automations.json` schreiben

**Beim Anlegen/Bearbeiten:**
1. Aufgabe über die Suchfunktion aus der Master Task List auswählen (oder direkt eingeben)
2. Match-Typ wählen (Code / Prefix / Enthält)
3. Typ: Shell oder URL
4. Befehl/URL eingeben (Shell: Datei-Browser verfügbar)
5. Button-Text festlegen (erscheint als „▶ [Text]" im Planer)

Ungespeicherte Änderungen im Editor werden beim Schließen abgefragt.

---

## 8. Tagesbericht

Über **📊 Tagesbericht** lässt sich ein Vergleich von Planung vs. tatsächlichem Ablauf anzeigen.

**Vorgehen:**
1. Button klicken — der Log wird automatisch zuerst gespeichert.
2. Datum aus der Liste der verfügbaren Tage auswählen.
3. **📊 Erstellen** klicken.

Der Bericht enthält:
- **Zusammenfassung**: Geplante Aktivitäten, Erledigt/Übersprungen/Nicht erreicht (Stückzahl + Minuten + Prozent), Ungeplante Aktivitäten, tatsächliche Gesamtzeit
- **Drift-Analyse**: Vergleich geplante vs. tatsächliche Startzeit für erledigte Aktivitäten
- **Übersprungene Aktivitäten** mit Begründungen
- **Ungeplante Aktivitäten** mit Zeitstempeln
- **Nicht erreichte Aktivitäten** (waren in der Projektion, aber weder erledigt noch übersprungen)

Der Bericht wird als `logs/report-YYYY-MM-DD.txt` gespeichert und im Fenster angezeigt.

---

## 9. Tastenkombinationen

| Taste | Wirkung |
|---|---|
| **Enter** | In Dialogen: Bestätigen |
| **Escape** | In Dialogen: Abbrechen |

Es gibt derzeit keine globalen Shortcuts im Hauptfenster (keine Tastenbindungen für Erledigt/Überspringen etc.). Das ist ein bekannter offener Punkt.

---

## 10. Bekannte Einschränkungen und offene Punkte

### Funktionale Einschränkungen

- **Kein Export ins Ablauf-Format:** Der JSON-Log enthält dieselben Informationen wie die alten Ablauf-Textdateien, aber in anderem Format. Ein Konverter für Rückwärtskompatibilität mit der Aufwandserfassung ist geplant, aber noch nicht implementiert.

- **WC-Handling:** WC-Aktivitäten werden manchmal mehrfach geloggt (ungeplant + übersprungen), wenn sie sowohl als ungeplant als auch als Planungsposten auftauchen. Noch keine elegante Lösung.

- **Kein Mehrfach-Neustart an einem Tag:** Das Tool lädt beim Neustart den bestehenden Log, aber Warte-Timer (WAIT) werden relativ zur letzten abgeschlossenen Aktivität neu berechnet — das funktioniert gut, aber komplexe Szenarien (z.B. mehrfache Neustarts mit langen Wartezeiten) können zu kleinen Ungenauigkeiten führen.

- **Keine globalen Shortcuts:** Im Hauptfenster keine Tastenbindungen für die Hauptaktionen.

- **Noch keine Planungsvariablen-Unterstützung:** Das Feld `Dependencies` wertet `Planungsvariablen.X` aus (z.B. `Jause_zu_Hause`, `BRZ_geplant`), aber nur die in `day_context.py` definierten Variablen. Neue Planungsvariablen aus der CSV müssen dort manuell hinzugefügt werden.

### Bekannte Verhaltensweisen

- **Automatisches Scrollen im Erledigt-Panel:** Scrollt nur ans Ende, wenn neue Einträge hinzukommen, nicht bei jedem Refresh.
- **Preemption-Banner**: Verschwindet nach „Später" erst wieder, wenn sich der präemptierende Kandidat ändert (z.B. wenn er selbst abgearbeitet wird).
- **Kein Auto-Save:** Fenster schließen ohne Speichern zeigt eine Warnung, aber es liegt beim Benutzer, regelmäßig zu speichern.
