# structure-agent

Multi-agent pipeline for high-throughput protein structure prediction and
analysis, focused on phage receptor-binding proteins (RBPs) and metagenomic
samples. Sequences in, structures + analysis out.

## Two stages

The pipeline splits into two operationally distinct halves under `src/`.
They share a repo and a filesystem; they do **not** share Python imports.
Communication is by filesystem artifacts only.

### Stage 1 — deterministic prediction + measurement

`src/stage_1/`. Identity-agnostic, batch-shaped. Sequence in → structure +
geometric measurements out.

| Agent | Status | Role |
|---|---|---|
| `agent_0` | complete | heterogeneous nucleotide / protein FASTA → clean amino-acid FASTA + provenance metadata. Stack: BioPython, orfipy, ESM-2 650M, Modal (CPU fast app + GPU slow app). |
| `agent_1` | designed, not yet coded | structure prediction orchestrator. Boltz-2 production, ESMFold cheap pre-screen, quality-gates, hands coordinates + metadata to agent_2. |
| `agent_2` | complete (v4.0) | deterministic structural description. Final node of Stage 1. Geometric measurements (SASA, RMSD, asphericity, residue contacts) and spatial-pattern description (secondary structure, fold class, pocket composition) only. Emits the **Stage 1 bundle**: `<batch_id>_stage1_synthesis.md` plus structured JSON / CSV / PNG. |

### Stage 2 — interpretation

`src/stage_2/`. Identity-aware, exploratory. Stage 1 bundle + human input →
interpretive analysis.

| Agent | Status | Role |
|---|---|---|
| `agent_3` | designed v0, scope being revised | structural-element inference and Foldseek-anchored homolog retrieval. Resolves anchors with per-anchor metadata for hand-off to agent_4. |
| `agent_4` | not started | literature search, ranking, summarization keyed to agent_3's anchors. Produces a ranked reading list with per-paper attribution. |

See `src/stage_2/README.md` for the Stage 1 → Stage 2 contract.

## Architectural rules — non-negotiable

- **Zone discipline.** Zone 1 = direct geometric measurement. Zone 2 =
  spatial pattern description (including direct mappings from
  `references/interpretation_guide.md`). Zone 3+ = interpretation. Stage 1
  NEVER produces Zone 3 output. This boundary exists to prevent
  biologically plausible but incorrect outputs.
- **Identity-agnostic in Phase 1.** Filenames are opaque labels. They are
  never parsed for biological meaning.
- **Module independence.** Modules within an agent must not depend on each
  other's outputs.
- **Metadata passthrough.** Upstream metadata is forwarded unmodified; it
  never influences geometric measurements.
- **Errors are logged, not escalated.** Full automation — no
  human-in-the-loop intervention.

## Stack

- **Languages**: Python 3.10+; some Node.js for Mol\* rendering
  (`mvs-render`).
- **Bio**: BioPython, orfipy, ESM-2 650M, DSSP (`mkdssp`), molviewspec.
- **Structure prediction**: Boltz-2 (production), ESMFold (cheap CPU
  pre-screen).
- **Compute**: Modal (serverless GPU + CPU; CPU fast apps + GPU slow apps
  chained by orchestrator).
- **Analysis**: NumPy, SciPy, pandas, matplotlib, seaborn.
- **Outputs**: PDB / mmCIF, JSON sidecars, CSV, 300 DPI PNG figures, and
  the Stage 1 synthesis markdown.

## Repo layout

```
structure-agent/
├── CLAUDE.md                 # project instructions for Claude Code
├── STAGE_SPLIT.md            # rationale for the Stage 1 / Stage 2 boundary
├── data/                     # ad-hoc inputs
├── src/
│   ├── stage_1/
│   │   ├── agent_0/          # FASTA cleaning + translation
│   │   ├── agent_1/          # Boltz-2 structure prediction (designed)
│   │   └── agent_2/          # structural description + Stage 1 synthesis
│   │       ├── SKILL.md           # orchestration decision tree (Claude skill)
│   │       ├── scripts/           # parse, compare, binding_site, surface, render
│   │       ├── references/        # interpretation_guide.md
│   │       └── modal_app.py       # batch render on Modal
│   └── stage_2/
│       ├── agent_3/          # structural-element inference, Foldseek anchors (designed)
│       └── agent_4/          # literature search (not started)
└── README.md                 # this file
```

## Running

The pipeline runs primarily on [Modal](https://modal.com). Each agent's
`modal_app.py` is deployed independently and chained via Modal's named
`App`s and shared `Volume`s.

### Stage 1 quick start

```bash
# From the repo root, with .venv activated:
cd src/stage_1

# Deploy each Modal app (one-time per change):
modal deploy agent_0/modal_app.py
modal deploy agent_2/modal_app.py
# agent_1 deploy command lands when agent_1 is implemented

# Run agent_0 over a FASTA:
python agent_0/orchestrator.py <input.fasta> [...]

# Agent 2 is invoked by Claude reading src/stage_1/agent_2/SKILL.md.
# See src/stage_1/agent_2/README.md for the entry points.
```

### Local tests

```bash
cd src/stage_1
python -m pytest agent_0/test_fast_path.py -v
```

### Stage 2

Stage 2 reads the Stage 1 bundle written under `results/` (or whatever
output directory Stage 1 used). agent_3 and agent_4 are still under design;
see their READMEs for current scope.

## Working style

- Prefer agent judgment over rigid schemas. Trim features to minimum
  viable scope; defer threshold calibration to real-data testing.
- Push back on over-engineering, unnecessary dependencies, premature
  abstraction, and premature interpretation. No tests, deps, or scope
  added unless asked.
- When a biological error is identified, revise fully — no patching
  around it.

## Further reading

- `CLAUDE.md` — project instructions, architectural rules, stack notes.
- `STAGE_SPLIT.md` — rationale for the Stage 1 / Stage 2 split.
- `src/stage_1/agent_0/README.md` — agent_0 entry points and verdict
  semantics.
- `src/stage_1/agent_2/README.md` — agent_2 contract, scripts, outputs.
- `src/stage_1/agent_2/SKILL.md` — Claude orchestration decision tree.
- `src/stage_2/README.md` — Stage 1 → Stage 2 contract.
