"""
extract_netlist.py — Extract NOR netlist from 14500B VHDL-to-CMOL description.

Parses the "-> signal = NOT (...)" lines from Kurt's hand-crafted NOR decomposition
and produces a clean, machine-readable JSON netlist suitable for CMOL FPGA placement.

Handles:
- Duplicate signal assignments (keeps the flip-flop version over simple inverters)
- Fan-in analysis
- Feedback loop detection (flip-flops)
- External pin identification
"""
import json
import re
import sys
from collections import defaultdict

SOURCE_FILE = r"C:\Users\kurt_\Betrieb\Computerspiele\Emulation 14500B-Chip in VHDL in CMOL Cells Teil 2.txt"
OUTPUT_FILE = r"C:\Users\kurt_\.openclaw\workspace\kontensystem\tools\14500B_netlist.json"

# MC14500B chip pin definitions (accent on the actual IC package)
CHIP_INPUTS = {"clk", "rst", "i0", "i1", "i2", "i3", "data_in"}
CHIP_OUTPUTS = {"data_out", "write", "jmp", "rtn", "flg0", "flgf"}

# Signal name mapping: netlist name → chip pin name
# (where the netlist uses a different name than the IC pin)
SIGNAL_TO_PIN = {
    "jump": "jmp",
}

# Derived clock signals that should be generated internally, not external
# clk → clkrise (rising edge), clkfall (falling edge), nclkrise (NOT clkrise)
DERIVED_CLOCK_SIGNALS = {"clkrise", "clkfall", "nclkrise"}


def parse_nor_line(line: str):
    """Parse a '-> signal = NOT (a OR b OR c)' or '-> signal = NOT a' line.
    
    Returns (output_signal, [input_signals]) or None if not a gate definition.
    """
    # Strip leading "-> " and trailing whitespace/comments after "->"
    line = line.strip()
    if not line.startswith("->"):
        return None
    line = line[2:].strip()
    
    # Remove trailing comments like "-> OK" or "-> unnötig"
    # But be careful not to strip the actual definition
    # Comments after the definition are separated by "  ->" or similar
    
    # Match: signal = NOT (a OR b OR c) or signal = NOT a
    # Also handle: signal = NOT (a NOR b) which appeared once
    m = re.match(r'(\S+)\s*=\s*NOT\s*\((.+)\)\s*', line)
    if m:
        output = m.group(1)
        inner = m.group(2)
        # Split on OR (case-insensitive) or NOR
        inputs = re.split(r'\s+(?:OR|or|Or|NOR|nor)\s+', inner)
        inputs = [inp.strip() for inp in inputs if inp.strip()]
        return output, inputs
    
    # Simple inverter: signal = NOT othersignal
    m = re.match(r'(\S+)\s*=\s*NOT\s+(\S+)', line)
    if m:
        output = m.group(1).rstrip(';')
        inp = m.group(2).rstrip(';')
        return output, [inp]
    
    return None


