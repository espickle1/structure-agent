# Interpretation Guide — Protein Structure Analysis

A passive reference document. Claude reads this after scripts produce results to
contextualize findings, flag significance, and prioritize what to report.

This document does NOT orchestrate analysis. It is a lookup resource.

---

## Table of Contents

1. [Identity-Agnostic Interpretation](#identity-agnostic-interpretation)
2. [Disorder Assessment](#disorder-assessment)
3. [Fold, Shape & Overall Architecture](#fold-shape--overall-architecture)
4. [Surface Properties](#surface-properties)
5. [Structural Context Search](#structural-context-search)
6. [Comparative Analysis](#comparative-analysis)
7. [Binding Sites & Ligand Interactions](#binding-sites--ligand-interactions)
8. [Structure Quality & Validation](#structure-quality--validation)
9. [Sequence-Structure Mapping](#sequence-structure-mapping)
10. [AlphaFold-Specific Interpretation](#alphafold-specific-interpretation)
11. [Red Flags — Conditions Requiring User Attention](#red-flags)
12. [How Phylogeny and Function Change Interpretation](#phylogeny-and-function-context)

---

## Identity-Agnostic Interpretation

**Phase 1 analysis describes structure. It does not identify proteins.**

### Rules

1. **Filenames are opaque.** Never parse them for biological meaning. A file named
   `igaa_complex.cif` could contain any protein. Treat filenames as arbitrary labels.

2. **Fold classification is structural, not functional.** Report the SCOP class, CATH
   topology, and structural description. Do not say "this is protein X" — say "this fold
   is characteristic of the alpha/beta hydrolase superfamily."

3. **Literature search targets observations, not names.** When searching for context,
   query structural features: fold class, cofactor coordination geometry, domain
   architecture, unusual structural elements. Never query a guessed protein name.

4. **Multiple-hypothesis framing.** When structural evidence points toward a functional
   family, present it as inference from structure: "The domain architecture (PAS + HPt
   with Mg²⁺-coordinated histidine) is characteristic of bacterial two-component
   signaling systems." Do not collapse to a single identification.

5. **User-provided identity is validated, not assumed.** If the user names a protein,
   cross-check against structural observations (chain count, SS content, fold class,
   chain length, cofactors). Flag discrepancies. Do not silently accept an identity
   claim that contradicts the structural evidence.

6. **When the structure is confusing, say so.** If fold classification returns low
   confidence, metrics seem inconsistent, or signals don't converge — report the
   confusion honestly. The user may have context that resolves it. Do not fabricate
   a plausible-sounding explanation.

---

## Disorder Assessment

### Structural Indicators of Disorder

These observables from Phase 1 scripts collectively indicate whether a protein (or
region thereof) is intrinsically disordered:

| Indicator | Source | Disorder Signal |
|---|---|---|
| Secondary structure | DSSP via surface_analysis.py | >80% coil, no extended helical or sheet segments |
| Solvent exposure | SASA via surface_analysis.py | Uniformly high exposure, no buried core |
| Shape vs. chain length | Shape metrics | Rg >> 2.5 × N^0.4 Å (much larger than expected for globular protein of N residues) |
| Missing residues | Chain breaks via parse_structure.py | >30% of expected residues unresolvable in experimental structures |
| Contact density | Inferred from SASA | No region with packed hydrophobic core (buried fraction <30%) |

### What Is NOT a Disorder Indicator

- **Low pLDDT** does not mean disorder. Novel folds underrepresented in training data
  may have low confidence but perfectly ordered structure.
- **High B-factors** do not mean disorder. Anisotropic motion in a well-folded protein
  at high resolution produces high B-factors.
- These metrics report prediction confidence or crystallographic displacement, not
  the presence or absence of stable tertiary structure.

### Assessment Logic

The agent evaluates **convergence** of structural disorder indicators, not any single
metric:

- **Low disorder:** Secondary structure elements present, buried core exists, dimensions
  match chain length. Proceed with full analysis.
- **Mixed:** Some regions folded, others disordered. Segment the reporting. Whole-chain
  metrics are unreliable. Offer domain-specific Phase 2 analysis.
- **Predominantly disordered:** Indicators converge — overwhelmingly coil, no buried
  core, extended dimensions, extensive missing residues. Stop and tell the user that
  structural analysis cannot extract meaningful information. Offer disorder-specific
  follow-ups (charge distribution, low-complexity regions, short linear motifs).

---

## Fold, Shape & Overall Architecture

**Always report the overall fold and shape first.** Even if the protein is a generic globular
enzyme, state that explicitly. The reader needs a mental model of the protein before
interpreting any detailed findings.

### SCOP Class

The four main structural classes based on secondary structure content:

| SCOP Class | Typical SS Content | Examples |
|---|---|---|
| All-alpha | >40% helix, <10% sheet | Globins, cytochrome c, four-helix bundles |
| All-beta | >30% sheet, <10% helix | Immunoglobulin domains, beta-propellers, beta-barrels |
| Alpha/beta | >15% each, mixed topology | TIM barrels, Rossmann folds, alpha/beta hydrolases |
| Alpha+beta | >5% each, segregated | Ferredoxins, ubiquitin-like, thioredoxin |

### Common Fold Signatures

When reporting fold classification, always include:
- The SCOP class and closest fold match
- SCOP and CATH identifiers when available
- The confidence level (high/moderate/low) and what it's based on
- Whether database verification (SCOP/CATH/Dali/ECOD) would be needed for definitive assignment

Key fold archetypes to recognize:

- **Alpha/beta hydrolase** (SCOP c.69, CATH 3.40.50): Central beta-sheet of 5–8 strands
  flanked by alpha-helices. Contains the catalytic triad. 20–30% helix, 18–28% sheet.
  Globular. Includes lipases, esterases, PETases.
- **TIM barrel** (SCOP c.1, CATH 3.20.20): (β/α)₈ barrel, ~40% helix, ~25% sheet.
  Active site at the C-terminal end of the barrel. Roughly spherical.
- **Rossmann fold** (SCOP c.2, CATH 3.40.50): βαβαβ motif, nucleotide binding.
  ~35% helix, ~20% sheet.
- **Beta-sandwich** (various): Two beta-sheets packed face-to-face. High beta content (>35%).
  Immunoglobulin-like, fibronectin, jelly-roll topologies.
- **Beta-propeller** (SCOP b.66): Repeated 4-stranded beta-sheet blades arranged radially.
  >40% sheet, typically >200 residues.

### Fold Category Reference

When describing a protein's fold, report the structural category and its defining features.
Do NOT name specific proteins as comparisons — this can bias interpretation. Describe the
fold topology and let the user draw their own conclusions about functional implications.

| Fold | SCOP | CATH | Topology | Typical SS | Size Range | Functional Context |
|---|---|---|---|---|---|---|
| Alpha/beta hydrolase | c.69 | 3.40.50 | Central parallel β-sheet (5–8 strands) flanked by α-helices; catalytic triad (Ser-His-Asp/Glu) at strand C-termini | 20–30% H, 18–28% E | 150–550 res | Hydrolases, esterases, lipases, peptidases, dehalogenases |
| TIM barrel | c.1 | 3.20.20 | (β/α)₈ closed barrel; 8 parallel β-strands forming inner barrel, 8 α-helices on exterior; active site at C-terminal barrel end | 30–45% H, 20–30% E | 200–500 res | Isomerases, aldolases, synthases, oxidoreductases — the most functionally diverse fold |
| Rossmann fold | c.2 | 3.40.50 | βαβαβ repeating motif; parallel β-sheet (typically 6 strands) sandwiched between α-helices; nucleotide-binding pocket at sheet-helix junction | 30–45% H, 15–25% E | 150–500 res | NAD(P)+/FAD-dependent oxidoreductases, transferases, nucleotide-binding enzymes |
| Beta-sandwich (Ig-like) | b.1 | 2.60.40 | Two antiparallel β-sheets packed face-to-face; Greek key or jelly-roll connectivity | <10% H, >35% E | 50–250 res | Recognition domains, structural scaffolds, adhesion, carbohydrate binding |
| Beta-propeller | b.66 | 2.130.10 | Radially arranged β-sheet blades (4–8 blades, each 4 strands); central channel or binding surface | <10% H, >40% E | 200–650 res | Protein-protein interaction, signal transduction, hydrolysis |
| Four-helix bundle | a.24 | 1.20.120 | Four antiparallel α-helices packed in a bundle; hydrophobic core between helices | >60% H, <5% E | 60–180 res | Electron transport, metal binding, cytokine signaling |
| Globin fold | a.1 | 1.10.490 | 6–8 α-helices in a characteristic 3-over-3 sandwich; hydrophobic pocket for heme or similar cofactor | 55–80% H, <5% E | 100–200 res | Gas transport, storage, sensing, enzymatic oxidation |
| Coiled-coil | a.35 | 1.20.5 | Two or more α-helices wound around each other with heptad repeat (abcdefg); elongated shape | >70% H, minimal E | Variable | Structural scaffolds, molecular motors, transcription factors, membrane fusion |
| Thioredoxin fold | c.47 | 3.40.30 | Central β-sheet (4–5 strands, mixed parallel/antiparallel) flanked by α-helices; CxxC active-site motif | 20–35% H, 15–25% E | 80–130 res | Redox regulation, disulfide exchange, glutathione metabolism |

When Claude identifies a fold, it should:
1. State the fold name and SCOP/CATH identifiers
2. Describe the topology in structural terms (e.g., "central 8-stranded parallel beta-sheet
   with flanking helices" rather than "same fold as protein X")
3. Note the functional context of the fold class without implying the analyzed protein
   shares any specific function
4. If multiple candidates match, report all with confidence levels and explain what
   distinguishes them (topology verification, strand count, etc.)

### Shape Metrics

| Asphericity | Shape | Typical Examples |
|---|---|---|
| < 0.05 | Spherical/globular | Most enzymes, globins |
| 0.05–0.15 | Roughly globular | Slightly asymmetric globular proteins |
| 0.15–0.30 | Oblate or moderately elongated | Disc-like proteins, flat domain arrangements |
| > 0.30 | Prolate (elongated) | Coiled-coils, multi-domain strings, fibrous proteins |

**Important**: If a predicted structure includes an unstructured signal peptide or disordered
tail, asphericity will be inflated. Always note when disordered termini skew the shape metrics
and report what the shape would be for the structured core alone.

Radius of gyration (Rg) scales with protein size: approximately Rg ≈ 2.5 × N^0.4 Å for
a well-folded globular protein of N residues. Significantly larger Rg suggests extended or
multi-domain architecture.

---

## Surface Properties

### Surface Hydrophobicity

The mean surface hydrophobicity (Kyte-Doolittle scale, exposed residues only) indicates
overall surface character:

| Mean Surface Hydrophobicity | Interpretation |
|---|---|
| < -2.0 | Highly polar/charged surface — typical for soluble proteins |
| -2.0 to -0.5 | Moderately polar — common for enzymes |
| -0.5 to +0.5 | Mixed hydrophobic/polar — possible membrane association or protein-protein interface |
| > +0.5 | Hydrophobic surface — unusual for soluble proteins, suggests membrane contact or aggregation |

### Hydrophobic Patches

Contiguous exposed hydrophobic residues (≥3 residues, mean Kyte-Doolittle > 1.5) are
functionally significant. They may indicate:
- **Protein-protein interaction interfaces**: Hydrophobic patches that bury on complex formation
- **Membrane-binding surfaces**: Amphipathic patches that insert into bilayers
- **Substrate-binding platforms**: Flat hydrophobic surfaces that recruit hydrophobic substrates
  (e.g., PET polymer binding in PETases)
- **Signal peptides**: N-terminal hydrophobic stretches in secreted proteins (expected, not a finding)
- **Aggregation-prone regions**: If uncompensated by charged neighbors

### Surface Charge Distribution

Report the net surface charge and the spatial distribution of positive/negative residues:
- **Net charge near zero**: Typical for most soluble proteins at neutral pH
- **Strong net positive**: May indicate nucleic acid binding (histones, ribosomal proteins)
- **Strong net negative**: May indicate cation binding, repulsion of like-charged substrates
- **Charge asymmetry**: Positive and negative residues clustered on opposite faces suggests
  a dipole moment, which can drive oriented binding

### Exposure Distribution

| Category | Relative SASA | Typical Fraction (globular protein) |
|---|---|---|
| Exposed | > 40% | 25–35% of residues |
| Partially buried | 15–40% | 20–30% |
| Buried | < 15% | 40–55% |

Significant deviation from these ranges is noteworthy:
- Very high buried fraction (>60%) suggests a tightly packed core
- Very low buried fraction (<30%) may indicate a disordered or extended conformation
  (see Disorder Assessment section)

---

## Structural Context Search

### Purpose

Literature search contextualizes structural observations. It is NOT used to identify
proteins. Queries are constructed from observed structural features, never from
filenames or guessed names.

### Query Construction Priority

1. **Fold class + functional landscape:** "alpha/beta hydrolase fold catalytic mechanism"
2. **Cofactor coordination geometry:** "histidine-coordinated magnesium phosphotransfer"
3. **Unusual structural elements:** "proline kink transmembrane helix function"
4. **Domain architecture combinations:** "PAS domain coupled histidine kinase phosphorelay"
5. **User-provided context as modifier:** Append organism/pathway terms to the above

### Framing Results

Always frame literature findings as structural analogy, not identification:

**Correct:** "The domain architecture (multi-pass TM + large periplasmic domain coupled
to a PAS-HPt module with Mg²⁺-coordinated histidine) is characteristic of bacterial
two-component signaling systems."

**Incorrect:** "This protein is a two-component signaling receptor."

**Correct:** "This fold (c.69, alpha/beta hydrolase) is associated with hydrolytic
enzymes that cleave ester bonds, including lipases, esterases, and PET-degrading enzymes."

**Incorrect:** "This is a PETase."

### Convergence

When multiple independent structural signals point to the same functional family
(e.g., fold class AND cofactor coordination AND domain architecture), note the convergence
explicitly. Convergent evidence is stronger than any single signal, but it is still
structural inference, not identification.

---

## Comparative Analysis

### RMSD Interpretation

| Global Cα RMSD | Interpretation |
|---|---|
| < 0.5 Å | Nearly identical — differences are at noise level or crystal packing |
| 0.5–1.0 Å | Very similar — minor side-chain rearrangements, same backbone |
| 1.0–2.0 Å | Moderate — localized conformational changes likely present |
| 2.0–3.0 Å | Significant — domain movements, loop rearrangements, or hinge motions |
| > 3.0 Å | Major conformational change — different functional state or large domain movement |

### What Drives RMSD

When global RMSD is elevated, always check:
- **Core RMSD vs global RMSD**: If core RMSD is much lower than global, a few regions
  dominate the deviation. Report these regions specifically.
- **High-deviation regions**: Contiguous stretches above threshold. Classify as:
  - *Loops*: Flexible surface loops often show high deviation but are functionally
    unimportant. Low confidence (B-factor/pLDDT) in both structures suggests disorder.
  - *Hinge motions*: Rigid-body domain movements with a clear pivot point. Look for
    two well-superposed domains connected by a high-deviation hinge.
  - *Functional rearrangements*: Conformational changes near active sites or binding
    pockets. These are the most significant findings.
  - *Crystal contacts*: Regions that differ due to different crystal packing environments.
    Check if high-deviation residues are at crystal contact interfaces.

### Multi-Structure Comparisons

When comparing multiple structures against a reference:
- Look for **convergent deviations** — regions that move consistently across all queries
  suggest a systematic conformational change, not noise.
- If one query is similar and another divergent, the divergent one may represent a
  different functional state, ligand-bound vs apo, or different crystallization conditions.
- Report the range of RMSD values and whether they cluster or span a continuum.

---

## Binding Sites & Ligand Interactions

### Interaction Strength Hierarchy

1. **Salt bridges** (< 4.0 Å between charged groups): Strongest non-covalent interaction.
   A single salt bridge can contribute 1–5 kcal/mol.
2. **Hydrogen bonds** (< 3.5 Å donor–acceptor): Backbone H-bonds are structural; side-chain
   H-bonds to ligand are often specificity determinants.
3. **π-stacking** (< 5.5 Å centroid–centroid): Common with aromatic ligands. Parallel and
   T-shaped arrangements both count.
4. **Hydrophobic contacts** (< 4.5 Å C–C): Individually weak but collectively significant.
   Pocket shape complementarity is driven by hydrophobic packing.

### Druggability Signals

A pocket is likely druggable if:
- Total pocket residues ≥ 10
- Hydrophobic fraction > 40%
- Mix of hydrogen bond donors and acceptors at the rim
- Pocket is concave and enclosed, not a flat surface patch
- Residues are from multiple secondary structure elements (not just one loop)

### Catalytic Site Signals

Suspect a catalytic site if:
- Charged residues (Asp, Glu, His, Lys) are clustered in the pocket
- Metal ions (Zn, Mg, Mn, Fe) are coordinated by pocket residues
- A small molecule resembles a substrate, product, or cofactor
- Pocket residues are highly conserved (if conservation data is available)

### Allosteric Site Signals

Suspect an allosteric site if:
- The binding site is distant from the known active site (> 15 Å)
- Ligand binding causes conformational change propagating to a distant region
- The pocket is less conserved than the active site

### Ligand Pose Quality

- **Ligand B-factors much higher than surrounding protein**: The ligand position is
  uncertain. Report this as a confidence caveat.
- **Ligand B-factors comparable to protein**: Good confidence in the binding pose.
- **Very few interactions detected**: The ligand may be a crystallization artifact,
  weakly bound, or incorrectly modeled.

---

## Structure Quality & Validation

### Ramachandran Benchmarks

| Metric | Good | Acceptable | Concerning |
|---|---|---|---|
| Favored (%) | > 98% | 95–98% | < 95% |
| Allowed (%) | > 99.5% | 98–99.5% | < 98% |
| Outliers (%) | < 0.5% | 0.5–2% | > 2% |

A few Ramachandran outliers are normal in well-refined structures — they often occur at
functional sites (strained conformations near active sites or ligand-binding loops).
Outliers in featureless loops are more concerning as they suggest refinement problems.

### B-factor Interpretation

B-factors encode atomic displacement. Context matters:

| Resolution | Typical B-factor range | High B-factor threshold |
|---|---|---|
| < 1.5 Å | 5–25 Å² | > 40 Å² |
| 1.5–2.5 Å | 15–40 Å² | > 60 Å² |
| 2.5–3.5 Å | 25–60 Å² | > 80 Å² |
| > 3.5 Å | 40–80 Å² | Difficult to interpret |

Very high B-factors indicate disorder or poor electron density. If a region of interest
has B-factors much higher than the structure average, note this as a confidence caveat.

### Clash Analysis

- Clashscore < 5: Excellent refinement
- Clashscore 5–15: Acceptable
- Clashscore > 15: Potentially problematic — investigate clash locations

Clashes near functional sites are more concerning than surface clashes.

### Resolution-Dependent Trust

| Resolution | What you can trust |
|---|---|
| < 1.5 Å | Individual atom positions, hydrogen atoms, alternative conformations |
| 1.5–2.5 Å | Backbone trace, side-chain rotamers, water positions |
| 2.5–3.5 Å | Backbone trace, approximate side-chain positions, large ligands |
| > 3.5 Å | Backbone trace only — side-chain positions are modeled, not observed |

---

## Sequence-Structure Mapping

### Surface Accessibility Categories

| Relative SASA | Category | Typical residues |
|---|---|---|
| > 40% | Exposed | Charged, polar, mutation-tolerant |
| 15–40% | Partially buried | Mixed — context-dependent |
| < 15% | Buried | Hydrophobic core — mutations often destabilizing |

### Mutation Impact Framework

Assess mutation impact along three axes:

1. **Location**: Buried mutations are more disruptive than surface mutations. Active site
   mutations are functionally critical regardless of burial.
2. **Chemical change**: Conservative substitutions (e.g., Leu→Ile) are less disruptive
   than radical ones (e.g., Gly→Trp, charge reversals).
3. **Conservation**: Mutations at highly conserved positions are more likely deleterious.
   Variable positions tolerate substitution.

### Domain Boundary Identification

Look for:
- Regions of low contact density between chain segments
- Hinge points in comparative analysis (high deviation flanked by low deviation)
- Linker regions (extended conformation, high B-factors, poor electron density)

---

## AlphaFold-Specific Interpretation

### pLDDT Confidence Tiers

| pLDDT range | Interpretation |
|---|---|
| > 90 | High confidence — backbone and side-chain positions reliable |
| 70–90 | Confident — backbone reliable, side-chains approximate |
| 50–70 | Low confidence — fold may be correct but details unreliable |
| < 50 | Very low — likely disordered or no confident prediction |

### What NOT to Interpret from AlphaFold Predictions

- **B-factors**: These ARE pLDDT scores, not experimental displacement parameters.
  Do not interpret them as flexibility or dynamics.
- **Crystal contacts**: AlphaFold predicts a single chain in vacuum. There are no crystal
  contacts, symmetry mates, or lattice effects.
- **Ligand binding**: AlphaFold does not predict ligand positions. An empty pocket
  in an AlphaFold model does not mean the protein doesn't bind ligands.
- **Oligomeric state**: Standard AlphaFold predictions are monomeric. Do not infer
  biological assembly from a single-chain prediction.
- **Conformational states**: AlphaFold typically predicts one state (often the most
  populated in the training data). Alternative conformations are not modeled.

### PAE (Predicted Aligned Error) Matrix

If PAE data is available:
- Low PAE between domains → confident relative positioning
- High PAE between domains → domains may be correctly folded individually but their
  relative orientation is uncertain
- High PAE within a domain → the domain prediction itself is unreliable

---

## Red Flags

Conditions that warrant explicit user attention in the report:

### Structure Quality Red Flags
- Ramachandran outliers > 2%
- Clashes at functional sites (active site, binding pocket, interface)
- Resolution > 3.5 Å for any analysis depending on side-chain positions
- B-factors at region of interest >> structure average
- Missing residues in or adjacent to regions of interest

### Binding Site Red Flags
- Ligand B-factors >> surrounding protein B-factors (uncertain pose)
- Very few protein-ligand interactions (< 3 total) — possible artifact
- Ligand modeled with partial occupancy
- Binding pocket composed primarily of residues from crystal contacts

### Comparative Analysis Red Flags
- Global RMSD > 3 Å without clear structural explanation
- Chain matching failures — unmatched chains may indicate different biological assemblies
- Sequence identity < 90% between matched chains — interpret RMSD with caution,
  sequence differences contribute to structural differences independently
- Core RMSD close to global RMSD — deviation is distributed, not localized

---

## Phylogeny and Function Context

When conservation data or functional annotation is available, apply these principles:

### Conservation Elevates Significance

- A Ramachandran outlier at a **conserved** position → potential functional strain,
  report prominently
- The same outlier at a **variable** surface loop → likely noise, mention briefly
- A binding site residue that is **conserved** across the family → likely functionally
  critical, not just structurally tolerated
- A high-deviation region in comparative analysis at **conserved** positions →
  functional conformational change, not drift

### Conservation Diminishes Significance

- High B-factors at a **variable** loop → expected flexibility at a non-constrained position
- Missing residues at **variable** termini → common and unimportant

### Function Prioritizes Findings

When biological function is known:
- Binding sites for known substrates/cofactors are reported first and in detail
- Crystal contacts and artifact ligands are deprioritized
- Conformational changes near the active site are flagged as mechanistically relevant
- Interface analysis focuses on biologically relevant oligomeric contacts, not crystal contacts

### Without Conservation or Function

When no external annotation is provided:
- All findings are reported descriptively
- Claude does NOT speculate about function from coordinates alone beyond fold-level observations
- Binding sites are reported equally regardless of assumed biological relevance
- The report notes that conservation/function data would upgrade interpretation
