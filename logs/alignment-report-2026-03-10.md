# Alignment-Report: 10.03.2026

**Erstellt:** 11.03.2026  
**Zweck:** Zeitliches Alignment von Planner-Log, Altem Window Logger (korrigiert), windowmon und Projection für den 10.3.2026.

---

## Legende

| Symbol | Bedeutung |
|--------|-----------|
| 🔴 | Phantom-KS (Planner-Overhead im alten Logger) |
| 🟠 | Teleworking-Lücke (Firmen-Laptop Hauptaktivität, privater PC = Nebenbei) |
| 🔵 | Off-PC-Aktivität (nur im Planner, kein PC-Signal) |
| 🟡 | Projektion weicht stark ab |
| 🟢 | Gute Übereinstimmung aller Quellen |

---

## 1. Zeitstrahl in 15-Minuten-Blöcken (06:00–23:30)

> **Spalten:** Block | Planner-Log | Alter Logger (korr.) | windowmon dominant | Projection | Bemerkung

### Früh-Morgen (06:00–08:00)

| Block | Planner-Log | Alter Logger (korr.) | windowmon | Projection | Bemerkung |
|-------|-------------|----------------------|-----------|------------|-----------|
| **06:00** | Aufstehen, Rasierer fassen (05:59–06:01, off-PC) → WC (06:01–06:03) → Rasieren LEMTRA beginnt (off-PC) | LE Morgent.+Frst. (05:59–06:01) → IN div. Surfen (06:01–06:03) → KS Planung (06:03–06:05) | Planner (python.exe) → Edge (Google Translate, Edge) | Aufstehen 06:03, Rasieren 06:04 | 🔴 KS Planung 06:03 = Phantom (Abhaken LEMTAU während Rasieren off-PC beginnt). Planner sieht Rasieren, Logger sieht nur PC-Öffnen. |
| **06:15** | Rasieren off-PC endet 06:19 → Konversation Pappas (6x, 06:19–06:28) → Analyse TF (06:21–06:37, Einzel-Bursts) | IN div. Surfen (Edge, überwiegend) → RA Analyse TF → RW Bearb. Ohrwürmer | Edge (X/Twitter, Google Translate) | Anhören RW (06:19–06:23), Bearb. Essensplan (06:23–06:27), Vorbereitung Playlist Dusche (06:27–06:35) | 🟡 Projection: Radio/Essensplan. Realität: TF-Analyse + X-Surfen. Kein Radio, keine Playlist-Vorbereitung. |
| **06:30** | Analyse TF (weiter), Korrektur Planungsaktivitäten KSPLPL (06:37–06:42) | IN div. Surfen → KS Planung → KS Aufwandserfassung → RA Analyse TF | Edge (Excel Planungsaktivitaeten, X) | Feinschliff Rasur (06:35–06:41), Ausputzen Rasierer (06:41–06:43), Bearb. Ohrwürmer (06:43–06:46) | 🟡 Projection: Off-PC-Aktivitäten (Rasur-Finishing). Realität: PC-Arbeit (Korrektur Aktivitäten). Rasur-Finishing um ~1h30 nach hinten verschoben. |
| **06:45** | Update+Neustart OpenClaw Gateway (06:47–06:49), Wasser fassen (06:50–06:52, off-PC), Analyse TF (Bursts), Bearb. Essensplan (06:55–06:56), Nacherfassung Ablauf (06:56–06:57), Surfen Andon FM (06:57–07:01) | KS Planung → RA Analyse TF → LE Morgent. (Wasser) → LE Bearb. Essensplan → IN div. Surfen | Edge (Google Translate), Editor (TF-Datei) | Ausziehen (06:46), WC (06:47–06:52), Abwiegen, Reinigung Waschmuschel, **Duschen beginnt 06:55!** | 🟡 GROSSE Abweichung: Projection erwartete Dusche um 06:55. Realität: Dusche erst 08:28 (+1h33min). Wasser fassen 06:50 = off-PC korrekt (kurz). |
| **07:00** | Nacherfassung Ablauf KSPLNA (07:02–07:16, 07:17–07:22) → Analyse TF (07:16–07:17) | KS Planung (dominant, 07:09–07:22) → KS Aufwandserfassung → KS Diskussion OpenClaw | Planner (18x), Planner "Eintrag bearbeiten" (13x), Explorer (22x) | Duschen 06:55–07:15 | 🔴 KS Planung = legitime Nacherfassung Ablauf (kein Phantom; Kurt arbeitet aktiv). windowmon bestätigt: sehr viele Planner-Fokuswechsel = Nacherfassung-Modus. |
| **07:15** | Nacherfassung Ablauf (07:17–07:22), Anhören Radiosender/RW/Ohrwürmer RWMPMP (07:22–07:31, inkl. Nacherfassung TF) | KS Planung → RA Analyse TF → RW Anhören RW-Programm | Planner (11x), Explorer (21x), Editor TF (7x) | Einschmieren, Anziehen, Bett machen, Playlist Frühstück, Frühstücken | 🟡 Projection: Post-Dusche-Aktivitäten. Realität: noch Nacherfassung + Radio-Scan-Arbeit. Morgenroutine komplett verschoben. |
| **07:30** | Diskussion Vortag mit OpenClaw KSPLAW (07:31–07:35, 07:36–07:38), Anhören RW (Bursts), Erfassung Programm OpenAIR RWAFPR (07:42–07:44) | KS Diskussion OpenClaw → RW Anhören → RW Nacherfassung Radioscans → ?? OpenAIR txt | Radio Würmchen.exe (12x), Edge/OpenClaw (11x), Explorer (35x) | Frühstücken (07:29–07:54) | 🟢 OpenClaw-Diskussion + Radioscan im alten Logger bestätigt. Radio Würmchen.exe in windowmon sichtbar. |
| **07:45** | Anhören RW (07:44–07:57), Ansehen YouTube (07:57–07:59), Nacherfassung Ablauf (07:59–08:04) | RW Nacherfassung Radioscans → RA Analyse TF → RW Scan OpenAIR → IN YouTube → KS Aufwandserfassung | Radio Würmchen.exe (5x), Explorer (7x), MSACCESS (3x) | Frühstücken (07:29–07:54) | 🟢 Sehr gute Übereinstimmung: Radio-Scan + YouTube + Nacherfassung alle drei Quellen konsistent. |
| **08:00** | Nacherfassung Ablauf endet (08:04), Bearb. Essensplan (08:04–08:06), Vorbereitung Playlist Dusche (08:06–08:07, PC), Feinschliff Rasur LEMTFR (08:07–08:16, **off-PC!**) | KS Planung (08:01–08:05) → LE Bearb. Essensplan → RW Anhören (kurz) → LE Morgent.+Frst. (08:08–) | Planner (16x), Explorer (14x), MSACCESS (7x) | Papiersortierung (07:54–08:09), Termine prüfen, Mailprüfung... | 🔵 Feinschliff Rasur ist off-PC: Planner sieht es, Logger zeigt LE Morgent. (korrekt als Körperpflege), windowmon zeigt nur Planner-Fokuswechsel = Phantom-ish (Abhaken). 🟡 Projection: Papiersortierung – nicht geschehen. |
| **08:15** | Feinschliff endet 08:16 → Ausputzen Rasierer (08:16–08:18, off-PC) → Bearb. Ohrwürmer (08:18–08:21, PC) → Ausziehen (08:21) → WC (08:22) → Abwiegen (08:23) → Reinigung (08:24) → Starten Playlist (08:25–08:28) → **Duschen beginnt 08:28** | LE Bearb. Essensplan (08:14–08:16) → LE Morgent. (08:16+) → RW Bearb. Ohrwürmer → IN YouTube → LE Morgent. | Explorer (17x), Planner (11x), **Planner "Aufgabe erledigt" (9x!)** | Mailprüfung, Bearb. Essensplan, WC, Ermittlung Gesamtzeiten... | 🔴 9× "Aufgabe erledigt" in windowmon = jede Toiletten-Aktivität einzeln abgehakt → klassischer Planner-Overhead. Logger zeigt LE Morgent. korrekt (ein Eintrag für alle). |