def extract_netlist(source_path: str):
    """Extract all NOR gates from the source file."""
    gates_raw = []
    
    with open(source_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("->"):
                continue
            
            # Skip comment/summary lines
            if any(kw in line for kw in ["bis hier", "insg.", "cells n", 
                                          "(Zw.)", "ebenso", "benötigt"]):
                continue
            
            result = parse_nor_line(line)
            if result:
                output, inputs = result
                gates_raw.append({
                    "output": output,
                    "inputs": inputs,
                    "raw_line": line,
                })
    
    return gates_raw


def generate_ir_flipflops(gates_raw):
    """Generate IR flip-flop gates for bits 1, 2, 3.
    
    IR bit 0 is fully specified in the source file:
        -> ni0 = NOT i0
        -> ir0_nclkfall = NOT (nir0 OR clkfall)
        -> i0_clkfall = NOT (ni0 OR nclkfall)
        -> nir0 = NOT (i0_clkfall OR ir0_nclkfall)
        -> ir0 = NOT nir0
    
    Bits 1, 2, 3 are described as "ebenso" (likewise) in the source.
    Generate them by substituting signal names.
    """
    template = [
        ("ni{n}", ["i{n}"]),                          # ni1 = NOT i1
        ("ir{n}_nclkfall", ["nir{n}", "clkfall"]),    # ir1_nclkfall = NOT (nir1 OR clkfall)
        ("i{n}_clkfall", ["ni{n}", "nclkfall"]),      # i1_clkfall = NOT (ni1 OR nclkfall)
        ("nir{n}", ["i{n}_clkfall", "ir{n}_nclkfall"]),  # nir1 = NOT (i1_clkfall OR ir1_nclkfall)
        ("ir{n}", ["nir{n}"]),                         # ir1 = NOT nir1
    ]
    
    new_gates = []
    for bit in [1, 2, 3]:
        for output_tmpl, inputs_tmpl in template:
            output = output_tmpl.format(n=bit)
            inputs = [inp.format(n=bit) for inp in inputs_tmpl]
            new_gates.append({
                "output": output,
                "inputs": inputs,
                "raw_line": f"-> {output} = NOT ({' OR '.join(inputs)})  [auto-generated from ir0 template]",
            })
    
    return gates_raw + new_gates


def deduplicate_gates(gates_raw):
    """Handle duplicate signal assignments.
    
    Strategy: when a signal is assigned twice, keep the more complex
    version (more inputs = flip-flop feedback), discard the simple inverter.
    Exception: exact duplicates are just removed.
    """
    by_output = defaultdict(list)
    for g in gates_raw:
        by_output[g["output"]].append(g)
    
    gates = []
    duplicates_resolved = []
    
    for output, assignments in by_output.items():
        if len(assignments) == 1:
            gates.append(assignments[0])
        else:
            # Multiple assignments — pick the one with more inputs (flip-flop)
            # If identical, just keep one
            unique = {tuple(a["inputs"]): a for a in assignments}
            if len(unique) == 1:
                # Exact duplicate
                gates.append(assignments[0])
                duplicates_resolved.append(f"{output}: exact duplicate removed")
            else:
                # Different — keep the one with more inputs
                best = max(unique.values(), key=lambda a: len(a["inputs"]))
                gates.append(best)
                duplicates_resolved.append(
                    f"{output}: kept {len(best['inputs'])}-input version, "
                    f"discarded {[len(a['inputs']) for a in assignments if tuple(a['inputs']) != tuple(best['inputs'])]}-input version(s)"
                )
    
    return gates, duplicates_resolved


def analyze_netlist(gates):
    """Analyze the netlist for statistics and feedback loops."""
    all_outputs = {g["output"] for g in gates}
    all_inputs = set()
    for g in gates:
        all_inputs.update(g["inputs"])
    
    # Chip I/O pins (explicit, from MC14500B datasheet)
    # Map netlist signal names to chip pin names
    chip_output_signals = set()
    for g in gates:
        pin_name = SIGNAL_TO_PIN.get(g["output"], g["output"])
        if pin_name in CHIP_OUTPUTS:
            chip_output_signals.add(g["output"])
    
    # External inputs: signals used but not defined by any gate
    raw_external = all_inputs - all_outputs
    
    # Separate into chip input pins vs derived clock signals
    # Derived clocks (clkrise, clkfall, nclkrise) come from the clk pin
    # but aren't explicitly modeled as gates — note this for the user
    external_chip_pins = set()
    derived_signals = set()
    for sig in raw_external:
        if sig in DERIVED_CLOCK_SIGNALS:
            derived_signals.add(sig)
        else:
            external_chip_pins.add(sig)
    
    # Internal signals: both defined and used
    internal_signals = all_inputs & all_outputs
    
    # Feedback detection: signal used as input to a gate that 
    # (directly or indirectly) produces it
    # Simple heuristic: signal appears in its own gate's inputs
    direct_feedback = []
    for g in gates:
        if g["output"] in g["inputs"]:
            direct_feedback.append(g["output"])
    
    # Fan-in distribution
    fanin_dist = defaultdict(int)
    for g in gates:
        fanin_dist[len(g["inputs"])] += 1
    
    # Fan-out: how many gates use each signal as input
    fanout = defaultdict(int)
    for g in gates:
        for inp in g["inputs"]:
            fanout[inp] += 1
    
    return {
        "total_gates": len(gates),
        "chip_input_pins": sorted(external_chip_pins),
        "chip_output_pins": sorted(SIGNAL_TO_PIN.get(s, s) for s in chip_output_signals),
        "chip_output_signals": sorted(chip_output_signals),
        "derived_clock_signals": sorted(derived_signals),
        "internal_signals": sorted(internal_signals),
        "direct_feedback": sorted(direct_feedback),
        "fanin_distribution": dict(sorted(fanin_dist.items())),
        "max_fanin": max(len(g["inputs"]) for g in gates),
        "max_fanout_signal": max(fanout.items(), key=lambda x: x[1]),
        "high_fanout_signals": sorted(
            [(sig, cnt) for sig, cnt in fanout.items() if cnt >= 5],
            key=lambda x: -x[1]
        ),
    }


def main():
    print(f"Reading: {SOURCE_FILE}")
    gates_raw = extract_netlist(SOURCE_FILE)
    print(f"  Raw gate lines found: {len(gates_raw)}")
    
    gates_raw = generate_ir_flipflops(gates_raw)
    print(f"  After IR1-3 generation: {len(gates_raw)} lines")
    
    gates, dupes = deduplicate_gates(gates_raw)
    print(f"  After deduplication: {len(gates)} gates")
    if dupes:
        print(f"  Duplicates resolved:")
        for d in dupes:
            print(f"    {d}")
    
    analysis = analyze_netlist(gates)
    
    print(f"\n{'='*60}")
    print(f"  14500B NOR NETLIST SUMMARY")
    print(f"{'='*60}")
    print(f"  Total NOR gates:     {analysis['total_gates']}")
    print(f"  Chip input pins:     {len(analysis['chip_input_pins'])}")
    print(f"    {', '.join(analysis['chip_input_pins'])}")
    print(f"  Chip output pins:    {len(analysis['chip_output_pins'])}")
    print(f"    {', '.join(analysis['chip_output_pins'])}")
    if analysis['derived_clock_signals']:
        print(f"  Derived clock sigs:  {len(analysis['derived_clock_signals'])}")
        print(f"    {', '.join(analysis['derived_clock_signals'])}")
        print(f"    (generated from 'clk' pin, not modeled as gates)")
    print(f"  Direct feedback:     {len(analysis['direct_feedback'])}")
    print(f"    {', '.join(analysis['direct_feedback'])}")
    print(f"  Max fan-in:          {analysis['max_fanin']}")
    print(f"  Fan-in distribution:")
    for fanin, count in sorted(analysis['fanin_distribution'].items()):
        bar = '#' * count
        print(f"    {fanin} inputs: {count:2d} gates  {bar}")
    print(f"  High fan-out signals (>=5 uses):")
    for sig, cnt in analysis['high_fanout_signals']:
        print(f"    {sig}: used by {cnt} gates")
    
    # Build clean JSON netlist
    netlist = {
        "name": "MC14500B",
        "description": "Motorola 14500B Industrial Control Unit — NOR gate decomposition",
        "source": "Emulation 14500B-Chip in VHDL in CMOL Cells Teil 2.txt",
        "gates": [],
        "chip_input_pins": analysis["chip_input_pins"],
        "chip_output_pins": analysis["chip_output_pins"],
        "derived_clock_signals": analysis["derived_clock_signals"],
        "analysis": analysis,
    }
    
    for i, g in enumerate(sorted(gates, key=lambda x: x["output"])):
        netlist["gates"].append({
            "id": i,
            "output": g["output"],
            "inputs": g["inputs"],
            "fanin": len(g["inputs"]),
            "is_inverter": len(g["inputs"]) == 1,
            "has_feedback": g["output"] in g["inputs"],
        })
    
    # Write JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(netlist, f, indent=2, ensure_ascii=False)
    print(f"\nNetlist written to: {OUTPUT_FILE}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
