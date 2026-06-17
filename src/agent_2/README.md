# Agent 2 — Measurement through interpretation

The final stage of the pipeline. Consumes Agent 1 output (PDB / mmCIF +
sidecar metadata), takes deterministic geometric and surface measurements,
and writes an interpretive report from them.

Two layers with a hard boundary between them: the **scripts** measure and
describe only — no biological interpretation of what structures mean — while
the **`SKILL.md` synthesis** interprets the measurements into prose. Fold and
function are inference; they appear only in that prose, never as fields a
script emits.

The user-facing entry point is **Claude itself** (Claude Code in this repo,
or claude.ai with the skill installed). Claude reads `SKILL.md`, runs the
scripts in the right order, and assembles the result. Direct script
invocation exists as a debug / fallback path; it is not the primary surface.

## Scope

Per the project's architectural rules:

- **Scripts measure and describe.** Distances, angles, RMSD, SASA, radius of
  gyration, asphericity, residue contacts; and one step up — secondary-structure
  content, shape classification, pocket composition, interaction-type counts.
- **The SKILL synthesis interprets.** Fold-level character, function, identity,
  and mechanism are inference. They appear only in the report's prose, derived
  from and cited to the measurements — never as a field a measurement script
  emits. When the structure does not support a call, "insufficient structural
  evidence to assign function" is a valid, expected conclusion.

Identity-agnostic: filenames are opaque labels, never parsed for biological
meaning.

Metadata passthrough: any sidecar metadata from Agent 1 is forwarded
unmodified. It never influences geometric measurements.

Errors are logged, not escalated. No human-in-the-loop.

## How to run

### Claude Code (in this repo)

The intended workflow:

1. Open Claude Code at the repo root.
2. Ask Claude to analyse a directory of structures, e.g.:

   > "Run Agent 2 on `./data/`."
   > "Analyse the structures in `./src/agent_1/step1_results/`."
   > "Use `src/agent_2/SKILL.md` to analyse the `.cif` files in `./inputs/`."

3. Claude reads `src/agent_2/SKILL.md`, follows its decision tree, runs
   the four scripts on each structure, and presents the assembled result.

The skill currently lives inside the codebase at `src/agent_2/SKILL.md`,
not at a Claude-Code-auto-discovery path. Until that changes, the skill
will not auto-trigger on uploads or keywords — you have to point Claude at
it once per session (or install it; see below).

**Optional — make the skill auto-discoverable in this repo:**

```bash
mkdir -p .claude/skills
ln -s ../../src/agent_2 .claude/skills/protein-analysis
```

After this, opening Claude Code in the repo root will surface the skill
automatically on any `.pdb` / `.cif` / `.mmcif` reference or relevant
keywords (binding pocket, RMSD, AlphaFold, pLDDT, etc. — see the trigger
list in `SKILL.md`).

### claude.ai

Package `src/agent_2/` (the `SKILL.md`, `scripts/`, and `references/`
subtree) and install it as a skill in your claude.ai workspace. Then:

1. Upload one or more structure files in a conversation.
2. The skill auto-triggers on `.pdb` / `.cif` / `.mmcif` extensions or on
   keywords like "binding pocket", "superposition", "AlphaFold".
3. The skill installs Python dependencies in the ephemeral container at
   runtime, runs the scripts, and assembles the result.

DSSP (`mkdssp`) is required for secondary-structure assignment in
`surface_analysis.py`. Confirm the runtime container has it before relying
on the claude.ai path.

### Direct CLI (debug / fallback)

You can run any script by hand without Claude in the loop. This is for
debugging, scripting, or one-off use; it bypasses the orchestration in
`SKILL.md` (no disorder gate, no multi-structure routing, no validation).
Per-script signatures are documented in §Internals below.

```bash
python src/agent_2/scripts/parse_structure.py ./data/example.cif --output-dir ./out
```

## Environment differences — claude.ai vs Claude Code

Same `SKILL.md`, same scripts, different runtime. Deltas worth remembering
before picking a path:

1. **Pipeline framing is real only in Claude Code.** Agent 0 → 1 → 2
   chains via filesystem. claude.ai has no shared state across agents and
   treats Agent 2 as a standalone analyser.
2. **Report rendering is identical in both.** Step 9 emits a self-contained
   markdown report (`scripts/assemble_report.py` + in-session synthesis) with
   no dependency on claude.ai's built-in PDF / `frontend-design` skills. The
   old claude.ai-only "polished deliverable" asymmetry is gone.
3. **Persistence inverts the iteration model.** Claude Code: outputs
   persist in the repo, re-runs are diffable, scripts are editable and
   version-controlled. claude.ai: ephemeral container — fixes evaporate at
   session end, every run starts fresh, no cross-session cache.
