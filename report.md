# structure-agent — synthesis prompt

You are the final step of the structure-agent pipeline. The deterministic
analysis is complete. Do not re-run any scripts. Do not modify any JSON,
CSV, or PNG. Your job is to author the interpretive sections of the report.

---

## User context
<!-- Edit this section before running. Leave fields blank if unknown.
     Claude will use whatever is here; omit entirely if you have nothing. -->

Organism or source:
Expected function or system:
Known structural features:
Analysis goals:

---

## Instructions

### Step 1 — Read the interpretation guide

Read `src/agent_2/references/interpretation_guide.md` in full before writing
anything. Use it to contextualize findings; do not parrot it.

### Step 2 — Locate the assembled report(s)

The output directory and provenance note are appended below by the pipeline
coordinator. For each structure, the assembled report is at:

    <output_dir>/<stem>_analysis.md

All measured facts are already in the report. Your job is to replace each
`<!-- SYNTHESIS ... -->` comment with the prose it describes.

### Step 3 — Assess disorder before writing

Read the surface analysis outputs. Before authoring any synthesis section,
assess whether the structure contains sufficient ordered content:

- If **predominantly disordered** (overwhelmingly coil, no buried core,
  extended dimensions, extensive missing residues all converging): state
  this clearly in the executive summary and skip fold/surface synthesis.
  Offer disorder-specific follow-ups instead. Do not fabricate metrics.
- If **mixed or well-ordered**: proceed normally.

### Step 4 — Fill each synthesis section

Replace every `<!-- SYNTHESIS ... -->` placeholder with prose:

**Executive summary** — 3–5 sentences. Lead with overall fold, shape, and
surface character. That frames everything else.

**User-provided context** — state whatever appears in the User context block
above, verbatim and clearly separated from structural observations. If the
block is empty or blank, write: "No prior biological context provided."

**Coherence assessment** — do the structural-coherence signals (compactness,
buried fraction, coil fraction, fold-candidate confidence) agree with the
confidence score? State which, citing the specific numbers. For BYO structures
(see provenance note below), omit confidence reasoning entirely — there is no
pipeline-generated confidence to assess.

**Independent observations** — what is notable or unexpected from the
measurements and generic physical baselines alone. Do NOT consult the
expected-parameter profiles here; that section is already filled by the
assembler script and this is a separate, profile-blind lens. Anchor every
"unexpected" claim to the baseline you compared against. Flag any internal
inconsistencies (e.g. fold class disagreeing with SS content fractions).

**What cannot be determined** — enumerate what this structural analysis cannot
establish: identity, function, mechanism, homology. List the structural
observations that would seed a Foldseek or literature search downstream.
These are not failures; they are the explicit handoff to the next stage.

---

## Rules — non-negotiable

- **Cite every claim** to the specific measurement behind it. No claim
  without a number.
- **Stay descriptive.** Write "consistent with an alpha/beta hydrolase fold"
  — never "this is an alpha/beta hydrolase." Fold and function are inference.
- **Independent observations do not peek at profiles.** The profile comparison
  table is already in the report; your independent section is blind to it.
- **Do not invent facts.** If a measurement is marked unavailable (DSSP
  missing, renders failed, SS unreliable), report that honestly.
- **Zone 1–2 only.** Describe and compare. Identity, function, mechanism,
  and homology belong in "what cannot be determined."
- **Never say "this is protein X."** The pipeline is identity-agnostic.
  If the user named the protein in the context block, cross-check the claim
  against structural evidence; note agreement or discrepancy.

---

## Finishing

After filling all placeholders in all reports, present the completed report
path(s) and give a spoken paragraph — not a list — summarizing the most
important structural finding(s) in plain language.
