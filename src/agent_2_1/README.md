# Agent 2.1 — Structure rendering (Mol\*)

> **Status:** designed; spec only. The rendering code already exists under Agent 2
> (`agent_2/scripts/render_views.py`, `agent_2/modal_app.py`, and the
> `agent_2/agent_2_web_handoff.py` "self-contained Modal app" sketch) and is wired
> into `agent_2/SKILL.md` Step 4c. This directory will hold that code once the
> reorg below is approved. **No files have been moved yet.**

Aesthetic structure visualization for Agent 2 reports — publication-quality
Mol\* cartoon renders. The directory name `agent_2_1/` is the package-safe form of
the display name "Agent 2.1" (a dot can't be a Python package name).

## What it is — and what it is not

- **Is:** a *presentation* service. It draws a picture of coordinates that Agent 2
  already measured.
- **Is not:** a measurement step. It produces **no Zone 1 / Zone 2 output** — no
  geometry, no fold call, nothing that feeds analysis. A render is a view, not a
  finding. (This is why it sits *beside* Agent 2, not inside its measurement core.)

## Why separate from Agent 2

1. **Dependency isolation.** Rendering needs Node 20 + the `molstar` npm package
   (`mvs-render`) + `molviewspec` + headless GL (`libgl1`, `libglu1-mesa`,
   `libxi6`, `libxext6`) — a heavy, Linux-bound, GL-dependent stack. Core Agent 2
   is CPU-only stdlib + BioPython and runs anywhere (incl. local macOS). Keeping
   the GL/Node stack out of the core is exactly why the core ran end-to-end
   locally while only the renders were unavailable.
2. **Presentation vs. measurement.** Distinct concern, distinct failure mode,
   distinct cadence. Aesthetics iterate independently of the deterministic
   measurement contract.
3. **Already decoupled in practice.** Renders soft-fail today; Agent 2's report
   degrades gracefully without them. Naming the boundary makes the existing
   contract explicit.

## Inputs

- A structure file (PDB / mmCIF) — typically Agent 1's predicted CIF, or any
  structure Agent 2 is analysing.
- Optional: `--color {pLDDT,chain}` (default `pLDDT`, read from the B-factor
  column), `--size <W>x<H>` (default `1024x1024`).

## Outputs (the contract Agent 2 consumes)

Written into the shared results directory, keyed by structure stem:

- `<stem>_axis1.png`, `<stem>_axis2.png`, `<stem>_axis3.png` — three cartoon
  views down the long / mid / short principal (inertia) axes.
- `<stem>_render_views.json` — camera parameters, per-axis dimensions, color mode.
- On failure: a log under `render_failures/<stem>/<view>.{mvsj,error}`; the run
  still returns success. **Renders are optional by contract.**

## Contract with Agent 2 (unchanged by this split)

- **Filesystem handoff only.** Agent 2.1 writes PNGs + JSON into the results dir.
  No in-process import from Agent 2 into Agent 2.1.
- Agent 2's `assemble_report.py` and `SKILL.md` Step 4c **embed the axis PNGs by
  relative path when present**, and print **"Renders unavailable for `<stem>`"**
  when absent. Agent 2 never depends on Agent 2.1 succeeding — so a missing GL
  stack degrades the report, it does not break the pipeline.

## Runtime & deployment

Renders require Linux + GL, so the home is a **Modal** container — **not**
local macOS (GL is the sticking point there).

- **Modal (production / batch):** deploy the rendering app and fan structures
  across it with `.map()` over a Volume of CIFs. (Consolidated from
  `agent_2/modal_app.py` + the `agent_2_web_handoff.py` container recipe:
  Debian + Node 20 + `molstar` + `molviewspec` + `gemmi` + `numpy`.)
- **Local debug (Linux with the GL/Node stack only):**
  ```bash
  python render_views.py <structure.cif> --output-dir <dir> \
      [--color pLDDT|chain] [--size 1024x1024]
  ```

Fixed parameters (from `render_views.py`): 30° vertical FOV for camera distance,
1024×1024, 60 s `mvs-render` timeout per view, minimum 10 Cα atoms.

## Proposed layout & reorg (awaiting approval — not yet executed)

```
src/agent_2_1/
├── README.md          # this spec
├── render_views.py    # MOVE from agent_2/scripts/render_views.py  (the Mol* renderer)
└── modal_app.py       # MOVE from agent_2/modal_app.py             (Modal batch wrapper)
```

Reconcile `agent_2/agent_2_web_handoff.py` (the "Agent 2.1 as a self-contained
Modal app" sketch) into `modal_app.py` — keep one Modal entry point, not two.

Edits the move requires:
- `modal_app.py`: update the render-views import (currently
  `from agent_2.scripts.render_views import render_structure`) to the new path,
  and any `add_local_python_source(...)` argument.
- `agent_2/SKILL.md` Step 4c: update the invocation path
  (`python scripts/render_views.py …` → the `agent_2_1/` location).
- `agent_2/README.md` file tree: drop `render_views.py` from `agent_2/scripts/`
  and point to Agent 2.1.

Modal **app names are left untouched** (e.g. `agent_2-render`) per the
`STAGE_SPLIT.md` rule — directory/branding changes don't rename deployed apps.

## Note on STAGE_SPLIT.md

`STAGE_SPLIT.md` lists `render_views.py` as staying inside Agent 2's four/five
scripts. Splitting it into Agent 2.1 is a **deliberate divergence** — it treats
rendering as a presentation service distinct from the measurement layer, which is
consistent with that document's own framing of report formatting as
presentation. Worth reconciling with the collaborator when `stage-separation`
and `main` are merged.

## Out of scope

- Interactive viewers / HTML dashboards (separate concern).
- Any measurement, fold call, or Zone 1–2 output.
- Re-deriving camera geometry from Agent 2 output — `render_views.py` computes its
  own inertia-axis cameras and reads only the structure file.