### Dusche & Frühstück (08:30–09:30)

| Block | Planner-Log | Alter Logger (korr.) | windowmon | Projection | Bemerkung |
|-------|-------------|----------------------|-----------|------------|-----------|
| **08:30** | **Duschen LEMTDU (08:28–08:46, komplett off-PC!)** | LE Morgent.+Frst. (08:28–08:48, durchgehend) | **Planner python (1x), Window logger (1x) — fast leer!** | WC, Bearb. Essensplan, Ermittlung Gesamtzeiten | 🟢 PERFEKTES 3-Quellen-Alignment: Planner = Duschen, Logger = LE Morgent., windowmon ≈ leer → alle bestätigen Off-PC! |
| **08:45** | Duschen endet 08:46 → YouTube (08:46–08:48) → Einschmieren (08:48–08:50, off-PC) → Anziehen (08:50–08:53, off-PC) → Bett machen (08:53–08:56, off-PC) | IN YouTube (08:47) → KS Planung (08:48, Phantom) → LE Morgent. (08:49–08:56) | Planner (7x), Window logger (5x), Planner "Aufgabe erledigt" (5x) | Blutdruck, Bearb. Essensplan... | 🔴 KS Planung 08:48 = Phantom (Abhaken YouTube, dann weiter Anziehen off-PC). windowmon zeigt "Aufgabe erledigt" = Planner-Overhead. |
| **09:00** | Vorbereitung Playlist Frühstück (08:56), **Frühstücken (08:56–09:15, off-PC!)** | LE Morgent.+Frst. (08:57–09:14, durchgehend) | Editor Essensplan (1x), Edge YouTube (1x), Winamp (1x) — sehr spärlich! | Blutdruck, Bearb. Ohrwürmer, Scooterfahrten, Arzttermine... | 🟢 Gute Übereinstimmung: Frühstück bestätigt durch LE Morgent. (Logger) + fast leeres windowmon. Viele Projection-Items dieser Zeit gar nicht erreichbar (Frühstück war nicht eingeplant für 09:00). |
| **09:15** | Frühstück endet 09:15, Review Dok BRZG (09:15–09:17 kurz), Bearb. Essensplan Automatisierung (09:17–09:28) | KS Planung (09:13–09:16) → LE Bearb. Essensplan (09:17–09:44) | **MSACCESS (85x!), Explorer (18x), Planner (3x)** | Anhören Radio (09:12), Review Dok BRZG (09:17 fix) | 🟢 MSACCESS dominant = Essensplan-Datenbank. Logger zeigt LE Bearb. Essensplan. Alle konsistent. KS Planung 09:13 = Abhaken Frühstück (Phantom). |
| **09:30** | Einlass Sati (09:28–09:29, off-PC), Anhören RW mit Sati RWMPSE (09:29–09:30), Bearb. Essensplan (09:30–09:34), Anhören Sati (09:32–09:34), Bearb. Essensplan (09:34–09:43) | RW Bearb. Playlist → LE Bearb. Essensplan → RW Anhören RW-Programm → LE Bearb. Essensplan | MSACCESS (59x), Explorer (26x), Radio Würmchen.exe (6x) | Einlass Sati (fix 09:30, 10 min) → Review BRZG (09:40–10:27) | 🟢 Sati kam 02 Min früher (09:28 vs. 09:30). Radio Würmchen.exe + MSACCESS + Logger alle konsistent. Projection: BRZG-Review nicht gestartet. |

### Sati, Papiersortierung & Teleworking-Start (09:45–11:00)

