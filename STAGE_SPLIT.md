# Stage 1 / Stage 2 split — refactor brief

## Context

Agents 0, 1, and 2 form a deterministic, identity-agnostic, batch
prediction-and-measurement pipeline. Agent 3+ (Foldseek-anchored literature
retrieval, future interpretation work) is interactive, identity-aware, and
exploratory. These two halves have operationally contradictory shapes
(deterministic vs. judgment-based, batch vs. conversational, identity-agnostic
vs. identity-driven), and most analytic feedback loops will bypass the
prediction pipeline entirely.

We're labeling the existing boundary, not creating a new one. Nothing inside
Agents 0–1–2 reads Agent 2's output — Agent 2 is a leaf node, so its output
schema is already an external contract. Naming the boundary makes the contract
visible.

## Naming

- **Stage 1** = Agents 0, 1, 2. Sequence in → structure + measurements out.
- **Stage 2** = Agent 3+. Stage 1 bundle + human input → interpretive analysis.

"Agent 0/1/2/3" naming inside each stage stays for now (revisit at GitHub repo
creation, per existing roadmap).

## Zone discipline (unchanged, restated for clarity)

- Zone 1: direct geometric measurement.
- Zone 2: spatial pattern description, including direct mapping of measurements
  to reference values (e.g. "asphericity > 0.30 → prolate", "RMSD 2.0–3.0 Å
  typically reflects domain movements"). This is one-step inference from
  quantitative output, not interpretation.
- Zone 3+: identity-aware claims, claims sourced from outside the structure
  file, functional inference, mechanistic reasoning. Stage 2 only.

Stage 1 produces Zone 1 and Zone 2 output. Stage 2 is where Zone 3+ work
happens.

## What moves, what stays

### Stays in Stage 1 (Agent 2)

- All four scripts: `parse_structure.py`, `compare_structures.py`,
  `binding_site.py`, `surface_analysis.py`, `render_views.py`.
- `references/interpretation_guide.md` — direct mapping of quantitative
  outputs to structural descriptions. Zone 2 by the criterion above. Stays
  with the measurement layer because it's how the measurements become usable
  to downstream consumers (Stage 2, operators, auditors).
- `SKILL.md` orchestration through Step 8 (interpretation guide read +
  synthesis of Phase 1 results). Disorder gate, fold classification synthesis,
  surface interpretation, comparative analysis interpretation, AlphaFold
  caveats, red-flag reporting, user-context validation — all Zone 1–2,
  all stay.
- Markdown synthesis output. Sufficient for development, auditing, and
  Stage 2 consumption. Negligible overhead at 100+ sequences.

### Moves to Stage 2

- **`SKILL.md` Step 8b — Structural Context Search.** Web-anchored literature
  retrieval keyed to fold class, cofactor coordination, etc. Sources claims
  from outside the structure file → Zone 3. Also operationally Stage 2 work
  (network round-trip, non-deterministic ranker).
- **`SKILL.md` Step 9 — PDF / HTML report assembly.** Depends on
  `/mnt/skills/public/pdf/` and `/mnt/skills/public/frontend-design/`,
  which exist in claude.ai but not Claude Code. Presentation-layer work
  with environment-specific dependencies. The split also resolves the
  open question in `src/agent_2/README.md` about Step 9 silently failing
  outside claude.ai.

### Already in Stage 2

- `src/agent_3/AGENT.foldseek-literature-retrieval.md`
- `src/agent_3/VERB.pubmed-search-skill.md`
- `src/agent_3/OBJECT.foldseek_results.md`

## Stage 1 → Stage 2 contract

Stage 1 emits a per-batch bundle that Stage 2 consumes. Bundle contents
(already produced by Agent 2 today, plus the synthesis markdown):

- `<stem>_metadata.json`
- `<stem>_surface_analysis.json` + `<stem>_surface.csv` + plots
- `<stem>_binding_sites.json` + per-ligand CSVs and plots (when ligands
  present)
- `<reference_stem>_comparisons.json` + per-pair deviation CSVs and plots
  (when multiple structures)
- `<stem>_render_views.json` + axis renders (when rendering succeeds)
- Stage 1 synthesis markdown — the disorder assessment, fold synthesis,
  surface interpretation, comparative analysis interpretation, quality
  notes, context validation. The output of `SKILL.md` Steps 1–8.

The synthesis markdown is the human-readable handoff. The JSON/CSV/PNG
files are the machine-readable handoff. Stage 2 can use either or both.

## Layout

Two top-level directories under `src/`, one repo, shared root README:

```
src/
├── stage_1/
│   ├── agent_0/
│   ├── agent_1/
│   └── agent_2/
└── stage_2/
    ├── agent_3/      # structural-element inference + Foldseek
    └── agent_4/      # literature search
```

### Stage 2 directory provisioning

Stage 2 is unbuilt. We're scaffolding directories now to reflect known
near-term scope, not to lock in design. Two directories, both stubs.

**`stage_2/agent_3/`** — structural-element inference and Foldseek-anchored
homolog retrieval. The existing `src/agent_3/AGENT.foldseek-literature-retrieval.md`,
`VERB.pubmed-search-skill.md`, and `OBJECT.foldseek_results.md` move here as
**starter material**, not as a finished design. Note that
`AGENT.foldseek-literature-retrieval.md` v0 currently combines Foldseek
ingestion with literature retrieval as one workflow; with Agent 4 owning
literature, expect to revise it so Agent 3 produces resolved Foldseek
anchors and hands them off, while Agent 4 runs the PubMed search. The
`VERB.pubmed-search-skill.md` belongs with Agent 4 once Agent 4 exists —
move it then, not now.

**`stage_2/agent_4/`** — literature search. Empty directory plus a stub
README documenting intended scope: PubMed retrieval, ranking, summarization,
hand-off to whichever Stage 2 agent invokes it. No code yet. The stub exists
so the layout reflects the conceptual split before the code does.

**Stub READMEs.** Each Stage 2 agent directory gets a one-page README
stating: (1) intended scope, (2) inputs from Stage 1 bundle and/or other
Stage 2 agents, (3) outputs, (4) status (designed / in progress / built).
This is the same contract-first discipline Stage 1 uses, applied to
directories that don't have implementations yet.

**Don't pre-create agent_5+, agent_6+, etc.** Only create directories for
agents we've already named in conversation. Speculative scaffolding is the
scope-bloat path.

No shared Python imports between stages. They communicate by filesystem
artifacts only — the bundle described above. This is the rooms-in-a-house
model: conceptually independent, physically proximate, no service boundary.

## Refactor checklist for Claude Code

In rough order. Each item is small enough to do as a single change.

1. **Rename and move directories.** `src/agent_0` → `src/stage_1/agent_0`,
   etc. Update import paths in:
   - `src/stage_1/agent_0/orchestrator.py` (Modal function lookup string,
     `modal.Function.from_name("agent_0-fast", ...)` — Modal app name is
     separate from Python import path, decide whether to rename the deployed
     app or leave it).
   - `src/stage_1/agent_0/modal_app.py` (`add_local_python_source("agent_0")`).
   - `src/stage_1/agent_2/modal_app.py` (`add_local_python_source("agent_2")`,
     plus `from agent_2.scripts.render_views import render_structure`).
   - `src/stage_1/agent_0/test_fast_path.py` (imports).
   - All `from agent_X.foo import bar` statements across the package.
2. **Trim `src/stage_1/agent_2/SKILL.md`.** Remove Step 8b in full. Reduce
   Step 9 to "emit a synthesis markdown file in `results/`"; drop the
   PDF/HTML branching and the references to `/mnt/skills/public/pdf/` and
   `/mnt/skills/public/frontend-design/`. Update the report-structure list
   accordingly — sections 1–7, 9–11 stay; section 8 ("Structural context")
   is removed. Step 3b ("Structural views") stays.
3. **Define the synthesis markdown filename and location.** Suggest
   `results/<batch_id>_stage1_synthesis.md`. Add to the bundle inventory in
   `SKILL.md` Step 7.
4. **Update `src/stage_1/agent_2/README.md`.** Drop the "Optional — make the
   skill auto-discoverable" path-specific instructions if the move breaks
   them. Fix the "Environment differences" section: PDF/HTML report
   generation is no longer Step 9's job, so the claude.ai-vs-Claude-Code
   asymmetry around polished deliverables disappears. Update the "Open
   question for future work" note accordingly. Update internal references
   to script paths.
5. **Scaffold `src/stage_2/`.** Create three things:
   - `src/stage_2/README.md` — top-level Stage 2 doc. What Stage 2 reads
     from the Stage 1 bundle, the rooms-in-a-house framing, the
     agent_3/agent_4 split and what each owns, the rule that further agent
     directories aren't created speculatively.
   - `src/stage_2/agent_3/` — move existing `src/agent_3/*.md` files here
     (`AGENT.foldseek-literature-retrieval.md`, `OBJECT.foldseek_results.md`).
     Add a stub `README.md` with the four-section contract: scope (structural-
     element inference, Foldseek anchor resolution), inputs (Stage 1 bundle,
     user context), outputs (resolved Foldseek anchors + per-anchor metadata
     for hand-off to Agent 4), status (Foldseek workflow designed v0,
     structural-element inference not started). Note that
     `AGENT.foldseek-literature-retrieval.md` v0 still bundles literature
     retrieval; revising it to hand off to Agent 4 is design work, not
     refactor work.
   - `src/stage_2/agent_4/` — empty except for stub `README.md`. Same four-
     section contract: scope (literature search and summarization), inputs
     (resolved anchors from Agent 3, user-provided context), outputs (ranked
     reading list with per-paper anchor attribution), status (not started;
     `VERB.pubmed-search-skill.md` will move here when Agent 4 begins).
     Leave `VERB.pubmed-search-skill.md` in `src/stage_2/agent_3/` for now —
     moving it before Agent 4 is built creates a dangling reference.
6. **Update root `README.md` and `CLAUDE.md`.** Replace the "Agents" section
   with a Stage 1 / Stage 2 framing. Keep the architectural rules section
   intact — the rules don't change, only the labeling. Note that
   "Agents 0–2 NEVER produce Zone 3 output" is restated as "Stage 1 NEVER
   produces Zone 3 output."
7. **Modal app names — leave untouched.** Currently `agent_0-fast`,
   `agent1-step1-boltz2`, `agent_2-render`. Do NOT rename. "Stage" naming
   is for the top-level directory layout only; everything inside
   (Modal apps, Python packages, dataclasses, log prefixes, in-code
   "Agent N" references) keeps the existing "Agent" scheme.
8. **Smoke-test.** Run Agent 0's pytest suite from the new path to confirm
   imports still resolve. Walk Agent 2's `SKILL.md` decision tree against a
   small structure to confirm nothing references removed Step 8b / Step 9
   machinery.

## Out of scope for this refactor

- GitHub repo creation — separate roadmap item.
- "Agent N" → new naming inside each stage — separate roadmap item.
- Foldseek integration into Stage 2 — design work, not refactor work.
- Stage 1 synthesis markdown schema standardization — let it emerge from
  the first few real runs, formalize later.

## What this refactor does NOT change

- Zone discipline, identity-agnostic Phase 1, module independence,
  metadata passthrough, errors-logged-not-escalated. All non-negotiable
  rules survive intact.
- Agent 2's four scripts and their JSON/CSV/PNG outputs.
- Agent 0's 17 passing smoke tests.
- Agent 1's Step 1 design and `modal_app.py`.
- The `interpretation_guide.md` content (only Step 8b's web-search
  instructions in `SKILL.md` are affected).
