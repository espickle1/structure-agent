# Agent 1 — Step 1: Standalone Boltz-2 on Modal

**Goal:** Prove Boltz-2 runs cleanly in Modal and produces a usable prediction for a well-characterized reference enzyme (PETase, PDB 6EQE).

**Out of scope for this step:** LLM intake, orchestration, quality gate, retry logic, Agent 0 integration, Agent 2 integration. Pure infrastructure proof.

---

## Files

| File | Purpose |
|---|---|
| `modal_app.py` | Modal app definition. Pinned Boltz-2 v2.2.1 image, GPU entry point `predict_structure()`. |
| `step1_runner.py` | Local driver. Reads a FASTA, submits to Modal, downloads predicted CIF, writes a result JSON. |
| `validate.py` | Local validator. BioPython-based Cα RMSD comparison of prediction vs. reference. |
| `README_step1.md` | This file. |

---

## Pinned Versions

- **Boltz:** `2.2.1` (recorded in every result JSON)
- **Python:** `3.11`
- **GPU:** A100 (Modal default)

---

## Prerequisites (one-time setup on your machine)

```bash
# Modal CLI + auth
pip install modal
modal token set --token-id <YOUR_ID> --token-secret <YOUR_SECRET>

# Local dependencies for the driver and validator
pip install modal biopython numpy
```

You said Modal account and GPU access are confirmed, and the Anthropic API key is already stored as a Modal secret. The API key is not needed for Step 1 (no LLM yet) — it'll come in at Step 4.

---

## Running Step 1

From the directory containing `modal_app.py`:

```bash
# 1. Deploy the app (builds the container image, caches it)
modal deploy modal_app.py

# 2. Run the prediction on 6EQE
python step1_runner.py \
    --fasta /path/to/rcsb_pdb_6EQE.fasta \
    --output-dir ./step1_results/ \
    --structure-id 6EQE_step1
```

The first invocation will be slow because Boltz pulls weights (~few GB) and the image builds the first time. Subsequent runs reuse the cached image and volume.

**Expected result file layout:**
```
step1_results/
├── 6EQE_step1_result.json      # Metrics, runtime, version info
└── 6EQE_step1_predicted.cif    # Predicted structure
```

## Validating the Prediction

```bash
python validate.py \
    --predicted ./step1_results/6EQE_step1_predicted.cif \
    --reference /path/to/rcsb_pdb_6EQE.cif
```

---

## Success Criteria

Step 1 passes if **all four** are true:

1. **Image builds and the Modal function runs end-to-end.** No dependency resolution failures, no GPU allocation failures, no Boltz subprocess crashes.
2. **Predicted CIF is valid.** BioPython parses it, residue count within tolerance of the input sequence.
3. **Confidence metrics are in the expected range.** For a well-characterized enzyme: `complex_plddt` > 0.75, `ptm` > 0.7. Lower is concerning but not necessarily fatal (single-sequence mode can be conservative on novel folds — but PETase is not novel).
4. **Global Cα RMSD vs. 6EQE < 2.5 Å** on the overlap region. PETase has lots of close homologs in Boltz-2's training data, so sub-2 Å is achievable even single-sequence.

If any criterion fails, Step 1 is not done — we debug before moving to Step 2.

---

## Cost Expectations

From the design doc:
- PETase (290 aa monomer) on A100 at default recycling (3) and sampling (200) should run in roughly 1–3 minutes
- Modal A100 pricing ~$3–4/GPU-hour → Step 1 single prediction cost is **pennies**
- The one-time image build (baking the Boltz install) is the larger upfront cost — a few minutes of A100 time

The runtime gets recorded in `6EQE_step1_result.json` as `runtime_seconds` (GPU compute time) and `local_wall_clock_seconds` (submit → return round trip including Modal scheduling).

---

## Known Caveats

**Residue numbering.** Experimental crystal structures typically start at the first resolved residue (which, for 6EQE, is after the signal peptide — probably residue 33 or so of the full precursor). The prediction numbers from residue 1 of the submitted sequence. The validator attempts naive residue-number matching first; if the overlap is tiny, it reports the mismatch and flags that Step 2 should add sequence-based chain matching as a robust fallback.

**Signal peptide + His-tag.** The submitted FASTA includes both the native signal peptide (residues 1–25ish) and the C-terminal `HHHHHH` tag from the construct. Boltz will predict both, but they probably fold as disordered extensions (the signal peptide is typically cleaved *in vivo* and disordered *in vitro*; the His-tag is a flexible linker). These will drive up the overall RMSD against the crystal, which resolves only the mature catalytic domain. Validator reports per-residue deviations so we can see if the mismatch is localized to the termini.

**Boltz output path format.** The parser in `modal_app.py::_parse_boltz_output` looks for `<out_dir>/predictions/<stem>/<stem>_model_0.cif` first, then falls back to a recursive `*_model_0.cif` search. If Boltz 2.2.1 changed its output layout, the fallback should still find the file — but watch for parse errors and adjust.

**Image build weight caching.** The current image definition does **not** pre-download Boltz weights at build time. First prediction will pay the weight-download cost (~few minutes). If we want to pre-cache, we'd add a `run_function()` step to the image build that runs a tiny throwaway prediction. Deferred as an optimization — get the happy path working first.

---

## What Step 1 Does NOT Validate

- **Multimer prediction.** Only tested on a monomer here. Step 2 should include a homotrimer test (john_test.cif is a natural target once available).
- **Stoichiometry retry logic.** No retry controller in Step 1. All retries and quality gating come in Step 3.
- **MSA mode.** Single-sequence only per v1 design. Not testing MSA pathway.
- **Metadata sidecar schema.** The Step 1 result JSON is informal; the production sidecar schema gets locked in during Step 6 (Agent 2 integration).

---

## After Step 1 passes

Move to Step 2: batch execution. Take a small FASTA file of N sequences, fan out with `modal_app.predict_structure.map(...)`, collect results. Hardcoded configs (still no LLM). Proves orchestration and parallelism.

---

## Honest Caveat

I wrote this without the ability to run it against your Modal account. The code is based on Boltz 2.2.1's documented CLI and Modal's current API, but there will likely be small things to adjust on first run — a CLI flag that changed, an output path slightly different, a dependency that needs a specific version. Please share the stderr/stdout of the first failing run and I'll fix promptly.