| Block | Planner-Log | Alter Logger (korr.) | windowmon | Projection | Bemerkung |
|-------|-------------|----------------------|-----------|------------|-----------|
| **09:45** | Bearb. Essensplan endet (09:43), Review BRZG (09:43–09:44 kurz), Nacherfassung Ablauf (09:44–09:50), Review BRZG (09:50–09:55), Mund spülen + Häferl waschen (09:55–09:57, off-PC) | GE Bearbeitung Dok BRZG (mit Lücken) → KS Aufwandserfassung → KS Planung → RW Anhören (kurz) → KA Papiersortierung (09:55) | Planner (13x), Explorer (10x), MSACCESS (6x) | Review BRZG (09:40–10:27) | 🟢 GE Logger = BRZG korrekt. Häferl waschen off-PC (Planner only). |
| **10:00** | **Papiersortierung KA-Unterlagen (09:57–10:31, größtenteils off-PC, Sati anwesend)** | KS Planung (09:57) → LE Bearb. Essensdatenbank → **KA Papiersortierung (09:58–10:33!)** | **Explorer (3x), Window logger (2x) — fast leer!** | Review BRZG (09:40–10:27) | 🟢 PERFEKTES Alignment: Planner = Papiersortierung, Logger = KA Papiersortierung, windowmon ≈ leer → Off-PC bestätigt. Abweichung zur Projection: statt BRZG-Review kam Papiersortierung. |
| **10:15** | Papiersortierung (weiter, off-PC) | KA Papiersortierung (weiter) | **Window logger (1x), Explorer (1x) — extrem spärlich!** | Anhören RW mit Sati (10:27–10:35), Verabschiedung Sati (10:43), Bearb. Ohrwürmer (10:51) | 🟢 3-Quellen-Bestätigung Off-PC. Projection-Sati-Events trafen nicht ein (Sati fokussiert auf Putzen + Papiersortierung). |
| **10:30** | Papiersortierung endet 10:31, Verabschiedung Sati (10:31–10:32, off-PC), YouTube (10:32–10:33), Debugging Andon FM (10:33–10:35, 10:38–10:40, 10:41–10:42), YouTube (10:35–10:38, 10:42–10:44), Nacherfassung (10:40–10:41, 10:44–10:51) | RW Bearb. Ohrwürmer → IN div. Surfen → IN YouTube → RA Analyse TF → LE Bearb. Essensplan → RA Untersuchung Andon FM | Explorer (23x), Edge YouTube (11x), Edge Andon FM (8x) | Anhören RW mit Sati (10:27–10:35), Verabschiedung (10:43) | 🟡 Sati ging früher (10:29) als Projection (10:43). Planner und Logger zeigen Debugging + YouTube nach Abgang. |
| **10:45** | Nacherfassung (10:44–10:51), **Start Teleworking (10:51–10:57)**, Bearb. Essensplan (10:57–10:59), BKDD Standup beginnt (10:59) | KS Planung (10:45–10:51) → **BR Start Teleworking** → LE Bearb. Essensplan → IN YouTube (10:59–) | Planner (16x), Explorer (14x), Planner "Eintrag bearbeiten" (11x) | Bearb. Ohrwürmer (10:51), PC herunterfahren (10:56), **Start Teleworking (10:58)** | 🟡 PC wurde NICHT heruntergefahren (Radio Würmchen läuft weiter). Ohrwürmer übersprungen. Teleworking-Start ~10:51 (3 min früher als Projection). |
| **11:00** | **Abhalten BKDD Standup BREPGM (10:59–11:40) — auf Firmen-Laptop!** | IN Ansehen YouTube (10:59–11:46) — privater PC läuft YouTube | **Planner python (1x), Explorer (1x) — fast leer** | BKDD Standup (fix 11:00, 20 min) | 🟠 TELEWORKING-LÜCKE: Arbeit auf Firmen-Laptop. Privater PC: YouTube passiv. windowmon extrem spärlich = korrekte Teleworking-Erkennung! |

### Teleworking-Hauptblock (11:00–15:45)

