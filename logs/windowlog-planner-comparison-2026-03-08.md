# Vergleich Window Log vs. Planner Log — 2026-03-08

## Zusammenfassung (Executive Summary)

Am 8. März 2026 wurden 2958 Window-Log-Einträge verarbeitet (21 Korrekturen durch bestehende Regeln). Der Tag zeigt ein typisches Muster: intensive Morgenroutine, Schwimmbad, dann ab Nachmittag starke Fokussierung auf Planungsarbeit (Planner-Handbuch, Logs) und Radio-Würmchen-Aktivitäten (Thinking Frequencies, Ohrwürmer).

**Hauptergebnisse:**
- **314.6 Min "div. Surfen (News)"** im Window Log — ein großer Teil davon ist tatsächlich OpenClaw-Webchat (Diskussionen mit Sidestepper), Begutachtung von Handbüchern, und andere spezifische Tätigkeiten. Das Window Log kann Browser-Tabs nicht nach Inhalt unterscheiden.
- **37.3 Min "Bearbeitung Unbenannt"** — ungespeicherte Notepad-Dateien, kontextabhängig verschiedenen Aktivitäten zuzuordnen.
- **~50 Min in "??" (unbekannt)**-Kategorien für benannte Textdateien — diese können mit neuen Regeln automatisch zugeordnet werden.
- Offline-Aktivitäten (Schwimmbad 07:55–08:58, Laufen 13:39–14:35, WC, Küche, etc.) fehlen naturgemäß im Window Log.

## Timeline-Vergleich (Schlüsselperioden)

### Morgenroutine (05:56–07:55)

| Zeit | Planner-Aktivität | Window Log | Übereinstimmung |
|------|-------------------|------------|-----------------|
| 05:56–05:58 | Aufstehen, Rasierer fassen | div. Surfen (News) → Rasier-Pause? | ⚠️ WL zeigt PC-Nutzung |
| 05:58–06:13 | Rasieren + Planung + Ohrwürmer | Surfen, Planung, Ohrwürmer, Aufwandserfassung | ✅ Gut |
| 06:13–06:53 | Auswertung Tagesablauf + OpenClaw | div. Surfen (News) = OpenClaw-Webchat | ⚠️ Nicht unterscheidbar |
| 06:53–06:57 | Eintragen Doku Ohrwürmer | Planung (KS) | ⚠️ Leichte Abweichung |
| 06:57–06:59 | Anhören Andon Labs TF | Anhören RW-Programm | ✅ Passt |
| 06:59–07:03 | Bearb. Essensplan | KS Planung → LE Essensplan | ✅ Passt |
| 07:03–07:04 | Vorbereitung Playlist | RW Bearb. Playlist | ✅ Passt |
| 07:04–07:26 | Frühstücken | LE Morgent.+Frst. + ~Vergleich forcierter Preise.txt | ✅ Passt |
| 07:49–07:52 | Bearb. Ohrwürmer (durchzunehmende) | RW Bearb. Ohrwürmer | ✅ Passt |

### Schwimmbad (07:55–08:58)

| Zeit | Planner | Window Log | Übereinstimmung |
|------|---------|------------|-----------------|
| 07:55–08:58 | Besuch Schwimmbad | LE Morgent.+Frst. (idle/andere Aktivität) | ✅ Offline korrekt |

### Thinking Frequencies Analyse (08:59–10:03)

| Zeit | Planner | Window Log | Übereinstimmung |
|------|---------|------------|-----------------|
| 08:59–09:15 | Untersuchung Playlist Andon FM | Andon FM Station logs.txt.music.txt, Bearb. Ähnlichkeiten | ⚠️ WL zeigt Dateien statt Aktivitätsnamen |
| 09:15–09:27 | Zähne putzen | div. Surfen + Bearbeitung Unbenannt | ⚠️ Parallel PC-Nutzung |
| 09:27–10:03 | Analyse Thinking Frequencies + London Calling | div. Surfen, Bearbeitung Unbenannt, YouTube | ⚠️ Sehr fragmentiert |

### Essensplan-Block (11:22–12:38)

| Zeit | Planner | Window Log | Übereinstimmung |
|------|---------|------------|-----------------|
| 11:22–12:38 | Bearb. Essensplan (Lokalsuche) | LE Bearb. Essensplan + Essensdb + YouTube | ✅ Gut, YouTube als Hintergrund |

### Nachmittag: Ohrwürmer-Dokumentation (14:49–15:50)

