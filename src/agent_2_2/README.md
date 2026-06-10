# Agent 2.2 — Cα backbone trace (matplotlib placeholder)

> **Status:** working. The lightweight, **system-agnostic** structure renderer —
> the fallback to use while Agent 2.1's Mol* cartoons are parked on the
> molstar-headless version issue.

A pure-Python Cα-trace renderer. It reads Cα coordinates, rotates into the
inertia eigenbasis, and draws three principal-axis 3D backbone traces with
matplotlib's Agg backend. **No GL, no Node, no Modal, no desktop program** —
`pip install biopython numpy matplotlib` and it runs anywhere (the directory
name `agent_2_2` is the package-safe form of "Agent 2.2").

## What it is — and is not

- **Is:** a quick, dependency-light structural *worm trace* — enough to see the
  fold's overall shape and (optionally) its pLDDT gradient, generated locally in
  seconds with nothing heavier than matplotlib.
- **Is not:** a cartoon. No side chains, no secondary-structure ribbons, no
  ray tracing. For publication-grade figures, use Agent 2.1 (Mol*) once its
  headless recipe is pinned.

## Why it exists

Agent 2.1 (Mol* `mvs-render`) gives the nice cartoons but needs a containerized
GL/Node stack and is currently blocked on a molstar version mismatch. Agent 2.2
is the **always-available fallback**: it satisfies the *same output contract*,
so the report embeds whichever renderer ran.

## Contract (identical to Agent 2.1)

Inputs: a PDB or mmCIF file (tolerates minimal predicted mmCIFs — reads atom
records directly, so no `_atom_site.occupancy` needed).

Outputs into `--output-dir`:
- `<stem>_axis1.png`, `<stem>_axis2.png`, `<stem>_axis3.png` — three traces
  down the long / mid / short principal axes.
- `<stem>_render_views.json` — `renderer: "matplotlib-ca-trace"`, color mode,
  Cα count, approximate dimensions, and per-view camera angles.

Because the filenames match Agent 2.1, `assemble_report.py` / `SKILL.md`
Step 4c embed these with no changes. Only one renderer should run per structure
(2.1 preferred; 2.2 when GL is unavailable).

## Usage

```bash
python render_trace.py <structure.cif|.pdb> --output-dir <dir> \
    [--color index|pLDDT] [--size 1024x1024]
```

- `--color index` (default): rainbow N→C, always meaningful.
- `--color pLDDT`: colour by the B-factor column (auto-detects 0–1 vs 0–100),
  apt for predicted structures.

CPU only. Self-contained — does not import other Agent 2 modules.