| Block | Planner-Log | Alter Logger (korr.) | windowmon | Projection | Bemerkung |
|-------|-------------|----------------------|-----------|------------|-----------|
| **11:15–11:30** | Standup (10:59–11:40), Planung BRZ (11:40–12:03) — Firmen-Laptop | IN Ansehen YouTube (Privater PC) | (keine Einträge) | BKDD Standup, Planung BRZ | 🟠 Teleworking. windowmon = komplett leer → eindeutige Off-PC/Firmen-Laptop-Zeit. |
| **11:45** | Planung BRZ (weiter) | IN div. Surfen (ab 11:46, privater PC) | Edge YouTube (1x) | Arbeitszeit Vormittag (11:40–) | 🟠 Teleworking. Privater PC: YouTube/Edge sporadisch. |
| **12:00–12:30** | Arbeitszeit Vormittag (12:03–12:28), Einlass Sati (12:28–12:34) | IN div. Surfen (11:46–13:04, privater PC) | Planner python, Edge Andon FM (je 1x in 12:00, 12:30); nichts in 12:15, 12:45 | Einlass Sati (fix 12:07), Mittagessen (12:37) | 🟠 Sati Einlass: Planner 12:28 vs. Projection 12:07 (+21 Min Verspätung). Logger zeigt privaten PC-Surfen als Parallelaktivität. |
| **12:30–13:00** | Einlass/Koordination Sati (12:28–12:34), **Mittagessen (12:34–13:04, off-PC!)** | IN div. Surfen → LE WC/Jause (13:04–) | Nichts in 12:45 — leeres Fenster während Essen! | Mittagessen (12:37–13:37, 60 min) | 🟢 Mittagessen bestätigt durch leeres windowmon (12:45) + Logger. Planner: 30 Min statt geplante 60 Min. |
| **13:00** | WC (13:04–13:11, off-PC), Korrektur Andon FM-Scraper RWAFAN (13:11–13:24) | LE WC (13:04–13:11) → KS Diskussion OpenClaw → IN div. Surfen (13:14) | **Edge OpenClaw (3x), Window logger (2x), Code.exe (2x)** | Geschirr abwaschen, Spaziergang-Entscheidung... | 🟢 VS Code erscheint zum ersten Mal = Andon FM Scraper. KS Diskussion OpenClaw = kurze Rückfrage. |
| **13:15–13:45** | Korrektur Andon FM (13:11–13:24, 13:26–13:33, 13:34–13:48), YouTube Rosin's (Pausen) | IN div. Surfen → IN YouTube → LE Bearb. Essensplan | **Code.exe (9–11x), Live365Scraper.exe (10x)** dominant | WC Arbeit (fix 12:00, 13:30) | 🟢 Live365Scraper.exe = Scraper läuft und testet! Code + Live365Scraper = Andon FM Arbeit. Logger sieht YouTube (Rosin's) zwischen Code-Sessions. |
| **13:45–14:00** | Andon FM endet (13:48), Surfen Molt.chess (13:49–13:51), Nacherfassung Ablauf (13:53–14:02) | KS Diskussion OpenClaw → KS Aufwandserfassung → KS Planung | Code (11x), Planner (8x), Explorer (8x) | Arbeitszeit Nachmittag | 🔴 KS Planung = Nacherfassung Ablauf (legitim, kein Phantom). |
| **14:00** | Nacherfassung endet (14:02), Blutdruck messen (14:02–14:05, off-PC), YouTube Rosin's (14:05–14:18) | LE Bearb. Essensdatenbank → GE Blutdruck messen → IN Ansehen YouTube | Planner (6x), Edge YouTube (4x), Planner edit (3x) | Arbeitszeit Nachmittag | 🟠 Teleworking. Blutdruck = off-PC (Planner only, Planner check-off kurz). |
| **14:15** | YouTube (14:05–14:18), Nacherfassung (14:18–14:19, 14:22–14:36), Surfen X (14:19–14:21) | IN div. Surfen → GE Bearbeitung BRZG (kurz) → KS Planung (14:22+) | **Planner (18x), Planner "Aufgabe erledigt" (8x), Planner edit (4x)** | Arbeitszeit Nachmittag | 🔴 18x Planner-Fokus = Nacherfassung-Cluster. "Aufgabe erledigt" = Planner-Overhead. |
| **14:30** | Nacherfassung (14:22–14:36), Bearb. Essensplan neuer Plan (14:36–14:47) | KS Planung → LE Bearb. Essensplan | **Planner (15x), MSACCESS (10x), Planner "Ungeplante Aktivität" (9x)** | Arbeitszeit Nachmittag | 🟠 Teleworking läuft. MSACCESS = Essensplan-DB. Planner-Overhead für Essensplan-Buchung. |
| **14:45** | Bearb. Essensplan endet (14:47), Wasser fassen (14:47–14:49, off-PC), Befragung Arena.AI RWPLPL (14:49–14:57) | KS Planung → LE WC/Jause → RW Bearb. Playlist → IN div. Surfen | **Explorer (16x), Winamp.exe (12x), Editor Unbenannt (10x)** | Arbeitszeit Nachmittag | 🟠 Winamp = Radio/Musik lief nebenbei. Editor = Arena.AI Antwort-Entwurf? |
| **15:00** | WC (14:57–15:03, off-PC), YouTube Rosin's (15:04–15:07), Surfen Andon FM (15:07–15:08), YouTube (15:08–15:10), Analyse Andon FM (15:10–15:13), YouTube (15:13–15:24) | IN YouTube → IN div. Surfen → GE Blutdruck messen (15:10–15:13) → IN YouTube | **Edge YouTube 2-adults (6x), Edge Excel Statistik (5x)** | Arbeitszeit Nachmittag | 🟠 Teleworking. Privater PC: YouTube + Statistik-Excel. Blutdruck 2× heute (auch 14:02–14:05). |
| **15:15** | YouTube (15:13–15:24), Analyse Andon FM (15:24–15:25, 15:28–15:29), YouTube (15:25–15:28), OpenAIR (15:29–15:30) | IN YouTube → RA Untersuchung Andon FM (Bursts) → IN div. Surfen | Edge YouTube/Rosin's (6x), Edge Andon FM (3x), Edge OpenAIR (3x) | Arbeitszeit Nachmittag | 🟠 Planner und windowmon gut konsistent: YouTube + Radio-URLs. |
| **15:30** | Nacherfassung (15:30–15:35), Anhören Backlink Broadcast (15:35–15:37), **Arbeitszeit Nachmittag BREPDZ (15:37–19:41)** | KS Planung (15:30–15:36) → IN div. Surfen (15:36–15:52) | **Planner (15x), Planner "Ungeplante Aktivität" (7x), Planner edit (4x)** | Arbeitszeit Nachmittag | 🔴 KS Planung = Nacherfassung Ablauf (legitim). |
| **15:45** | Arbeitszeit Nachmittag (Teleworking Firmen-Laptop) | IN div. Surfen | Edge WordCounter (3x), Edge Arena AI (3x) | Arbeitszeit Nachmittag | 🟠 Arena AI → Befragung RWPLPL Nachwirkung. |

### Teleworking-Nachmittag & KS Wartung (16:00–19:30)

| Block | Planner-Log | Alter Logger (korr.) | windowmon | Projection | Bemerkung |
|-------|-------------|----------------------|-----------|------------|-----------|
| **16:00–16:45** | Arbeitszeit Nachmittag (Firmen-Laptop) | IN div. Surfen (15:52–16:55) | Keine Einträge 16:00–16:15; Planner+Arena AI (1x je) in 16:30; WINWORD+Arena AI in 16:45 | Arbeitszeit Nachmittag | 🟠 Teleworking. Privater PC extrem spärlich. WINWORD 16:45 = Firmen-Doku? (Nur 1x Fokus = kurz geöffnet). |
| **17:00** | Arbeitszeit Nachmittag (Firmen-Laptop) | **KS Wartung Tagesplanung KSPLWA (17:03–19:05, ~2h!)** | Explorer (4x), Editor master_task_list_v4.html (1x) | Arbeitszeit Nachmittag (Projection-Ende: 18:13) | 🟠 KS Wartung Tagesplanung 17:03–19:05 auf privatem PC = Kurt pflegte sein Planungssystem parallel zur Teleworking-Arbeit. Kein Phantom, sondern legitime Nebentätigkeit auf privatem PC. |
| **17:15–18:30** | Arbeitszeit Nachmittag (Firmen-Laptop) | KS Wartung Tagesplanung KSPLWA (weiter) | Keine Einträge (17:15–18:15); Planner python (1x) in 17:30, 18:30 | Arbeitszeit Nachmittag (Projection-Ende 18:28!) | 🟠 🟡 Teleworking läuft 1h13min über Projection-Ende (18:28) hinaus bis 19:41. |
| **18:45–19:00** | Arbeitszeit Nachmittag (weiter) | KS Wartung KSPLWA endet 19:05 → LE Bearb. Essensplan (19:05–19:36 mit WC-Pause) | Keine Einträge 18:45; Editor Essensplan (3x) in 19:00 | Projection: Lüften 13:00 (fix, übersprungen), Wäsche, Anhören RW, Papa-Aufgaben... | 🟡 Alle Projection-Abend-Aktivitäten um diese Zeit stark verzögert. |
| **19:15** | Arbeitszeit Nachmittag (endet 19:41) | LE Bearb. Essensplan (weiter) | Keine Einträge | Laufen (Projection 18:42–19:16)! | 🟡 Laufen laut Projection bereits ab 18:42. Tatsächlich noch Teleworking bis 19:41. |
| **19:30** | Arbeitszeit endet 19:41 → Zeiten sammeln (19:41–19:48) → SAP (19:48–19:54) → Abschluss → Nacherfassung | **KS Planung (19:36–19:57)** | Planner (2x) in 19:30; **Planner (8x), Planner done (5x), Planner ungeplant (2x) in 19:45** | Zeiten sammeln, SAP-Eingabe | 🔴 KS Planung 19:36 = Nacherfassung post-Teleworking (legitim). windowmon bestätigt: Planner-Cluster nach TW-Ende. |

