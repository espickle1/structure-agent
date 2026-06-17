---
name: protein-analysis
description: >
  End-to-end protein structure analysis from PDB, mmCIF, or AlphaFold prediction files.
  Performs structure parsing, quality validation, binding site detection, ligand interaction
  analysis, and multi-structure comparison (superposition, RMSD, conformational changes).
  Produces a markdown analysis report with embedded publication-quality figures, plus the
  raw data (JSON/CSV/PNG). Use this skill whenever the user uploads or references a protein structure file
  (.pdb, .cif, .mmcif), mentions protein structure analysis, asks about binding pockets,
  active sites, structural alignment, superposition, RMSD, Ramachandran analysis, B-factors,
  ligand interactions, or any structural biology workflow. Also trigger for AlphaFold
  predictions, pLDDT scores, or predicted structure confidence. Trigger even for casual
  references like "look at this structure", "compare these proteins", or "what's in the
  binding site".
---

# Protein Structure Analysis Skill

## Overview

This skill orchestrates a standardized, reproducible protein structure analysis pipeline.
Four fixed scripts run the same analysis every time (Phase 1). Bespoke code is only
written during iterative consultation with the user (Phase 2).

**Architecture:**
- `SKILL.md` — This file. Pure orchestration logic.
- `scripts/parse_structure.py` — Structure parsing and metadata extraction.
- `scripts/compare_structures.py` — Multi-structure superposition, RMSD, deviation profiles.
- `scripts/binding_site.py` — Ligand detection, pocket analysis, interaction classification.
- `scripts/surface_analysis.py` — SASA, surface properties, secondary structure, shape, dimensions.
- `references/interpretation_guide.md` — Passive reference for contextualizing results.

**Error handling:** If any script exits non-zero, HALT the pipeline and present the error
to the user. Do not skip failed analyses or attempt workarounds.

**Default deliverable:** a markdown synthesis report (`results/<stem>_analysis.md`) — deterministic facts assembled by a script, interpretive sections authored here. No external PDF/HTML skill dependency; runs the same in Claude Code and claude.ai.

---

## Core Principle: Identity-Agnostic Analysis

Phase 1 describes structure. It never identifies a protein by name or function.

- **Filenames are opaque labels.** They appear in metadata tables exactly as provided but
  are NEVER parsed for biological meaning. A file named `igaa_complex.cif` tells you
  nothing about what the protein is. Do not infer biology from filenames.
- **Measurements report structural categories** (shape, secondary-structure content,
  surface character). They do not speculate about which specific protein the structure
  "is" or what function it performs. Fold-level character may appear in the synthesis
  prose as explicit inference derived from the SS/shape numbers — never as a field
  emitted by a measurement script.
- **The agent does not guess protein identity.** If the user does not provide identity
  information, the analysis proceeds purely from structural observations. The honest
  default is: "I can describe what the structure shows; I cannot tell you what protein
  this is without additional information."
- **"Insufficient structural evidence to assign function" is a valid, expected
  conclusion — not a failure.** When the structure does not support a specific fold or
  functional call, say so plainly. The one thing this analysis must never ship is a
  confidently-wrong fold-or-function claim.

This principle applies throughout Phase 1 and during synthesis. Phase 2 may involve
identity-informed analysis if the user provides that context.

---

## Phase 0: Environment Setup

Install dependencies before running any script:

```
pip install --break-system-packages -q biopython matplotlib seaborn numpy pandas scipy
apt-get install -y -qq dssp
```

For mmCIF files, also install gemmi:

```
pip install --break-system-packages -q gemmi
```

Install Mol* CLI for structure renders. **Soft-fail:** if any of these
commands fail (e.g. claude.ai sandbox without npm global install), log the
warning and continue — `render_views.py` will be skipped per-structure later
and the report will note "Renders unavailable" instead of HALTing the
pipeline.

```
apt-get install -y -qq nodejs npm libgl1 libglu1-mesa libxi6 libxext6 \
    || echo "WARN: GL/Node install failed — renders will be skipped"
npm install -g molstar@latest \
    || echo "WARN: molstar install failed — renders will be skipped"
pip install --break-system-packages -q molviewspec \
    || echo "WARN: molviewspec install failed — renders will be skipped"
```

