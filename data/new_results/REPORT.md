# Agent 2 Phase 1 Report — `MHPk_step1_predicted.cif`

**Date:** 2026-05-05
**Pipeline:** Agent 2 (deterministic structural description)
**Source:** Agent 1 Boltz-2 prediction (`src/agent_1/step1_results/`)
**Output directory:** `data/new_results/`

---

## 1. Executive summary

A 381-residue, single-chain Boltz-2 prediction. **Mixed alpha/beta architecture**
(40% helix, 25% sheet, 35% coil) classified by SS content as an alpha/beta
hydrolase or TIM-barrel candidate, but **shape metrics conflict with both
archetypes** — the structure is markedly elongated (axis ratio 3.8 : 1, ~76 ×
49 × 41 Å) where canonical alpha/beta hydrolases and TIM barrels are roughly
globular. The discrepancy is consistent with a multi-domain fold rather than a
single canonical enzyme topology; fold classification is reported as a
whole-chain average and is unreliable for multi-domain inputs (a known
limitation; see Methods). **Buried core is present** (44% buried residues,
Rg 0.87× expected for a folded protein of this size), so the protein is
not predominantly disordered. Two low-pLDDT regions (residues 24–51 and
71–122) span ~21% of the chain and warrant caution in the corresponding
structural conclusions.

---

## 2. User-provided context

No prior biological context provided; all findings derived from structural
observation.

Note: per Agent 2's identity-agnostic policy, the filename "MHPk" was treated
as an opaque label and is not used for inference.

---

## 3. Structure overview

| Property | Value |
|---|---|
| File | `MHPk_step1_predicted.cif` |
| Format | mmCIF |
| Source | **AlphaFold-style prediction (pLDDT in B-factor)** — Boltz-2 output |
| Models | 1 |
| Chains | 1 (A) |
| Residues | 381 |
| Atoms | 3023 |
| Chain breaks | 0 |
| Modified residues | 0 |
| Ligands (non-solvent) | None |
| Metals | None |
| Waters | None |
| Resolution | N/A (predicted structure) |

Chain A pLDDT statistics (B-factor column): mean 63.9, median 66.6, min 26.3,
max 95.6, σ 19.0.

## 3b. Structural views

**Renders unavailable for `MHPk_step1_predicted`.** SKILL.md Step 4c soft-failed
because `mvs-render` is not installed in the local environment (requires
`npm install -g molstar`). The measurement outputs in this report are
unaffected. To produce the three axis-aligned cartoon renders (long / mid /
short principal axis, pLDDT-colored), install the Mol* CLI and re-run:

```
npm install -g molstar
pip install --user --break-system-packages molviewspec
python3 src/agent_2/scripts/render_views.py \
    src/agent_1/step1_results/MHPk_step1_predicted.cif \
    --output-dir data/new_results
```

This will write `MHPk_step1_predicted_axis{1,2,3}.png` and
`MHPk_step1_predicted_render_views.json` into `data/new_results/`.

---

## 4. Fold & shape

### Secondary structure content (DSSP)

| Class | Count | Fraction |
|---|---|---|
| Helix | 153 | 40% |
| Sheet | 96  | 25% |
| Coil  | 132 | 35% |

SCOP class assignment: **alpha/beta** (>15% helix and >15% sheet).

### Shape metrics (Cα-based gyration tensor)

| Metric | Value |
|---|---|
| Radius of gyration (Rg) | 23.49 Å |
| Expected Rg for folded N=381 (≈ 2.5·N^0.4) | 26.9 Å |
| Rg / expected | 0.87 (more compact than typical) |
| Asphericity | 0.27 |
| Axis ratios (long:mid, long:short) | 3.81, 4.69 |
| Approximate dimensions | 75.6 × 49.0 × 41.0 Å |
| Shape classification | **prolate (elongated)** |

### Fold candidates and discrepancy flag

The script returns two candidate folds based on SS content:

| Candidate | SCOP | CATH | Confidence | Basis |
|---|---|---|---|---|
| Alpha/beta hydrolase | c.69 | 3.40.50 | high | SS content consistent with canonical alpha/beta hydrolase fold |
| TIM barrel | c.1 | 3.20.20 | moderate | SS content and shape compatible with (β/α)₈ barrel topology |