### Abend: Spaziergang, Mail, Abendzeremonie (19:45–23:30)

| Block | Planner-Log | Alter Logger (korr.) | windowmon | Projection | Bemerkung |
|-------|-------------|----------------------|-----------|------------|-----------|
| **19:45** | Nacherfassung endet, Entscheidung Spaziergang (19:56) → WC (19:57–20:03, off-PC), Begutachtung Ngrok (20:03–20:04), Anziehen (20:04–20:06, off-PC) | KS Planung → LE WC/Jause (19:57–20:03) → IN div. Surfen (20:03–20:04) | Planner (8x), Planner done (5x) in 19:45; Edge Andon FM + Planner + Window logger in 20:00 | Post-Arbeit: WC (fix 18:29), PC herunterfahren (18:38), Anziehen, Laufen (18:42) | 🟢 WC bestätigt in Logger + Planner. PC NICHT heruntergefahren. Laufen jetzt erst ~+1h24min verspätet. |
| **20:00** | **Laufen / E-Bike-Suche GEGYLS (20:06–20:48, komplett off-PC!)** | **GE Laufen / Scootersuche (20:04–20:51)** | **Keine Einträge in 20:15-Block!** | Laufen (18:42–19:16, 34 min) | 🟢 PERFEKTES 3-Quellen-Alignment für Off-PC! Planner = Laufen, Logger = GE Laufen, windowmon = leer. Dauer: 42 min (8 min länger als 34 min Projection). 3 E-Bikes gefunden (Notiz im Planner). |
| **20:15–20:30** | Laufen (off-PC) | GE Laufen (weiter) | Keine Einträge (20:15); Planner (1x), Window logger (1x) in 20:30 | Nachtmahl fassen (fix 20:00), diverse Abend-Aktivitäten | 🟢 Off-PC bestätigt. Laufen endete 20:48. |
| **20:45** | Laufen endet 20:48, Nachtmahl fassen (20:48–20:51, off-PC), **Mail Ewiger Speiseplan an Michael Kainz LEPLES (20:51–21:11)** | GE Laufen endet 20:51 → ?? Ewiger Speiseplan.txt → IN div. Surfen → **IN Bearbeitung Mails (20:54–21:11)** | **Edge Outlook (9x), Editor Ewiger Speiseplan.txt (6x), Explorer (5x)** | Teller waschen, Geldbörse, Kommunikation Judith... | 🟢 Sehr gute Konsistenz: Planner + Logger + windowmon alle zeigen Mail + Ewiger Speiseplan. Viele Projection-Items (Geldbörse, Judith, Ohrwürmer...) nicht erledigt. |
| **21:00** | Mail endet 21:11, Surfen Molt.chess (21:11–21:12), Lesen Ewiger Speiseplan (21:12–21:13), div. Surfen (21:13–21:14), Teller waschen (21:14–21:17, off-PC), Bearb. Essensplan LEEPKO (21:18–21:22) | IN Mails → IN div. Surfen → LE WC/Jause (21:14–21:17) → LE Bearb. Essensplan (21:17–21:22) | Edge Outlook (4x), Explorer (4x), Editor Ewiger Speiseplan (3x) | Champion's Mindset (21:09), Ohrwürmer Nachfassen (21:20) | 🔵 Teller waschen = off-PC. Projection-Items Champion's Mindset, Ohrwürmer = nicht erledigt. |
| **21:15** | Bearb. Essensplan, **Nacherfassung Ablauf (21:22–21:30)**, Bearb. Essensplan Start Korrekturlauf (21:30–21:31) | LE Bearb. Essensplan → KS Planung (21:22–) → KS Aufwandserfassung | **Planner (17x), Explorer (8x), MSACCESS (6x)** | Tagebuch (21:30–21:40), Papiersortierung (21:40–21:49) | 🔴 KS Planung = Nacherfassung Ablauf (legitim). MSACCESS = Essensplan-DB. |
| **21:30** | Versorgung Mitbringsel LEPOPO (21:31–21:35), Ausräumen Geschirrspüler (21:35–21:40, off-PC), Nacherfassung (21:40–21:44), **Anhören RW/Ohrwürmer/Korr. Andon FM (21:44–22:20)** | LE Versorgung Mitbringsel (21:32–21:38) → LE Bearb. Essensplan → KS Planung | **Planner (17x), Explorer (6x)** in 21:30; **Explorer (10x), Radio Würmchen.exe (7x), Code.exe (4x)** in 21:45 | Papiersortierung, Übersiedeln, Börsenkurse, Anhören RW (21:01–21:09) | 🟢 Radio Würmchen.exe + Code = Anhören + Andon FM Arbeit konsistent. Versorgung Mitbringsel = off-PC korrekt im Logger. 🟡 Papiersortierung, Übersiedeln, Börsenkurse = nicht erledigt. |
| **21:45** | Anhören RW/Andon FM weiter | RW Nacherfassung Radioscans → **RA Untersuchung Andon FM (21:51–22:20, intensiv)** | Explorer (10x), Radio Würmchen (7x), Code (4x) | Anhören RW, Börsenkurse, Kreuzungs-FGPA | 🟢 Andon FM Untersuchung: Planner + Logger + windowmon alle bestätigt. Börsenkurse/FGPA = nicht erledigt. |
| **22:00–22:15** | Anhören RW/Andon FM (bis 22:20) | RA Untersuchung Andon FM (intensiv), RW Nacherfassung Radioscans | **Editor "Andon FM Station logs.txt" (15x), Code.exe (11x)** in 22:00; **Radio Würmchen.exe (9x)** in 22:15 | Anhören RW (22:00–22:08), Börsenkurse (22:08–22:16), Vorbereitung Zähne (22:20 fix) | 🟢 Gute Konsistenz. windowmon: Radio Würmchen + Editor Andon FM logs = tatsächliche Arbeit sichtbar. |
| **22:15** | Anhören endet 22:20 → Vorbereitung Zähne (22:20–22:22, off-PC), Zähne putzen (22:22–22:32, off-PC), Bugfixing Andon FM (22:32–22:39) | RW Nacherfassung → **KS Planung (22:20–22:21, Phantom!)** → LE Abendzeremonie (22:21–22:27) → IN div. Surfen → RA Untersuchung Andon FM (22:28–22:37) | Radio Würmchen (9x) in 22:15; Explorer (7x), Code (6x), Live365Scraper (6x) in 22:30 | Vorbereitung Zähne (22:20 fix), Zähne putzen (22:25–22:37) | 🔴 KS Planung 22:20 = Phantom (Abhaken Anhören RW). Logger LE Abendzeremonie = korrekt. Live365Scraper = Andon FM weiter getestet. 🟢 Abendzeremonie fix 22:20 = Projection getroffen! |
| **22:30** | Bugfixing Andon FM (22:32–22:39), Zwischenraumzahnbürste (22:39–22:55, off-PC) | RA Untersuchung Andon FM → **?? Bearbeitung Unbenannt (22:37–23:07, 30 min!)** | Explorer (7x), Code (6x), Live365Scraper (6x) in 22:30; **Keine Einträge in 22:45!** | Zwischenraumzahnbürste (22:37–22:53) | 🟢 "Bearbeitung Unbenannt" im Logger = Abendzeremonie off-PC (unlabeled window). windowmon 22:45 leer = Badezimmer bestätigt! 3-Quellen-Alignment. |
| **22:45** | Zwischenraumzahnbürste (off-PC, weiter), Bugfixing Andon FM (22:55–23:00) | ?? Bearbeitung Unbenannt (weiter, off-PC) | Keine Einträge | Zahnseide (22:53–22:58), Reinigung (22:58–23:00) | 🟢 Durchgehend off-PC bestätigt durch leeres windowmon. |
| **23:00** | Bugfixing Andon FM (22:55–23:00), Zahnseide (23:00–23:03, off-PC), Reinigung (23:03–23:04, off-PC), Bett machen (23:05–23:06, off-PC), Ausziehen (23:06–23:08, off-PC), Bugfixing Andon FM (23:08–23:13), Nacherfassung Ablauf (23:13–23:19) | ?? Bearbeitung Unbenannt endet 23:07 → RA Untersuchung Andon FM (23:07–23:11) → IN div. Surfen (23:11–23:13) → **KS Planung (23:13–23:19)** | Code (7x), Planner (7x), Explorer (5x) | Bett machen (23:00–23:02), Ausziehen (23:02–23:06), Ohrwürmer Charts (23:06–23:08), Einschmieren, WC, im Bett (23:18) | 🟢 Bugfixing zwischen Badezimmer-Aktivitäten verwoben. Logger "Bearbeitung Unbenannt" = Abendzeremonie off-PC. KS Planung = Nacherfassung (legitim). |
| **23:15** | Nacherfassung endet 23:19, Bearb. Ohrwürmer Charts (23:19–23:21), Einschmieren (23:21–23:23, off-PC), WC (23:23–23:25, off-PC), Bearb. Ohrwürmer Liste (23:25), **im Bett (23:32)** | KS Planung → RW Bearb. Ohrwürmer → RA Untersuchung Andon FM (kurz) → LE Abendzeremonie → LE Bearb. Essensplan (23:26) → GE Dok BRZG (23:28, kurz) → KS Planung (23:32) → **andere Aktivität (23:33 = Schlaf!)** | **Explorer (30x), Planner (24x), Planner done (14x)** — Nacherfassung-Cluster! | **im Bett (23:18)** | 🟡 im Bett: Projection 23:18, Actual 23:32 (+14 min). PC NICHT heruntergefahren (Radio Würmchen). Planner-Cluster = letzte Nacherfassung. |
| **23:30** | (Schlaf) | andere Aktivität (23:33–) | Explorer (7x), Live365Scraper (3x), Planner (3x) | PC herunterfahren (23:17) | PC läuft weiter mit Live365Scraper (Radiosystem). |