4. **Neither path is push-button yet.** `SKILL.md` is not symlinked under
   `.claude/skills/protein-analysis/` for Claude Code auto-discovery, and
   not packaged for claude.ai upload. Both work today only when Claude is
   pointed at `SKILL.md` explicitly.

**Practical fit:**

- *claude.ai* → ad-hoc single-structure analysis.
- *Claude Code* → pipeline use, batch processing, iteration on the agent
  itself. Same self-contained markdown report either way.

**Resolved.** Step 9 previously assumed claude.ai's external PDF/HTML skills and
silently failed elsewhere; it now emits self-contained markdown via
`scripts/assemble_report.py`, produced identically in Claude Code and claude.ai.

## Architecture

```
src/agent_2/
├── SKILL.md                          # Claude skill — orchestration decision tree
├── README.md                         # This file (agent contract)
├── modal_app.py                      # Modal wrapper for batch rendering on /scratch
├── scripts/
│   ├── parse_structure.py            # Structure parsing & metadata extraction
│   ├── compare_structures.py         # Multi-structure superposition & RMSD
│   ├── binding_site.py               # Ligand detection & pocket / interaction analysis
│   ├── surface_analysis.py           # SASA, surface properties, secondary structure, shape
│   ├── render_views.py               # Mol* cartoon renders (Agent 2.1; blocked on #18)
│   ├── render_trace.py               # Cα-trace figures (Agent 2.2; matplotlib, no GL — active renderer)
│   └── assemble_report.py            # Deterministic markdown report (facts + figures + profile matrix)
└── references/
    ├── interpretation_guide.md       # Passive reference for the SKILL synthesis
    └── profiles/                     # Optional expected-parameter profiles (+ schema README)
```

The scripts are independent. They do not import each other and do not
share state. Each takes a structure file (and optional flags), emits files
into `--output-dir`, and prints a human-readable summary to stdout.

`SKILL.md` is the orchestration layer Claude follows. It is allowed to
diverge from this README — README documents the agent's contract and how
to invoke it; SKILL.md documents how a Claude session orchestrates the
internals.

`references/interpretation_guide.md` is a passive document the Claude session
running the skill consults during synthesis. Agent 2's scripts never read it.

## Inputs and outputs

**Inputs** (typical paths):

- `./data/` — ad-hoc structure files you drop in for analysis.
- `./src/agent_1/step1_results/` — predicted structures from Agent 1
  (ESMFold2-Fast; one CIF per folded record).
- Anywhere else — point Claude at any directory containing PDB or mmCIF.
- *(optional)* expected-parameter profiles from `references/profiles/` — pass
  one or more to flag deviations against an explicit baseline (see that dir's
  README).

Optional sidecar metadata from Agent 1 is forwarded by the orchestrator,
not consumed by Agent 2 scripts.

**Outputs (per structure):**

- `<stem>_metadata.json` — chain inventory, residues / atoms, ligands /
  metals, AlphaFold detection, resolution, B-factor / pLDDT stats.
- `<stem>_surface_analysis.json` + `<stem>_surface.csv` +
  `<stem>_surface_profile.png` + `<stem>_exposure_pie.png` — SASA,
  hydrophobicity, charge, secondary structure, shape metrics.
- `<stem>_binding_sites.json` + per-ligand `<stem>_<lig>_<chain><resid>_pocket.csv`
  + `<stem>_<lig>_<chain><resid>_summary.png` — pocket composition and
  interaction classification (only if non-solvent ligands are present).
- `<reference_stem>_comparisons.json` + per-pair `<ref>_vs_<query>_chain<X>_deviations.csv`
  + `<ref>_vs_<query>_chain<X>_deviation.png` + `<ref>_vs_<query>_chain<X>_bfactor.png`
  — superposition stats, per-residue deviations, B-factor / pLDDT
  comparison (only if multiple structures are provided).
- `<stem>_render_views.json` + `<stem>_axis{1,2,3}.png` — three axis-aligned
  cartoon views (down long / mid / short principal axis) and a sidecar with
  camera parameters and color mode. Soft-fails: a missing render is logged
  to `render_failures/<stem>/<view>.{mvsj,error}` and the pipeline continues.

- `<stem>_analysis.md` — the markdown analysis report. `scripts/assemble_report.py`
  fills it with deterministic facts, embedded figures, the prediction-quality /
  coherence signals, and an expected-parameter comparison matrix; the Claude
  session then fills the marked synthesis sections (executive summary,
  independent observations, coherence assessment, "what cannot be determined"),
  each claim cited to a measurement.

All plots are 300 DPI PNG. All JSON is indented for diff-friendliness.

Report formatting is **self-contained markdown** — no PDF/HTML or external-skill
dependency, identical in Claude Code and claude.ai. (An optional PDF is a
separate render step if ever wanted; the embedded figures carry over.)

