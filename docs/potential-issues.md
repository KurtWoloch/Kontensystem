# Potenzielle Issues für das Kontensystem

Diese Liste enthält extrahierte Bugs, Feature-Requests und Verbesserungen aus der Dokumentation, die noch nicht als GitHub-Issue existieren.

## Nacherfassung / WindowMon-Import (Logik & GUI)

- Typ: enhancement
- Titel: Synthetische autodetect-corrections bei Zeitraum-Ausdehnung
- Beschreibung: Wenn ein Segment in der Nacherfassung zeitlich ausgedehnt wird und dabei andere Segmente überdeckt, sollen für die überdeckten Segmente automatisch synthetische Corrections generiert werden. Das verhindert den Verlust der Lernbasis für die AutoDetect-Erkennung.
- Anmerkung: Aufgrund der Timeline-Praxis wäre es vielleicht angebracht, dies nach Länge der überdeckten Segmente zu gewichten... wenn sie innerhalb der selben Minute beginnen und enden, kann die synthetische Correction relativ irrelevant sein, weil ich den Block nur zu dem Zweck absorbiere, um zu verhindern dass er als Aktivität mit 0 Minuten Dauer importiert wird; falls solche Importe aber ohnehin unterbunden werden sollen, könnte ich mir das händische "Merging" in diesem Fall sparen, aber im Moment ist es so.
- Quelle: nacherfassung-improvements.md (V1)
- Priorität-Einschätzung: mittel

- Typ: enhancement
- Titel: Priorisierte Vorschläge beim Eintippen im Log-Dialog
- Beschreibung: Vorschläge für Aktivitäten sollen intelligenter sortiert werden: 1. Heute geplante Aktivitäten, 2. Bereits heute geloggte, 3. Kürzlich verwendete, 4. Historische. Dadurch werden häufig genutzte Task-Codes vor veralteten bevorzugt.
- Quelle: nacherfassung-improvements.md (V2)
- Anmerkung: Die Erkennung wurde in letzter Zeit schon verbessert, mir fallen nicht mehr so viele Fehlvorschläge auf.
- Priorität-Einschätzung: niedrig

- Typ: enhancement
- Titel: Arbeitskontext-Erkennung (Geplante Aktivität als Default)
- Beschreibung: Fensterwechsel, die zum Arbeitskontext der geplanten Aufgabe passen (z.B. Wechsel zwischen Notepad und bestimmten Webseiten), sollen automatisch zu einem Block zusammengefasst werden. Nur echte Abweichungen vom Kontext erzeugen neue Blöcke.
- Quelle: nacherfassung-improvements.md (V3a)
- Anmerkung: Dies könnte auch im Kontext des geplanten Redesigns der Windowlog-Correction betrachtet werden, wo die verschiedenen Erkennungsregeln unterschiedliche Prioritäten bekommen.
- Priorität-Einschätzung: hoch

- Typ: enhancement
- Titel: Statistische Fenster-Aktivitäts-Profile (Exklusivitätsanalyse)
- Beschreibung: Aus historischen Logs soll automatisch ein Exklusivitäts-Score für Fenstertitel berechnet werden. Fenster, die fast exklusiv bei einer bestimmten Aktivität auftreten, helfen dabei, den Arbeitskontext automatisch zu erkennen oder neue Kontexte vorzuschlagen.
- Quelle: nacherfassung-improvements.md (V3b)
- Anmerkung: Dies könnte auch im Kontext des geplanten Redesigns der Windowlog-Correction betrachtet werden, um die Confidence der daraus resultierenden Regel festzulegen
- Priorität-Einschätzung: mittel

- Typ: enhancement
- Titel: Checkbox "Änderungen auf gleiche Fenstertitel im Intervall anwenden"
- Beschreibung: In der neuen Timeline-Ansicht soll es möglich sein, bei einer manuellen Reklassifizierung (z.B. PDF-Name zu bestimmtem Task) diese Änderung per Checkbox automatisch auf alle gleichen Fenstertitel im aktuellen Zeitintervall anzuwenden.
- Quelle: nacherfassung-v2-design.md
- Anmerkung: Dieses Feature wurde bereits realisiert, nur die automatische Speicherung und Anwendung auf erneute Aufrufe der Timeline funktioniert noch nicht (wenn die Checkbox gewählt ist).
- Priorität-Einschätzung: mittel

- Typ: enhancement
- Titel: Regel-Editor für Klassifizierungsregeln
- Beschreibung: Eine GUI zur Verwaltung der WindowMon-Klassifizierungsregeln, inklusive Unterstützung für Substring-Matches, Confidence-Level (0-100) und Gültigkeitsdauer (permanent vs. temporär).
- Quelle: nacherfassung-v2-design.md
- Priorität-Einschätzung: mittel

