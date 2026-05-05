# structure-agent

Automation for protein structure prediction and analysis. Sequences in,
structures + analysis out.

The pipeline is split into two operationally distinct stages under `src/`:

- **Stage 1** (`src/stage_1/`) — deterministic, identity-agnostic, batch
  prediction-and-measurement. Agents 0 (sequence cleaning), 1 (Boltz-2
  structure prediction), 2 (deterministic structural description). Emits
  a per-batch bundle: synthesis markdown plus structured
  JSON / CSV / PNG.
- **Stage 2** (`src/stage_2/`) — interactive, identity-aware,
  exploratory interpretation. Agent 3 (structural-element inference,
  Foldseek anchor resolution), Agent 4 (literature search). Consumes the
  Stage 1 bundle plus user input.

See `CLAUDE.md` for the architectural rules (non-negotiable),
`STAGE_SPLIT.md` for the rationale behind the split,
`src/stage_2/README.md` for the Stage 1 → Stage 2 contract, and each
agent's own README for detail.