## Internals — per-script reference

You normally do not invoke these directly. `SKILL.md` runs them on your
behalf. Documented here so you can audit what the orchestrator is doing,
or invoke a single script for debugging.

### `parse_structure.py`

```bash
python parse_structure.py <structure_file> [--output-dir <dir>]
```

Reads PDB or mmCIF. Auto-detects format and AlphaFold predictions
(heuristic: filename + B-factor distribution + missing resolution).

**Outputs:** `<stem>_metadata.json` + human-readable summary to stdout.

### `compare_structures.py`

```bash
python compare_structures.py <reference> <query1> [<query2> ...] [--output-dir <dir>]
```

Greedy chain matching by sequence length (5 % tolerance, ties broken by
sequence identity), Cα superposition via SVD, per-residue deviation
profile, high-deviation region detection (contiguous stretches above
2.0 Å), B-factor / pLDDT comparison plots.

**Outputs:** `<reference_stem>_comparisons.json` + per matched chain per
query: `<ref>_vs_<query>_chain<X>_deviations.csv`,
`<ref>_vs_<query>_chain<X>_deviation.png`,
`<ref>_vs_<query>_chain<X>_bfactor.png`.

### `binding_site.py`

```bash
python binding_site.py <structure_file> [--output-dir <dir>] \
                       [--cutoff <Å>] [--exclude-ligands HOH,SO4,...]
```

Finds non-solvent ligands, defines pockets via KD-tree neighbour search at
`--cutoff` (default 5.0 Å), classifies interactions (H-bond, salt bridge,
hydrophobic contact, π-stack), computes pocket composition by chemical
class.

**Flags:**

- `--cutoff <float>` — pocket definition radius in Å (default 5.0).
  Phase-1 default; override only for Phase-2 / bespoke work.
- `--exclude-ligands HOH,SO4,...` — comma-separated residue names to add
  to the built-in exclusion list (see §Fixed parameters).

**Outputs:** `<stem>_binding_sites.json` + per ligand:
`<stem>_<lig>_<chain><resid>_pocket.csv`,
`<stem>_<lig>_<chain><resid>_summary.png`.

### `render_views.py`

```bash
python render_views.py <structure_file> [--output-dir <dir>] \
                       [--color {pLDDT,chain}] [--size 1024x1024]
```

Three axis-aligned cartoon renders driven by Mol* (`mvs-render`) with
molviewspec-built scenes. Camera vectors come from the inertia tensor of
the Cα coordinates (long / mid / short principal axes); the script computes
them itself and does not consume any other Agent 2 output.

Default coloring is pLDDT via the mmCIF `atom_site.B_iso_or_equiv` field
(matches Boltz-2 outputs). `--color chain` switches to a per-chain palette.

**Flags:**

- `--color {pLDDT,chain}` — coloring scheme (default `pLDDT`).
- `--size <W>x<H>` — image size in pixels (default `1024x1024`).

**Outputs:** `<stem>_render_views.json` + `<stem>_axis1.png`,
`<stem>_axis2.png`, `<stem>_axis3.png`. Per-view failures land in
`render_failures/<stem>/<view>.{mvsj,error}` and do not stop the run.

**Fixed parameters:** 30° vertical FOV (15° half-angle) for camera distance,
1024×1024 image size, 60 s mvs-render timeout per view, minimum 10 Cα atoms.

### `render_trace.py`

```bash
python render_trace.py <structure_file> [--output-dir <dir>] \
                       [--color {index,pLDDT}] [--size 1024x1024]
```

Agent 2.2 — the system-agnostic figure renderer and the active default while
`render_views.py` (Agent 2.1, Mol\*) is blocked on #18. Reads Cα coordinates
directly (tolerates minimal predicted mmCIFs — no occupancy needed), rotates
into the inertia eigenbasis, and draws three principal-axis backbone traces
with matplotlib's Agg backend. **Pure Python — no GL / Node / Mol\*** — so it
runs locally on any machine and inside the Modal image unchanged. Self-contained:
imports no other Agent 2 module. Same output contract as `render_views.py`, so
the report (`views_section` in `assemble_report.py`) embeds whichever ran and
captions it by the `renderer` field of the sidecar.

**Outputs:** `<stem>_render_views.json` (with `renderer: "matplotlib-ca-trace"`)
+ `<stem>_axis1.png`, `<stem>_axis2.png`, `<stem>_axis3.png`.

### `surface_analysis.py`

```bash
python surface_analysis.py <structure_file> [--output-dir <dir>]
```

Per-residue SASA (Shrake–Rupley) and exposure classification, surface
hydrophobicity (Kyte–Doolittle), charge distribution at pH 7, hydrophobic
patch detection, secondary structure (DSSP via `mkdssp`, with PDB-record
fallback), and shape metrics (radius of gyration, asphericity, principal-axis
ratios).

