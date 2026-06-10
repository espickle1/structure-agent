# Expected-parameter profiles

Optional, hand-editable reference files. Each states what's *expected* for a
target class, so the report can flag deviations against an **explicit, cited
baseline** rather than the model's implicit expectations. Profiles are
**optional** — with none supplied (the default for novel / low-homology
targets) the report relies on the independent-observations synthesis.

Pass one or more to the assembler:

```bash
python scripts/assemble_report.py <stem> --results-dir <results> \
    --profile references/profiles/globular_enzyme.md \
    --profile references/profiles/denovo_monomer.md
```

Running several profiles against one structure is the intended pattern: the
match/deviation pattern across profiles is a structural differential — and
because the independent-observations synthesis ignores the profiles, running N
of them also samples that read N times (a robustness signal).

## Format

A markdown table. Recognised columns (header row, case-insensitive):

| column | meaning |
|---|---|
| `parameter` | a canonical name from the vocabulary below |
| `min` | lower bound (blank = unbounded below) |
| `max` | upper bound (blank = unbounded above) |
| `unit` | display only |
| `note` | shown verbatim in the report's comparison matrix |

Blank `min` **and** `max` makes the row informational only. Unknown parameter
names are reported as "unknown parameter" — never silently dropped.

## Parameter vocabulary

Names map to the measurement scripts' JSON. **Fractions are 0–1, not
percentages** (e.g. `coil_fraction` max of `0.45`, not `45`).

| parameter | unit | source |
|---|---|---|
| `radius_of_gyration` | Å | surface_analysis → shape |
| `asphericity` | — | surface_analysis → shape (0 = spherical) |
| `helix_fraction` | 0–1 | surface_analysis → secondary structure |
| `sheet_fraction` | 0–1 | surface_analysis → secondary structure |
| `coil_fraction` | 0–1 | surface_analysis → secondary structure |
| `buried_fraction` | 0–1 | surface_analysis → surface stats |
| `exposed_fraction` | 0–1 | surface_analysis → surface stats |
| `surface_net_charge` | e | surface_analysis → surface stats (pH 7) |
| `surface_hydrophobicity_mean` | — | surface_analysis → surface stats (Kyte–Doolittle) |
| `total_sasa` | Å² | surface_analysis → surface stats |
| `num_chains` | — | parse_structure → metadata |
| `total_residues` | — | parse_structure → metadata |

Keep this vocabulary in sync with `PARAM_REGISTRY` in
`scripts/assemble_report.py`.

> **Avoid length-dependent absolutes** (e.g. a fixed `radius_of_gyration`
> bound): the report's "Prediction quality / structural coherence" section
> already assesses Rg against the 2.5·N^0.4 folded-globular expectation.

All bounds in the shipped seed profiles are **calibrate-on-real-data
placeholders** — adjust them per target class before relying on the verdicts.
