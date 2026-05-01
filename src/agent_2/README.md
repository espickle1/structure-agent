# Protein Structure Analysis Skill (v3)

A reproducible, agentic pipeline for protein structure analysis. Drop a PDB or mmCIF file into Claude and get a standardized analysis — parsing, multi-structure comparison, binding site detection, and interaction classification — assembled into a PDF report.

---

## What's New in v3

- **Identity-agnostic analysis.** Phase 1 never identifies a protein by name or function.
  Filenames are opaque labels. Fold classification reports structural categories, not
  specific protein names. Literature search targets observed features, not guessed identities.
- **User context intake.** The agent asks for biological context (organism, function, known
  features) in free-text form. Context is validated against structural data, feeds into
  literature search, and is transparently reported.
- **Disorder gate.** After initial scripts run, the agent assesses whether the structure
  contains sufficient ordered content for meaningful analysis. Uses structural signals only
  (SS content, SASA, shape metrics, missing residues) — not pLDDT or B-factors. If the
  structure is predominantly disordered, the agent says so directly instead of generating
  a report full of meaningless metrics.
- **Structural context search.** Literature search is keyed to observed features — fold
  class, cofactor coordination, domain architecture, unusual structural elements.
  Results are framed as structural analogy ("this fold is characteristic of..."),
  never as identification ("this protein is...").
- **Consistency gate.** User-provided claims are cross-checked against Phase 1 output.
  Discrepancies are flagged, not silently accepted.
- **Disulfide bonds removed.** No longer detected, reported, or mentioned in any output.

---

## Architecture

```
protein-analysis/
├── SKILL.md                          # Orchestration decision tree
├── README.md                         # This file
├── scripts/
│   ├── parse_structure.py            # Structure parsing & metadata extraction
│   ├── compare_structures.py         # Multi-structure superposition & RMSD
│   ├── binding_site.py               # Ligand detection & pocket analysis
│   └── surface_analysis.py           # SASA, surface properties, shape, fold classification
└── references/
    └── interpretation_guide.md       # Passive reference for result contextualization
```

**SKILL.md** is the orchestrator. It contains the decision tree that routes inputs to the correct scripts in the correct order. No code snippets — pure workflow logic.

**Scripts** are the Phase 1 standardized baseline. They run identically every time with fixed parameters. They are never modified during a session.

**interpretation_guide.md** is a passive reference. Claude reads it after scripts produce results to contextualize numbers, flag significance, and apply domain-specific interpretation.

---

## Installation

### Claude Code (preferred)

Place the `protein-analysis/` directory in your project's skill location, or install the packaged `.skill` file.

Dependencies (installed automatically by the skill):

```
pip install biopython matplotlib numpy scipy pandas seaborn
apt-get install dssp
```

### claude.ai

Upload structure files directly. The skill installs dependencies in the ephemeral container at runtime.

---

## Usage

Upload one or more structure files and ask Claude to analyze them. Examples:

- "Analyze this structure"
- "Compare these two PDB files"
- "What's in the binding site?"
- "Give me a full structural analysis"

The skill triggers on `.pdb`, `.cif`, and `.mmcif` files, and on keywords like superposition, RMSD, binding pocket, B-factor, pLDDT, and AlphaFold.

---

## Two-Phase Workflow

### Phase 1: Standardized Analysis

Every structure gets the same treatment. Same scripts, same parameters, same output format.

Pipeline order:
1. Detect inputs
2. Gather user context (free-text, optional)
3. `parse_structure.py` on every uploaded file
4. `surface_analysis.py` on every uploaded file
5. **Disorder gate** — assess whether structure has sufficient ordered content
6. `compare_structures.py` if multiple structures are provided
7. `binding_site.py` if any structure contains non-solvent ligands
8. Validate user context against structural data
9. Read interpretation guide
10. **Structural context search** — literature search keyed to observed features
11. Assemble PDF report

If any script fails, the pipeline halts and presents the error.

### Phase 2: Iterative Consultation

After Phase 1 completes, Claude presents findings and offers targeted follow-up. Bespoke code is written only here, at the user's direction, to investigate specific questions arising from the standardized results.

New user context can arrive at any point during Phase 2. Phase 1 data doesn't change — interpretation adjusts.

---

## Analysis Priorities

1. **Fold, shape & surface** — overall architecture, fold classification, surface character
2. **Comparative / multi-structure analysis** — superposition, RMSD, conformational changes
3. **Binding sites & ligand interactions** — pocket detection, interaction classification
4. **Structure quality & validation** — B-factors/pLDDT, chain breaks, resolution caveats
5. **Sequence-structure mapping** — SASA, conservation, mutation context (typically Phase 2)

---

## Design Decisions

