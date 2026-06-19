# Agent 1 — Structure prediction

Curated amino-acid FASTA → folded 3D structures + confidence-annotated metadata,
for handoff to Agent 2. Engine: **ESMFold2-Fast** (Biohub) — single-sequence, no
MSA — chosen for novel / metagenomic / low-homology targets where MSAs are scarce
or uninformative.

Operates in fold-and-annotate mode only: it predicts coordinates and records
confidence, but performs **no biological interpretation** and **no quality
rejection**. Every fold is emitted and tagged with a pLDDT tier; downstream
agents decide what to trust.

## Architecture

A warm-model Modal app driven by a local orchestrator:

```
cleaned.faa ─┐
sidecar.jsonl┤
             ▼
       orchestrator.py ──► fold_app (GPU, ESMFold2-Fast)
             │                warm @app.cls, .map() over records
             │                      │
             ▼                      ▼
   structures.jsonl  ◄──── per record: cif, pLDDT, pTM, iPTM
   rejections.jsonl  ◄──── fold failures (logged, not escalated)
   structures/<record_id>.cif
```

## Layout

| Path | Purpose |
| ---- | ------- |
| `fold_app/modal_app.py` | ESMFold2-Fast Modal app. Warm `@app.cls`, `fold()` method. Self-contained model / GPU constants. |
| `orchestrator.py`       | Local driver: read Agent 0 output → fan folds → annotate confidence → write outputs. |
| `shared/config.py`      | Orchestrator knobs: confidence tiers (TUNE), output names, app-lookup names. |
| `shared/schemas.py`     | `StructureRecord` (→ structures.jsonl), `FoldFailure` (→ rejections.jsonl), `classify_confidence`. |
| `validate.py`           | Lightweight Cα-RMSD validator vs a reference structure (engine-agnostic, minimal-CIF tolerant). |
| `esmfold2_eval.py`      | Single-fold benchmark tool (used for the 6EQE / 1UBQ validations). |
| `boltz_fallback/`       | Prior Boltz-2 Step 1 engine, kept as a documented fallback. |

## Running

```bash
# Run a batch from src/ (so the agent_1 package imports). The fold app runs
# ephemerally (the orchestrator enters `with app.run()`) — no deploy step; it
# spins up and tears down per batch, leaving nothing running afterwards.
python -m agent_1.orchestrator \
    --input-fasta /path/to/cleaned.faa \
    [--sidecar /path/to/sidecar.jsonl] \
    --output-dir /path/to/out/
```

## Outputs

- `structures/<record_id>.cif` — predicted structure, one per folded record.
- `structures.jsonl` — one `StructureRecord` per fold: `record_id`, `parent_id`,
  `cif_path`, `plddt_mean`, `ptm`, `iptm`, `confidence_tier`, `sequence_length`,
  `model`, `fold_params`, and `upstream` (Agent 0's sidecar record, verbatim).
- `rejections.jsonl` — one `FoldFailure` per errored fold: `record_id`,
  `parent_id`, `stage`, `detail`, `upstream`. Failures are logged, not escalated.

## Confidence annotation — not a gate

By design, Agent 1 **never rejects on confidence**. Every fold is emitted; mean
pLDDT is mapped to a tier (`PLDDT_HIGH` / `PLDDT_MEDIUM` in `shared/config.py`,
both **TUNE-on-real-data**) and recorded in the sidecar. Agent 2 (which halts on
predominantly disordered inputs) decides what to do with low-confidence folds.

## Benchmarks

ESMFold2-Fast, single-sequence, scored with `validate.py`:

| Target          | Fold                  | Cα RMSD vs crystal     | Note                                   |
| --------------- | --------------------- | ---------------------- | -------------------------------------- |
| 6EQE PETase     | α/β-hydrolase, 298 aa | 0.91 Å                 | vs 7.85 Å for single-sequence Boltz-2  |
| 1UBQ ubiquitin  | β-grasp, 76 aa        | 0.58 Å (ordered core)  | tail residues 75–76 genuinely flexible |

Both are well-characterized targets: they confirm the engine works across folds
and sizes — **not** performance on the novel/metagenomic target class, which is a
separate validation exercise.

## Known gaps / TODOs

1. **Live batch runs executed.** The `.map()` fan-out over the fold app has now
   been run end-to-end — two batches totalling 8 sequences (216–886 aa), 0 fold
   failures — feeding Agent 2. Larger-scale throughput characterization is still open.
2. **GPU is A100, not yet throughput-tuned.** `fold_app/modal_app.py` uses A100
   (40 GB). L4 (24 GB) OOM'd on larger sequences; A100 has folded up to 886 aa with
   headroom. Cost/throughput tuning (a smaller GPU for short batches, request
   batching) is still open.
3. **Confidence tiers still placeholders — but data now exists.** `PLDDT_HIGH` = 0.90
   looks too strict: across the recent real folds, compact well-formed models scored
   ~0.74–0.88 mean pLDDT and all landed in the *medium* tier, none *high*. Recalibrate
   `PLDDT_HIGH` / `PLDDT_MEDIUM` (`shared/config.py`) downward against a labelled set.
4. **Model revision unpinned.** Pin `ESMFOLD2_REVISION` before production
   (`structures.jsonl` currently records `model_revision: null`).
5. **Deferred** (not automated in code): retry logic, LLM-driven intake, multimer
   support, and an automated Agent 2 handoff — the A1→A2 bridge was driven manually
   in validation (`modal volume put` of the CIFs onto the shared `/scratch` volume,
   then Agent 2's `surface_analysis_remote`), proving the path but not yet wired into
   the orchestrator.
