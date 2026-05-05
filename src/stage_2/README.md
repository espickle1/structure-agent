# Stage 2 — Interpretation layer

Stage 2 reads the per-batch bundle that Stage 1 (Agents 0 / 1 / 2) emits and
produces interpretive analysis. Where Stage 1 is deterministic,
identity-agnostic, and batch-shaped, Stage 2 is interactive,
identity-aware, and exploratory. The two halves are operationally
contradictory and most analytic feedback loops bypass Stage 1 entirely once
the bundle is in hand.

## What Stage 2 reads from Stage 1

Per the Stage 1 → Stage 2 contract (`STAGE_SPLIT.md`), each batch produces:

- `<stem>_metadata.json`
- `<stem>_surface_analysis.json` + `<stem>_surface.csv` + plots
- `<stem>_binding_sites.json` + per-ligand CSVs and plots (when ligands
  present)
- `<reference_stem>_comparisons.json` + per-pair deviation CSVs and plots
  (when multiple structures)
- `<stem>_render_views.json` + axis renders (when rendering succeeded)
- `<batch_id>_stage1_synthesis.md` — the Stage 1 synthesis markdown,
  consolidating Steps 1–8 of Agent 2's `SKILL.md` (disorder gate, fold
  classification synthesis, surface interpretation, comparative analysis,
  AlphaFold caveats, red-flag reporting, user-context validation).

The synthesis markdown is the human-readable handoff. The JSON / CSV / PNG
files are the machine-readable handoff. Stage 2 may use either or both.

## Rooms in a house

Stage 1 and Stage 2 share a repo and a filesystem; they do **not** share
Python imports. Communication is by filesystem artifacts only — the bundle
above. Conceptually independent, physically proximate, no service boundary.

## Agents

- **`agent_3/`** — structural-element inference and Foldseek-anchored
  homolog retrieval. Resolves Foldseek anchors plus per-anchor metadata for
  hand-off to Agent 4.
- **`agent_4/`** — literature search and summarization. Consumes resolved
  anchors from Agent 3 (and any user-supplied context) and produces a
  ranked reading list with per-paper anchor attribution.

See each agent's `README.md` for the four-section contract (scope, inputs,
outputs, status).

## No speculative scaffolding

Further `agent_N/` directories (agent_5, agent_6, …) are not created until
the agent has been named and scoped in conversation. Empty stubs ahead of
design are how scope creeps; the Stage 2 layout reflects what we've already
committed to, not what we might build.

## Zone discipline

Stage 2 is where Zone 3+ work happens — identity-aware claims, claims
sourced from outside the structure file, functional inference, mechanistic
reasoning. Stage 1 produces only Zone 1 (direct measurement) and Zone 2
(spatial pattern description, including direct mappings from the
interpretation guide). Do not push Zone 3+ work back into Stage 1.