| Decision | Setting |
|---|---|
| Error handling | Halt on script failure, present error to user |
| Phase 1 parameters | Fixed — no user overrides; parameter changes are Phase 2 work |
| Multi-structure reference | First uploaded file is reference unless user specifies otherwise |
| Chain matching | By sequence length (5% tolerance), ties broken by sequence identity |
| Default deliverable | PDF report |
| Ligand exclusion | Built-in list of solvents, ions, and crystallization additives; user can extend |
| Pocket cutoff | 5.0 Å (fixed in Phase 1) |
| Deviation threshold | 2.0 Å Cα displacement defines "high-deviation" regions |
| Interaction cutoffs | H-bond: 3.5 Å, salt bridge: 4.0 Å, hydrophobic: 4.5 Å, π-stack: 5.5 Å |
| Identity inference | Never in Phase 1; structural description only |
| Disorder assessment | Structure-derived signals only; not pLDDT or B-factor based |
| Disulfide bonds | Not detected or reported |
| User context | Free-text, validated against data, transparently reported |

---

## Deliverable Formats

- **PDF report** (default) — Executive summary, user context, structure overview, comparative analysis, binding sites, structural context, quality notes, methods
- **Interactive HTML dashboard** — React single-file artifact with tabbed sections and interactive plots
- **Raw data + figures** — CSV/TSV files and 300 DPI PNG plots
- **All of the above**

---

## Scripts

### parse_structure.py

```
python parse_structure.py <structure_file> [--output-dir <dir>]
```

Reads PDB or mmCIF. Auto-detects format and AlphaFold predictions. Outputs `<stem>_metadata.json` and a human-readable summary to stdout.

### compare_structures.py

```
python compare_structures.py <reference> <query1> [query2 ...] [--output-dir <dir>]
```

Compares queries against the reference. Produces per-comparison RMSD statistics, per-residue deviation CSVs, deviation profile plots, and B-factor comparison plots. Outputs `<reference_stem>_comparisons.json`.

### binding_site.py

```
python binding_site.py <structure_file> [--output-dir <dir>] [--exclude-ligands HOH,SO4]
```

Finds non-solvent ligands, defines pockets via KD-tree neighbor search, classifies interactions, computes pocket composition. Outputs `<stem>_binding_sites.json`, pocket CSVs, and summary plots.

### surface_analysis.py

```
python surface_analysis.py <structure_file> [--output-dir <dir>]
```

Computes per-residue SASA (Shrake-Rupley) and exposure classification, surface hydrophobicity (Kyte-Doolittle), charge distribution, secondary structure (DSSP), shape metrics (radius of gyration, asphericity, principal dimensions), and fold classification (SCOP class + common fold matching with SCOP/CATH identifiers). Outputs `<stem>_surface_analysis.json`, per-residue CSV, surface profile plot, and exposure distribution plot.

---

## Ligand Exclusion List

The following are excluded from ligand analysis by default:

**Water:** HOH, WAT, H2O, DOD

**Common ions:** NA, CL, K, CA, MG, ZN, FE, MN, CO, CU, NI, CD, SO4, PO4, NO3

**Crystallization additives:** GOL, EDO, PEG, PGE, MPD, DMS, ACT, FMT, TRS, CIT, BME, EOH, IMD, EPE, MES, IPA, CAC

**Buffer components:** HED, TAR, MLI, BIG, BCT

**Unknowns:** UNX, UNL, UNK

Users can extend this list via `--exclude-ligands` or specify replacements during Phase 2.

---

## Open Architectural Questions

1. **Multiple protein complexes** — Interface analysis at subunit boundaries (treating inter-chain interfaces like binding sites). Decision logic to be added to SKILL.md.
2. **Function inference** — Confident annotation requires external databases (UniProt, Pfam, EC) or user input. Fold-level structural analogy is possible but always framed as inference, not identification.
3. **Phylogeny and functional annotation as inputs** — Upgrades interpretation from descriptive to hypothesis-driven. Conservation scores distinguish constrained positions from drift; known function prioritizes mechanistically relevant findings.
4. **Sequence-based identification** — BLAST or similar searches are out of scope for this skill; best handled by a dedicated sequence analysis agent.
5. **Chain matching tolerance** — The 5% length tolerance is too strict when signal peptides are present. Pairwise sequence alignment fallback should be integrated.
6. **Per-domain fold classification** — Averaging SS content over multi-chain complexes is misleading. Per-chain or per-domain classification needed for oligomeric structures.

---

## Requirements

- Python 3.10+
- BioPython
- matplotlib, seaborn
- numpy, scipy, pandas
- DSSP (mkdssp) — for secondary structure assignment
- No GPU required — all computation is lightweight CPU work
