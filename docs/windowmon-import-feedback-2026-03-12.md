# WindowMon Import — Feedback & Verbesserungsideen (2026-03-12)

## Probleme (Kurt's Feedback)

### 1. Task-Kürzel fehlt bei den meisten Vorschlägen
AutoDetect-Regeln vergeben synthetische Namen wie "Planer-Bedienung", "Diskussion OpenClaw".
Diese haben kein 6-stelliges Task-Kürzel. Nur Off-PC-Einträge mit Code im Fenstertitel
haben eins. → Fast jeder Eintrag muss editiert werden, um einen Task-Code zu bekommen.

**Idee:** AutoDetect-Regeln könnten direkt Task-Codes vergeben (statt nur Account + Name),
zumindest für häufig wiederkehrende Aktivitäten. Alternativ: CodeSuggestor automatisch
auf den AutoDetect-Namen anwenden und das Ergebnis gleich als Default setzen.

### 2. Kontenkürzel (2-stellig) nicht änderbar und nicht ins Log übernommen
Das Account-Kürzel aus AutoDetect wird angezeigt, lässt sich beim Editieren nicht ändern,
und fließt nicht ins Log ein. Wenn man den Task ändert, passt das Account-Kürzel nicht mehr.

**Idee:** Account-Kürzel aus dem 6-stelligen Task-Code ableiten (erste 2 Zeichen).
Wenn Task-Code gesetzt → Account automatisch aktualisieren. Account-Feld im Edit-Dialog
änderbar machen oder ganz weglassen (da redundant mit Task-Code).

### 3. Zusammengehörige Aktivitäten werden aufgesplittet
Fensterwechsel innerhalb derselben logischen Aktivität erzeugen separate Vorschläge.
Besonders störend: Moltbook-Checker-Script (alle 20 Min) verursacht kurzen Fensterwechsel,
der z.B. "Spazieren gehen" in zwei Teile zerreißt.

**Idee A:** Bekannte "Störer"-Prozesse (Moltbook-Checker, Scheduled Tasks) in AutoDetect
als "transparent" markieren — sie unterbrechen den vorherigen Block nicht.
**Idee B:** Zusammenfassung aufeinanderfolgender Blöcke mit gleichem Account/Aktivität
schon VOR der Anzeige (nicht erst als manueller Merge-Schritt).

### 4. Workflow-Vergleich mit Ablauf-Datei
Alter Workflow: Window Log + Ablauf-Datei nebeneinander → schneller Überblick.
Neuer Workflow: Einzelne Vorschläge durchklicken → langsamer.

**Idee:** Kompaktere Übersicht, die mehr dem "nebeneinander"-Gefühl entspricht.
Evtl. Split-View: links die windowmon-Einträge als Timeline, rechts die Vorschläge.

## Priorisierung
1. Task-Code aus CodeSuggestor automatisch in Vorschläge einsetzen (quick win)
2. Account aus Task-Code ableiten
3. Störer-Prozesse nicht als Aktivitätswechsel werten
4. Automatisches Pre-Merge gleicher aufeinanderfolgender Aktivitäten
5. UI-Redesign (Split-View) — langfristig
