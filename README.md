# structure-agent

Multi-agent pipeline for high-throughput protein structure prediction and analysis, focused on novel and metagenomic single-chain proteins — targets where homologs and MSAs are scarce.

## What it does

Sequences in, structures and structural descriptions out. The pipeline accepts heterogeneous FASTA input (DNA, RNA, or protein), normalizes it to clean amino-acid sequences, predicts 3D structures, generates deterministic structural descriptions, and surfaces relevant literature for downstream interpretation.

The bet behind the architecture: at metagenomic scale, structure *prediction* is no longer the bottleneck — interpretation is. Splitting the work across narrowly-scoped agents keeps each stage deterministic, auditable, and free of premature biological inference.

## Pipeline

```
raw FASTA
    │
    ▼
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Agent 0 │ ─▶ │ Agent 1 │ ─▶ │ Agent 2 │ ─▶ │ Agent 3 │
│ ingest  │    │ predict │    │ describe│    │ literature
└─────────┘    └─────────┘    └─────────┘    └─────────┘
    │              │              │              │
    ▼              ▼              ▼              ▼
clean AA       PDB/mmCIF      structural      ranked
FASTA +        + per-          description    reading
sidecar        prediction      JSON +          list
JSONL          JSON            PDF report
```

JSONL sidecars thread through every stage as the pipeline's metadata bus.

## The agents

**Agent 0 — input preprocessing** *(complete).*
Heterogeneous FASTA → clean amino-acid FASTA. Type detects DNA / RNA / protein, enumerates ORFs, scores them with ESM-2 650M perplexity, applies a length and ambiguity quality gate, and emits a per-record provenance sidecar. Two Modal apps (CPU fast path, GPU slow path) chained by a local orchestrator.
See [`src/agent_0/README.md`](src/agent_0/README.md).

**Agent 1 — structure prediction** *(engine validated; batch orchestrator built, live run pending).*
ESMFold2-Fast on Modal — single-sequence, no MSA — purpose-built for novel, metagenomic, and low-homology targets. On the 6EQE PETase benchmark it reaches **0.91 Å Cα RMSD from a bare sequence** (vs 7.85 Å for single-sequence Boltz-2). A batch orchestrator consumes Agent 0's `cleaned.faa` + `sidecar.jsonl`, fans folds across a warm-model Modal app, and emits confidence-annotated `structures.jsonl` — every fold is kept and tagged with a pLDDT tier, never rejected on quality. A live batch run on Modal is the next checkpoint. The prior Boltz-2 Step 1 is kept as a documented fallback under `boltz_fallback/`.
See [`src/agent1/`](src/agent1/) — orchestrator, fold app, and the ESMFold2 eval; Boltz fallback in [`src/agent1/boltz_fallback/`](src/agent1/boltz_fallback/).

**Agent 2 — structural description** *(complete, v3).*
Identity-agnostic, deterministic structural analysis. Parses PDB / mmCIF, computes SASA, secondary structure, fold class, shape metrics, ligand pockets and interactions, and multi-structure superposition / RMSD. Halts on predominantly disordered inputs. CPU-only Claude skill — no GPU, no biological identity inference.
See [`src/agent_2/README.md`](src/agent_2/README.md) and [`src/agent_2/SKILL.md`](src/agent_2/SKILL.md).

**Agent 3 — literature retrieval** *(v0).*
Foldseek hits in, ranked PubMed reading list out. Resolves PDB / UniProt anchors, runs a single combined-anchor PubMed search, attributes papers to anchors, and ranks by anchor depth × TM-score. Structural-feature query construction and the SUBJECT framework are deferred.
See [`src/agent_3/AGENT.foldseek-literature-retrieval.md`](src/agent_3/AGENT.foldseek-literature-retrieval.md).

## Architectural principles

These rules are non-negotiable across all four agents and shape what each one will and won't produce.

- **Zone discipline.** Zone 1 is direct geometric measurement, Zone 2 is spatial pattern description, Zone 3+ is interpretation. Agents 0–2 never produce Zone 3 output. The boundary exists to prevent biologically plausible but incorrect outputs from leaking into downstream stages.
- **Identity-agnostic Phase 1.** Filenames are opaque labels. No agent parses them for biological meaning. Identity inference, if it happens at all, happens later and explicitly.
- **Module independence.** Modules within an agent operate on dataclass inputs and outputs only — they never read each other's internal state.
- **Metadata passthrough.** Upstream metadata flows through unmodified. It never influences geometric measurements.
- **Errors are logged, not escalated.** Full automation; no human-in-the-loop intervention inside the pipeline.

## Stack

- **Language:** Python 3.10+
- **Bio libraries:** BioPython, orfipy, DSSP
- **Models:** ESM-2 650M (Agent 0 perplexity scoring), ESMFold2-Fast (Agent 1 prediction)
- **Compute:** Modal — CPU fast app + GPU slow app for Agent 0; H100 for Agent 1
- **Outputs:** PDB / mmCIF, JSONL sidecars, PDF reports

## Repository layout

```
structure-agent/
├── DIRECTIONS.md             # How to deploy and run — start here
├── LICENSE
├── README.md                 # This file
├── data/                     # Local data dir (untracked)
└── src/
    ├── agent0/               # Input preprocessing
    ├── agent1/               # Structure prediction (ESMFold2-Fast)
    ├── agent_2/              # Structural description skill
    └── agent_3/              # Literature retrieval agent
```

Each agent ships its own README / SKILL / AGENT document with the operational detail.

## Status

| Agent   | Status                  | Next milestone                                       |
|---------|-------------------------|------------------------------------------------------|
| Agent 0 | Complete                | Threshold calibration on real data                   |
| Agent 1 | Engine validated; batch orchestrator built | Live batch run on Modal; confidence-tier calibration            |
| Agent 2 | Complete (v3)           | Per-domain fold classification for oligomers         |
| Agent 3 | v0                      | Structural-feature query construction; bioRxiv coverage |

Three Agent 0 thresholds (`PERPLEXITY_REJECT_ABOVE`, `PERPLEXITY_TIE_FRACTION`, `NUCLEOTIDE_PURITY_MIN`) ship with placeholder values. Calibrate before production.

## Running it

See [`DIRECTIONS.md`](DIRECTIONS.md).

## License

See [`LICENSE`](LICENSE).