Copy uploaded structure files from `/mnt/user-data/uploads/` to `/home/claude/work/`.
Create an output directory: `/home/claude/work/results/`.

---

## Phase 1: Decision Tree

Follow this sequence for every invocation. Each step either runs a script or makes a
routing decision. All script parameters are fixed — no user overrides in Phase 1.

### Step 1: Detect Inputs

Scan uploaded files. Classify each by extension and content:
- `.pdb` → PDB format
- `.cif`, `.mmcif` → mmCIF format
- `.fasta`, `.fa` → Supplementary sequence (not analyzed by scripts, held for Phase 2)

Count structure files. This determines the workflow branch.

### Step 1b: Gather User Context

After detecting inputs, ask:

> "Anything you know about this structure — organism, function, what you're looking for —
> will help me interpret the results. Whatever you have is
> useful; if you have nothing, I'll work from the structure alone."

**Accept free-text context.** There is no fixed schema. The user may provide anything
from nothing to extensive annotation. Examples of what users might provide:
- Organism or phylogenetic context ("Gram-negative bacterium", "marine metagenome")
- Functional system ("two-component signaling", "secreted protease")
- Known structural features ("five TM helices expected", "catalytic triad at Ser160")
- Protein identity ("this is IgaA from E. coli")
- Design context ("this is a chimeric construct", "de novo designed protein")
- Analysis goals ("I'm interested in the binding pocket", "compare the active sites")

**If the user provides context:**
- Extract individual claims from the free text.
- Record all user-provided context verbatim for inclusion in the report.
- Classify each claim as **checkable** (can be validated against Phase 1 output) or
  **contextual** (steers interpretation but cannot be confirmed from structure alone).
- Checkable claims will be cross-validated after Phase 1 scripts run (see Step 7b).
- Contextual claims feed synthesis weighting (Step 9).

**If the user provides nothing:** Proceed with identity-agnostic analysis. Note in the
report: "No prior biological context provided; all findings derived from structural observation."

**Context can arrive at any point in the session.** If the user provides new context
during Phase 2, re-evaluate current synthesis against the new information.
Phase 1 results do not change — interpretation does.

### Step 2: Run parse_structure.py on Every Structure

For each structure file, run:

```
python scripts/parse_structure.py <file> --output-dir results/
```

Read the JSON output. Extract:
- Is this experimental or AlphaFold predicted?
- Does it contain non-solvent ligands?
- How many chains? (oligomeric state)
- Any chain breaks, modified residues?

If the script exits non-zero: **HALT. Present the error to the user.**

### Step 3: Route by Structure Count

**Single structure** → Go to Step 4 (surface analysis), then Step 4b (disorder gate),
then Step 5 (binding site).
**Multiple structures** → Go to Step 4, then Step 4b, then Step 6 (comparative analysis),
then Step 5.

### Step 4: Surface Analysis (Every Structure)

Run for every structure file:

```
python scripts/surface_analysis.py <file> --output-dir results/
```

This produces: per-residue SASA and exposure classification, surface hydrophobicity
and charge maps, secondary structure assignments (via DSSP), and overall shape metrics
(radius of gyration, asphericity, principal dimensions).

If the script exits non-zero: **HALT. Present the error to the user.**

### Step 4b: Disorder Assessment Gate

After Steps 2 and 4 complete, the agent has secondary structure assignments, SASA data,
shape metrics, and chain break information. Use these structural observables to assess
whether the structure contains sufficient ordered content for meaningful analysis.

**Evaluate the convergence of these disorder indicators:**
- **Secondary structure content:** What fraction of residues are assigned coil by DSSP?
  Predominantly coil (>80%) with no extended helical or sheet segments is a strong
  disorder signal.
- **Solvent exposure:** Is SASA uniformly high across the chain? A folded protein has
  a buried core; an intrinsically disordered protein has persistently high exposure
  throughout.
