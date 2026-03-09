# Feature: Integrierter Window Monitor ("Lernendes System")

**Status:** Design / Konzept  
**Datum:** 2026-03-09  
**Anlass:** 57% Meta-Anteil am 08.03 — Erfassung und Nacherfassung kosten zu viel Zeit  
**Vorgänger:** VB5 Window Logger (seit ~2008, automatische Fenster-Erkennung)

---

## Vision

Das Planungstool übernimmt die Window-Überwachung selbst (ersetzt langfristig den VB5 Window Logger). Durch die Kombination von **geplantem Task + aktuellem Fenstertitel** kann das System:

1. Automatisch erkennen, welche Aktivität gerade stattfindet
2. Abweichungen von der Planung anzeigen
3. Aktivitäts-Wechsel automatisch loggen (mit Bestätigung)
4. Die manuelle Nacherfassung weitgehend eliminieren

## Kernidee: Kontext-bewusste Erkennung

Der entscheidende Vorteil gegenüber dem VB5-Logger: Das Tool kennt den **geplanten Task**. Damit können gleiche Fenstertitel unterschiedlich interpretiert werden:

| Fenstertitel | Geplant: "Scan Thinking Frequencies" | Geplant: "Bearb. Essensplan" |
|---|---|---|
| "Chrome - YouTube" | → Passt (Musik hören) | → Abweichung? |
| "Notepad - Protokoll Mittagessen" | → Abweichung | → Passt |
| "Chrome - Austrian Charts" | → Verwandt (Radio) | → Abweichung |
| "OpenClaw Webchat" | → Abweichung | → Abweichung |

### Drei Zustände

- **✅ Bestätigung:** Fenstertitel passt zum geplanten Task → automatisch loggen
- **⚠️ Verwandt:** Fenstertitel passt zu einem anderen bekannten Task → Vorschlag: "Meinst du [anderer Task]?"
- **❓ Unbekannt:** Kein Match → nichts tun oder nachfragen

## Phasenplan

### Phase 1: Rohe Window-Überwachung (MVP)
- Python-Thread im Planner, der alle X Sekunden das aktive Fenster abfragt
- Anzeige des aktuellen Fenstertitels irgendwo in der GUI (z.B. Statusleiste)
- Logging in eigenes Format (parallel zum VB5-Logger, der weiterläuft)
- Noch keine automatische Erkennung — nur Datensammlung
- **Ziel:** Sicherstellen, dass die Datenerfassung funktioniert und nichts verloren geht

### Phase 2: Regelbasierte Erkennung
- Import der bestehenden Regeln aus `windowlog_corrector.py` (aktuell ~30 Regeln)
- Plus neue Regeln aus der Vergleichsanalyse vom 08.03 (~10 HIGH-Confidence)
- Anzeige in der GUI: "Erkannte Aktivität: [Name]" neben dem aktuellen Fenstertitel
- Vergleich mit geplantem Task: Bestätigung / Abweichung / Unbekannt
- **Noch kein automatisches Loggen** — nur visuelle Anzeige

### Phase 3: Halb-automatisches Loggen
- Wenn ein Aktivitätswechsel erkannt wird (neues Fenster → andere Aktivität), schlägt das Tool vor: "Wechsel zu [neue Aktivität]?"
- Bestätigung: Ein Klick/Tastendruck loggt den Wechsel mit korrekter Startzeit
- Korrektur: User kann den Vorschlag ändern
- Ablehnung: Fenstertitel wird als "Rauschen" markiert (z.B. kurzer Tab-Wechsel)
- **Ziel:** Drastische Reduktion der manuellen Eingabe

### Phase 4: Regellernen
- Jede Korrektur (User ändert vorgeschlagene Aktivität) wird als neue Regel gespeichert
- Format: `{window_title_pattern, planned_task_context, actual_activity, confidence, date_added}`
- Regeln mit genug Bestätigungen werden automatisch hochgestuft
- Regeln, die oft korrigiert werden, werden zurückgestuft oder entfernt
- **Ziel:** System wird mit der Zeit genauer, ohne dass jemand Regeln programmieren muss

