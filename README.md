# structure-agent

Multi-agent pipeline for high-throughput protein structure prediction and
analysis, focused on novel and metagenomic single-chain proteins — targets
where homologs and MSAs are scarce. Sequences in, structures + analysis out.

## What it does

Heterogeneous FASTA (DNA / RNA / protein, mixed quality) goes in. The
pipeline cleans and translates it to amino-acid sequences, predicts
structures with ESMFold2-Fast (single-sequence, no MSA — suited to
low-homology targets; Boltz-2 stays a documented fallback for multimers),
takes deterministic geometric and surface measurements, and writes an
interpretive report that separates what was measured from what is inferred.
The motivating use case is novel and metagenomic proteins, where sequences
arrive far faster than humans can analyse them; this repo is the automation
layer between "we have sequences" and "we have something worth reading."

## Agents

| Agent | Role | Status |
| --- | --- | --- |
| Agent 0 | Input preprocessing — FASTA cleanup, ORF selection, ESM-2 perplexity gate | Complete |
| Agent 1 | Structure prediction orchestrator — ESMFold2-Fast on Modal (single-sequence); Boltz-2 fallback for multimers | Operational |
| Agent 2 | Final stage — measurement through interpretation. Deterministic scripts measure geometry, surface, secondary structure, shape, and renders (JSON / CSV / PNG); an interpretive `SKILL.md` reads those outputs and writes the report | Complete |

Agent 2 is the end of the pipeline. The interpretation once scoped as a
separate "Agent 3" is merged into Agent 2's `SKILL.md` — one skill, one
deliverable. Homolog- and literature-grounded interpretation (Foldseek +
PubMed) is deferred to a possible separate project; it is not part of this
repo.

## Architectural rules

- **Measured vs inferred.** The report separates what was directly measured
  from what is inferred, and states "insufficient structural evidence to
  assign function" when the structure does not support a call. Fold and
  function are inference — they live in the report's prose, never as fields
  emitted by a measurement script. This boundary prevents biologically
  plausible but incorrect outputs.
- **Identity-agnostic measurement.** Filenames are opaque labels; never
  parsed for biological meaning.
- **Module independence.** Modules within an agent don't depend on each
  other's outputs.
- **Metadata passthrough.** Upstream metadata is forwarded unmodified;
  it never influences geometric measurements.
- **Errors logged, not escalated.** Full automation, no human-in-the-loop.

## Stack

Python · BioPython · orfipy · ESM-2 650M · ESMFold2-Fast · Boltz-2 ·
Modal (CPU + GPU apps) · DSSP · Mol*. Outputs: PDB / mmCIF, JSON sidecars,
CSV, PNG, markdown report.

## Pointers

- Per-agent setup and invocation: [src/agent_0/README.md](src/agent_0/README.md),
  [src/agent_1/README.md](src/agent_1/README.md),
  [src/agent_2/README.md](src/agent_2/README.md).
- Architectural rules and working style: [CLAUDE.md](CLAUDE.md).
- License: Apache 2.0 — see [LICENSE](LICENSE).