| Zeit | Planner | Window Log | Übereinstimmung |
|------|---------|------------|-----------------|
| 14:49–15:50 | Dokumentation Ohrwurm-Projekt RWOWDO | RW Bearb. Ohrwürmer (dominant), Bearbeitung Unbenannt | ✅ Gut, "Unbenannt" = Doku-Entwurf |

### Nachmittag/Abend: Planner-Arbeit (15:50–22:37)

| Zeit | Planner | Window Log | Übereinstimmung |
|------|---------|------------|-----------------|
| 15:50–16:03 | Diskussion OpenClaw Sicherung | div. Surfen (News) = OpenClaw | ⚠️ Nicht unterscheidbar |
| 16:04–17:02 | Begutachtung Planner-Handbuch | div. Surfen (News), projection.json, Unbenannt | ⚠️ Meist als Surfen erfasst |
| 17:04–17:23 | Diskussion Planner mit OpenClaw | div. Surfen (News) | ⚠️ OpenClaw = Browser |
| 17:25–17:38 | Erstellung JSON-Converter | div. Surfen (News) | ⚠️ OpenClaw-Webchat |
| 18:32–18:55 | Diskussion JSON-Konverter | div. Surfen (News) | ⚠️ OpenClaw |
| 19:01–19:04 | Surfen Austrian Charts | RW Surfen Austrian Charts | ✅ Perfekt |
| 20:35–22:32 | Nacherfassung Ablauf (wiederholt) | KS Planung + Aufwandserfassung | ✅ Gut |

### Abendzeremonie (22:37–00:06)

| Zeit | Planner | Window Log | Übereinstimmung |
|------|---------|------------|-----------------|
| 22:37–23:09 | Zähne putzen + Zwischenraum | Programm TF.txt, Surfen, Atariage | ⚠️ Parallel PC-Nutzung |
| 23:23–23:40 | Eintragen Zeiten Atariage | CS Surfen Atariage | ✅ Perfekt |

## Abgeleitete neue Regeln

### HIGH Confidence (eindeutige Zuordnung)

| # | Datei/Titel-Muster | → Konto | → Aktivität | Begründung |
|---|---------------------|---------|-------------|------------|
| 1 | `Programm Thinking Frequencies` in Titel | RW | Scan Thinking Frequencies | Immer im Kontext von TF-Analyse; 25.4 Min am Tag |
| 2 | `DJ Breaks Thinking Frequencies` in Titel | RW | Scan Thinking Frequencies | DJ-Breaks-Erfassung für TF; 3.5 Min |
| 3 | `Andon FM Station logs.txt.music.txt` in Titel | RA | Erfassung Sendungen Thinking Frequencies | Musik-Logs von Andon FM; 13.8 Min |
| 4 | `Andon FM Station logs.txt.shows.txt` in Titel | RA | Erfassung Sendungen Thinking Frequencies | Shows-Logs von Andon FM; 1.4 Min |
| 5 | `Andon FM Station logs.txt` (ohne .music/.shows) in Titel | RA | Erfassung Sendungen Thinking Frequencies | Basis-Logs; 2.5 Min |
| 6 | `~Vergleich forcierter Preise` in Titel | LE | Bearb. Essensplan | Preisvergleichs-Datei für Essensplan; 17.5 Min |
| 7 | `Protokoll Mittagessen` in Titel | LE | Bearb. Essensplan | Kochprotokolle; 5.3 Min gesamt |
| 8 | `planner-log-` in Titel | KS | Begutachtung Planung-Logs | Planner-Log JSON-Dateien |
| 9 | `projection-` in Titel (.json) | KS | Begutachtung Planung-Projection | Projektionsdateien |
| 10 | `master_task_list` in Titel | KS | Begutachtung Master Task List | Master Task List |

### MEDIUM Confidence (starker Hinweis)

| # | Datei/Titel-Muster | → Konto | → Aktivität | Begründung |
|---|---------------------|---------|-------------|------------|
| 11 | `report_Soul` oder `report_soul` in Titel | RA | Lesen/Bearb. Soul.txt (Andon FM) | Soul-Reports von Andon FM; 3.2 Min |
| 12 | `KorrekturForciertePreise` in Titel (> 5 Sek) | LE | Bearb. Essensplan | Schon teilweise durch bestehende Regeln abgedeckt, aber nur für "Single"-Fälle |

### LOW Confidence (kontextabhängig)

| # | Datei/Titel-Muster | → Konto | → Aktivität | Begründung |
|---|---------------------|---------|-------------|------------|
| 13 | `Bearbeitung Unbenannt` (Notepad) | ?? | Kontextabhängig | 37.3 Min — könnte Ohrwürmer-Doku, Notizen, oder Ablauf-Erfassung sein |

