# DIRECTIONS

How to deploy and run `structure-agent`. Assumes you have read [`README.md`](README.md) for the project's purpose and architecture.

The pipeline runs four agents in sequence; each can also be invoked standalone. Below covers prerequisites, then per-agent deployment and invocation in pipeline order.

> **Current state.** Agent 1 exists only as Step 1 — a standalone single-monomer Boltz-2 proof on Modal. Batch fan-out, orchestration, retry logic, and LLM intake are not yet implemented and are not covered here. Agent 2 is documented as a Claude skill; direct CLI invocation of its scripts is not covered.

---

## Prerequisites

### Local environment

- Python 3.10 or newer
- DSSP (`mkdssp`) for Agent 2 secondary structure assignment
  - Linux: `apt-get install dssp`
  - macOS: `brew install brewsci/bio/dssp`
  - Windows: install via WSL or a pre-built binary

Per-agent Python dependencies live in each agent's directory; install them as needed.

### Modal (required for Agents 0 and 1)

```bash
pip install modal
modal token set --token-id <YOUR_ID> --token-secret <YOUR_SECRET>
```

Confirm GPU access on your Modal account before deploying Agent 1 (A100 required).

### Anthropic API key

Stored as a Modal secret. Not used by Agent 0 or by Agent 1 Step 1. Will be needed when Agent 1's LLM intake step is implemented.

### Claude harness (required for Agents 2 and 3)

Agent 2 and Agent 3 are Claude skills / agents — invoke them through Claude Code or claude.ai. No additional CLI is required.

---

## Agent 0 — input preprocessing

**Install host dependencies:**

```bash
pip install -r src/agent_0/requirements-orchestrator.txt
```

The fast-path and slow-path Modal images install their own pinned dependencies (`requirements-fast.txt`, `requirements-slow.txt`) when the images are built.

**Deploy the Modal app (one-time, or after image changes):**

```bash
modal deploy src/agent_0/modal_app.py
```

**Run a batch:**

```bash
python -m agent0.orchestrator \
    --input /path/to/input.fasta \
    --output-dir /path/to/output \
    [--client-metadata /path/to/metadata.json]
```

**Outputs (in `--output-dir`):**

| File              | Contents                                                                                                                                          |
|-------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| `cleaned.faa`     | Amino-acid FASTA, ready for Agent 1                                                                                                               |
| `sidecar.jsonl`   | One JSON per output AA record: verdict, frame, genetic code, perplexity, transformations, original sequence, client metadata                      |
| `rejections.jsonl`| One JSON per rejected input: reason, stage, original sequence, client metadata                                                                    |

**Smoke tests:**

```bash
pip install pytest biopython
python -m pytest src/agent_0/test_fast_path.py -v
```

17 fast-path tests, no Modal / GPU dependency. Slow-path validation requires the deployed environment.

**Known limitations:**

- ESM-2's 1024-residue context window truncates sequences 1024–2000 aa during scoring. Chunked-mean perplexity is not yet implemented.
- Heavy IUPAC ambiguity codes (R, Y, W, S, K, M, B, D, H, V, N) classify as protein and are caught only by the downstream X-fraction gate.

See [`src/agent_0/README.md`](src/agent_0/README.md) for module-by-module detail.

---

## Agent 1 — structure prediction (Step 1)

**Scope of Step 1:** prove Boltz-2 runs cleanly on Modal and produces a usable prediction for a single monomer. No orchestration, no batch fan-out, no quality gate, no Agent 0 integration.

**Install local driver dependencies:**

```bash
pip install modal biopython numpy
```

**Deploy the Modal app:**

```bash
cd src/agent_1
modal deploy modal_app.py
```

The first invocation pulls Boltz weights (~few GB) and builds the container image. Subsequent runs reuse the cached image and volume.

**Run a prediction:**

```bash
python step1_runner.py \
    --fasta /path/to/input.fasta \
    --output-dir ./step1_results/ \
    --structure-id <run_id>
```

**Outputs (in `--output-dir`):**

| File                          | Contents                                                                          |
|-------------------------------|-----------------------------------------------------------------------------------|
| `<run_id>_predicted.cif`      | Predicted structure                                                               |
| `<run_id>_result.json`        | Confidence metrics, runtime, Boltz version, Modal scheduling overhead             |

**Validate against a reference:**

