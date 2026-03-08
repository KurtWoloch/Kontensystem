#!/usr/bin/env python3
"""
json2table.py — Universeller JSON-zu-Tabelle-Konvertierer

Konvertiert JSON-Arrays oder JSONL-Dateien (die im Prinzip Datentabellen
darstellen) in CSV oder HTML.

Verwendung:
    py tools/json2table.py <eingabe.json> [optionen]

Optionen:
    -f, --format csv|html   Ausgabeformat (Standard: html)
    -o, --output <datei>    Ausgabedatei (Standard: Eingabename mit neuer Endung)
    -c, --columns <spalten> Kommagetrennte Spaltenliste (Standard: alle)
    -s, --sort <spalte>     Nach dieser Spalte sortieren
    -r, --reverse           Absteigende Sortierung
    --open                  Ausgabedatei nach Erstellung im Browser/Editor oeffnen
    --no-open               Nicht oeffnen (Standard)

Beispiele:
    py tools/json2table.py logs/planner-log-2026-03-07.json
    py tools/json2table.py logs/planner-log-2026-03-07.json -f csv
    py tools/json2table.py logs/planner-log-2026-03-07.json -c activity,started_at,completed_at,skipped,comment --open
    py tools/json2table.py logs/projection-2026-03-07.json -s est_start --open
"""

import json
import csv
import os
import sys
import html
import argparse
import subprocess
from pathlib import Path


def load_json(path: str) -> list:
    """Laedt JSON-Array oder JSONL-Datei."""
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()

    # Versuch 1: JSON-Array
    if content.startswith("["):
        data = json.loads(content)
        if isinstance(data, list):
            return data

    # Versuch 2: JSONL (eine JSON-Zeile pro Zeile)
    records = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def get_columns(data: list, requested: list = None) -> list:
    """Ermittelt die Spalten (alle oder nur angeforderte, in stabiler Reihenfolge)."""
    if requested:
        return requested

    # Alle Keys in der Reihenfolge ihres ersten Auftretens
    seen = {}
    for row in data:
        if isinstance(row, dict):
            for key in row:
                if key not in seen:
                    seen[key] = True
    return list(seen.keys())


def format_value(val) -> str:
    """Formatiert einen Wert fuer die Anzeige."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "ja" if val else "nein"
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def to_csv(data: list, columns: list, output_path: str):
    """Schreibt CSV-Datei."""
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)
        for row in data:
            writer.writerow([format_value(row.get(col)) for col in columns])
    print(f"CSV geschrieben: {output_path} ({len(data)} Zeilen)")


def to_html(data: list, columns: list, output_path: str, title: str = ""):
    """Schreibt HTML-Datei mit sortierbar/filterbar-Tabelle."""
    if not title:
        title = Path(output_path).stem

    # Spaltennamen etwas lesbarer machen
    display_names = {col: col.replace("_", " ").title() for col in columns}

    lines = []
    lines.append("<!DOCTYPE html>")
    lines.append('<html lang="de">')
    lines.append("<head>")
    lines.append(f"<title>{html.escape(title)}</title>")
    lines.append('<meta charset="utf-8">')
    lines.append("<style>")
    lines.append("""