### Phase 5: Offline-Lücken und Aufwandserfassung
- Wenn keine PC-Aktivität erkannt wird (> X Minuten), fragt das Tool beim nächsten Fensterwechsel: "Was hast du seit [letzte Aktivität] gemacht?" — mit Vorschlägen basierend auf Tageszeit und Planung
- Export des korrigierten Logs in ein Format, das die Access-DB-Aufwandserfassung direkt importieren kann
- **Ziel:** Kein separater Nacherfassungs-Schritt mehr nötig

## Technische Notizen

### Window-Titel abfragen (Windows)
```python
import ctypes
def get_active_window_title():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value
```
Oder via `pywin32` / `win32gui` für robustere Lösung.

### Polling-Intervall
- VB5-Logger pollt jede Sekunde (Timer1), loggt bei Fensterwechsel
- Phase-1-Monitor: identisches Verhalten (1-Sekunden-Polling, Log bei Titeländerung)
- Browser/Excel: Titel wird auch bei gleichem Handle geprüft (Tab-Wechsel ändert nicht den Handle)

### Minutenrundung für Aufwandserfassung
Wichtig für Phase 5 (Access-DB-Export): Die Aufwandserfassung zählt **nur den letzten Eintrag pro Minute**. Dauer einer Aktivität = Differenz der auf ganze Minuten abgerundeten Zeitstempel.

Beispiel: Wechsel um 14:03:12, 14:03:45 und 14:07:20 → für Minute 14:03 zählt der Eintrag von 14:03:45. Aktivität dauert von 14:03 bis 14:07 = 4 Minuten.

Das JSONL-Log enthält sekundengenaue Zeitstempel. Die Minutenaggregation erfolgt erst beim Export.

### Regelformat (Phase 2+)
```yaml
rules:
  - pattern: "Thinking Frequencies"
    match_type: "contains"  # contains | regex | exact
    activity: "Scan Thinking Frequencies"
    account: "RW"
    code: "RWMPMP"
    confidence: high
    source: "windowlog_corrector migration"
    
  - pattern: "Austrian Charts"
    match_type: "contains"
    activity: "Surfen Austrian Charts"
    account: "RA"
    confidence: high
    context_boost:  # Höhere Confidence wenn geplanter Task passt
      planned_account: "RA"
```

### Datenformat (Phase 1)
```json
{
  "timestamp": "2026-03-08T06:13:42",
  "window_title": "Chrome - Thinking Frequencies Playlist",
  "process_name": "chrome.exe",
  "planned_task": "Scan Thinking Frequencies RWMPMP",
  "recognized_activity": null,
  "match_state": "unknown"
}
```

## Parallelbetrieb

Während der Entwicklung läuft der VB5-Window Logger weiter. Das neue System schreibt sein eigenes Log. Erst wenn die Erkennung zuverlässig ist und die Daten konsistent mit dem VB5-Log übereinstimmen, kann der alte Logger abgeschaltet werden.

## Bezug zur Gesamtvision

Aus `planning-unified-vision.md`:
> "Automatic activity detection from window changes, matched against plan"
> "Learnable mappings: every time this file is edited → this activity"

Dieses Feature ist die direkte Umsetzung dieser Vision.

## Erwarteter Zeitgewinn

Basierend auf dem 08.03:
- Nacherfassung Ablauf: 75 min → ~5-10 min (nur Offline-Lücken + Korrekturen)
- Begutachtung/Korrektur Logs: 30+ min → ~5 min
- Aufwandserfassung-Korrektur (Access): geschätzt 30-60 min/Woche → nahe 0
- **Geschätzte Ersparnis: 60-90 Minuten pro Tag**