- Typ: bug
- Titel: "AutoDetect wiederherstellen" bei falscher Korrektur / Korrektur-Scope
- Beschreibung: Wenn eine AutoDetect-Korrektur vorgenommen wird, überschreibt sie manchmal fälschlicherweise das Label für alle nachfolgenden Segmente, statt nur für die spezifischen Fenster. Es braucht einen Button, um das Original-AutoDetect wiederherzustellen und eine Begrenzung des Korrektur-Scopes.
- Quelle: nacherfassung-improvements.md (V7)
- Priorität-Einschätzung: mittel

- Typ: improvement
- Titel: Refactoring windowmon_import.py Grundlogik
- Beschreibung: Die aktuelle _consolidate_blocks Logik ist mit 6 Passes zu komplex geworden. Ein Refactoring soll die Lücken-Logik vereinfachen, indem nur auf das letzte Event vor und das erste nach der Lücke an Minutengrenzen geschaut wird.
- Quelle: nacherfassung-improvements.md (Architektur-Warnung)
- Priorität-Einschätzung: mittel

- Typ: enhancement
- Titel: Task-Kürzel bei Vorschlägen automatisch aus CodeSuggestor einsetzen
- Beschreibung: Wenn AutoDetect einen Namen ohne 6-stelliges Task-Kürzel vorschlägt (z.B. "Planer-Bedienung"), soll der CodeSuggestor automatisch angewendet werden, um ein Default-Kürzel zu setzen, damit nicht jedes Segment manuell editiert werden muss.
- Quelle: windowmon-import-feedback-2026-03-12.md
- Anmerkung: Hier wurde mittlerweile schon einiges verbessert und die meisten Vorschläge mit Task-Codes ausgestattet, die generische Aktivität "Planer-Bedienung" scheint nicht mehr aufzutreten, aber es kommt in der Timeline immer noch zu starken Fragmentierungen, in der sich ständig Blöcke "Erfassung Aufwand" und "Nacherfassung Aufwand" abwechseln.
- Priorität-Einschätzung: hoch

- Typ: enhancement
- Titel: Account-Kürzel aus Task-Code ableiten und änderbar machen
- Beschreibung: Das 2-stellige Account-Kürzel soll im Edit-Dialog änderbar sein bzw. sich automatisch aus den ersten zwei Zeichen des 6-stelligen Task-Codes ableiten und korrekt ins Log übernommen werden.
- Quelle: windowmon-import-feedback-2026-03-12.md
- Priorität-Einschätzung: mittel

- Typ: enhancement
- Titel: Störer-Prozesse als transparent markieren
- Beschreibung: Bekannte, periodische Hintergrundprozesse (wie der Moltbook-Checker, der kurz den Fokus stiehlt) sollen in den AutoDetect-Regeln als "transparent" markiert werden, sodass sie vorherige Aktivitätsblöcke nicht zerschneiden.
- Quelle: windowmon-import-feedback-2026-03-12.md
- Priorität-Einschätzung: mittel

## Planer-Bedienung & GUI

- Typ: enhancement
- Titel: Beliebige Aktivität aus "Geplant" direkt loggen
- Beschreibung: Ein Doppelklick auf einen beliebigen Eintrag in der "Geplant"-Liste soll direkt den Log-Dialog öffnen. Die Aktivität wird ins Log geschrieben und später in der Queue automatisch stillschweigend übersprungen. Dies löst die "Angstblockade" bei Desynchronisation.
- Quelle: nacherfassung-improvements.md (V8)
- Anmerkung: Dies wurde im Großen und Ganzen schon implementiert. Nur im Zusammenhang mit der Timeline ergibt sich noch das Problem, dass aus der Timeline importierte Aktivitäten, die sich mit der Planung decken, danach im Plan immer noch aufscheinen.
- Priorität-Einschätzung: niedrig

- Typ: enhancement
- Titel: Bereinigte Projektion als alternative Ansicht ("Restplan")
- Beschreibung: Eine neue Ansicht (Toggle/Tab), die den Tag in der ursprünglichen chronologischen Reihenfolge (Tagesprojektion) zeigt, aber bereits erledigte/übersprungene Aktivitäten ausblendet. Dient der Orientierung, wenn der Planer desynchronisiert ist.
- Quelle: nacherfassung-improvements.md (V9)
- Anmerkung: wurde bereits implementiert
- Priorität-Einschätzung: niedrig