- **Shape vs. chain length:** Is the radius of gyration abnormally large for the number
  of residues? A folded globular protein follows Rg ≈ 2.5 × N^0.4 Å. Significantly
  larger Rg suggests no compact core.
- **Missing residues:** In experimental structures, extensive chain breaks (>30% of
  expected residues missing) indicate regions the crystallographer could not build —
  strong evidence of disorder.
- **Contact density:** If available from SASA data, check whether any region has a
  packed hydrophobic core. Disordered proteins lack long-range contacts.

**Decision branches:**

**Low disorder (most proteins):** Clear secondary structure elements, buried core present,
dimensions consistent with chain length. Proceed normally.

**Mixed disorder:** Some regions appear folded (SS elements, buried residues) while others
are extensively coiled and exposed. Proceed with analysis, but:
- Segment reporting: "Residues X–Y are well-structured; residues Z–W appear disordered."
- Note that whole-chain metrics (overall shape, average dimensions) are unreliable
  when a large disordered region skews them.
- Offer Phase 2 domain-specific analysis of the structured portion.

**Predominantly disordered:** Disorder indicators converge across a large fraction of the
structure — overwhelmingly coil, uniformly high SASA, extended dimensions, extensive
missing residues. **Stop structural analysis and tell the user directly:**

> "This structure does not contain stable tertiary structure — [describe the converging
> evidence]. Surface analysis, shape metrics, and binding site detection are not
> meaningful for intrinsically disordered proteins. If you're interested in
> disorder-specific properties (charge distribution along the sequence, low-complexity
> regions, short linear motifs), I can investigate those as targeted follow-ups."

Do not generate a full report with meaningless metrics. The agent has explicit permission
to say "there is no extractable structural information here."

**Important:** This assessment uses only structure-derived signals. Do not use pLDDT or
B-factors as primary disorder evidence — low confidence in a structure prediction does
not necessarily mean disorder, and high B-factors in experimental structures may reflect
anisotropic motion in a well-folded protein.

### Step 4c: Render Structure Views (Every Surviving Structure)

For every structure that passes the disorder gate (predominantly disordered
structures are skipped — rendering uniformly coiled chains is wasted work),
run the Cα-trace renderer (Agent 2.2 — pure matplotlib, no GL, runs anywhere):

```
python scripts/render_trace.py <file> --output-dir results/ --color pLDDT
```

Produces three axis-aligned views (`axis1` long, `axis2` mid, `axis3` short)
plus a `<stem>_render_views.json` sidecar with camera params. Coloring is
pLDDT (B-factor column). This is a Cα worm trace, not a cartoon.

