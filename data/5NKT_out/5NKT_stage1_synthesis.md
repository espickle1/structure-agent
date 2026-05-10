# Stage 1 Synthesis — 5NKT.cif

**Batch ID:** 5NKT  
**Date:** 2026-05-09  
**Scripts:** parse_structure.py, surface_analysis.py, render_views.py  
**Output directory:** `data/5NKT_out/`

---

## 1. Executive Summary

A single-chain 151-residue all-beta protein resolved at 1.5 Å by X-ray crystallography. The structure is markedly elongated (50.2 × 24.1 × 22.2 Å, asphericity 0.347), well beyond the prolate threshold, with a tightly packed beta-sandwich core (58% buried residues). The fold classifier returns an immunoglobulin-like beta-sandwich (SCOP b.1, CATH 2.60.40) at moderate confidence. A chain break at residue position 91–94 divides the chain roughly 60:40 and is the most structurally notable feature relative to the user's interest in domain organization. No non-solvent ligands are present. B-factors are slightly elevated given the resolution, warranting a flag at the chain-break region.

---

## 2. User-Provided Context

| Item | Provided by user | Checkable? |
|---|---|---|
| Organism | Escherichia coli | No — cannot be verified from coordinates alone |
| Function | Attachment to host | No — functional assignment requires Zone 3+ inference |
| Analysis goal | Overall organization between all domains | Steers synthesis toward domain-level architectural description |

No user-provided claims are directly checkable against Phase 1 structural output. All three are treated as contextual priors carried forward to Stage 2.

---

## 3. Structure Overview

| Field | Value |
|---|---|
| File | 5NKT.cif |
| Source | Experimental — X-RAY DIFFRACTION |
| Resolution | 1.5 Å |
| Chains | 1 (Chain A) |
| Residues | 151 |
| Atoms | 2250 |
| Waters | 153 |
| Ligands | None |
| Metals | None |
| Missing residues | 2 (chain break at residues 91→94, gap = 2) |
| AlphaFold prediction | No |

**Chain A sequence (151 aa):**
```
GGTVHFKGEVVNAACAVDAGSVDQTVQLGQVRTASLAQEGATSSAVGFNIQLNDCDTNVA
SKAAVAFLGTAIDAGHTNVLALQSSGSATNVGVQILDR TGAALTLDGATFSSETTLNNGT
NTIPFQARYFATGAATPGAANADATFKVQYQ
```

---

## 3b. Structural Views

Renders unavailable for `5NKT` — `mvs-render` requires the npm `gl` package, which is not installed in this environment. Refer to `5NKT_render_views.json` for computed camera parameters (principal-axis vectors and approximate dimensions).

---

## 4. Fold & Shape

**Shape classification:** Prolate (elongated)  
**Dimensions:** 50.2 × 24.1 × 22.2 Å (long × mid × short principal axis)  
**Radius of gyration:** 15.82 Å  
**Asphericity:** 0.347 (>0.30 — strongly prolate; see note below)  
**Long:mid ratio:** 4.84 — the long axis is nearly 5× the cross-sectional width  
**Long:short ratio:** 5.85

The Rg of 15.82 Å is below the ~18.6 Å expected for a globular protein of 151 residues (Rg ≈ 2.5 × N^0.4). This combination — lower-than-globular Rg with high asphericity — is consistent with a tightly packed elongated structure rather than an extended or partially unfolded chain. The 39% coil fraction is notable (above the typical ~20–30% for well-folded all-beta structures) and may reflect the loop-rich connectivity of a beta-sandwich topology, or the presence of two structural segments with a flexible inter-segment region.

**Secondary structure:**

| Element | Residues | Fraction |
|---|---|---|
| Helix | 4 | 3% |
| Sheet | 88 | 58% |
| Coil | 59 | 39% |
| **Total** | 151 | — |

**Fold classification:**  
- **SCOP class:** All-beta  
- **Best candidate:** Immunoglobulin-like beta-sandwich (SCOP b.1, CATH 2.60.40)  
- **Confidence:** Moderate  
- **Basis:** High beta-sheet content (58%) with minimal helix (3%), consistent with a beta-sandwich topology. Definitive assignment (strand count, connectivity, Greek-key vs. jelly-roll topology) requires database verification (SCOP/CATH/Dali/ECOD) and is Phase 2 work.

---

## 5. Surface Properties

| Metric | Value |
|---|---|
| Total SASA | 4202.5 Å² |
| Exposed residues | 22 (15%) |
| Partially buried | 42 (28%) |
| Buried residues | 87 (58%) |
| Mean surface hydrophobicity (KD scale) | −0.414 |
| Surface net charge | +2 |
| Exposed positive residues | 2 |
| Exposed negative residues | 0 |
| Hydrophobic patches | None detected |

