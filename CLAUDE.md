# CLAUDE.md

Multi-agent pipeline for high-throughput protein structure prediction and analysis, focused on phage receptor-binding proteins (RBPs) and metagenomic samples. Sequences in, structures + analysis out.

## Stages

Two operationally distinct halves under `src/`:

**Stage 1 — deterministic prediction + measurement (sequence in → structure + measurements out).**

- **Agent 0** (complete): heterogeneous nucleotide/protein FASTA → clean amino acid FASTA + provenance metadata. Stack: BioPython, orfipy, ESM-2 650M, Modal (CPU fast app + GPU slow app).
- **Agent 1** (designed, not yet coded): structure prediction orchestrator. Runs Boltz-2, quality-gates, hands coordinates + metadata to Agent 2.
- **Agent 2** (complete, v4.0): deterministic structural description. Geometric measurements and spatial patterns only. Final node of Stage 1; emits the Stage 1 bundle (synthesis markdown + JSON / CSV / PNG).

**Stage 2 — interpretive analysis (Stage 1 bundle + human input → interpretation).**

- **Agent 3** (designed v0, scope being revised): structural-element inference and Foldseek-anchored homolog retrieval. Emits resolved anchors for hand-off to Agent 4.
- **Agent 4** (not started): literature search, ranking, summarization keyed to Agent 3's anchors.

Stage 1 and Stage 2 communicate by filesystem artifacts only — no shared Python imports. See `src/stage_2/README.md` for the Stage 1 → Stage 2 contract; see `STAGE_SPLIT.md` for the rationale.

## Architectural rules — non-negotiable

- **Zone discipline.** Zone 1 = direct geometric measurement. Zone 2 = spatial pattern description. Zone 3+ = interpretation. Stage 1 NEVER produces Zone 3 output. This boundary exists to prevent biologically plausible but incorrect outputs.
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
- Boltz-2 (production), ESMFold (cheap CPU pre-screen)
- Modal (serverless GPU/CPU; CPU fast + GPU slow apps chained by orchestrator)
- Outputs: PDB/mmCIF, JSON sidecars, PDF reports