---

## 2. Zusammenfassung der Abweichungen

### 2.1 Was sieht der Planner, das die Logger NICHT sehen? (Off-PC-Aktivitäten)

Der Planner ist die einzige Quelle für körperliche Off-PC-Tätigkeiten. Der alte Window Logger erfasst diese nur, wenn Kurt manuell das Logger-Fenster öffnet und die Aktivität auswählt ("idle"-Modus).

| Zeitraum | Planner-Aktivität | Logger-Signal | windowmon-Signal |
|----------|-------------------|---------------|-----------------|
| 06:03–06:19 | Rasieren (off-PC) | LE Morgent. (korrekt) | Nur Planner-App kurz |
| 08:07–08:28 | Feinschliff Rasur, Ausputzen, WC, Abwiegen, Reinigung | LE Morgent.+Frst. | Planner "Aufgabe erledigt" (Phantom) |
| 08:28–08:46 | **Duschen** | LE Morgent.+Frst. | **Fast leer (1–2 Einträge)** |
| 08:48–08:56 | Einschmieren, Anziehen, Bett machen | LE Morgent. | Planner done (Phantom) |
| 08:56–09:15 | **Frühstücken** | LE Morgent.+Frst. | Sehr spärlich (1–2 Einträge) |
| 09:28–09:29 | Einlass Sati Ersoy | (keine Logger-Lücke) | Keine Unterbrechung |
| 09:55–09:57 | Mund spülen, Häferl waschen | KA Papiersortierung folgt | Planner brief |
| 09:57–10:31 | **Papiersortierung KA-Unterlagen** | KA Papiersortierung | **Fast leer** |
| 14:02–14:05 | Blutdruck messen | GE Blutdruck messen | Planner kurz |
| 15:10–15:13 | Blutdruck messen (2x!) | GE Blutdruck messen | Edge YouTube umgeben |
| **20:06–20:48** | **Laufen / E-Bike-Suche** | **GE Laufen / Scootersuche** | **Komplett leer (20:15-Block)!** |
| 20:48–20:51 | Nachtmahl fassen | GE Laufen endet | Kein Signal |
| 21:14–21:17 | Teller waschen | LE WC/Jause | Kein Signal |
| 21:35–21:40 | Ausräumen Geschirrspüler | LE Bearb. Essensplan | Kein Signal |
| 22:20–23:25 | Abendzeremonie (10+ Einzelschritte) | LE Abendzer. + ?? Bearbeitung Unbenannt | 22:45 komplett leer |

