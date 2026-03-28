# Learner Rule Design — Welche Fenstertitel taugen als Lernbasis?

Stand: 2026-03-28, basierend auf windowtitle_learner.py Analyse über 18 Tage (10.–27.3.2026)

## Kategorien von Fenstertiteln

### Kategorie 1: Direkte App-Fenster (HOCHSICHER)

Fenstertitel von Anwendungen, die eindeutig einer Aktivität zugeordnet werden können.

**Beispiele (aus Learner mit ≥80% Confidence):**
- `WINWORD.EXE: "Dokumentation Projekt Ohrwürmer*.doc"` → Dokumentation Ohrwurm-Projekt RWOWDO (98.8%, 154m)
- `EXCEL.EXE: "Aktienuntersuchung*.xls"` → Bearbeitung Börsenkurse FIAKBK (100%, 17x)
- `EXCEL.EXE: "Liste Fahrten mit E-Scootern.xls"` → Bearb. Liste Scooterfahrten FZSCLI (100%, 29m)
- `EXCEL.EXE: "Protokoll Geldbörse*.xls"` → Bearb. Geldbörse FIBGGB (87%, 32m)
- `EXCEL.EXE: "Blutdruckmesswerte.xls"` → Blutdruck messen GEBMBM (95%, 22m)
- `msedge.exe: "E-Mail – Kurt Woloch – Outlook*"` → Mailprüfung INMAPR (71–100%)
- `python.exe: "CMOL-FPGA Placer — MC14500B"` → Spielen Kreuzungs-FGPA CSEXKF (100%, 21x)
- `WINWORD.EXE: "Überlegungen zu Erbschaft*.doc"` → Judith/Vorsorgevollmacht PAWFAF (99%, 46m)
- `Acrobat.exe: "VTG_*.pdf"` → kontextabhängig, aber meist Friedhof/Rechnungen

**Regel-Generierung:** Substring-Match auf Dateiname/Titel → Aktivität. Hohe Confidence, sofort nutzbar.

### Kategorie 2: Planner Off-PC-Fenster (SICHER)

Fenstertitel mit dem Muster `"Tagesplanung — Off-PC — [Aktivität]"`

**Bedeutung:** Der User hat die Aktivität im Planner gestartet und ist dann vom PC weggegangen, um sie tatsächlich auszuführen. Die Aktivität im Titel ist in der Regel korrekt.

**Regel:** `"Tagesplanung — Off-PC — X"` → X mit hoher Confidence

**Ausnahmen/Einschränkungen:**
- Wenn Issue #22 (inkonsistente Off-PC-Erkennung) behoben ist, werden auch Pop-Up-Fenster "Off-PC" signalisieren → dann gilt dasselbe für `"Aufgabe erledigt — Off-PC — X"`
- Solange #22 offen ist: Nur Hauptfenster-Off-PC ist zuverlässig

### Kategorie 3: Planner Reaktiver-Planer-Fenster (UNZUVERLÄSSIG)

Fenstertitel mit dem Muster `"Tagesplanung — Reaktiver Planer — [Aktivität]"`

**Problem:** Zeigt die laut Priorität nächste geplante Aktivität, NICHT was der User tatsächlich macht. Der Learner zeigt, dass diese Titel fast immer ambig sind (Top-Confidence < 80%).

**Typisches Bild:**
- `"Tagesplanung — Reaktiver Planer — Geschirr abwaschen LEMEGA"` → 22% Essensplan, 22% Nacherfassung, 14% Kalender, 8% Mail, 6% Blutdruck...
- `"Tagesplanung — Reaktiver Planer — Bearbeitung Börsenkurse FIAKBK"` → 42% Nacherfassung, 15% YouTube, 15% WC, 10% Börsenkurse...

**Regel:** NICHT als direkte Lernbasis verwenden. Diese Titel sagen mehr über den Planungszustand aus als über die tatsächliche Aktivität.

