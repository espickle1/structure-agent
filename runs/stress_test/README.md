# stress_test — Agent 1 → Agent 2 runs for SKILL fold-class validation

Persisted from ephemeral `/tmp` (2026-06-16/17). Sequence labels (`seq*`, `t*`) are
**opaque** — identity-agnostic per CLAUDE.md; do not read biology into them.

## Layout
- `a1/structures/<id>.cif` — ESMFold2-Fast predictions (Agent 1, Modal A100).
- `a2/<id>_surface_analysis.json` + `_surface.csv` — Agent 2 measurements (real DSSP on Modal).
- `a2/<id>_metadata.json` — Agent 2 parse (local).
- `a2/<id>_{surface_profile,exposure_pie,axis1,axis2,axis3}.png` — plots + Cα-trace renders.
- `a2/t{1..5}_analysis.md` — **full assembled reports** (deterministic facts + authored synthesis).
- `batch1_seq.faa`, `batch2_t.faa` — input sequences (as folded).

Reports were generated for the **t1–t5** batch. `seq1–seq3` (batch 1) are persisted as
structures + measurements only (used earlier to stress-test the procedure).

## Provenance notes
- **t2** was supplied as a **coding nucleotide sequence** (2,661 nt); Agent 0's fast path
  translated the clean single ORF → 886 aa before folding. See `t2_analysis.md`.
- **t3** carries a C-terminal His-tag (expression artifact; folds as a disordered tail).

## Coarse fold-class verdicts (per the SKILL "Fold-class framing" procedure)
| id | n | pLDDT | class | notes |
|----|---|-------|-------|-------|
| t1 | 859 | 0.738 | α/β-or-α+β, β-rich | multidomain whole-chain average; compact; strongly acidic surface |
| t2 | 886 | 0.757 | predominantly all-β | helix 4.9% at the ~5% floor; multidomain; translated from nt |
| t3 | 270 | 0.854 | mixed α/β (hedged) | somewhat elongated (descriptive); fully polar, patch-free surface |
| t4 | 755 | 0.879 | predominantly all-α | sheet 4.5% at the floor; multidomain; 16 hydrophobic surface patches |
| t5 | 277 | 0.843 | mixed α/β (hedged) | somewhat elongated; modest core; N-terminal hydrophobic stretch |

0/5 named-fold calls. t2 (helix 4.9%) and t4 (sheet 4.5%) are the first real near-floor
cases — reported as "predominantly" with the minor component surfaced, not dropped.