`scripts/render_views.py` (Agent 2.1 — Mol\* `mvs-render` cartoons) is the
higher-fidelity renderer with identical output filenames (a drop-in
replacement), currently blocked on the molstar headless version pin (#18).
Switch this step to it once that is resolved.

**Renders are presentation-layer, not measurement.** Unlike Steps 2/4/5/6, a
non-zero exit from the renderer is **logged and skipped, not HALT-ed**. The
agent's contract (JSON/CSV) is unaffected. If the renderer exits non-zero or
no views are produced, note "Renders unavailable for `<stem>`" in the Step 9
report and proceed.

### Step 5: Binding Site Analysis (If Ligands Present)

Check the parse metadata: does `has_ligands` == true for any structure?

If yes, run for each structure that has ligands:

```
python scripts/binding_site.py <file> --output-dir results/
```

If the user provided additional ligand names to exclude, pass them:

```
python scripts/binding_site.py <file> --output-dir results/ --exclude-ligands <LIST>
```

If no structures have ligands, skip this step and note "No non-solvent ligands detected"
in the report.

If the script exits non-zero: **HALT. Present the error to the user.**

### Step 6: Comparative Analysis (Multiple Structures Only)

Designate the **first uploaded file** as the reference structure, unless the user
explicitly names a different reference.

Run:

```
python scripts/compare_structures.py <reference> <query1> [query2 ...] --output-dir results/
```

Chain matching is handled internally by the script (length-based matching with 5%
tolerance, ties broken by sequence identity). Unmatched chains are reported as absent.

If the script exits non-zero: **HALT. Present the error to the user.**

### Step 7: Collect All Outputs

After all scripts complete, gather:
- All `*_metadata.json` files
- All `*_surface_analysis.json` files
- All `*_comparisons.json` files (if comparative)
- All `*_binding_sites.json` files (if ligands present)
- All `*_render_views.json` files and `*_axis{1,2,3}.png` renders (when
  rendering succeeded — may be absent for some or all structures)
- All PNG plots
- All CSV files

### Step 7b: Validate User-Provided Context (If Any)

If the user provided context in Step 1b (or later in the session), cross-check each
**checkable claim** against Phase 1 output:

| User claim | Check against |
|---|---|
| "This is a homodimer" | Chain count, sequence identity between chains |
| "Five TM helices expected" | Hydrophobic segment count from surface analysis |
| "Active site has a catalytic triad" | Binding site output, pocket residue composition |
| "~300 residues per chain" | Parsed chain lengths |
| "Alpha-helical protein" | SS content from surface analysis |
| "Contains a Mg²⁺ cofactor" | Metal list from parse output |

**If a checkable claim agrees with data:** Note it as confirmed. Use it with confidence
in synthesis.

**If a checkable claim disagrees with data:** Flag the discrepancy to the user. Do not
silently accept the user's claim over structural evidence.

> "You mentioned five TM helices, but the hydrophobicity analysis detected three
> candidate segments. This could indicate that some TM helices are amphipathic and
> below the detection threshold, or that the expected count needs revisiting."

**Contextual claims** (organism, function, pathway) cannot be directly checked. Carry
them as stated priors for synthesis.

### Step 8: Read Interpretation Guide

Read `references/interpretation_guide.md`. Use it to:
- Describe the overall fold, shape, and surface character of the protein (state the
  coarse structural class per **Fold-class framing** in Step 9b)
- Contextualize RMSD values (what do the numbers mean?)
- Classify high-deviation regions (loops, hinges, functional rearrangements)
- Interpret surface properties (hydrophobic patches, charge distribution, exposure)
- Assess binding site quality (druggability signals, interaction strength, pose confidence)
- Flag red-flag conditions that need user attention
- Apply AlphaFold-specific caveats if any structure is a prediction

Do NOT parrot the guide. Synthesize findings into a coherent narrative that a structural
biologist would find useful.

### Step 9: Assemble the Markdown Report

Produce one markdown report, `results/<stem>_analysis.md`, in two layers.

**(a) Deterministic facts — run the assembler. Do NOT hand-transcribe numbers.**

```
python scripts/assemble_report.py <stem> --results-dir results/ \
    [--profile references/profiles/<name>.md ...]
```

It writes the report with every measured fact, the embedded figures, the
prediction-quality / coherence signals, and the expected-parameter comparison
matrix already filled — and leaves `<!-- SYNTHESIS ... -->` placeholder comments
for you. Pass `--profile` once per expected-parameter profile the user selected
(none is fine — the default for novel / low-homology targets; pass several to
compare against multiple profiles at once). If the script exits non-zero: **HALT
and present the error.**

**(b) Synthesis — replace each `<!-- SYNTHESIS ... -->` placeholder** with prose
you author from the measured facts plus the interpretation guide (Step 8):

- **Cite every claim** to the specific measurement it rests on. No claim without
  a number behind it.
- **Executive summary** — 3–5 sentences, the most notable structural observations.
- **Independent observations** — what is notable or unexpected from the
  measurements + generic physical baselines **alone**; do **not** consult the
  expected-parameter profiles here (that keeps it an independent lens). Flag genuine
  internal inconsistencies — measurements that directly contradict one another — but an
  elongated shape is **not** one: it never contradicts the fold class (see Fold-class
  framing, step 4). Anchor every "unexpected" to the baseline you compared against.
- **Coherence assessment** — state whether the structural-coherence signals
  (compactness, core, coil) agree with the confidence score, or
  whether a low pLDDT sits alongside a coherent fold (common for low-homology
  targets). pLDDT is reported context, **never** a gate.
- **What cannot be determined** — identity, function, mechanism, homology. State
  these plainly as the limits of structural analysis; "insufficient structural
  evidence to assign function" is a valid, expected conclusion, not a failure.
- **Stay descriptive:** describe and compare. "Consistent with profile X" —
  never "is an X." Leave the deterministic facts the assembler wrote intact; only
  fill the placeholders.

#### Fold-class framing (the coarse class, as inference)

State the overall structural class first (Analysis Priority 1), in prose, as inference
from the measured SS content, per-residue SS, and shape — never as a measured field.
The ceiling is the four coarse classes (all-α, all-β, α/β, α+β), plus — only when the
structure clearly shows it — a layer flavor (e.g. "3-layer α/β/α"). Never name a specific
fold or superfamily, and never emit SCOP fold / CATH identifiers. Procedure:

1. **Validity gate.** Trust the reliability flag only when it agrees with the data. If
   DSSP did not run (`dssp_success`/`reliable` false, or the all-coil-fallback warning is
   present), there is no SS measurement: state "secondary structure unavailable for this
   model; no fold class can be assigned" and stop here. If the flag is **absent** (older
   or variant output), infer it from the fractions — helix + sheet ≈ 0 (all-coil) ⇒
   unavailable, stop; substantial helix/sheet ⇒ treat as reliable and continue. Do not
   read the 0%/0%/all-coil fallback as a genuinely all-coil protein, and do not withhold a
   class from real SS just because the flag is missing.