**Schlussfolgerung:** Der alte Logger erfasst Off-PC-Aktivitäten korrekt als Makro-Kategorien (LE Morgent., GE Laufen), weil Kurt manuell auswählt. windowmon hat diese Lücken natur­gemäß, zeigt aber durch Leere (<2 Einträge/Block) zuverlässig Off-PC-Zeiten an.

---

### 2.2 Was sehen die Logger, das der Planner NICHT sieht?

| Zeitraum | Logger-Signal | windowmon-Signal | Bedeutung |
|----------|---------------|-----------------|-----------|
| Ganztags | RA Untersuchung Andon FM (39 min gesamt) | Edge Andon FM, Live365Scraper | Viele kurze Andon-FM-Checks zwischen Aktivitäten |
| 06:27 | ?? Bearbeitung Starte Report heute.bat | CMD kurz | Batch-Script-Start (nicht im Planner) |
| 11:46–13:04 | IN div. Surfen (Edge Browsing) | Edge diverse Tabs | Privater PC surft während Standup/Arbeit |
| 14:45 | Winamp.exe läuft | Winamp (12x) | Musik spielte im Hintergrund (nicht geloggt) |
| 13:15 | git-credential-manager.exe | 4x | Git-Authentifizierung während Code-Arbeit |
| 17:03–19:05 | **KS Wartung Tagesplanung (~2h)** | WINWORD, Explorer (sporadisch) | Planungssystem-Wartung auf privatem PC während Teleworking |
| 23:26–23:30 | LE Bearb. Essensplan, GE Bearbeitung Dok BRZG | Explorer, Live365Scraper | Letzte PC-Korrekturen vor Schlaf (im Planner nur "Nacherfassung") |
| Ganztags | Live365Scraper.exe läuft | 3–10x in mehreren Blöcken | Radioscraper läuft im Hintergrund (Systemtask) |

---

### 2.3 Wo erscheint "KS Planung" als Phantom (Planner-Bedienung, nicht echte KS-Arbeit)?

**Echter Phantom-KS** (Planner kurz im Vordergrund um Aktivität abzuhaken, während tatsächliche Tätigkeit off-PC weiterläuft):

| Zeitpunkt | Dauer | Ausgelöst durch | Tatsächliche Aktivität |
|-----------|-------|-----------------|----------------------|
| 06:03–06:05 | ~2 min | Abhaken LEMTAU/Aufstehen | Rasieren läuft weiter (off-PC) |
| 08:25–08:25 | <1 min | Abhaken WC/Abwiegen/etc. | Morgentoilette off-PC |
| 08:48–08:48 | ~1 min | Abhaken YouTube nach Dusche | Anziehen off-PC |
| 08:56–08:57 | ~1 min | Abhaken Vorbereitung Playlist | Frühstücken beginnt |
| 09:13–09:16 | 3 min | Abhaken Frühstück | Übergang zu Essensplan |
| 09:57 | <1 min | Abhaken Mund spülen/Häferl | Papiersortierung beginnt |
| 22:20–22:21 | ~1 min | Abhaken Anhören RW | Zähne putzen off-PC beginnt |

**Legitime KS-Arbeit** (fälschlicherweise als Phantom verdächtig, aber tatsächlich Planungsarbeit):

| Zeitraum | Dauer | Art |
|----------|-------|-----|
| 07:02–07:22 | 20 min | Nacherfassung Ablauf (aktive Schreibarbeit) |
| 09:44–09:50 | 6 min | Nacherfassung Ablauf |
| 10:44–10:51 | 7 min | Nacherfassung + Ablauf |
| 13:53–14:02 | 9 min | Nacherfassung Ablauf |
| 14:18–14:36 | 18 min | Nacherfassung Ablauf |
| 15:30–15:36 | 6 min | Nacherfassung Ablauf |
| 17:03–19:05 | ~122 min | **KS Wartung Tagesplanung KSPLWA** (private PC Nebentätigkeit während Teleworking) |
| 19:36–19:57 | 21 min | Post-Teleworking Nacherfassung + SAP-Eingabe |
| 21:22–21:43 | 21 min | Nacherfassung Ablauf |
| 23:13–23:19 | 6 min | Letzte Nacherfassung |

**KS-Gesamtzeit laut alter Logger: 122.5 min (KS Planung) + 122.2 min (KS Wartung) = 244.7 min (~4h)**  
Davon geschätzt echte Phantome: ~12 min (6–7 einzelne Abhak-Ereignisse).  
Der Rest ist echte KS-Arbeit (Nacherfassung, Planung, SAP).

---

### 2.4 Wo weicht die Projection am stärksten von der Realität ab?

| Kategorie | Projection | Realität | Abweichung |
|-----------|-----------|---------|------------|
| **Duschen** | 06:55–07:15 | 08:28–08:46 | **+1h33min** (größte Einzelabweichung) |
| **Morgenroutine abgeschlossen** | ~07:54 (Frühstück 07:29–07:54) | ~09:15 | +1h21min |
| **PC herunterfahren vor TW** | Ja (10:56–10:58) | Nicht geschehen | Radio Würmchen als Grund |
| **Teleworking-Ende** | ~18:28 | 19:41 | **+1h13min** Überstunden |
| **Laufen** | 18:42–19:16 (34 min) | 20:06–20:48 (42 min) | +1h24min Verspätung, +8 min länger |
| **Abendzeremonie** | Beginn 22:20 (fix) | Beginn 22:20 | **0 min Abweichung** ✓ |
| **im Bett** | 23:18 | 23:32 | +14 min |
| **Papiersortierung (Wohnzimmer)** | 07:54–08:09 | Übersprungen (Sati-abhängig, kommt erst dran wenn Sati am PC putzt) | — |
| **Review Dok BRZG** | 09:17–10:27 | 09:15–09:17 + 09:43–09:55 (nur ~8 min total) | Massiv kürzer |
| **Abend-Backlog** | Papa-Pflege, Geldbörse, Judith, Ohrwürmer, Tagebuch, Champion's Mindset, Papiersortierung hereingekommene, Übersiedeln, Börsenkurse | **Keines davon erledigt** | Teleworking-Überstunden fraßen den Abend |

---

## 3. Empfehlungen für AutoDetect-Regel-Übersetzung

