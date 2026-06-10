# DIRECTIONS

How to deploy and run `structure-agent`. Assumes you have read [`README.md`](README.md) for the project's purpose and architecture.

The pipeline runs four agents in sequence; each can also be invoked standalone. Below covers prerequisites, then per-agent deployment and invocation in pipeline order.

> **Current state.** Agent 1 is operational — ESMFold2-Fast on Modal with a batch orchestrator (covered below). Retry logic and LLM-driven intake are deferred. Agent 2 is documented as a Claude skill; direct CLI invocation of its scripts is not covered.

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

Confirm GPU access on your Modal account before deploying Agent 1 (ESMFold2-Fast runs on H100 by default; right-sizable to a cheaper GPU).

### Anthropic API key

Stored as a Modal secret. Not used by Agent 0 or Agent 1. Will be needed when Agent 1's LLM intake step is implemented.

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

## Agent 1 — structure prediction

ESMFold2-Fast (Biohub) on Modal — single-sequence, no MSA — folds Agent 0's curated FASTA into structures with confidence-annotated metadata for Agent 2. Operational: a warm-model Modal app plus a batch orchestrator.

**Install the local driver dependency:**

```bash
pip install modal
```

The fold runs on Modal; the orchestrator is a thin local driver. `validate.py` additionally needs `biopython numpy`.

**Deploy the fold app (one-time, or after image changes):**

```bash
modal deploy src/agent1/fold_app/modal_app.py
```

The first deploy builds the `esm` image; the first fold downloads ESMFold2-Fast weights to a Modal Volume. Both are cached for subsequent runs.

**Run a batch (from `src/`, so the `agent1` package imports):**

```bash
cd src
python3 -m agent1.orchestrator \
    --input-fasta /path/to/cleaned.faa \
    [--sidecar /path/to/sidecar.jsonl] \
    --output-dir /path/to/out/
```

`--input-fasta` is Agent 0's `cleaned.faa`; pass its `sidecar.jsonl` to carry Agent 0 metadata through unmodified. Without a sidecar, `parent_id` falls back to `record_id`.

**Outputs (in `--output-dir`):**

| File                          | Contents                                                                                          |
|-------------------------------|---------------------------------------------------------------------------------------------------|
| `structures/<record_id>.cif`  | Predicted structure, one per folded record                                                        |
| `structures.jsonl`            | Per fold: pLDDT / pTM / iPTM, confidence tier, model, fold params, + Agent 0 metadata passthrough |
| `rejections.jsonl`            | Per errored fold: stage, detail, passthrough. Fold failures are logged, not escalated             |

**Confidence is annotated, not gated.** Every fold is emitted and tagged with a mean-pLDDT tier (`PLDDT_HIGH` / `PLDDT_MEDIUM` in `src/agent1/shared/config.py`, both **calibrate-on-real-data**). Agent 1 never rejects on quality; Agent 2 decides.

**Validate against a reference (local, no GPU):**

```bash
python3 src/agent1/validate.py \
    --predicted /path/to/out/structures/<record_id>.cif \
    --reference /path/to/reference.cif
```

Reports Cα RMSD over the residue-number overlap. Tolerant of minimal mmCIF — works on both ESMFold2 and RCSB / Boltz output.

**Benchmarks (single-sequence, vs crystal):** 6EQE PETase 0.91 Å; 1UBQ ubiquitin 0.58 Å on the ordered core. Both are easy, well-characterized targets — they confirm the engine, not performance on the novel / metagenomic target class.

**GPU:** the fold app requests H100; the 0.2B Fast model likely fits a cheaper GPU (A10G / L4). Right-size in `src/agent1/fold_app/modal_app.py` before scaling batches.

**Fallback:** the prior Boltz-2 Step 1 engine is preserved under `src/agent1/boltz_fallback/` — see its `README_step1.md`.

See [`src/agent1/README.md`](src/agent1/README.md) for the full package spec.

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

**Agent 1** (`src/agent1/shared/config.py`):

| Parameter      | Default | Notes                                  |
|----------------|---------|----------------------------------------|
| `PLDDT_HIGH`   | 0.90    | ≥ → HIGH tier (annotation, not a gate) |
| `PLDDT_MEDIUM` | 0.70    | ≥ → MEDIUM; below → LOW. Calibrate.    |

**Agent 2:** Phase 1 parameters fixed; override only in Phase 2.

**Agent 3:** TM-score and e-value thresholds calibration-deferred. User can override per run.

---

## Tests and smoke checks

| Agent   | Test                                       | Notes                                       |
|---------|--------------------------------------------|---------------------------------------------|
| Agent 0 | `pytest src/agent_0/test_fast_path.py`     | 17 fast-path tests, no Modal / GPU          |
| Agent 1 | `validate.py` Cα RMSD vs a reference       | 6EQE 0.91 Å, 1UBQ 0.58 Å core (single-seq)  |
| Agent 2 | None (yet)                                 | Skill is exercised manually via Claude      |
| Agent 3 | None (yet)                                 | Agent is exercised manually via Claude      |

---

## Where to find more detail

- Agent 0: [`src/agent_0/README.md`](src/agent_0/README.md)
- Agent 1: [`src/agent1/README.md`](src/agent1/README.md)
- Agent 2: [`src/agent_2/README.md`](src/agent_2/README.md), [`src/agent_2/SKILL.md`](src/agent_2/SKILL.md)
- Agent 3: [`src/agent_3/AGENT.foldseek-literature-retrieval.md`](src/agent_3/AGENT.foldseek-literature-retrieval.md), [`src/agent_3/OBJECT.foldseek_results.md`](src/agent_3/OBJECT.foldseek_results.md), [`src/agent_3/VERB.pubmed-search-skill.md`](src/agent_3/VERB.pubmed-search-skill.md)