**Outputs:** `<stem>_surface_analysis.json`, `<stem>_surface.csv`,
`<stem>_surface_profile.png`, `<stem>_exposure_pie.png`.

## Fixed parameters

Phase 1 parameters are fixed. Per-run overrides exist only where a flag is
documented above (`binding_site.py --cutoff`, `--exclude-ligands`).
Parameter sweeps are Phase-2 / bespoke work, not Agent 2's concern.

| Parameter                | Value  | Source                                |
| ------------------------ | ------ | ------------------------------------- |
| Pocket cutoff            | 5.0 Å  | `binding_site.py:75` `POCKET_CUTOFF`  |
| H-bond distance          | 3.5 Å  | `binding_site.py:71` `HBOND_DIST_CUTOFF` |
| Salt bridge distance     | 4.0 Å  | `binding_site.py:72` `SALT_BRIDGE_CUTOFF` |
| Hydrophobic contact      | 4.5 Å  | `binding_site.py:73` `HYDROPHOBIC_CUTOFF` |
| π-stack centroid         | 5.5 Å  | `binding_site.py:74` `PI_STACK_CUTOFF` |
| High-deviation threshold | 2.0 Å  | `compare_structures.py:54` `DEVIATION_THRESHOLD` |
| Chain-match tolerance    | 5 %    | `compare_structures.py:118` `length_tolerance` |
| Disorder gate signals    | structural only | SS content, SASA, shape, missing residues — **never** pLDDT or B-factor |
| Disulfide bonds          | not detected | by design; not reported in any output |

### Ligand exclusion list

Residues skipped by ligand analysis by default (in `parse_structure.py` and
`binding_site.py`):

- **Water**: HOH, WAT, H2O, DOD
- **Common ions / metals**: NA, CL, K, CA, MG, ZN, FE, MN, CO, CU, NI, CD,
  SO4, PO4, NO3
- **Crystallisation additives**: GOL, EDO, PEG, PGE, MPD, DMS, ACT, FMT,
  TRS, CIT, BME, EOH, IMD, EPE, MES, IPA, CAC
- **Buffer components**: HED, TAR, MLI, BIG, BCT
- **Unknowns**: UNX, UNL, UNK

Extend per-run via `binding_site.py --exclude-ligands` (or ask Claude to
extend the list).

## Dependencies

When run via Claude (Claude Code or claude.ai), `SKILL.md` installs
dependencies on first use. For direct CLI use you install them yourself:

- Python 3.10+
- `biopython`, `numpy`, `scipy`, `pandas`, `matplotlib`, `seaborn`
- `mkdssp` (DSSP binary) for secondary structure assignment
- `molviewspec` (Python) and `mvs-render` (Mol* CLI, shipped with the
  `molstar` npm package) for `render_views.py` (Agent 2.1). Headless GL libs
  (`libgl1`, `libglu1-mesa`, `libxi6`, `libxext6`) are required on Linux
  containers.
- `render_trace.py` (Agent 2.2) needs **none** of the Mol\*/GL stack — only
  `matplotlib` (listed above). It is the active renderer until Agent 2.1's
  Mol\* path is unblocked, and runs anywhere (local or the Modal image).

```bash
pip install biopython matplotlib numpy scipy pandas seaborn molviewspec

# DSSP binary
apt-get install -y dssp                  # Debian / Ubuntu / Modal containers
brew install brewsci/bio/dssp            # macOS

# Mol* CLI for render_views.py
apt-get install -y nodejs npm libgl1 libglu1-mesa libxi6 libxext6   # Debian / Ubuntu
npm install -g molstar                                              # provides mvs-render
```

CPU only — no GPU required for any Agent 2 script.

## Known limitations / open questions

1. **Multiple-protein interface analysis.** Inter-chain interfaces in
   oligomeric complexes are not currently treated as binding sites. Decision
   logic still owed.
2. **Chain-matching tolerance is brittle.** The 5 % length tolerance fails
   when signal peptides, expression tags, or unresolved termini cause
   length mismatch between otherwise-identical chains. Pairwise sequence
   alignment fallback should be added in `compare_structures.py:match_chains`.
3. **Whole-structure SS averaging.** `surface_analysis.py` averages
   secondary-structure content over the full structure (or full multi-chain
   complex), which is misleading for multi-domain or oligomeric inputs. The
   synthesis should segment by chain or domain rather than reading the
   whole-chain fractions as one number.
4. **Skill not at an auto-discovery path.** `SKILL.md` is at
   `src/agent_2/SKILL.md`, not `.claude/skills/protein-analysis/`. Until
   symlinked or installed, Claude Code does not auto-trigger the skill on
   structure-file references — you have to point Claude at it explicitly.