### Regel 1: Duschen/Badezimmer-Block erkennen (HOHER WERT)
**Trigger:** windowmon < 3 Einträge in 15-min-Block + Zeitraum 07:00–09:30 + vorher LE Morgent. im alten Logger  
**→ AutoDetect:** `LEMTDU` (Duschen) oder allgemeiner `LE/Morgentoilette`  
**Begründung:** Duschen erzeugt das zuverlässigste Off-PC-Signal des ganzen Tages. 3-Quellen-Bestätigung.

### Regel 2: Phantom-KS von echtem Nacherfassen unterscheiden
**Trigger "Phantom":** "Aufgabe erledigt"-Fenster innerhalb 30 Sek. geöffnet und wieder geschlossen, dann sofort nicht-KS-Fenster  
**Trigger "Echte Nacherfassung":** Planner-Fenster dominant für > 5 min + mehrere "Eintrag bearbeiten" + "Ungeplante Aktivität erfassen" in Cluster  
**→ AutoDetect:** Phantom → ignorieren für KS-Zeiterfassung. Cluster → `KSPLNA` (Nacherfassung Ablauf)  
**Begründung:** 244 min KS gesamt, davon nur ~12 min echte Phantome. Wichtig für saubere KS-Zeiterfassung.

### Regel 3: Andon FM Scraper-Arbeit erkennen
**Trigger:** `Live365Scraper.exe` + `Code.exe` gleichzeitig aktiv, ODER Editor mit "Andon FM Station logs" im Titel  
**→ AutoDetect:** `RWAFAN` (Korrektur/Test Andon FM-Scraper)  
**Begründung:** Live365Scraper erscheint 3–4 mal täglich wenn Scraper-Arbeit läuft. windowmon sieht diesen Background-Prozess.

### Regel 4: Teleworking-Begleitnutzung privater PC
**Trigger:** BR Start Teleworking im Planner (oder alten Logger) → dann YouTube/Edge auf privatem PC → kein Planner-Cluster  
**→ AutoDetect:** Keine eigene KS-Zeit zuweisen. Stattdessen Anmerkung "TW-Begleitung" (privater PC nebenbei)  
**Begründung:** 10:59–19:41 waren 8h42min. Auf privatem PC sah es aus wie 4h YouTube + 2h Surfen + 2h KS Wartung. Die Hauptaktivität passierte unsichtbar.

### Regel 5: Laufen/Spaziergang Off-PC-Block
**Trigger:** windowmon leer für ≥ 30 min (2 Blöcke) nach 19:00 + kein Sleep-Event + vorher GE Laufen im alten Logger oder Planner GEGYLS  
**→ AutoDetect:** `GEGYLS` (Laufen)  
**Begründung:** 20:15 komplett leer in windowmon = eindeutigste Offline-Periode des Abends.

### Regel 6: Arena.AI Befragung
**Trigger:** Edge-Tab mit "Arena AI" im Titel (arena.aidotio, artificialanalysis.ai/arena) für > 3 min  
**→ AutoDetect:** `RWPLPL` (Befragung Arena.AI heutige RW-Playlist)  
**Begründung:** Arena AI taucht in 15:45-Block auf, passt zur Planner-Aktivität 14:49–14:57.

### Regel 7: Abendzeremonie Off-PC identifizieren
**Trigger:** windowmon leer 22:30–23:30 + kurze Code/Live365Scraper-Bursts (< 3 min) = Bugfixing-Unterbrechungen  
**→ AutoDetect:** `LEAZ...` (Abendzeremonie) für leere Blöcke, Code-Bursts als `RWAFAN` Bugfixing markieren  
**Begründung:** Abendzeremonie-Struktur ist täglich, Bugfixing war einmalig aber würde wiederholt als Code+leer erkennbar sein.

### Regel 8: Morgenroutine-Verzögerungswarnung
**Trigger:** 06:00–07:30 zeigt > 20 Planner-Einträge + RA/RW/IN aktiv + kein LE Morgent. Block > 10 min  
**→ AutoDetect:** Warnung "Morgenroutine verzögert - Projektion unrealistisch" + Schätze neue Dusch-Zeit  
**Begründung:** Heute: Dusche um +1h33 verschoben. Wenn morgens viel Radioscan/OpenClaw läuft → Badezimmer-Block nach hinten verschieben.

### Regel 9: Nacherfassungs-Cluster präzise erkennen
**Trigger:** Planner-App Fokus-Wechsel > 10× in 15 min + Mix aus "Tagesplanung", "Eintrag bearbeiten", "Ungeplante Aktivität erfassen"  
**→ AutoDetect:** `KSPLNA` (Nacherfassung Ablauf) — NICHT als `KSPLWA` (Wartung) klassifizieren  
**Begründung:** Nacherfassungs-Cluster haben deutlich höhere Frequenz (18x in 15 min) als normale Planungsarbeit.

### Regel 10: Radio Würmchen als Hintergrundindikator
**Trigger:** `Radio Würmchen.exe` als Prozess aktiv (läuft durchgehend, auch im Hintergrund)  
**→ AutoDetect:** Nicht als eigene Aktivität werten, aber als Kontextindikator: "PC-Abschaltung unmöglich" wenn Radio Würmchen läuft  
**Begründung:** PC wurde wegen Radio Würmchen mehrfach nicht heruntergefahren (10:56 Projection, 21:22 Projection, 23:17 Projection). AutoDetect könnte PC-Herunterfahren als "nicht ausgeführt" markieren wenn Radio Würmchen läuft.

---

## Anhang: Tages-Statistik

| Metrik | Wert |
|--------|------|
| Planungsbeginn (Planner) | 05:59 |
| im Bett | 23:32 |
| Tageslänge aktiv | ~17h33min |
| Teleworking-Dauer (Planner) | 10:51–19:41 = **8h50min** |
| Projection: Teleworking-Ende | ~18:28 = **1h13min Überstunden** |
| Laufen | 20:06–20:48 = 42 min (projected 34 min) |
| KS-Gesamtzeit (alter Logger) | ~245 min (~4h) davon ~12 min echte Phantome |
| Phantom-KS-Anteil | ~5% der KS-Zeit |
| Off-PC-Zeit (Duschen, Frühstück, Laufen, Abendzer.) | ca. 180 min (~3h) |
| Andon FM Scraper-Arbeit | ~39 min (Planner) + ~25 min (Logger RA) |
| Wichtigstes unerledigtes Projection-Item | Review Dok BRZG (nur ~8 min von 60 min Projection) |
| windowmon-Abdeckung (06:00–23:30) | Vollständig mit Lücken in Off-PC-Zeiten und Teleworking |
