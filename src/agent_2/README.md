# Agent 2 — Deterministic structural description

Geometric measurement and spatial-pattern description of predicted protein
structures. Consumes Agent 1 output (PDB / mmCIF + sidecar metadata) and
emits structured JSON / CSV / PNG for Agent 3 interpretation.

Operates strictly in measurement / description mode — no biological
interpretation of what structures mean.

The user-facing entry point is **Claude itself** (Claude Code in this repo,
or claude.ai with the skill installed). Claude reads `SKILL.md`, runs the
scripts in the right order, and assembles the result. Direct script
invocation exists as a debug / fallback path; it is not the primary surface.

## Scope (Zone discipline)

Per the project's architectural rules:

- **Zone 1** — direct geometric measurement. Distances, angles, RMSD,
  SASA, radius of gyration, asphericity, residue contacts.
- **Zone 2** — spatial pattern description. Secondary-structure content,
  shape classification, fold-class assignment by SS/shape signature,
  pocket composition, interaction-type counts.
- **Zone 3** — interpretation. Function inference, identity assignment,
  mechanistic reasoning. **Forbidden in Agent 2.** Lives in Agent 3.

Identity-agnostic: filenames are opaque labels. Fold classification reports
structural categories, never specific protein names.

Metadata passthrough: any sidecar metadata from Agent 1 is forwarded to
Agent 3 unmodified. It never influences geometric measurements.

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

1. **Pipeline framing is real only in Claude Code.** Agent 0 → 1 → 2 → 3
   chains via filesystem. claude.ai has no shared state across agents and
   treats Agent 2 as a standalone analyser.
2. **claude.ai gets polished deliverables for free.** PDF + React HTML
   dashboard come from built-in skills (`/mnt/skills/public/pdf/`,
   `/mnt/skills/public/frontend-design/`) that `SKILL.md` Step 9 wires
   into. In Claude Code those skills do not exist; report rendering is
   improvised in-session (e.g. inline markdown + base64-embedded PNG HTML)
   or deferred to Agent 3.
3. **Persistence inverts the iteration model.** Claude Code: outputs
   persist in the repo, re-runs are diffable, scripts are editable and
   version-controlled. claude.ai: ephemeral container — fixes evaporate at
   session end, every run starts fresh, no cross-session cache.
4. **Neither path is push-button yet.** `SKILL.md` is not symlinked under
   `.claude/skills/protein-analysis/` for Claude Code auto-discovery, and
   not packaged for claude.ai upload. Both work today only when Claude is
   pointed at `SKILL.md` explicitly.

**Practical fit:**

- *claude.ai* → ad-hoc single-structure analysis with a polished report.
- *Claude Code* → pipeline use, batch processing, iteration on the agent
  itself. No free rendering layer.

**Open question for future work.** `SKILL.md` Step 9's PDF / HTML branch
assumes the external skills exist and silently fails outside claude.ai.
Candidate fix: detect the environment and fall back to inline rendering
when the built-in skills are absent.

## Architecture

```
src/agent_2/
├── SKILL.md                          # Claude skill — orchestration decision tree
├── README.md                         # This file (agent contract)
├── scripts/
│   ├── parse_structure.py            # Structure parsing & metadata extraction
│   ├── compare_structures.py         # Multi-structure superposition & RMSD
│   ├── binding_site.py               # Ligand detection & pocket / interaction analysis
│   └── surface_analysis.py           # SASA, surface properties, shape, fold classification
└── references/
    └── interpretation_guide.md       # Passive reference for downstream (Agent 3) use
```

The four scripts are independent. They do not import each other and do not
share state. Each takes a structure file (and optional flags), emits files
into `--output-dir`, and prints a human-readable summary to stdout.

`SKILL.md` is the orchestration layer Claude follows. It is allowed to
diverge from this README — README documents the agent's contract and how
to invoke it; SKILL.md documents how a Claude session orchestrates the
internals.

`references/interpretation_guide.md` is a passive document for Agent 3 (or
a Claude session running the skill) to consult during synthesis. Agent 2's
scripts never read it.

## Inputs and outputs

**Inputs** (typical paths):

- `./data/` — ad-hoc structure files you drop in for analysis.
- `./src/agent_1/step1_results/` — predicted structures from Agent 1
  (available once Agent 1 is implemented; Agent 1 is currently designed
  but not yet coded).
- Anywhere else — point Claude at any directory containing PDB or mmCIF.

Optional sidecar metadata from Agent 1 is forwarded by the orchestrator,
not consumed by Agent 2 scripts.

**Outputs (per structure):**

- `<stem>_metadata.json` — chain inventory, residues / atoms, ligands /
  metals, AlphaFold detection, resolution, B-factor / pLDDT stats.
- `<stem>_surface_analysis.json` + `<stem>_surface.csv` +
  `<stem>_surface_profile.png` + `<stem>_exposure_pie.png` — SASA,
  hydrophobicity, charge, secondary structure, shape metrics, fold class.
- `<stem>_binding_sites.json` + per-ligand `<stem>_<lig>_<chain><resid>_pocket.csv`
  + `<stem>_<lig>_<chain><resid>_summary.png` — pocket composition and
  interaction classification (only if non-solvent ligands are present).
- `<reference_stem>_comparisons.json` + per-pair `<ref>_vs_<query>_chain<X>_deviations.csv`
  + `<ref>_vs_<query>_chain<X>_deviation.png` + `<ref>_vs_<query>_chain<X>_bfactor.png`
  — superposition stats, per-residue deviations, B-factor / pLDDT
  comparison (only if multiple structures are provided).

All plots are 300 DPI PNG. All JSON is indented for diff-friendliness.

Final report formatting (PDF, interactive HTML dashboard) is **not** produced
by Agent 2. `SKILL.md` delegates those to external Claude Code skills
(`/mnt/skills/public/pdf/`, `/mnt/skills/public/frontend-design/`) when run
in skill mode. Agent 2's contract ends at JSON / CSV / PNG.

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

### `surface_analysis.py`

```bash
python surface_analysis.py <structure_file> [--output-dir <dir>]
```

Per-residue SASA (Shrake–Rupley) and exposure classification, surface
hydrophobicity (Kyte–Doolittle), charge distribution at pH 7, hydrophobic
patch detection, secondary structure (DSSP via `mkdssp`, with PDB-record
fallback), shape metrics (radius of gyration, asphericity, principal-axis
ratios), and fold classification (SCOP class + canonical-fold matching with
SCOP / CATH IDs).

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

```bash
pip install biopython matplotlib numpy scipy pandas seaborn

# DSSP binary
apt-get install -y dssp                  # Debian / Ubuntu / Modal containers
brew install brewsci/bio/dssp            # macOS
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
3. **Per-domain fold classification.** `surface_analysis.py` averages SS
   content over the full structure (or full multi-chain complex), which is
   misleading for multi-domain or oligomeric inputs. Per-chain or
   per-domain classification needed.
4. **Skill not at an auto-discovery path.** `SKILL.md` is at
   `src/agent_2/SKILL.md`, not `.claude/skills/protein-analysis/`. Until
   symlinked or installed, Claude Code does not auto-trigger the skill on
   structure-file references — you have to point Claude at it explicitly.
