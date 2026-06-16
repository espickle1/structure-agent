# Handoff — Finalize the Single-Protein Structural Report (merge Agent 2 + Agent 3)

**For:** Claude Code, reorganizing `structure-agent` before the v1 freeze.
**Date:** 2026-06-16
**TL;DR:** Agent 3 does not become a separate module. The existing `src/agent_2/SKILL.md` (Steps 1–10) already *is* the deliverable. This session retired the stage/zone scaffolding, kept one output property in its place, and deferred the Foldseek/literature interpretation work to a possible separate project. Tasks below.

---

## Decisions this session

1. **No separate Agent 3.** `src/agent_2/SKILL.md` already runs the deterministic scripts *and* produces the interpretive PDF. Agent 2 and Agent 3 are merged: one SKILL, one deliverable. We are not building a downstream module.

2. **Retire the stage/zone scaffolding.** The Stage 1/2 split and the Zone 1/2/3 taxonomy were architecture-time guidelines. They are no longer project vocabulary. Drop the labels, the numbering, and any "this stays in Zone N / Stage N" framing in the docs.

3. **Keep exactly one property in their place:** the report **distinguishes what was measured from what was inferred**, and is allowed to conclude **"the structure does not support a specific functional assignment"** when that is the honest answer. Rationale: this is a proposed ATC Core deliverable going to other labs — the one thing it cannot ship is a confidently-wrong fold-or-function claim. (This is the bacterial β-sandwich → human γ-crystallin problem in one sentence.)

4. **Defer the Foldseek-neighbor → literature → function-inference pipeline.** It can be its own project. Two clarifications so this isn't misread:
   - Agent 1's Foldseek QC (the ipTM × hit-count 2×2 against AFDB50/BFVD) **stays** — it is structural quality control, not interpretation. Do not touch it.
   - A neighbor-*seeded* interpretive search was never wired into Agent 2, so there is nothing to remove for it — just don't build it now. (Note the existing Step 8b literature search is a *different*, feature-seeded thing — see Decision 1.)

---

## Tasks (this version)

### A. Code change — one file

**`src/agent_2/scripts/surface_analysis.py`: remove `classify_fold` (~line 383).**

- Delete the function and its output — the `scop_class` assignment **and** the `fold_candidates` list (the named matches like "alpha/beta hydrolase", "TIM barrel", "immunoglobulin-like beta-sandwich" with their `scop_id` / `cath_id` / `basis` fields).
- **Keep everything it consumed.** Those are real measurements and stay in the JSON/CSV:
  - secondary-structure fractions from `compute_secondary_structure` (helix / sheet / coil),
  - shape metrics from `compute_shape_metrics` (radius of gyration, asphericity, principal eigenvalues, axis ratios, approximate dimensions).
- **Why this change survives dropping the framework:** `classify_fold` is the one place a *script* emits an inference — loose SS-ratio thresholds mapped to a named fold — as if it were a measurement field. That is precisely what the one retained property (measured vs inferred) forbids, regardless of zone vocabulary. Fold-level character can still appear in the report, but as explicit inference in the prose, derived from the SS/shape numbers above — not as a hardcoded field.

### B. SKILL.md edits — `src/agent_2/SKILL.md`

1. **Step 4 (Surface & Fold Analysis):** drop the fold-classification output from the description; keep SASA/surface, secondary structure, shape, dimensions.
2. **Step 9 report structure, item 4 ("Fold & shape"):** remove "Overall fold classification (SCOP class, closest fold match)." Retitle to **"Shape & secondary structure"** (shape, dimensions, SS content, SS strip).
3. **Core Principle ("Identity-Agnostic Analysis"):** keep its intent — most of its text already *is* the retained property. Two adjustments: (a) it should no longer frame itself as one zone/stage of a multi-agent system; (b) state plainly that **"insufficient structural evidence to assign function" is a valid, expected conclusion, not a failure.** `references/interpretation_guide.md` (~line 528) already sets the no-function-beyond-fold-level ceiling — this just makes hitting it a legitimate stated outcome, and makes sure nothing in Step 9 *forces* a functional guess.
4. **Remove downstream-handoff language:** anything describing Agent 2 output as a feed to "Agent 3", a "Phase1Bundle" passed to a next agent, or synthesis performed elsewhere. There is no downstream; this SKILL owns interpretation end to end.
5. **Literature search:** resolve **Decision 1** before editing Step 8b and Step 9 item 8.

### C. Documentation hygiene (does not block the freeze)

- `README.md` still references a v3 layout — update to the current structure.
- `binding_site.py`: a prior note had it removed in v4.0, but it is currently present and wired (Step 5 + Step 9 item 7). Confirm intended status and reconcile the note (see Decision 2).

---

## Decisions needed from James

**1. Literature search (Step 8b) — in v1 or not?**
Current Step 8b is web-search-based and *feature-seeded* (queries built from observed fold class, cofactor coordination geometry, unusual elements, domain architecture, user context). It is already framed as "structural analogs, not identifications" and already skips gracefully when no search is available. It is **not** the crystallin-trap design — that was the neighbor-seeded version, which was never built.

- **Recommended — drop for v1.** Cleanest expression of "finalize with what we have"; removes the last avenue for plausible-but-wrong external analogy; the report stands on the structure's own measurements plus any user-provided context. Remove Step 8b and Step 9 item 8; fold literature contextualization into the separate project.
- **Alternative — keep it.** It's lightweight and analog-framed. One coupling to note: once `classify_fold` is removed (Task A), its priority-1 "fold class" query axis loses its deterministic seed, so it would search on an *inferred* fold descriptor instead. Its other axes (cofactor, unusual elements, domain architecture, user context) are unaffected.

**2. `binding_site.py` — live or retired?**
Present, wired, and functional. It was earlier flagged for removal under the zone framework; with that retired and the report doing interpretation, there's no longer a reason to pull it. Default: **stays.** Confirm.

---

## Not changing (guardrail against over-reorganizing)

- **Agents 0 and 1** — frozen.
- **Agent 1's Foldseek QC** — stays untouched.
- **All deterministic measurements** — parse, SASA/surface, secondary structure, shape, renders, comparative RMSD, binding-site geometry — stay.
- **PDF as the default deliverable** — stays.