```bash
python validate.py \
    --predicted ./step1_results/<run_id>_predicted.cif \
    --reference /path/to/reference.cif
```

Reports BioPython-based Cα RMSD on the overlap region.

**Pinned versions:** Boltz `2.2.1`, Python `3.11`, A100 GPU.

**Step 1 success criteria — all four must hold:**

1. Image builds and the Modal function runs end-to-end.
2. Predicted CIF parses and residue count matches input within tolerance.
3. Confidence metrics in expected range: `complex_plddt > 0.75`, `ptm > 0.7` for well-characterized targets.
4. Global Cα RMSD < 2.5 Å on the overlap region.

**Cost expectations:** Modal A100 ~$3–4/GPU-hr. A 290 aa monomer at default recycling and sampling runs in 1–3 minutes — pennies per prediction. The one-time image build dominates upfront cost.

**Known caveats:**

- Residue numbering: experimental crystals start at the first resolved residue; predictions number from residue 1 of the submitted sequence. Validator falls back to recursive search if naive numbering matching fails.
- Signal peptide and His-tag in the submitted FASTA fold as disordered extensions and inflate RMSD against the mature crystal. Inspect per-residue deviation to localize.
- Boltz output path: parser looks for `<out_dir>/predictions/<stem>/<stem>_model_0.cif` then falls back to recursive `*_model_0.cif` search. Watch for parse errors if Boltz changes its layout.

See [`src/agent_1/README_step1.md`](src/agent_1/README_step1.md) for the full Step 1 spec.

---

## Agent 2 — structural description (Claude skill)

Agent 2 runs as a Claude skill. Drop one or more PDB / mmCIF files into Claude and ask for analysis.

**Setup:**

- **Claude Code:** place `src/agent_2/` in your project's skill location, or install the packaged `.skill` file. Dependencies install automatically.
- **claude.ai:** upload structure files directly. Dependencies install in the ephemeral container at runtime.

**Trigger:** the skill activates on `.pdb`, `.cif`, `.mmcif` files and on keywords like *superposition*, *RMSD*, *binding pocket*, *B-factor*, *pLDDT*, *AlphaFold*.

**Sample prompts:**

- "Analyze this structure"
- "Compare these two PDB files"
- "What's in the binding site?"
- "Give me a full structural analysis"

**Phase 1 workflow (fixed; runs the same way every time):**

1. Detect inputs.
2. Gather user context (free-text, optional).
3. Parse every uploaded file.
4. Run surface analysis on every uploaded file.
5. **Disorder gate** — halt if predominantly disordered.
6. Compare structures if multiple are provided.
7. Run binding-site analysis if any structure contains non-solvent ligands.
8. Validate user context against structural data.
9. Read the interpretation guide.
10. Structural-context literature search (observed-feature based, never identity-based).
11. Assemble the PDF report.

If any script fails, the pipeline halts and presents the error.

**Phase 2 (optional):** iterative consultation. Bespoke code only here, only at the user's direction.

**Phase 1 fixed parameters (override only in Phase 2):**

| Parameter                | Value                                              |
|--------------------------|----------------------------------------------------|
| Pocket cutoff            | 5.0 Å                                              |
| High-deviation threshold | 2.0 Å Cα displacement                              |
| H-bond cutoff            | 3.5 Å                                              |
| Salt bridge cutoff       | 4.0 Å                                              |
| Hydrophobic cutoff       | 4.5 Å                                              |
| π-stack cutoff           | 5.5 Å                                              |
| Chain matching           | by sequence length, 5% tolerance                   |

**Deliverable formats (selectable):** PDF (default), interactive HTML dashboard, raw CSV / 300 DPI PNG figures, or all of the above.

**Identity-agnostic guarantee:** Phase 1 never identifies a protein by name or function. Filenames are opaque labels. Fold classification reports structural categories, not specific protein names. Literature search targets observed features, not guessed identities.

See [`src/agent_2/README.md`](src/agent_2/README.md) and [`src/agent_2/SKILL.md`](src/agent_2/SKILL.md) for the full skill specification.

---

## Agent 3 — literature retrieval

Agent 3 runs as a Claude agent over Foldseek output. It does not run Foldseek itself — provide the hits.

**Inputs (any of):**