2. **Class from SS presence/absence** (`secondary_structure_content` fractions). Treat
   helix or sheet below **~5% of assigned residues** as not a defining component — a
   provisional, arbitrary starting cutoff, not calibrated; revise it when a real
   borderline case appears:
   - sheet absent, helix present → **all-α**
   - helix absent, sheet present → **all-β**
   - both present → **α/β or α+β** (step 3 decides)
   - both absent (mostly coil) → no class; describe as low-SS and stop.
3. **α/β vs α+β from per-residue *ordering*** (`ss_assignments`, in sequence order):
   - strands and helices interleave along the chain (…E-H-E-H…) → lean **α/β**
   - strands cluster in one region, helices in another → lean **α+β**
   - ambiguous → report "mixed α/β character" and say the parallel-vs-antiparallel
     distinction needs topology this pipeline does not compute. Do not force the call.
4. **Shape — a descriptive note, not a consistency check** (`shape.asphericity`, axis
   ratios, Rg vs the ~2.5·N^0.4 globular expectation). Report whether the structure is
   globular or **elongated/fibrous**. Elongation is an unusual-but-legitimate characteristic
   worth highlighting (most single domains are globular; fibrous, filament-forming, and
   multidomain-string architectures are not) — but it is **not** an inconsistency and never
   contradicts the fold class. Elongated proteins occur in every class, so do **not** frame
   elongation as "disagreeing" with the class, do **not** call it an internal inconsistency,
   and do **not** let it lower the fold-class confidence. Report the shape plainly; name no
   fold from it.
5. **Multi-domain guard.** For large chains (~>400 residues, or multi-lobed in the
   renders), state the class is a whole-chain average across probable domains, not a
   single-domain assignment; omit the layer flavor, **and collapse the step-3 α/β-vs-α+β
   call to "mixed; per-domain segmentation needed"** — across multiple domains the
   per-residue ordering is a whole-chain average that cannot separate the two.
6. **Render as labeled inference.** Give the class, the measured fractions it rests on, a
   confidence (below), and the ceiling: "a structural class inferred from SS content and
   shape, not a fold identification; database verification (SCOP/CATH/Foldseek) would be
   needed to name a specific fold."

Confidence:
- **High** — real DSSP; one type cleanly absent or both clearly present (≥~10%); ordering
  unambiguous. (Shape does not bear on the class — see step 4 — so it neither raises nor
  lowers this.)
