# Per-Title Confidence Thresholds für ambige Fenstertitel

**Datum:** 2026-04-03
**Quelle:** Analyse windowmon-2026-04-02 + autodetect-corrections-2026-04-02 + Planner-Log
**Status:** Spezifikation, noch nicht implementiert

## Problem

Der AutoDetect verwendet einen globalen Konfidenz-Schwellenwert (aktuell 50%), unter dem ein Fenstertitel nicht als eigenständiger Block erkannt wird. Einige häufig vorkommende Fenstertitel haben aber eine so breite Verwendung, dass ihre höchste Konfidenz strukturell unter 50% liegt — z.B. "Microsoft Access" (18%), "OpenClaw Control" (65%, aber auf das falsche Thema). Das führt dazu, dass reale Aktivitätswechsel nicht erkannt werden und große zusammenhängende Blöcke entstehen, die manuell getrennt werden müssen.

Am 2.4.2026 waren 29 manuelle Korrekturen nötig; geschätzt 60-70% davon hätten durch niedrigere Schwellenwerte für bestimmte Titel vermieden werden können.

## Ansatz

Für bestimmte, empirisch identifizierte Fenstertitel wird eine **individuelle Mindestkonfidenz** festgelegt, die niedriger als der globale Schwellenwert sein darf. Wenn die höchste Konfidenz im Store für diesen Titel über der individuellen Schwelle liegt, wird diese Zuordnung verwendet — **auch wenn sie eventuell falsch ist**. Der Benutzer benennt dann einen Block um, und die bestehende Propagation in der Timeline korrigiert alle gleichartigen Blöcke automatisch.

### Designentscheidungen

1. **Keine generischen Kategorien einführen.** Stattdessen wird immer die höchste Konfidenz aus dem Confidence Store genommen. Das stellt sicher, dass jeder Block ein Task-Kürzel hat und abrechnungsfähig ist.

2. **Propagation existiert bereits.** Die Timeline führt beim Reklassifizieren bereits automatische Propagation durch — wenn ein Block umbenannt wird, werden gleichartige Blöcke mitgeändert. Kein weiterer Feature-Bedarf.

3. **Planer-Titel Sonderbehandlung.** Fenstertitel, die mit "Tagesplanung — Reaktiver Planer" beginnen (aber NICHT "Off-PC" enthalten), werden als Planer-Arbeit klassifiziert (Nacherfassung Ablauf KSPLNA oder äquivalent). Enthält der Titel "Off-PC", wird die im Titel genannte Aktivität als tatsächlich durchgeführte Aktivität zugewiesen.

## Ausnahmetabelle

| Fenstertitel (Pattern) | Prozess | Aktuelle höchste Konfidenz | Empfohlene Schwelle | Begründung |
|---|---|---|---|---|
| `"Microsoft Access"` (ohne spezifischen Tabellennamen) | MSACCESS.EXE | 18,0% | **10%** | Zu >80% Essensplan, aber breite Streuung auf >20 Aktivitäten. Unterkategorie des Essensplans ist für Abrechnung irrelevant. |
| `"OpenClaw Control"` | msedge.exe | 65,4% (auf KSPLAW) | **40%** | Höchste Konfidenz zeigt auf historisch häufigstes Thema. Bei neuem Thema ist die Zuordnung falsch, aber einmalige Umbenennung + Propagation korrigiert den Rest. |
| `"Andon FM \| Andon Labs"` | msedge.exe | 27,8% (auf RAAFSU) | **20%** | Immer Andon-FM-Kontext. Ob "Surfen" oder "Analyse" ist kontextabhängig, aber die Store-Zuordnung ist akzeptabel als Startpunkt. |
| `"*Essensplan*.txt - Editor"` | notepad.exe | 25,7% | **15%** | Eindeutig Essensplan-Arbeit. Unterkategorie (Protokoll, gegessen, Kontrolle) wird über Store-Konfidenz approximiert. |
| `"~VersuchEssensplan*.txt"` | notepad.exe | — | **Pattern-Match → Essensplan** | Automatisch generierte Testauswertungen des Essensplans. Kommen immer zusammen mit Access + Rechner vor. 100% Essensplan. |
| `"Tagesplanung — Reaktiver Planer"` (ohne "Off-PC") | python.exe | 43,5% (auf KSPLNA) | **35%** | Planer-Bedienung = Planer-Arbeit. Die aktuelle KSPLNA-Zuordnung ist korrekt für den Normalfall. |
| `"Tagesplanung — Off-PC — [Aktivität]"` | python.exe | variabel | **Standard (50%)** | Sonderbehandlung: Die genannte Aktivität im Titel ist die tatsächlich durchgeführte. Suffix-basierte Extraktion statt Store-Lookup. |

## Implementierung

### Option A: Konfigurationsdatei (empfohlen)

Eine separate JSON-Datei `data/confidence_thresholds.json`:

```json
{
  "overrides": [
    {
      "pattern": "MSACCESS.EXE||Microsoft Access",
      "match_type": "prefix",
      "min_confidence": 0.10,
      "note": "Essensplan-Arbeit, Unterkategorie irrelevant"
    },
    {
      "pattern": "msedge.exe||OpenClaw Control",
      "match_type": "exact",
      "min_confidence": 0.40,
      "note": "Thema wechselt, aber Propagation korrigiert"
    },
    {
      "pattern": "msedge.exe||Andon FM | Andon Labs",
      "match_type": "exact",
      "min_confidence": 0.20,
      "note": "Immer Andon-FM-Kontext"
    },
    {
      "pattern": "notepad.exe||*Essensplan*",
      "match_type": "glob",
      "min_confidence": 0.15,
      "note": "Essensplan-Editor"
    },
    {
      "pattern": "notepad.exe||~VersuchEssensplan*",
      "match_type": "glob",
      "min_confidence": 0.0,
      "force_activity": "Bearb. Essensplan LEEPEP",
      "note": "Auto-generierte Testauswertungen, immer Essensplan"
    },
    {
      "pattern": "python.exe||Tagesplanung — Reaktiver Planer",
      "match_type": "prefix",
      "min_confidence": 0.35,
      "exclude_substring": "Off-PC",
      "note": "Planer-Bedienung = Planer-Arbeit"
    }
  ]
}
```

### Option B: Hardcodiert in AutoDetect

Fallback, falls die Konfigurationsdatei zu aufwändig ist. Die Regeln werden direkt in `autodetect.py` als Dictionary implementiert.

## Beziehung zu bestehenden Issues

- **#21 (Überwachtes Lernen aus Korrekturdaten):** Komplementär. #21 verbessert die Store-Konfidenzen über Zeit; dieses Feature senkt die Schwelle, ab der niedrige Konfidenzen akzeptiert werden.
- **#24 (Session-Level Confidence Learning):** Komplementär. #24 lernt innerhalb einer Session; dieses Feature wirkt ab dem ersten Block.
- **#15 (Störer-Prozesse als transparent):** Tangential. Störer werden komplett ignoriert; dieses Feature behandelt ambige aber *relevante* Titel.
- **#10 (Regel-Editor):** Die Schwellen-Overrides könnten langfristig über den Regel-Editor verwaltet werden.

## Erwarteter Effekt

Basierend auf der Analyse vom 2.4.2026:
- **~20 von 29 Korrekturen** hätten vermieden oder auf eine einzige Umbenennung + Propagation reduziert werden können
- Größte Einzelhebel: "OpenClaw Control" (~12 Korrekturen) und "Microsoft Access" (~8 Korrekturen)
- Nacherfassungszeit-Reduktion geschätzt: 30-40 Minuten an Tagen mit vielen Kontext-Wechseln