**Discrepancy flag** (per the interpretation guide's rule on confusing
signals): both candidate folds are characteristically globular — alpha/beta
hydrolases ~spherical, TIM barrels ~spherical. The observed asphericity
(0.27) and axis ratio (3.8 : 1) describe a markedly elongated structure
that does not match either archetype. The fold classifier averages SS
content over the entire chain and is known to be unreliable for multi-
domain inputs (README §"Known limitations"). Two plausible structural
explanations consistent with the observations — both Zone 3 (interpretation)
and offered as Phase-2 follow-ups, not as conclusions:

- A two-domain fold with a flexible inter-domain linker (consistent with the
  large low-pLDDT region at residues 71–122).
- A non-canonical topology where SS content happens to fall in the alpha/beta
  range but the chain organization is not hydrolase-like or TIM-like.

Database verification (SCOP / CATH / Foldseek / Dali) is the appropriate next
step for definitive fold assignment.

---

## 5. Surface properties

| Property | Value |
|---|---|
| Total SASA | 19,214 Å² |
| Exposed (relSASA > 40%) | 99 residues (26%) |
| Partial (15–40%) | 116 (30%) |
| Buried (<15%) | 166 (44%) |
| Surface hydrophobicity (Kyte–Doolittle, mean over exposed) | −1.86 |
| Surface net charge (pH 7) | 0 |
| Exposed positive residues | 21 |
| Exposed negative residues | 21 |
| Hydrophobic patches | 2 small patches (3 res each) |

Hydrophobic patch detail:

| Patch | Residues | Length | Mean hydrophobicity |
|---|---|---|---|
| 1 | 29–31  | 3 | 3.13 |
| 2 | 125–127 | 3 | 1.83 |

Both patches are tiny (3 residues) and the surface is otherwise
hydrophilic. Net surface charge of 0 with balanced exposed positive/negative
residues is consistent with a soluble cytosolic-style surface character.

The 44% buried fraction confirms a clear hydrophobic core — the protein is
**not** intrinsically disordered (see §9 disorder gate).

Surface plots:

- `MHPk_step1_predicted_surface_profile.png` — per-residue SASA / hydrophobicity / charge / SS strip (300 DPI)
- `MHPk_step1_predicted_exposure_pie.png` — exposure distribution
- `MHPk_step1_predicted_surface.csv` — per-residue surface table

---

## 6. Comparative analysis

Not applicable — single structure provided. (To run a comparative analysis,
provide ≥2 structure files; SKILL.md Step 6 will then call
`compare_structures.py`.)

---

## 7. Binding site analysis

Not applicable — `parse_structure.py` reports no non-solvent ligands and no
metals (`has_ligands: false`). Binding-site analysis is skipped per SKILL.md
Step 5.

If interface analysis between hypothetical multimerization partners or a
ligand of interest is wanted, that is Phase-2 bespoke work.

---

## 8. Structural context

Not performed in this run. Web search is available in this environment but
was not invoked because the fold classification itself is uncertain (see
§4 discrepancy flag) — searching by a candidate fold that may not actually
match the structure risks anchoring interpretation on the wrong family.
**Recommended next step:** run a structural search (Foldseek against AFDB or
PDB) to ground the fold call in real homologues before any literature
contextualization.

---

## 9. Quality notes

### pLDDT distribution

| Tier | Range | Count | Fraction |
|---|---|---|---|
| Low | <50 | 107 | 28% |
| Moderate | 50–70 | 111 | 29% |
| High | 70–90 | 134 | 35% |
| Very high | ≥90 | 29 | 8% |

Mean 63.9, median 66.6 — overall moderate confidence with a heavy tail of
low-confidence residues.

### Low-pLDDT contiguous regions (≥5 residues)

| Region | Length | Notes |
|---|---|---|
| Residues 24–51 | 28 res | Long low-confidence stretch near the N-terminus |
| Residues 71–122 | 52 res | Largest low-confidence region; ~14% of the chain |
| Residues 373–381 | 9 res | C-terminal tail |

These regions account for ~89 of the 107 low-pLDDT residues (~23% of the
chain). Two interpretations are equally plausible without more evidence:

- **Genuine flexibility / disorder** — the regions are real but not well-
  predicted because they are loops, linkers, or intrinsically disordered.
