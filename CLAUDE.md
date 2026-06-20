# CLAUDE.md

APSARA (Automated Protein Structure Analysis & Reporting Agent) is a multi-agent pipeline for high-throughput protein structure prediction and analysis, focused on novel and metagenomic single-chain proteins — targets where homologs and MSAs are scarce. Sequences in, structures + analysis out.

## Agents

- **Agent 0** (complete): heterogeneous nucleotide/protein FASTA → clean amino acid FASTA + provenance metadata. Stack: BioPython, orfipy, ESM-2 650M, Modal (CPU fast app + GPU slow app).
- **Agent 1** (operational): structure prediction orchestrator. Folds single sequences with ESMFold2-Fast (no MSA) on Modal, annotates a mean-pLDDT confidence tier (never gates on quality), hands coordinates + metadata to Agent 2. Boltz-2 retained as a documented fallback for multimers (`src/agent_1/boltz_fallback/`).
- **Agent 2** (complete): the final stage — measurement through interpretation. Deterministic scripts measure geometry, surface, secondary structure, shape, and renders (JSON/CSV/PNG); an interpretive SKILL (`src/agent_2/SKILL.md`) reads those outputs and writes the markdown report.
- **Agent 3**: not a separate module. Interpretation was merged into Agent 2's SKILL — nothing to build here.

## Architectural rules — non-negotiable

- **Measured vs inferred.** The report separates what was directly measured from what is inferred, and states "insufficient structural evidence to assign function" when the structure doesn't support a call. Fold and function are inference — they belong in the report's prose, never as fields emitted by a measurement script. This boundary exists to prevent biologically plausible but incorrect outputs.
- **Identity-agnostic in Phase 1.** Filenames are opaque labels. Never parse them for biological meaning.
- **Module independence.** Modules within an agent must not depend on each other's outputs.
- **Metadata passthrough.** Upstream metadata is forwarded unmodified; it never influences geometric measurements.
- **Errors are logged, not escalated.** Full automation — no human-in-the-loop intervention.

## Working style

- Prefer agent judgment over rigid schemas. Trim features to minimum viable scope; defer threshold calibration to real-data testing.
- Push back on over-engineering, unnecessary dependencies, premature abstraction, or premature interpretation. Don't add tests, deps, or scope unless asked.
- When I correct a biological error, revise fully — don't patch around it.

## Stack

- Python; BioPython, orfipy, ESM-2 650M
- ESMFold2-Fast (production structure prediction; single-sequence, no MSA); Boltz-2 (documented fallback for multimers)
- Modal (serverless GPU/CPU; CPU fast + GPU slow apps chained by orchestrator)
- Outputs: PDB/mmCIF, JSON sidecars, CSV, PNG, markdown reports
