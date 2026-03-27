#!/usr/bin/env python3
"""
cmol_placer.py — CMOL-FPGA Placement Tool for the MC14500B NOR Netlist

Loads the 82-gate NOR netlist from 14500B_netlist.json and provides:
  • Greedy initial placement based on connectivity
  • Simulated-annealing optimiser (runs in background thread)
  • Interactive Tkinter visualisation with scrollable/zoomable grid

Architecture: narrow (Sait) CMOL-FPGA variant — asymmetric signal reach.

Usage:
    python cmol_placer.py
    python cmol_placer.py --rows 30 --cols 30
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional
import tkinter as tk
from tkinter import filedialog, messagebox

# ── Theme (Catppuccin Mocha) ──────────────────────────────────────────────────
COLOR_BG     = "#1e1e2e"
COLOR_FG     = "#cdd6f4"
COLOR_ACCENT = "#89b4fa"
COLOR_DONE   = "#a6e3a1"   # all inputs routable   (green)
COLOR_SKIP   = "#f38ba8"   # unroutable inputs      (red)
COLOR_WARN   = "#f9e2af"   # partially routable     (yellow)
COLOR_PANEL  = "#181825"
COLOR_LIST   = "#313244"
COLOR_IO     = "#cba6f7"   # chip I/O pin cells     (mauve)
COLOR_EMPTY  = "#45475a"   # empty grid cell
COLOR_SEL    = "#fab387"   # selected cell           (peach)
COLOR_GRID   = "#585b70"   # grid line colour
COLOR_ARROW  = "#f38ba8"   # unroutable connection line

NETLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "14500B_netlist.json")

UNROUTABLE_PENALTY  = 50      # cost per unroutable connection
OUTPUT_EDGE_WEIGHT  = 0.5     # weight for output-gate edge-proximity cost
DEFAULT_ROWS        = 24
DEFAULT_COLS        = 24
CELL_SIZE_DEFAULT   = 28
CELL_SIZE_MIN       = 6
CELL_SIZE_MAX       = 60

# ── CMOL Routing ──────────────────────────────────────────────────────────────

def can_reach(sr: int, sc: int, dr: int, dc: int) -> bool:
    """Return True if cell (sr, sc) can send its output to cell (dr, dc).

    Narrow (Sait) CMOL-FPGA asymmetric reach:
      Send left  1–2 :  dr == sr,  dc ∈ {sc-1, sc-2}
      Send down  1–2 :  dc == sc,  dr ∈ {sr+1, sr+2}
      Send right 1   :  dr == sr,  dc == sc+1
      Send up    1   :  dc == sc,  dr == sr-1
    """
    if dr == sr:
        d = sc - dc
        return d in (1, 2) or d == -1        # left 1/2 or right 1
    if dc == sc:
        d = dr - sr
        return d in (1, 2) or d == -1        # down 1/2 or up 1
    return False


def manhattan(r1: int, c1: int, r2: int, c2: int) -> int:
    return abs(r1 - r2) + abs(c1 - c2)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Gate:
    id: int
    output: str
    inputs: list
    fanin: int
    is_inverter: bool


@dataclass
class Netlist:
    gates: list                       # list[Gate]
    chip_inputs: list                 # external input pin signal names
    chip_outputs: list                # chip output pin names
    chip_output_signals: list         # gate output names driving chip outputs
    derived_clocks: list              # clkfall, clkrise, nclkrise
    output_to_gate: dict              # output_signal → Gate
    fanout: dict                      # signal → consumer count
    all_io_signals: list              # chip_inputs + derived_clocks (ordered)


@dataclass
class Placement:
    grid_rows: int
    grid_cols: int
    gate_positions:  dict = field(default_factory=dict)   # gate_id → (row, col)
    input_positions: dict = field(default_factory=dict)   # io_signal → (row, col)
    _cell_gate:  dict = field(default_factory=dict, repr=False)
    _cell_input: dict = field(default_factory=dict, repr=False)

    def rebuild_index(self) -> None:
        self._cell_gate  = {pos: gid for gid, pos in self.gate_positions.items()}
        self._cell_input = {pos: sig for sig,  pos in self.input_positions.items()}

    def gate_at(self, r: int, c: int) -> Optional[int]:
        return self._cell_gate.get((r, c))

    def input_at(self, r: int, c: int) -> Optional[str]:
        return self._cell_input.get((r, c))

    def is_occupied(self, r: int, c: int) -> bool:
        return (r, c) in self._cell_gate or (r, c) in self._cell_input

    def source_pos(self, signal: str, netlist: Netlist) -> Optional[tuple]:
        """Return grid position of the source of `signal`."""
        if signal in self.input_positions:
            return self.input_positions[signal]
        gate = netlist.output_to_gate.get(signal)
        if gate is not None:
            return self.gate_positions.get(gate.id)
        return None

    def copy(self) -> "Placement":
        p = Placement(
            grid_rows=self.grid_rows,
            grid_cols=self.grid_cols,
            gate_positions=dict(self.gate_positions),
            input_positions=dict(self.input_positions),
        )
        p.rebuild_index()
        return p

    def to_dict(self) -> dict:
        return {
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols,
            "gate_positions": {str(k): list(v) for k, v in self.gate_positions.items()},
            "input_positions": {k: list(v) for k, v in self.input_positions.items()},
        }

    @staticmethod
    def from_dict(d: dict) -> "Placement":
        p = Placement(
            grid_rows=d["grid_rows"],
            grid_cols=d["grid_cols"],
            gate_positions={int(k): tuple(v) for k, v in d["gate_positions"].items()},
            input_positions={k: tuple(v) for k, v in d["input_positions"].items()},
        )
        p.rebuild_index()
        return p


# ── Netlist loading ───────────────────────────────────────────────────────────

def load_netlist(path: str) -> Netlist:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    gates = [
        Gate(
            id=g["id"], output=g["output"], inputs=list(g["inputs"]),
            fanin=g["fanin"], is_inverter=g["is_inverter"],
        )
        for g in data["gates"]
    ]
    output_to_gate = {g.output: g for g in gates}

    fanout: dict = {}
    for g in gates:
        for inp in g.inputs:
            fanout[inp] = fanout.get(inp, 0) + 1

    chip_inputs      = list(data.get("chip_input_pins", []))
    chip_outputs     = list(data.get("chip_output_pins", []))
    chip_out_signals = list(data.get("analysis", {}).get("chip_output_signals", chip_outputs))
    derived_clocks   = list(data.get("derived_clock_signals", []))
    all_io           = chip_inputs + derived_clocks

    return Netlist(
        gates=gates,
        chip_inputs=chip_inputs,
        chip_outputs=chip_outputs,
        chip_output_signals=chip_out_signals,
        derived_clocks=derived_clocks,
        output_to_gate=output_to_gate,
        fanout=fanout,
        all_io_signals=all_io,
    )


# ── Cost function ─────────────────────────────────────────────────────────────

def compute_cost(
    placement: Placement, netlist: Netlist
) -> tuple:
    """Return (total_cost, per_gate_cost dict, unroutable_count).

    Cost components:
      - Unroutable connection : UNROUTABLE_PENALTY each
      - Routable connection   : manhattan distance
      - Output gate edge dist : OUTPUT_EDGE_WEIGHT × distance-from-bottom-right
    """
    per_gate: dict = {}
    total = 0.0
    unroutable = 0
    rows, cols = placement.grid_rows, placement.grid_cols

    for gate in netlist.gates:
        if gate.id not in placement.gate_positions:
            continue
        dr, dc = placement.gate_positions[gate.id]
        gate_cost = 0.0

        for sig in gate.inputs:
            src = placement.source_pos(sig, netlist)
            if src is None:
                gate_cost += UNROUTABLE_PENALTY
                unroutable += 1
                continue
            sr, sc = src
            if sr == dr and sc == dc:
                pass  # same cell — free (degenerate)
            elif can_reach(sr, sc, dr, dc):
                gate_cost += manhattan(sr, sc, dr, dc)
            else:
                gate_cost += UNROUTABLE_PENALTY
                unroutable += 1

        if gate.output in netlist.chip_output_signals:
            edge_dist = min(rows - 1 - dr, cols - 1 - dc)
            gate_cost += max(0, edge_dist) * OUTPUT_EDGE_WEIGHT

        per_gate[gate.id] = gate_cost
        total += gate_cost

    return total, per_gate, unroutable


def connection_status(
    placement: Placement, netlist: Netlist, gate: Gate
) -> list:
    """Return list of (signal, src_pos, dst_pos, routable) for a gate's inputs."""
    dr, dc = placement.gate_positions.get(gate.id, (-1, -1))
    result = []
    for sig in gate.inputs:
        src = placement.source_pos(sig, netlist)
        if src is None:
            result.append((sig, None, (dr, dc), False))
            continue
        sr, sc = src
        ok = (sr == dr and sc == dc) or can_reach(sr, sc, dr, dc)
        result.append((sig, (sr, sc), (dr, dc), ok))
    return result