- **Novel/underrepresented topology** — Boltz-2 has lower confidence in these
  regions because they are underrepresented in training data, but they may
  still be ordered in the actual protein.

Per the interpretation guide, **low pLDDT alone does not establish
disorder**. The disorder gate (§9b) used SS content, SASA, Rg, and chain
breaks — all structural observables — and concluded the chain has stable
tertiary structure overall.

### Disorder gate result (Step 4b)

| Indicator | Observed | Threshold | Verdict |
|---|---|---|---|
| Coil fraction | 35% | >80% would flag | clearly ordered |
| Buried fraction | 44% | <30% would flag | clear core |
| Rg vs expected (2.5·N^0.4) | 0.87× | >>1 would flag | compact |
| Chain breaks | 0 | >30% missing would flag | complete |

**Verdict: Low disorder. Proceed with full analysis.**

### Caveats for downstream interpretation

1. Any structural conclusion that depends on residues in the 24–51 or
   71–122 windows should be flagged as low-confidence — the prediction
   itself is uncertain there.
2. The whole-chain fold classification is unreliable for what is plausibly a
   multi-domain protein (see §4 discrepancy flag). Per-domain re-analysis
   (Phase 2 work) would tighten this.
3. Hydrophobic-patch detection is very sparse (2 × 3-residue patches). If
   the protein is multi-domain, a domain-domain interface might present
   as a hydrophobic patch on the isolated-domain surface but not on the
   whole-chain surface. Phase 2 per-domain SASA would clarify.

---

## 10. Context validation

No user context provided — section omitted.

---

## 11. Methods

### Pipeline

Per SKILL.md Phase 1 decision tree:

| Step | Script | Status |
|---|---|---|
| 2 | `parse_structure.py` | ✓ |
| 4 | `surface_analysis.py` | ✓ |
| 4b | Disorder gate (Claude judgment) | ✓ — low disorder |
| 4c | `render_views.py` | ✗ soft-failed (mvs-render not installed) |
| 5 | `binding_site.py` | skipped (no non-solvent ligands) |
| 6 | `compare_structures.py` | skipped (single structure) |
| 7 | Output collection | ✓ |
| 8 | Interpretation guide | ✓ |
| 9 | Report assembly | ✓ (Markdown — Claude Code env, no `/mnt/skills/public/pdf/`) |

### Fixed parameters

- DSSP for secondary-structure assignment via BioPython `DSSP` wrapper
  around `mkdssp` (Homebrew install).
- Shrake–Rupley SASA via BioPython.
- Fold classification by SS-fraction signature + shape metrics
  (`surface_analysis.py:classify_fold`).
- Disorder gate uses structural signals only (coil fraction, SASA, Rg,
  chain breaks) — never pLDDT or B-factor (per interpretation guide).

### Software versions

- Python 3.13 (Homebrew)
- BioPython 1.87
- DSSP `mkdssp` (Homebrew brewsci/bio/dssp)
- Boltz-2 (Agent 1 step1 — version recorded in upstream sidecar)

### Outputs in `data/new_results/`

```
MHPk_step1_predicted_metadata.json          (Step 2)
MHPk_step1_predicted_surface_analysis.json  (Step 4)
MHPk_step1_predicted_surface.csv            (Step 4)
MHPk_step1_predicted_surface_profile.png    (Step 4)
MHPk_step1_predicted_exposure_pie.png       (Step 4)
REPORT.md                                   (Step 9 — this file)
```

---

## Phase 2 follow-ups offered

The standardized analysis is complete. If anything looks interesting,
unexpected, or needs deeper investigation, targeted Phase-2 analyses can be
written to address them. Strong candidates given §4's discrepancy flag and
§9's quality notes:

1. **Foldseek / AFDB structural search** to ground the fold call in real
   homologues — should be done before any literature-based interpretation.
2. **Per-domain analysis** — split the chain at the residue 122 low-pLDDT
   boundary (or wherever a more careful boundary call places it) and re-run
   `surface_analysis.py` on each domain. Tightens fold classification and
   surface metrics, separates inter-domain hydrophobic surface from solvent-
   facing surface.
3. **Render the structure** — install `mvs-render` and run Step 4c so the
   report has 3D views.
4. **Inter-domain linker characterization** — focused analysis of residues
   71–122 (length, composition, predicted flexibility, contact density to
   the rest of the chain).