The buried fraction (58%) exceeds the typical range for well-folded globular proteins (40–55%), indicating a tightly packed hydrophobic core. The surface is mildly hydrophilic (KD mean −0.414), placing it in the mixed zone on the interpretation scale; no discrete hydrophobic patches are present. The surface charge is close to neutral (net +2) with notably few exposed charged residues overall — both positive (2) and negative (0) counts are low — suggesting a predominantly polar but uncharged surface. No charge asymmetry (dipole) signal.

---

## 6. Comparative Analysis

Not applicable — single structure.

---

## 7. Binding Site Analysis

Not applicable — no non-solvent ligands detected. If a potential ligand-binding pocket is of interest for Phase 2, it can be investigated with `binding_site.py` in cavity-detection mode.

---

## 8. Quality Notes

**Resolution:** 1.5 Å — high quality. Backbone, side-chain rotamers, and water positions are reliable. Individual atom positions can be trusted.

**B-factors:**

| Stat | Value |
|---|---|
| Mean | 41.68 Å² |
| Median | 35.97 Å² |
| Min | 19.53 Å² |
| Max | 88.94 Å² |
| Std | 17.31 Å² |

At 1.5 Å resolution, the interpretation guide places the high B-factor threshold at >40 Å². The mean (41.68 Å²) sits marginally above this threshold, and the maximum (88.94 Å²) is substantially elevated. The chain break at residues 91–94 is the most likely locus of high B-factors — residues flanking the gap are typically disordered or mobile. This region warrants attention when interpreting the structural boundary between what may be two distinct segments.

**Chain break:** Residues 92–93 are unresolved (gap = 2 at 91→94). Two missing residues at 1.5 Å resolution is consistent with a locally disordered or mobile loop rather than a crystallographic artifact. This break falls at approximately 60% along the chain (position 91/151) and divides the sequence into a longer N-terminal segment (~91 residues) and a shorter C-terminal segment (~58 residues).

**Modified residues:** None.  
**Ramachandran validation:** Not computed in this pipeline (Phase 2 / external validation tool).

---

## 9. Context Validation

No user-provided claims were checkable against Phase 1 structural output. The contextual claims (E. coli organism, host-attachment function) are carried forward as priors for Stage 2 literature search and interpretation. See §3 above.

**On the domain organization goal:** The user's interest in "overall organization between all domains" is relevant to the following structural observations, reported here without functional interpretation:

- The structure is a single polypeptide chain of 151 residues — there is no direct crystallographic evidence of multiple discrete domains in the sense of separately folded units in the deposited file.
- The strongly elongated shape (asphericity 0.347, long:mid ratio 4.84) is inconsistent with a single compact globular domain and is more typical of an extended or tandem-domain architecture.
- The chain break at position 91–94 divides the chain into two unequal segments (91 + 58 residues). Whether this break marks an inter-domain linker or a disordered loop within a single domain cannot be determined from structural observables alone.
- The fold classifier returned an immunoglobulin-like beta-sandwich at moderate confidence. At 151 residues, this could represent a single elongated Ig-like domain or two consecutive beta-sandwich units — the 91-residue N-terminal segment is at the upper bound for a single Ig-like domain, while the 58-residue C-terminal segment is at the lower bound.

Definitive domain boundary mapping is Phase 2 work (e.g., domain-decomposed DSSP analysis, inter-segment contact counting, or Dali/ECOD database lookup).

---

## 10. Methods

| Step | Script | Version / Notes |
|---|---|---|
| Structure parsing | `parse_structure.py` | BioPython; mmCIF via gemmi 0.7.5 |
| Surface & fold analysis | `surface_analysis.py` | SASA: Shrake–Rupley; SS: DSSP (mkdssp 4.5.8); shape: inertia tensor; fold: SS/shape signature matching |
| Renders | `render_views.py` | Skipped — npm `gl` not installed; `mvs-render` could not render |

Fixed Phase 1 parameters: pocket cutoff 5.0 Å (unused), deviation threshold 2.0 Å (unused), 1024×1024 render size (skipped).

All outputs in `data/5NKT_out/`:
- `5NKT_metadata.json`
- `5NKT_surface_analysis.json`
- `5NKT_surface.csv`
- `5NKT_surface_profile.png`
- `5NKT_exposure_pie.png`
- `5NKT_render_views.json` (camera parameters; no PNG renders)
- `5NKT_stage1_synthesis.md` (this file)