- **Moderate** — a fraction sits near the ~5% floor, or the α/β-vs-α+β ordering is
  ambiguous: state the class, hedge the sub-call.
- **Low / withhold** — DSSP failed (→ step 1), `total_assigned` tiny, or multi-domain:
  name the broad character (α-rich / β-rich / mixed) and decline to go further.

The report is the deliverable bundle's human-readable centerpiece, alongside the
machine-readable JSON/CSV and the figure PNGs from Step 7.

### Step 10: Present Results

Present the report (`results/<stem>_analysis.md`) to the user. Include a brief spoken summary of
the most important findings — do not just dump the report without commentary.

Then transition to Phase 2.

---

## Phase 2: Iterative Consultation

After presenting Phase 1 results, explicitly offer Phase 2:

> "The standardized analysis is complete. If anything looks interesting, unexpected, or
> needs deeper investigation, I can write targeted follow-up analyses."

Phase 2 is user-directed. Bespoke code is written ONLY in response to specific questions
that arise from the Phase 1 results. Examples of Phase 2 work:
- Custom distance measurements between specific residues
- Alternative superposition strategies (e.g., aligning on a specific domain only)
- Focused analysis of a specific loop or interface
- Mapping user-provided conservation data onto the structure
- Generating additional plots or visualizations
- Re-running binding site analysis with a different cutoff
- Per-domain structural characterization for multi-chain complexes
- Interface analysis at subunit boundaries

Phase 2 code is disposable — it is not added to the standardized pipeline.

**New context during Phase 2:** If the user provides new biological context mid-session
(identity, function, organism), the agent:
1. Cross-checks checkable claims against existing Phase 1 data (Step 7b logic).
2. Flags any discrepancies.
3. Re-evaluates synthesis in light of the new context.
4. Does NOT re-run Phase 1 scripts — the data hasn't changed, only the interpretation.

---

## Analysis Priorities (Ranked)

When synthesizing results, weight findings in this order:

1. **Fold, shape & surface** — Overall architecture, shape, secondary-structure content,
   surface character. This frames everything else. State it first, even if the protein is a
   generic globular enzyme.
2. **Comparative / multi-structure analysis** — Conformational changes, RMSD patterns,
   convergent deviations across structures.
3. **Binding sites & ligand interactions** — Pocket architecture, key interactions,
   druggability, catalytic signals.
4. **Structure quality & validation** — B-factors, chain breaks, resolution caveats.
   Important context but rarely the headline finding.
5. **Sequence-structure mapping** — Conservation, mutation context. Typically
   Phase 2 work unless the user provides sequence data upfront.

---

## Special Cases

### AlphaFold Predictions

When `alphafold_detection.is_predicted` is true:
- Use "pLDDT" not "B-factor" in all reporting.
- Apply pLDDT confidence tiers from the interpretation guide.
- Include explicit caveats about what cannot be inferred from predicted models.
- If comparing experimental vs predicted: note this asymmetry in the report.

### Oligomeric Structures

When a structure has multiple chains:
- Parse reports per-chain statistics automatically.
- If the user asks about interfaces, treat inter-chain contacts as binding sites
  (this is Phase 2 bespoke work — the standardized pipeline does not auto-analyze
  interfaces unless the user requests it).

### No Ligands Present

If no structures contain non-solvent ligands:
- Skip binding site analysis entirely.
- Note this in the report.
- The comparative analysis (if applicable) becomes the primary finding.

### Single Structure, No Ligands

This is the minimal case:
- Parse → report metadata, B-factors/pLDDT, quality notes.
- The report will be brief. Offer Phase 2 options: surface accessibility, secondary
  structure assignment, domain identification.

### Structural Discrepancies

If Phase 1 results contain internally inconsistent or unexpected signals — e.g., cofactor
coordination that doesn't match any known motif, or measurements that directly contradict
one another (an elongated shape is **not** such a case — see Fold-class framing, step 4) —
note the discrepancy in the report without
attempting to explain it away. The agent says what it sees, including when what it sees
is confusing. The user may have context that resolves the discrepancy.