**Mögliche Nutzung:** Als schwacher Hint in Kombination mit dem tatsächlich aktiven App-Fenster (→ Arbeitskontext-Erkennung, Issue #7).

### Kategorie 4: Planner Pop-Up-Fenster (VORSICHT)

Fenstertitel wie:
- `"Aufgabe erledigt — [Aktivität]"`
- `"Vorgezogene Aktivität erfassen — [Aktivität]"`
- `"Ungeplante Aktivität erfassen"`
- `"Eintrag bearbeiten — [Aktivität]"`
- `"Block reklassifizieren"`
- `"Import bestätigen"` / `"Import abgeschlossen"`
- `"Vorschlag bearbeiten"`
- `"Nacherfassung aus windowmon — [Datum]"`
- `"Timeline Nacherfassung — [Datum]"`

**Problem:** Diese Fenster sind kurzfristige Planner-Bedienungsmomente. Sie repräsentieren die Tätigkeit "Planner bedienen" (Nacherfassung/Erfassung), NICHT die im Titel genannte Aktivität.

**Regel:** Alle diese Titel sollten als **"Planner-Bedienung"** klassifiziert werden, nicht als die genannte Aktivität.

**Differenzierung:**
- `"Vorschlag bearbeiten"` → 83% Nacherfassung (116m) — das ist korrekt, weil Vorschläge bearbeiten = Nacherfassung
- `"Timeline Nacherfassung — *"` → ambig (45% Redesign, 39% Nacherfassung am 27.3.) — wird stabiler über mehr Tage
- `"Eintrag bearbeiten — [X]"` → meistens Nacherfassung, NICHT die Aktivität X

**Achtung:** Erst wenn Issue #22 gefixt ist und Pop-Ups bei tatsächlichem Off-PC auch "Off-PC" im Titel tragen, kann `"Aufgabe erledigt — Off-PC — X"` als Kategorie 2 behandelt werden.

### Kategorie 5: Teleworking-Artefakte (AUSFILTERN)

Wenn die geloggte Aktivität BRZ-Codes enthält (BREPDZ, BRTWGF, BREPGM, BREPWC, BREPZE, BRFAFA, BRFAHF, BRZG), ist der private PC-Fenstertitel bedeutungslos — der User arbeitet am Firmenlaptop.

**Regel:** Diese Zuordnungen aus der Lernbasis ausschließen (bereits im Learner implementiert).

### Kategorie 6: Generische/wechselnde Browser-Titel (KONTEXTABHÄNGIG)

Fenstertitel wie `"OpenClaw Control und X weitere Seiten"` oder `"YouTube und X weitere Seiten"` wechseln je nach Anzahl offener Tabs und der gerade aktiven Seite.

**Problem:** Derselbe Tab-Count-Titel kann bei verschiedenen Aktivitäten auftreten. Die Confidence ist stark von der Periode abhängig.

**Regel:** Nur als Lernbasis verwenden, wenn Confidence über einen längeren Zeitraum stabil hoch bleibt (>80% über >7 Tage).

## Substring-Regeln (generalisiert aus Learner-Daten)

Aus den Einzelergebnissen lassen sich generalisierte Regeln ableiten:

| Substring im Titel | App | → Aktivität | Confidence |
|---|---|---|---|
| `Aktienuntersuchung` | EXCEL.EXE | Bearbeitung Börsenkurse FIAKBK | ~100% |
| `Liste Fahrten mit E-Scootern` | EXCEL.EXE | Bearb. Liste Scooterfahrten FZSCLI | ~100% |
| `Protokoll Geldbörse` | EXCEL.EXE | Bearb. Geldbörse FIBGGB | ~87% |
| `Blutdruckmesswerte` | EXCEL.EXE | Blutdruck messen GEBMBM | ~95% |
| `Dokumentation Projekt Ohrwürmer` | WINWORD.EXE | Dokumentation Ohrwurm-Projekt RWOWDO | ~99% |
| `Überlegungen zu Erbschaft` | WINWORD.EXE | Vorsorgevollmacht PAWFAF | ~99% |
| `CMOL-FPGA Placer` | python.exe | Spielen Kreuzungs-FGPA CSEXKF | ~100% |
| `E-Mail – Kurt Woloch – Outlook` | msedge.exe | Mailprüfung INMAPR | ~71-100% |
| `Google Maps` + Routentitel | msedge.exe | Bearb. Liste Scooterfahrten FZSCLI | ~90% |
| `eBanking \| BAWAG` | msedge.exe | kontextabhängig (Überweisung) | ~90% |
| `Nacherfassung aus windowmon` | python.exe | Nacherfassung Ablauf KSPLNA | ~87-97% |
| `Vorschlag bearbeiten` | python.exe | Nacherfassung Ablauf KSPLNA | ~83% |

## Nächste Schritte

1. Hochkonfidente App-Fenster-Regeln (Kategorie 1) als erste automatische Regeln implementieren
2. Off-PC-Titel (Kategorie 2) als Regeln nutzen
3. Issue #22 fixen → Pop-Up-Off-PC ermöglichen → Kategorie 4 teilweise zu Kategorie 2 upgraden
4. Arbeitskontext-Erkennung (Issue #7) für ambige Browser-Titel entwickeln
5. Feedback-Loop (Issue #21) auf Basis dieser Kategorisierung implementieren
