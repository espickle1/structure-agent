# Agent 3 — Structural-element inference and Foldseek anchor resolution

## Scope

Two responsibilities, both Stage 2:

- **Structural-element inference** — interpret Stage 1's geometric and
  spatial-pattern output to propose structural elements (folds, motifs,
  domain boundaries, plausible binding-site categories). Identity-aware
  reasoning, Zone 3 by design.
- **Foldseek anchor resolution** — run / consume Foldseek searches keyed
  to Stage 1 structures, deduplicate hits, attach per-anchor metadata
  (PDB ID, chain, organism, resolution, alignment quality), and emit a
  resolved anchor list ready for hand-off to Agent 4 for literature
  retrieval.

## Inputs

- The Stage 1 bundle for the batch (synthesis markdown +
  JSON / CSV / PNG, per `src/stage_2/README.md`).
- User-provided context (organism, pathway, function, prior beliefs).
  Carried through Stage 1 as stated priors; Agent 3 is the first place
  where it influences interpretation.

## Outputs

- Resolved Foldseek anchors with per-anchor metadata, in a structured
  format Agent 4 can consume directly.
- A structural-element inference report (form TBD — markdown to start;
  schema emerges from real runs).

## Status

- Foldseek workflow: designed v0 in
  `AGENT.foldseek-literature-retrieval.md`. The v0 spec currently bundles
  Foldseek ingestion *and* literature retrieval as one workflow. With
  Agent 4 now owning literature, the spec needs revision: Agent 3 should
  produce resolved anchors and stop there, leaving PubMed search to
  Agent 4. **Design work, not refactor work.**
- Structural-element inference: not started.
- `OBJECT.foldseek_results.md` defines the Foldseek output schema and
  stays here.
- `VERB.pubmed-search-skill.md` lives in this directory for now and will
  move to `../agent_4/` once Agent 4 begins; moving it before then
  creates a dangling reference.