- Typ: enhancement
- Titel: "Bis hierher erledigt" — Bulk-Complete
- Beschreibung: In der "Restplan"-Ansicht soll man eine Aktivität auswählen und alle vorherigen Aktivitäten bis zu diesem Punkt auf einmal als erledigt markieren können (mit den vorläufig geplanten Zeiten). Synchronisiert den Planer in Sekunden.
- Quelle: nacherfassung-improvements.md (V10)
- Anmerkung: wurde bereits implementiert, wird aber im Moment kaum benutzt... vielleicht an Bürotagen wieder stärker (hauptsächlich nützlich, wenn eine Serie von Off-PC-Aktivitäten geplant ist und danach geschlossen als erledigt abgehakt werden soll)
- Priorität-Einschätzung: niedrig

- Typ: enhancement
- Titel: Reihenfolge-Flexibilität der Queue erhöhen
- Beschreibung: Es sollen Mechanismen geschaffen werden, um Aktivitäten "out-of-order" nachzuerfassen, ohne dass die sequentielle Logik der Planer-Queue blockiert oder Verdopplungen entstehen.
- Quelle: nacherfassung-improvements.md (V4)
- Anmerkung: Mit dem Doppelklick und Loggen beliebiger Aktivitäten wurde hier schon viel Flexibilität eingeführt, Verdopplungen entstehen manchmal noch, aber die Gründe dafür sollten erst einmal erfasst werden.
- Priorität-Einschätzung: mittel

- Typ: enhancement
- Titel: Originale Projektion als alternative Sortierordnung
- Beschreibung: Ein Toggle-Button, der die Geplant-Liste nach der ursprünglichen Tagesanfangs-Projektion sortiert (mit den ursprünglich geplanten Zeiten) anstatt nach der dynamischen Queue.
- Quelle: nacherfassung-improvements.md (V5)
- Anmerkung: wurde bereits implementiert
- Priorität-Einschätzung: niedrig

- Typ: enhancement
- Titel: Log-Einträge in GUI bearbeiten, löschen und duplizieren
- Beschreibung: Einmal geloggte Einträge im Planner sollen per Schnelllöschung (Entf/Backspace) entfernbar sein und per Doppelklick in einem Formular geändert oder dupliziert werden können (z.B. für wiederkehrende Aktivitäten).
- Quelle: feature-log-editing.md
- Anmerkung: wurde bereits implementiert
- Priorität-Einschätzung: niedrig

## Reports & Background-Tracking

- Typ: enhancement
- Titel: Verbesserung des Tagesberichts (Nacherfasst vs. geplant)
- Beschreibung: Der Tagesbericht soll eine neue Kategorie "Nacherfasst (nicht im Plan)" für windowmon_import-Aktivitäten erhalten. Zusätzlich soll eine Überzeit-Analyse pro Aktivitätskategorie (geplante vs. tatsächliche Zeit) eingebaut werden.
- Anmerkung: hier gäbe es noch viel Potential für Verbesserungen, da ich eigentlich für mich wirklich wichtigen Informationen nur durch LLM-gestützte Analyse jedes Tages durch OpenClaw bekommen kann. Hier wären weitere auszuwertende Punkte noch zu erfassen.
- Quelle: nacherfassung-improvements.md (V6)
- Priorität-Einschätzung: hoch

- Typ: enhancement
- Titel: Integrierter Window Monitor: Halb-automatisches Loggen
- Beschreibung: Der Planner soll bei erkannten Aktivitätswechseln (basierend auf Fenstertiteln und geplantem Task) automatisch vorschlagen: "Wechsel zu [neue Aktivität]?". Ein Klick loggt den Wechsel mit korrekter Startzeit.
- Quelle: feature-window-monitor.md (Phase 3)
- Anmerkung: Bin nicht sicher, ob das so einen Sinn ergibt und wie mein Workflow dazu aussehen würde, aber es könnte eventuell einen Sinn machen... nur was passiert, wenn es zu mehreren Wechseln kommt, bis ich wieder zum Planer zurückkomme?
- Priorität-Einschätzung: mittel

- Typ: enhancement
- Titel: Integrierter Window Monitor: Offline-Lücken-Nachfrage
- Beschreibung: Wenn längere Zeit keine PC-Aktivität erkannt wurde, fragt das Tool beim nächsten Fensterwechsel automatisch: "Was hast du seit [letzte Aktivität] gemacht?" und bietet Vorschläge basierend auf Tageszeit und Planung.
- Quelle: feature-window-monitor.md (Phase 5)
- Anmerkung: Das ist eine gute Idee, es müsste aber zuerst präzisiert werden, wie die Vorschläge genau gemacht werden... dies erscheint so, wie es geschrieben wurde, noch etwas nebulös.
- Priorität-Einschätzung: mittel
