# Structural analysis — `ptm0.199_r6_seed2_LM_m0.15`

> Facts are emitted deterministically from the measurement scripts. Sections marked with a SYNTHESIS comment are authored by the Claude session (judgment), kept visibly separate from the measured facts.

## Executive summary

<!-- SYNTHESIS (Claude, per SKILL.md Step 9): 3–5 sentences: the most notable structural observations. Structural observations only; cite the measurement(s) each claim rests on. Replace this comment. -->

## User-provided context

<!-- SYNTHESIS (Claude, per SKILL.md Step 9): State any context the user gave (organism, goal, expected features), verbatim and clearly separated from observations; else "None provided." Structural observations only; cite the measurement(s) each claim rests on. Replace this comment. -->

## Structure overview

- **Source:** experimental
- **Chains:** 1 (single chain)
- **Residues / atoms:** 79 / 571
- **Missing residues:** 0
- **Non-solvent ligands:** none
  - chain **A**: 79 res

## Structural views

![ptm0.199_r6_seed2_LM_m0.15 — down long axis](ptm0.199_r6_seed2_LM_m0.15_axis1.png)

![ptm0.199_r6_seed2_LM_m0.15 — down mid axis](ptm0.199_r6_seed2_LM_m0.15_axis2.png)

![ptm0.199_r6_seed2_LM_m0.15 — down short axis](ptm0.199_r6_seed2_LM_m0.15_axis3.png)

_Cα backbone trace (Agent 2.2 matplotlib placeholder), down the long / mid / short principal axes; coloured by pLDDT._

## Shape & secondary structure

- **Shape:** oblate (disc-like) (asphericity 0.16, Rg 15.91 Å)
- **Approx. dimensions:** 48.6 × 34 × 17.6 Å
- **Secondary structure:** helix 64.6%, sheet 0.0%, coil 35.4% _(method: pydssp)_
- **⚠ SS assigned by pydssp (fallback), not mkdssp** — pydssp is a simplified DSSP reimplementation and can over- or under-call short helix/sheet segments on imperfect (e.g. predicted) backbones. Treat fractions near the ~5% floor, the helix/sheet split, and any coil-vs-disorder reasoning as provisional; install mkdssp for reference-grade assignment.

## Surface properties

- **Exposure:** buried 0.0%, partial 24.1%, exposed 75.9%
- **Total SASA:** 7584.9 Å²
- **Surface hydrophobicity (KD):** mean 0.2 ± 2.74
- **Surface charge (pH 7):** net 4.1 e (8 +, 3 −)
- **Hydrophobic patches:** 6:
  - residues 14–16 (len 3, mean KD 2.93)
  - residues 28–30 (len 3, mean KD 2.13)
  - residues 36–40 (len 5, mean KD 2.74)
  - residues 59–61 (len 3, mean KD 1.8)
  - residues 70–74 (len 5, mean KD 2)
  - residues 76–78 (len 3, mean KD 2.8)

![Per-residue SASA & hydrophobicity](ptm0.199_r6_seed2_LM_m0.15_surface_profile.png)

![Exposure breakdown](ptm0.199_r6_seed2_LM_m0.15_exposure_pie.png)

## Prediction quality / structural coherence

Confidence is **reported, never gated** — these signals are inputs for the synthesis below, not a pass/fail.

- **B-factor (chain A):** mean 43.03, median 42.67, range 31.11–59.98, std 6.43
- **Compactness:** Rg 15.91 Å vs ~14.4 Å expected for 79 residues (2.5·N^0.4) — consistent
- **Core present:** buried fraction 0.0%
- **Coil fraction:** 35.4%

### Coherence assessment

<!-- SYNTHESIS (Claude, per SKILL.md Step 9): Do the structural-coherence signals (compactness, core, coil) agree with the confidence score, or does a low B-factor sit alongside a coherent fold (common for low-homology targets)? State which, citing the signals above. Structural observations only; cite the measurement(s) each claim rests on. Replace this comment. -->

## Expected-parameter comparison

_No expected-parameter profile supplied — this is the default for novel / low-homology targets. See the independent observations below._

## Independent observations

<!-- SYNTHESIS (Claude, per SKILL.md Step 9): What is notable or unexpected from the measurements + generic physical baselines ALONE (do NOT consult the expected-parameter profiles here). Flag internal inconsistencies. Anchor 'unexpected' to a stated baseline. Close with ONE sentence stating the scope limit: this is structural description, not an identity / fold-name / function call — say 'insufficient structural evidence to assign function' when the structure does not support one. Keep it to one line; the generic limits of structural analysis live in the README, so do not re-enumerate identity / homology / mechanism here. Structural observations only; cite the measurement(s) each claim rests on. Replace this comment. -->

## Methods

- **Measurements (deterministic):** `parse_structure.py` (metadata, confidence stats), `surface_analysis.py` (Shrake–Rupley SASA, Kyte–Doolittle hydrophobicity, charge at pH 7, DSSP secondary structure, shape metrics), `render_trace.py` (Agent 2.2 Cα-trace figures; `render_views.py` Mol* cartoons when Agent 2.1 is available).
- **Report facts** below the synthesis sections are emitted verbatim from the above scripts' JSON by `assemble_report.py` — no transcription.
- **Synthesis** sections (executive summary, independent observations incl. the one-line scope statement, coherence assessment) are authored by Claude per `SKILL.md` Step 9, each claim cited to a measurement.