- `OBJECT.foldseek_results.md` (preferred — see template at [`src/agent_3/OBJECT.foldseek_results.md`](src/agent_3/OBJECT.foldseek_results.md))
- Raw m8 / TSV from `foldseek easy-search`
- Pasted Foldseek output

**Required columns:** `query`, `target`, `evalue`, plus at least one of `alntmscore`, `qtmscore`, `ttmscore`, `prob`. `theader`, `taxname`, `taxlineage` are used when present.

**Trigger phrases:**

- "Run foldseek-literature-retrieval"
- "Find papers for these Foldseek hits"
- "What's been published on these structural homologs?"
- "Reading list for this Foldseek result"

**Parameter overrides:**

| Parameter      | Default | Override syntax           |
|----------------|---------|---------------------------|
| `tm_score_min` | 0.5     | "TM-score above 0.6"      |
| `evalue_max`   | 1e-3    | "e-value below 1e-5"      |
| `max_anchors`  | 10      | "top 5 anchors only"      |
| `max_results`  | 15      | "up to 25 papers"         |

**Target ID handling:**

| Source                              | Resolved as          | PubMed              |
|-------------------------------------|----------------------|---------------------|
| PDB chain (`1abc_A`)                | PDB code             | yes                 |
| AlphaFold DB (`AF-Q12345-F1-...`)   | UniProt accession    | yes                 |
| ESMAtlas (`MGYP...`)                | —                    | skipped, reported   |
| Other                               | verbatim             | flagged for review  |

**Output:** markdown reading list with Foldseek-hits-to-anchors mapping, per-paper anchor attribution, and anchor-depth × TM-score ranking. Anchor-hitting papers are ranked above context-only papers. Format detailed in [`src/agent_3/AGENT.foldseek-literature-retrieval.md`](src/agent_3/AGENT.foldseek-literature-retrieval.md).

**Empty-result handling:** the agent reports the gap and asks before relaxing thresholds. It will never silently broaden the query.

---

## Configuration summary

Operator-tunable thresholds across the pipeline:

**Agent 0** (`src/agent_0/config.py`):

| Parameter                 | Default | Notes                                     |
|---------------------------|---------|-------------------------------------------|
| `LENGTH_MIN_AA`           | 50      | Below: structure prediction unreliable    |
| `LENGTH_MAX_AA`           | 2000    | Above: Boltz-2 / ESMFold throughput drops |
| `X_FRACTION_MAX`          | 0.02    | Total ambiguity ceiling                   |
| `X_RUN_MAX`               | 3       | Consecutive ambiguity run                 |
| `X_TERMINAL_BUFFER`       | 10      | Zero ambiguity in first / last 10 aa      |
| `DEFAULT_GENETIC_CODE`    | 11      | Bacterial / phage standard                |
| `PERPLEXITY_REJECT_ABOVE` | 15.0    | **Calibrate on real data**                |
| `PERPLEXITY_TIE_FRACTION` | 0.15    | Multi-ORF emission band                   |

**Agent 2:** Phase 1 parameters fixed; override only in Phase 2.

**Agent 3:** TM-score and e-value thresholds calibration-deferred. User can override per run.

---

## Tests and smoke checks

| Agent   | Test                                       | Notes                                       |
|---------|--------------------------------------------|---------------------------------------------|
| Agent 0 | `pytest src/agent_0/test_fast_path.py`     | 17 fast-path tests, no Modal / GPU          |
| Agent 1 | Step 1 success criteria above              | Image build + RMSD against a reference      |
| Agent 2 | None (yet)                                 | Skill is exercised manually via Claude      |
| Agent 3 | None (yet)                                 | Agent is exercised manually via Claude      |

---

## Where to find more detail

- Agent 0: [`src/agent_0/README.md`](src/agent_0/README.md)
- Agent 1: [`src/agent_1/README_step1.md`](src/agent_1/README_step1.md)
- Agent 2: [`src/agent_2/README.md`](src/agent_2/README.md), [`src/agent_2/SKILL.md`](src/agent_2/SKILL.md)
- Agent 3: [`src/agent_3/AGENT.foldseek-literature-retrieval.md`](src/agent_3/AGENT.foldseek-literature-retrieval.md), [`src/agent_3/OBJECT.foldseek_results.md`](src/agent_3/OBJECT.foldseek_results.md), [`src/agent_3/VERB.pubmed-search-skill.md`](src/agent_3/VERB.pubmed-search-skill.md)
