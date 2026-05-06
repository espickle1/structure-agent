# structure-agent

Multi-agent pipeline for high-throughput protein structure prediction and
analysis, focused on phage receptor-binding proteins (RBPs) and
metagenomic samples. Sequences in, structures + analysis out.

## What it does

Heterogeneous FASTA (DNA / RNA / protein, mixed quality) goes in. The
pipeline cleans and translates it, predicts structures with Boltz-2,
extracts deterministic geometric and surface measurements, and — in the
exploratory half — surfaces structural homologs and the literature that
has been published on them. The motivating use case is phage RBPs and
metagenomes, where sequences arrive far faster than humans can analyse
them; this repo is the automation layer between "we have sequences" and
"we have something worth reading."

## Architecture: Stage 1 / Stage 2

Two halves with operationally contradictory shapes, separated by a
filesystem contract (the per-batch bundle) — no shared Python imports.

- **Stage 1** (Agents 0, 1, 2). Deterministic, batch, identity-agnostic.
  Sequence in → structure + measurements out.
- **Stage 2** (Agent 3+). Interactive, identity-aware, exploratory.
  Stage 1 bundle + human input → interpretive analysis.

See [STAGE_SPLIT.md](STAGE_SPLIT.md) for the full rationale.

### Agents at a glance

| Agent | Role | Status |
| --- | --- | --- |
| Agent 0 | Input preprocessing — FASTA cleanup, ORF selection, ESM-2 perplexity gate | Complete |
| Agent 1 | Structure prediction orchestrator — Boltz-2 on Modal | Step 1 only (single-sequence proof) |
| Agent 2 | Deterministic structural description — geometry, surface, binding sites, comparison | Complete (v4.0) |
| Agent 3 | Foldseek-anchored homolog & literature retrieval | v0 designed, not coded |
| Agent 4 | Literature search (PubMed) | Scaffolded directory only |

## Zone discipline

The single most important rule for reading agent output:

- **Zone 1** — direct geometric measurement (distances, angles, RMSD, SASA).
- **Zone 2** — spatial pattern description and one-step inference from
  measurements (e.g. "asphericity > 0.30 → prolate").
- **Zone 3+** — identity-aware claims, functional inference, mechanistic
  reasoning. **Stage 2 only.** Stage 1 never produces Zone 3 output.

This boundary exists to prevent biologically plausible but incorrect
outputs from a deterministic measurement layer.

## Other architectural rules

- **Identity-agnostic in Stage 1.** Filenames are opaque labels; never
  parsed for biological meaning.
- **Module independence.** Modules within an agent don't depend on each
  other's outputs — each takes a dataclass and returns another.
- **Metadata passthrough.** Upstream metadata is forwarded unmodified;
  it never influences geometric measurements.
- **Errors logged, not escalated.** Full automation, no human-in-the-loop.

## Stack

Python · BioPython · orfipy · ESM-2 650M · Boltz-2 · Modal (CPU + GPU
apps) · DSSP · Mol*. Outputs: PDB / mmCIF, JSON sidecars, CSV, PNG,
markdown synthesis.

## Pointers

- Per-agent setup and invocation: [src/agent_0/README.md](src/agent_0/README.md),
  [src/agent_1/README_step1.md](src/agent_1/README_step1.md),
  [src/agent_2/README.md](src/agent_2/README.md).
- Stage 1 / Stage 2 design rationale: [STAGE_SPLIT.md](STAGE_SPLIT.md).
- Architectural rules and working style: [CLAUDE.md](CLAUDE.md).
- License: Apache 2.0 — see [LICENSE](LICENSE).