body {
    font-family: 'Segoe UI', Consolas, monospace;
    background: #1e1e2e; color: #cdd6f4;
    margin: 20px; font-size: 13px;
}
h1 { color: #89b4fa; font-size: 18px; }
.info { color: #a6adc8; margin-bottom: 12px; }
table {
    border-collapse: collapse; width: 100%;
    margin-top: 8px;
}
th {
    background: #313244; color: #89b4fa;
    padding: 6px 10px; text-align: left;
    border-bottom: 2px solid #45475a;
    cursor: pointer; user-select: none;
    position: sticky; top: 0;
}
th:hover { background: #45475a; }
th.sorted-asc::after { content: ' ▲'; color: #a6e3a1; }
th.sorted-desc::after { content: ' ▼'; color: #f38ba8; }
td {
    padding: 4px 10px;
    border-bottom: 1px solid #313244;
    max-width: 400px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
td:hover { white-space: normal; overflow: visible; }
tr:hover { background: #313244; }
tr.skipped { color: #7f849c; }
tr.ungeplant { color: #f9e2af; }
.filter-row input {
    width: 100%; box-sizing: border-box;
    background: #181825; color: #cdd6f4;
    border: 1px solid #45475a; padding: 3px 6px;
    font-size: 12px;
}
.stats { color: #a6adc8; margin-top: 8px; font-size: 12px; }
""")
    lines.append("</style>")
    lines.append("</head>")
    lines.append("<body>")
    lines.append(f"<h1>{html.escape(title)}</h1>")
    lines.append(f'<div class="info">{len(data)} Eintraege &bull; {len(columns)} Spalten</div>')

    # Tabelle
    lines.append('<table id="mainTable">')

    # Header
    lines.append("<thead>")
    lines.append("<tr>")
    for i, col in enumerate(columns):
        lines.append(f'<th onclick="sortTable({i})">{html.escape(display_names[col])}</th>')
    lines.append("</tr>")

    # Filterzeile
    lines.append('<tr class="filter-row">')
    for i in range(len(columns)):
        lines.append(f'<td><input type="text" oninput="filterTable()" placeholder="Filter..."></td>')
    lines.append("</tr>")
    lines.append("</thead>")

    # Body
    lines.append("<tbody>")
    for row in data:
        # CSS-Klasse fuer besondere Zeilen
        css_class = ""
        if row.get("skipped") is True:
            css_class = ' class="skipped"'
        elif row.get("list") == "ungeplant":
            css_class = ' class="ungeplant"'

        lines.append(f"<tr{css_class}>")
        for col in columns:
            val = format_value(row.get(col))
            lines.append(f"<td title=\"{html.escape(val)}\">{html.escape(val)}</td>")
        lines.append("</tr>")
    lines.append("</tbody>")
    lines.append("</table>")

    # Statistik-Zeile (fuer Log-Dateien)
    if any("skipped" in row for row in data[:1]):
        done = sum(1 for r in data if not r.get("skipped"))
        skipped = sum(1 for r in data if r.get("skipped"))
        ungeplant = sum(1 for r in data if r.get("list") == "ungeplant")
        lines.append(f'<div class="stats">Erledigt: {done} &bull; Uebersprungen: {skipped} &bull; Ungeplant: {ungeplant}</div>')

    # JavaScript: Sortierung + Filter
    lines.append("""
<script>
let sortCol = -1, sortAsc = true;
function sortTable(col) {
    const table = document.getElementById('mainTable');
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.rows);
    if (sortCol === col) { sortAsc = !sortAsc; } else { sortCol = col; sortAsc = true; }

    // Reset header classes
    table.querySelectorAll('th').forEach(th => th.className = '');
    table.tHead.rows[0].cells[col].className = sortAsc ? 'sorted-asc' : 'sorted-desc';

    rows.sort((a, b) => {
        let va = a.cells[col].textContent.trim();
        let vb = b.cells[col].textContent.trim();
        // Try numeric
        let na = parseFloat(va), nb = parseFloat(vb);
        if (!isNaN(na) && !isNaN(nb)) return sortAsc ? na - nb : nb - na;
        // Try time HH:MM
        if (/^\\d{2}:\\d{2}/.test(va) && /^\\d{2}:\\d{2}/.test(vb)) {
            return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
        }
        return sortAsc ? va.localeCompare(vb, 'de') : vb.localeCompare(va, 'de');
    });
    rows.forEach(r => tbody.appendChild(r));
}

function filterTable() {
    const table = document.getElementById('mainTable');
    const inputs = table.tHead.rows[1].querySelectorAll('input');
    const filters = Array.from(inputs).map(i => i.value.toLowerCase());
    const rows = table.tBodies[0].rows;
    for (let r = 0; r < rows.length; r++) {
        let show = true;
        for (let c = 0; c < filters.length; c++) {
            if (filters[c] && !rows[r].cells[c].textContent.toLowerCase().includes(filters[c])) {
                show = false; break;
            }
        }
        rows[r].style.display = show ? '' : 'none';
    }
}
</script>
""")
    lines.append("</body></html>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"HTML geschrieben: {output_path} ({len(data)} Zeilen)")


def main():
    parser = argparse.ArgumentParser(
        description="JSON/JSONL zu CSV oder HTML konvertieren"
    )
    parser.add_argument("input", help="Eingabedatei (JSON-Array oder JSONL)")
    parser.add_argument("-f", "--format", choices=["csv", "html"], default="html",
                        help="Ausgabeformat (Standard: html)")
    parser.add_argument("-o", "--output", help="Ausgabedatei")
    parser.add_argument("-c", "--columns",
                        help="Kommagetrennte Spaltenliste (Standard: alle)")
    parser.add_argument("-s", "--sort", help="Nach dieser Spalte sortieren")
    parser.add_argument("-r", "--reverse", action="store_true",
                        help="Absteigende Sortierung")
    parser.add_argument("--open", action="store_true",
                        help="Datei nach Erstellung oeffnen")

    args = parser.parse_args()

    # Eingabe laden
    input_path = args.input
    if not os.path.exists(input_path):
        print(f"Fehler: Datei nicht gefunden: {input_path}", file=sys.stderr)
        sys.exit(1)

    data = load_json(input_path)
    if not data:
        print("Fehler: Keine Daten in der Datei.", file=sys.stderr)
        sys.exit(1)

    # Spalten
    requested_cols = args.columns.split(",") if args.columns else None
    columns = get_columns(data, requested_cols)

    # Sortierung
    if args.sort:
        if args.sort not in columns:
            print(f"Warnung: Spalte '{args.sort}' nicht gefunden, ignoriert.",
                  file=sys.stderr)
        else:
            def sort_key(row):
                val = row.get(args.sort)
                if val is None:
                    return ""
                if isinstance(val, (int, float)):
                    return val
                return str(val)
            data.sort(key=sort_key, reverse=args.reverse)

    # Ausgabedatei
    ext = ".csv" if args.format == "csv" else ".html"
    if args.output:
        output_path = args.output
    else:
        output_path = str(Path(input_path).with_suffix(ext))

    # Konvertieren
    title = Path(input_path).stem
    if args.format == "csv":
        to_csv(data, columns, output_path)
    else:
        to_html(data, columns, output_path, title=title)

    # Oeffnen
    if args.open:
        if sys.platform == "win32":
            os.startfile(output_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", output_path])
        else:
            subprocess.run(["xdg-open", output_path])


if __name__ == "__main__":
    main()