# ── Greedy placement ──────────────────────────────────────────────────────────

def greedy_placement(netlist: Netlist, rows: int, cols: int) -> Placement:
    """Greedy initial placement using connectivity scoring.

    Strategy:
      1. Chip I/O signals → top row (row 0)
      2. Direct I/O consumers → rows 1-2 (top area)
      3. High-fanout / interconnect gates → center
      4. Chip-output-producing gates → bottom area
    """
    occupied: set = set()
    input_positions: dict = {}

    # Place chip I/O along top row
    for idx, sig in enumerate(netlist.all_io_signals):
        c = min(idx, cols - 1)
        input_positions[sig] = (0, c)
        occupied.add((0, c))

    # Connectivity score for each gate
    def gate_score(gate: Gate) -> float:
        return (
            sum(netlist.fanout.get(inp, 0) for inp in gate.inputs)
            + netlist.fanout.get(gate.output, 0) * 2.0
        )

    def sorted_positions(center_r: int, center_c: int) -> list:
        """All free cells sorted by distance from (center_r, center_c)."""
        pts = [(r, c) for r in range(rows) for c in range(cols)
               if (r, c) not in occupied]
        pts.sort(key=lambda p: (p[0] - center_r) ** 2 + (p[1] - center_c) ** 2)
        return pts

    gate_positions: dict = {}

    # Identify groups
    io_set = set(netlist.all_io_signals)
    io_consumers = [g for g in netlist.gates
                    if any(inp in io_set for inp in g.inputs)]
    out_gates    = [g for g in netlist.gates
                    if g.output in netlist.chip_output_signals
                    and g not in io_consumers]
    rest         = [g for g in netlist.gates
                    if g not in io_consumers and g not in out_gates]
    rest.sort(key=gate_score, reverse=True)

    def place_group(group: list, center_r: int, center_c: int):
        pool = sorted_positions(center_r, center_c)
        idx  = 0
        for g in group:
            while idx < len(pool) and pool[idx] in occupied:
                idx += 1
            if idx >= len(pool):
                break
            gate_positions[g.id] = pool[idx]
            occupied.add(pool[idx])
            idx += 1

    # Calculate compact cluster size based on gate count, not grid size.
    # This ensures gates stay close together even on large grids.
    import math
    n_gates = len(netlist.gates)
    cluster_side = int(math.ceil(math.sqrt(n_gates))) + 2  # e.g. 82 → ~12
    cluster_center_r = min(cluster_side // 2 + 1, rows // 2)  # near top, close to I/O
    cluster_center_c = min(cluster_side // 2, cols // 2)

    # I/O consumers near top (close to chip inputs)
    place_group(io_consumers, 1, cluster_center_c)
    # Output gates slightly below center of cluster
    place_group(out_gates, cluster_center_r + cluster_side // 3, cluster_center_c)
    # Remaining gates: center of cluster, outward
    place_group(rest, cluster_center_r, cluster_center_c)

    p = Placement(
        grid_rows=rows,
        grid_cols=cols,
        gate_positions=gate_positions,
        input_positions=input_positions,
    )
    p.rebuild_index()
    return p


# ── Simulated Annealing ───────────────────────────────────────────────────────

class SAState:
    """SA optimiser state.  Call step() repeatedly or run() in a thread."""

    T0       = 50.0
    T_MIN    = 0.02
    ALPHA    = 0.9997     # per-step cooling (≈ e^(-3/10000))

    def __init__(self, placement: Placement, netlist: Netlist):
        self.placement  = placement.copy()
        self.netlist    = netlist
        self.T          = self.T0
        self.iteration  = 0
        cost, _, unr    = compute_cost(self.placement, netlist)
        self.cost       = cost
        self.best_cost  = cost
        self.unroutable = unr
        self.best_placement = placement.copy()

    def step(self) -> None:
        """One SA move attempt."""
        if self.T <= self.T_MIN:
            return

        p = self.placement
        gate_ids = list(p.gate_positions.keys())
        if len(gate_ids) < 2:
            return

        if random.random() < 0.65:
            # ── Swap two gates ────────────────────────────────────────────────
            a, b = random.sample(gate_ids, 2)
            pa, pb = p.gate_positions[a], p.gate_positions[b]
            p.gate_positions[a] = pb
            p.gate_positions[b] = pa
            p.rebuild_index()
            new_cost, _, new_unr = compute_cost(p, self.netlist)
            delta = new_cost - self.cost
            if delta <= 0 or random.random() < math.exp(-delta / max(self.T, 1e-9)):
                self.cost = new_cost
                self.unroutable = new_unr
                if new_cost < self.best_cost:
                    self.best_cost = new_cost
                    self.best_placement = p.copy()
            else:
                # Undo swap
                p.gate_positions[a] = pa
                p.gate_positions[b] = pb
                p.rebuild_index()
        else:
            # ── Relocate one gate to a random empty cell ──────────────────────
            gid = random.choice(gate_ids)
            old_pos = p.gate_positions[gid]
            # Find empty cell
            found = False
            for _ in range(30):
                nr = random.randrange(p.grid_rows)
                nc = random.randrange(p.grid_cols)
                if not p.is_occupied(nr, nc):
                    found = True
                    break
            if not found:
                self.T *= self.ALPHA
                self.iteration += 1
                return

            p.gate_positions[gid] = (nr, nc)
            p.rebuild_index()
            new_cost, _, new_unr = compute_cost(p, self.netlist)
            delta = new_cost - self.cost
            if delta <= 0 or random.random() < math.exp(-delta / max(self.T, 1e-9)):
                self.cost = new_cost
                self.unroutable = new_unr
                if new_cost < self.best_cost:
                    self.best_cost = new_cost
                    self.best_placement = p.copy()
            else:
                # Undo
                p.gate_positions[gid] = old_pos
                p.rebuild_index()

        self.T *= self.ALPHA
        self.iteration += 1


# ── SA Runner (background thread) ─────────────────────────────────────────────

class SARunner:
    """Runs SAState.step() in a daemon thread; calls `callback` periodically."""

    BATCH = 500    # steps between GUI callbacks

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop   = threading.Event()
        self.sa: Optional[SAState] = None

    def start(self, sa: SAState, callback) -> None:
        self._stop.clear()
        self.sa = sa
        self._thread = threading.Thread(
            target=self._run, args=(callback,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self, callback) -> None:
        sa = self.sa
        while not self._stop.is_set() and sa.T > sa.T_MIN:
            for _ in range(self.BATCH):
                if self._stop.is_set():
                    return
                sa.step()
            callback()
        # Final callback when done
        callback()


# ── Tkinter GUI ───────────────────────────────────────────────────────────────

class CmolPlacerApp:
    """Main application window."""

    def __init__(self, root: tk.Tk, netlist: Netlist,
                 rows: int = DEFAULT_ROWS, cols: int = DEFAULT_COLS):
        self.root      = root
        self.netlist   = netlist
        self.rows      = rows
        self.cols      = cols
        self.cell_size = CELL_SIZE_DEFAULT

        self.placement: Optional[Placement] = None
        self.sa_state:  Optional[SAState]   = None
        self.runner     = SARunner()

        self.selected_cell: Optional[tuple] = None   # (row, col)
        self._per_gate_cost: dict = {}
        self._total_cost = 0.0
        self._unroutable = 0
        self._show_connections = tk.BooleanVar(value=True)

        self._build_ui()
        self._reset()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.title("CMOL-FPGA Placer — MC14500B")
        self.root.configure(bg=COLOR_BG)
        self.root.minsize(900, 600)

        # Top-level layout: canvas frame (left) + sidebar (right)
        main = tk.Frame(self.root, bg=COLOR_BG)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Canvas area ───────────────────────────────────────────────────────
        canvas_frame = tk.Frame(main, bg=COLOR_BG)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            canvas_frame, bg=COLOR_PANEL,
            highlightthickness=0, cursor="crosshair",
        )
        vbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL,
                            command=self.canvas.yview,
                            bg=COLOR_LIST, troughcolor=COLOR_BG)
        hbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL,
                            command=self.canvas.xview,
                            bg=COLOR_LIST, troughcolor=COLOR_BG)
        self.canvas.configure(
            yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar.pack(side=tk.RIGHT,  fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>",        self._on_click)
        self.canvas.bind("<MouseWheel>",       self._on_mousewheel)
        self.canvas.bind("<Button-4>",         self._on_mousewheel)  # Linux
        self.canvas.bind("<Button-5>",         self._on_mousewheel)

        # ── Right sidebar ─────────────────────────────────────────────────────
        sidebar = tk.Frame(main, bg=COLOR_PANEL, width=240)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Title
        tk.Label(sidebar, text="CMOL Placer", bg=COLOR_PANEL, fg=COLOR_ACCENT,
                 font=("Consolas", 13, "bold")).pack(pady=(10, 2))
        tk.Label(sidebar, text="MC14500B NOR Netlist",
                 bg=COLOR_PANEL, fg=COLOR_FG,
                 font=("Consolas", 9)).pack(pady=(0, 8))

        # Control buttons
        btn_cfg = dict(
            bg=COLOR_LIST, fg=COLOR_FG, activebackground=COLOR_ACCENT,
            activeforeground=COLOR_BG, relief=tk.FLAT,
            font=("Consolas", 10), pady=4, cursor="hand2",
        )
        self._btn_run  = tk.Button(sidebar, text="▶  Run SA",    **btn_cfg,
                                   command=self._toggle_sa)
        self._btn_step = tk.Button(sidebar, text="⟩  Step × 500", **btn_cfg,
                                   command=self._step_sa)
        btn_reset = tk.Button(sidebar, text="↺  Reset",         **btn_cfg,
                              command=self._reset)
        btn_save  = tk.Button(sidebar, text="💾  Save",          **btn_cfg,
                              command=self._save)
        btn_load  = tk.Button(sidebar, text="📂  Load",          **btn_cfg,
                              command=self._load)

        for b in (self._btn_run, self._btn_step, btn_reset, btn_save, btn_load):
            b.pack(fill=tk.X, padx=8, pady=2)

        # Zoom
        zoom_frame = tk.Frame(sidebar, bg=COLOR_PANEL)
        zoom_frame.pack(fill=tk.X, padx=8, pady=(4, 2))
        tk.Label(zoom_frame, text="Zoom:", bg=COLOR_PANEL, fg=COLOR_FG,
                 font=("Consolas", 9)).pack(side=tk.LEFT)
        tk.Button(zoom_frame, text="−", **btn_cfg, width=2,
                  command=self._zoom_out).pack(side=tk.RIGHT, padx=1)
        tk.Button(zoom_frame, text="+", **btn_cfg, width=2,
                  command=self._zoom_in).pack(side=tk.RIGHT, padx=1)

        # Show connections toggle
        chk = tk.Checkbutton(
            sidebar, text="Show connections",
            variable=self._show_connections,
            bg=COLOR_PANEL, fg=COLOR_FG, selectcolor=COLOR_LIST,
            activebackground=COLOR_PANEL, activeforeground=COLOR_FG,
            font=("Consolas", 9), command=self._redraw,
        )
        chk.pack(anchor=tk.W, padx=8, pady=(4, 0))

        # Grid config
        cfg_frame = tk.LabelFrame(
            sidebar, text=" Grid ", bg=COLOR_PANEL, fg=COLOR_ACCENT,
            font=("Consolas", 9), labelanchor="n",
        )
        cfg_frame.pack(fill=tk.X, padx=8, pady=(8, 2))

        row_frame = tk.Frame(cfg_frame, bg=COLOR_PANEL)
        row_frame.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(row_frame, text="Rows:", bg=COLOR_PANEL, fg=COLOR_FG,
                 font=("Consolas", 9), width=6).pack(side=tk.LEFT)
        self._rows_var = tk.IntVar(value=self.rows)
        tk.Spinbox(row_frame, from_=10, to=64, textvariable=self._rows_var,
                   width=4, bg=COLOR_LIST, fg=COLOR_FG,
                   font=("Consolas", 9)).pack(side=tk.LEFT)

        col_frame = tk.Frame(cfg_frame, bg=COLOR_PANEL)
        col_frame.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(col_frame, text="Cols:", bg=COLOR_PANEL, fg=COLOR_FG,
                 font=("Consolas", 9), width=6).pack(side=tk.LEFT)
        self._cols_var = tk.IntVar(value=self.cols)
        tk.Spinbox(col_frame, from_=10, to=64, textvariable=self._cols_var,
                   width=4, bg=COLOR_LIST, fg=COLOR_FG,
                   font=("Consolas", 9)).pack(side=tk.LEFT)

        tk.Button(cfg_frame, text="Apply Grid Size", **btn_cfg,
                  command=self._apply_grid_size).pack(
                      fill=tk.X, padx=4, pady=(2, 4))

        # Legend
        legend = tk.LabelFrame(
            sidebar, text=" Legend ", bg=COLOR_PANEL, fg=COLOR_ACCENT,
            font=("Consolas", 9), labelanchor="n",
        )
        legend.pack(fill=tk.X, padx=8, pady=(6, 2))
        for color, label in [
            (COLOR_DONE, "All routable"),
            (COLOR_WARN, "Partial"),
            (COLOR_SKIP, "Unroutable"),
            (COLOR_IO,   "Chip I/O"),
            (COLOR_EMPTY,"Empty"),
            (COLOR_SEL,  "Selected"),
        ]:
            row = tk.Frame(legend, bg=COLOR_PANEL)
            row.pack(fill=tk.X, padx=4, pady=1)
            tk.Label(row, bg=color, width=3, relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
            tk.Label(row, text=label, bg=COLOR_PANEL, fg=COLOR_FG,
                     font=("Consolas", 8)).pack(side=tk.LEFT)

        # Detail panel
        self._detail_frame = tk.LabelFrame(
            sidebar, text=" Selected Cell ", bg=COLOR_PANEL, fg=COLOR_ACCENT,
            font=("Consolas", 9), labelanchor="n",
        )
        self._detail_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 4))

        self._detail_text = tk.Text(
            self._detail_frame, bg=COLOR_LIST, fg=COLOR_FG,
            font=("Consolas", 8), wrap=tk.WORD,
            state=tk.DISABLED, relief=tk.FLAT,
            height=12,
        )
        self._detail_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(
            self.root, textvariable=self._status_var,
            bg=COLOR_LIST, fg=COLOR_FG,
            font=("Consolas", 9), anchor=tk.W, padx=6,
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _cell_xy(self, r: int, c: int) -> tuple:
        """Canvas pixel top-left for cell (r, c)."""
        cs = self.cell_size
        return c * cs, r * cs

    def _canvas_size(self) -> tuple:
        return self.cols * self.cell_size, self.rows * self.cell_size

    def _cell_color(self, r: int, c: int) -> str:
        if self.placement is None:
            return COLOR_EMPTY
        if (r, c) == self.selected_cell:
            return COLOR_SEL

        if self.placement.input_at(r, c) is not None:
            return COLOR_IO

        gid = self.placement.gate_at(r, c)
        if gid is None:
            return COLOR_EMPTY

        gate = self.netlist.output_to_gate.get(
            next((g.output for g in self.netlist.gates if g.id == gid), ""), None
        )
        if gate is None:
            return COLOR_EMPTY

        statuses = connection_status(self.placement, self.netlist, gate)
        if not statuses:
            return COLOR_DONE
        ok_count  = sum(1 for _, _, _, ok in statuses if ok)
        bad_count = len(statuses) - ok_count
        if bad_count == 0:
            return COLOR_DONE
        if ok_count == 0:
            return COLOR_SKIP
        return COLOR_WARN

    def _gate_label(self, gid: int) -> str:
        """Short label for a gate."""
        for g in self.netlist.gates:
            if g.id == gid:
                lbl = g.output
                # Abbreviate long names
                if len(lbl) > 10 and self.cell_size < 30:
                    lbl = lbl[:8] + "…"
                elif len(lbl) > 14:
                    lbl = lbl[:12] + "…"
                return lbl
        return f"#{gid}"

    def _redraw(self) -> None:
        if self.placement is None:
            return
        cs = self.cell_size
        cw, ch = self._canvas_size()
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0, 0, cw, ch))

        # Pre-compute gate lookup for speed
        gate_by_id = {g.id: g for g in self.netlist.gates}

        # Draw cells
        for r in range(self.rows):
            for c in range(self.cols):
                x0, y0 = self._cell_xy(r, c)
                x1, y1 = x0 + cs - 1, y0 + cs - 1
                color = self._cell_color(r, c)

                self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    fill=color, outline=COLOR_GRID, width=1,
                    tags="cell",
                )

                # Label
                if cs >= 16:
                    gid = self.placement.gate_at(r, c)
                    sig = self.placement.input_at(r, c)
                    if gid is not None:
                        lbl = self._gate_label(gid)
                        font_size = max(5, min(8, cs // 4))
                        self.canvas.create_text(
                            x0 + cs // 2, y0 + cs // 2,
                            text=lbl, fill=COLOR_BG,
                            font=("Consolas", font_size),
                            tags="label",
                        )
                    elif sig is not None and cs >= 20:
                        font_size = max(5, min(7, cs // 4))
                        lbl = sig if len(sig) <= 8 else sig[:6] + "…"
                        self.canvas.create_text(
                            x0 + cs // 2, y0 + cs // 2,
                            text=lbl, fill=COLOR_BG,
                            font=("Consolas", font_size, "italic"),
                            tags="label",
                        )

        # Connection lines
        if self._show_connections.get():
            self._draw_connections(gate_by_id)

    def _draw_connections(self, gate_by_id: dict) -> None:
        """Draw unroutable connections as red lines.
        
        If a cell is selected, draw all its connections (routable in accent,
        unroutable in red).  Otherwise draw only unroutable connections.
        """
        cs = self.cell_size
        half = cs // 2

        def centre(r: int, c: int) -> tuple:
            x, y = self._cell_xy(r, c)
            return x + half, y + half

        for gate in self.netlist.gates:
            if gate.id not in self.placement.gate_positions:
                continue
            dr, dc = self.placement.gate_positions[gate.id]
            selected = (dr, dc) == self.selected_cell
            statuses = connection_status(self.placement, self.netlist, gate)

            for sig, src, dst, ok in statuses:
                if src is None:
                    continue
                draw = selected or not ok
                if not draw:
                    continue
                sr, sc = src
                color = COLOR_ACCENT if (ok and selected) else COLOR_ARROW
                width = 2 if selected else 1

                # Only draw if both endpoints are on grid
                if 0 <= sr < self.rows and 0 <= sc < self.cols:
                    x0, y0 = centre(sr, sc)
                    x1, y1 = centre(dr, dc)
                    self.canvas.create_line(
                        x0, y0, x1, y1,
                        fill=color, width=width,
                        arrow=tk.LAST, arrowshape=(6, 8, 3),
                        tags="conn",
                    )

    def _update_detail(self) -> None:
        """Update the right-panel detail text for the selected cell."""
        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)

        if self.selected_cell is None or self.placement is None:
            self._detail_text.insert(tk.END, "Click a cell to see details.")
            self._detail_text.config(state=tk.DISABLED)
            return

        r, c = self.selected_cell
        lines = [f"Cell ({r}, {c})\n"]

        gid = self.placement.gate_at(r, c)
        sig = self.placement.input_at(r, c)

        if gid is not None:
            gate = next((g for g in self.netlist.gates if g.id == gid), None)
            if gate:
                lines.append(f"Gate #{gate.id}\n")
                lines.append(f"Out: {gate.output}\n")
                lines.append(f"Fan-in: {gate.fanin}\n")
                fo = self.netlist.fanout.get(gate.output, 0)
                lines.append(f"Fan-out: {fo}\n")
                lines.append(f"Cost: {self._per_gate_cost.get(gid, 0):.1f}\n")
                lines.append("\nInputs:\n")
                for inp_sig, src, dst, ok in connection_status(
                        self.placement, self.netlist, gate):
                    status = "✓" if ok else "✗"
                    src_str = f"({src[0]},{src[1]})" if src else "?"
                    lines.append(f" {status} {inp_sig}\n   ← {src_str}\n")
        elif sig is not None:
            lines.append(f"I/O Pin: {sig}\n")
            if sig in self.netlist.chip_inputs:
                lines.append("Type: Chip Input\n")
            elif sig in self.netlist.derived_clocks:
                lines.append("Type: Derived Clock\n")
            fo = self.netlist.fanout.get(sig, 0)
            lines.append(f"Fan-out: {fo}\n")
        else:
            lines.append("(empty cell)")

        self._detail_text.insert(tk.END, "".join(lines))
        self._detail_text.config(state=tk.DISABLED)

    def _update_status(self) -> None:
        sa = self.sa_state
        if sa:
            running = self.runner.is_running()
            state   = "RUNNING" if running else "stopped"
            self._status_var.set(
                f"SA {state}  |  Cost: {sa.cost:.1f}  "
                f"Best: {sa.best_cost:.1f}  "
                f"Unroutable: {sa.unroutable}  "
                f"Iter: {sa.iteration:,}  "
                f"T: {sa.T:.4f}"
            )
        else:
            self._status_var.set(
                f"Cost: {self._total_cost:.1f}  "
                f"Unroutable: {self._unroutable}  "
                f"(no SA running)"
            )

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_click(self, event: tk.Event) -> None:
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        c = int(cx // self.cell_size)
        r = int(cy // self.cell_size)
        if 0 <= r < self.rows and 0 <= c < self.cols:
            self.selected_cell = (r, c)
        else:
            self.selected_cell = None
        self._redraw()
        self._update_detail()

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.state & 0x0004:  # Ctrl held → zoom
            if event.num == 4 or event.delta > 0:
                self._zoom_in()
            else:
                self._zoom_out()
        else:
            # Scroll
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
            else:
                self.canvas.yview_scroll(int(-event.delta / 40), "units")

    def _zoom_in(self) -> None:
        if self.cell_size < CELL_SIZE_MAX:
            self.cell_size = min(CELL_SIZE_MAX, self.cell_size + 4)
            self._redraw()

    def _zoom_out(self) -> None:
        if self.cell_size > CELL_SIZE_MIN:
            self.cell_size = max(CELL_SIZE_MIN, self.cell_size - 4)
            self._redraw()

    # ── SA control ────────────────────────────────────────────────────────────

    def _toggle_sa(self) -> None:
        if self.runner.is_running():
            self.runner.stop()
            self._btn_run.config(text="▶  Run SA")
        else:
            if self.sa_state is None:
                if self.placement is None:
                    self._reset()
                self.sa_state = SAState(self.placement, self.netlist)
            self._btn_run.config(text="⏸  Pause SA")
            self.runner.start(self.sa_state, self._sa_callback)
            self._poll_sa()

    def _step_sa(self) -> None:
        if self.runner.is_running():
            return
        if self.sa_state is None:
            if self.placement is None:
                self._reset()
            self.sa_state = SAState(self.placement, self.netlist)
        for _ in range(500):
            self.sa_state.step()
        self._sync_from_sa()

    def _sa_callback(self) -> None:
        """Called from SA thread after each batch."""
        self.root.after(0, self._sync_from_sa)

    def _poll_sa(self) -> None:
        """Periodic GUI poll while SA is running."""
        self._update_status()
        if self.runner.is_running():
            self.root.after(200, self._poll_sa)
        else:
            self._btn_run.config(text="▶  Run SA")
            self._sync_from_sa()

    def _sync_from_sa(self) -> None:
        """Pull best placement from SA and refresh GUI."""
        if self.sa_state is not None:
            self.placement      = self.sa_state.placement.copy()
            self._total_cost    = self.sa_state.cost
            self._unroutable    = self.sa_state.unroutable
            _, self._per_gate_cost, _ = compute_cost(self.placement, self.netlist)
        self._update_status()
        self._redraw()
        self._update_detail()

    # ── Reset / apply grid ────────────────────────────────────────────────────

    def _reset(self) -> None:
        if self.runner.is_running():
            self.runner.stop()
        self.rows = self._rows_var.get()
        self.cols = self._cols_var.get()
        self.sa_state      = None
        self.selected_cell = None
        self.placement = greedy_placement(self.netlist, self.rows, self.cols)
        self._total_cost, self._per_gate_cost, self._unroutable = \
            compute_cost(self.placement, self.netlist)
        self._btn_run.config(text="▶  Run SA")
        self._update_status()
        self._redraw()
        self._update_detail()

    def _apply_grid_size(self) -> None:
        self._reset()

    # ── Save / Load ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        if self.placement is None:
            messagebox.showwarning("Save", "No placement to save.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="cmol_placement.json",
            title="Save Placement",
        )
        if not path:
            return
        data = {
            "placement": self.placement.to_dict(),
            "sa_stats": {
                "cost":       self._total_cost,
                "unroutable": self._unroutable,
                "iterations": self.sa_state.iteration if self.sa_state else 0,
                "temperature": self.sa_state.T if self.sa_state else None,
            } if self.sa_state else {},
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Save", f"Placement saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _load(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Placement",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if "placement" in data:
                pd = data["placement"]
            else:
                pd = data   # plain placement dict
            self.placement = Placement.from_dict(pd)
            self.rows = self.placement.grid_rows
            self.cols = self.placement.grid_cols
            self._rows_var.set(self.rows)
            self._cols_var.set(self.cols)
            if self.runner.is_running():
                self.runner.stop()
            self.sa_state = None
            self._btn_run.config(text="▶  Run SA")
            self._total_cost, self._per_gate_cost, self._unroutable = \
                compute_cost(self.placement, self.netlist)
            self._update_status()
            self._redraw()
            self._update_detail()
            messagebox.showinfo("Load", f"Placement loaded from:\n{path}")
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="CMOL-FPGA Placement Tool for the MC14500B NOR Netlist")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS,
                        help=f"Grid rows (default {DEFAULT_ROWS})")
    parser.add_argument("--cols", type=int, default=DEFAULT_COLS,
                        help=f"Grid cols (default {DEFAULT_COLS})")
    parser.add_argument("--netlist", default=NETLIST_FILE,
                        help="Path to 14500B_netlist.json")
    args = parser.parse_args()

    if not os.path.isfile(args.netlist):
        print(f"Error: netlist not found at {args.netlist}", file=sys.stderr)
        sys.exit(1)

    netlist = load_netlist(args.netlist)
    print(f"Loaded netlist: {len(netlist.gates)} gates, "
          f"{len(netlist.all_io_signals)} I/O signals")

    root = tk.Tk()
    app = CmolPlacerApp(root, netlist, rows=args.rows, cols=args.cols)
    root.mainloop()


if __name__ == "__main__":
    main()