## Lücken und Konflikte

### 1. OpenClaw-Webchat vs. div. Surfen
**Größtes Problem:** ~100+ Minuten OpenClaw-Diskussionen werden als "div. Surfen (News)" erfasst, weil beides im Browser stattfindet. Betroffene Planner-Einträge:
- Auswertung Tagesablauf + Diskussion mit OpenClaw (06:13–06:53, 40 Min)
- Diskussion Sicherung Planungs-Logs (15:50–16:03, 13 Min)
- Diskussion Handbücher mit OpenClaw (17:04–17:06, 2 Min)
- Diskussion Planner-Handbuch (17:11–17:23, 12 Min)
- Erstellung JSON-Converter (17:25–17:38, 13 Min)
- Diskussion JSON-Konverter (18:32–18:55, 23 Min)
- Nacherfassung Ablauf / Behebung Tab-Bug (21:02–21:19, 17 Min)

**Empfehlung:** Das Window Log kann OpenClaw nicht erkennen. Eine mögliche Lösung wäre, den OpenClaw-Webchat-Tab einen spezifischen Titel zu geben (z.B. "OpenClaw Chat") — dann könnte eine Regel greifen.

### 2. Offline-Aktivitäten ohne Window-Log
Folgende Planner-Aktivitäten haben naturgemäß keine Window-Log-Einträge:
- WC-Besuche (insgesamt ~35 Min)
- Schwimmbad (63 Min)
- Laufen/E-Bike (56 Min)
- Küchen-Aktivitäten (Kochen, Abwaschen, Essen, etc.)
- Körperpflege (Rasieren, Einschmieren, Zähne putzen)
- Bett machen, An-/Ausziehen, Lüften

### 3. Parallele PC-Nutzung während Offline-Tätigkeiten
Während Zähne putzen (22:37–23:09) lief der PC weiter und zeigte Atariage und TF-Programme — das deutet auf ein Muster hin, wo Kurt während Zahnpflege am PC browst.

### 4. Fragmentierung
Viele Planner-Einträge ab dem Nachmittag sind sehr kurz (1–3 Min) und wechseln schnell zwischen Aktivitäten. Das Window Log zeigt ein ähnliches Muster mit schnellem Fensterwechsel.

## Empfehlungen für Auto-Detection

### Sofort umsetzbar (neue Regeln für windowlog_corrector.py)
1. **Textdatei-Regeln** (Rules 1–11 oben): Können direkt als Pattern-Matching-Regeln implementiert werden. Geschätzte Verbesserung: ~50 Min von "??" zu korrektem Konto.

2. **Kontextuelles "Unbenannt":** Für "Bearbeitung Unbenannt" eine kontextuelle Regel einbauen, die den vorherigen/nächsten Eintrag prüft:
   - Wenn vor/nach Ohrwürmer → RW / Bearb. Ohrwürmer
   - Wenn vor/nach Essensplan → LE / Bearb. Essensplan
   - Wenn vor/nach Planung → KS / Nacherfassung Ablauf

### Mittelfristig
3. **OpenClaw-Tab-Erkennung:** Wenn der OpenClaw-Webchat einen erkennbaren Tab-Titel hätte, könnten ~100+ Min/Tag korrekt zugeordnet werden. Aktuell die größte Ungenauigkeits-Quelle.

4. **"div. Surfen" Aufspaltung:** Viel von "div. Surfen (News)" ist eigentlich spezifische Recherche. URL-basierte Erkennung (wenn der Window Logger URLs erfassen kann) wäre ideal.

### Langfristig
5. **Zeitraum-basierte Zuordnung:** Wenn der Planner-Log als Ground Truth dient, könnten Window-Log-Einträge innerhalb eines Planner-Zeitfensters automatisch dem Planner-Task zugeordnet werden (Rückwärts-Mapping).

## Statistik

| Metrik | Wert |
|--------|------|
| Window-Log-Einträge (nach Filterung) | 2958 |
| Planner-Einträge (nicht übersprungen) | ~95 |
| Bestehende Korrekturen angewendet | 21 |
| Neue Regel-Vorschläge | 13 |
| Geschätzte Verbesserung durch neue Regeln | ~50 Min von "??" → korrekte Zuordnung |
| Nicht-auflösbar (OpenClaw = Surfen) | ~100+ Min |
| Offline-Aktivitäten (kein WL möglich) | ~180+ Min |
