# Agent 0 — Input preprocessing for structure prediction pipeline

Converts heterogeneous client input (DNA / RNA / protein FASTA) into clean
amino-acid FASTA + provenance sidecar for handoff to Agent 1.

Operates strictly in transformation/quality-gating mode — no biological
interpretation of what sequences encode.

## Architecture

Two Modal apps, one orchestrator:

```
input.fasta ─┐
             │
             ▼
       orchestrator.py ──────► fast_app (CPU)
             │                    │
             │                    ├─ FAST_PATH_PASS    ──┐
             │                    ├─ PROTEIN_PASSTHROUGH ─┤
             │                    ├─ REJECTED ───────────┤
             │                    └─ SLOW_PATH_NEEDED    │
             │                              │            │
             │                              ▼            │
             │                    slow_app (GPU)         │
             │                    ESM-2 perplexity       │
             │                    code cascade           │
             │                              │            │
             │                              ├─ SLOW_PATH_PASS ─┤
             │                              └─ REJECTED ────────┤
             │                                                  │
             ▼                                                  │
    cleaned.faa  ◄─────────────────────────────────────────────┘
    sidecar.jsonl
    rejections.jsonl
```

## Pipeline stages

| Stage         | Module                          | Output                       |
| ------------- | ------------------------------- | ---------------------------- |
| Ingest        | `agent_0/ingest.py`             | `NormalizedRecord`           |
| Type detect   | `agent_0/type_detect.py`        | `TypedRecord` (DNA/RNA/AA)   |
| Fast translate| `agent_0/fast_translate.py`     | clean-CDS shortcut, code 11  |
| ORF enumerate | `agent_0/orf_enumerate.py`      | `list[ORFCandidate]`         |
| Score         | `agent_0/perplexity_score.py`   | ESM-2 650M perplexity        |
| Select        | `agent_0/orf_select.py`         | accepted candidates          |
| Gate          | `agent_0/quality_gate.py`       | length / X gates             |

Module independence: each stage receives one dataclass and returns another.
No module reads internal state of another's records.

## Deployment

All commands below assume the working directory is `src/` (the parent of the
`agent_0/` package). Run them from there so Python's import system can resolve
`agent_0` as an implicit namespace package.

```bash
# 1. Install dependencies for the host orchestrator:
pip install -r agent_0/requirements-orchestrator.txt

# 2. Deploy Modal apps (one-time, or after image changes).
#    The `-m` flag tells Modal to interpret the argument as a Python module
#    path (required by recent Modal versions; bare module paths are deprecated).
python -m modal deploy -m agent_0.modal_app
# Slow path is not yet implemented; deploy when added:
# python -m modal deploy -m agent_0.slow_modal_app

# 3. Run a batch:
python -m agent_0.orchestrator \
    --input /path/to/input.fasta \
    --output-dir /path/to/output \
    [--client-metadata /path/to/metadata.json]
```

On Windows PowerShell, if Modal's image build fails with a `'charmap' codec`
encoding error, set UTF-8 mode for the shell session before retrying:

```powershell
$env:PYTHONUTF8 = "1"
```

## Outputs

- `cleaned.faa` — amino-acid FASTA, ready for Agent 1
- `sidecar.jsonl` — one JSON object per output AA record:
  - `record_id`, `parent_id`
  - `verdict` (FAST_PATH_PASS / SLOW_PATH_PASS / PROTEIN_PASSTHROUGH)
  - `selected_frame`, `selected_genetic_code`, `nt_coordinates`
  - `perplexity` (slow path only)
  - `is_multi_orf`, `sibling_orfs`
  - `transformations` (audit trail)
  - `original_sequence`
  - `client_metadata` (passthrough)
- `rejections.jsonl` — one JSON object per rejected input:
  - `record_id`, `parent_id`
  - `reason` (RejectionReason enum value)
  - `stage`, `detail`
  - `original_sequence`
  - `client_metadata`

## Configuration

All thresholds in `agent_0/config.py`. Single source of truth.

| Parameter                  | Default | Notes                                     |
| -------------------------- | ------- | ----------------------------------------- |
| `LENGTH_MIN_AA`            | 50      | Below: structure prediction unreliable    |
| `LENGTH_MAX_AA`            | 2000    | Above: Boltz-2 / ESMFold throughput drops |
| `X_FRACTION_MAX`           | 0.02    | 2% total ambiguity ceiling                |
| `X_RUN_MAX`                | 3       | Consecutive ambiguity run                 |
| `X_TERMINAL_BUFFER`        | 10      | First/last 10 aa: zero ambiguity          |
| `DEFAULT_GENETIC_CODE`     | 11      | Bacterial / phage standard                |
| `FALLBACK_GENETIC_CODES`   | (1,4,6,15,25) | Cascade order                       |
| `PERPLEXITY_REJECT_ABOVE`  | 15.0    | **TUNE on real data**                     |
| `PERPLEXITY_TIE_FRACTION`  | 0.15    | Multi-ORF emission band                   |
| `ESM_MODEL_NAME`           | esm2_t33_650M_UR50D | 650M params, A10G fits     |

## Known gaps / TODOs

1. **ESM-2 max length is 1024.** Sequences 1024–2000 aa truncate during
   scoring. Fix: chunked-mean perplexity. Located in
   `agent_0/perplexity_score.py`. **Not yet implemented.**

2. **Three thresholds need real-data calibration:**
   `PERPLEXITY_REJECT_ABOVE`, `PERPLEXITY_TIE_FRACTION`,
   `NUCLEOTIDE_PURITY_MIN`. Defaults are placeholders. Calibrate on a
   batch of known-real proteins + known-junk before production.

3. **Heavy IUPAC ambiguity codes (R, Y, W, S, K, M, B, D, H, V, N) cannot
   be distinguished from protein by alphabet alone** — they are also valid
   AA single-letter codes. Such sequences will classify as protein and be
   caught (or not) by the downstream X-fraction gate. Document for clients.

4. **Codetta integration deferred.** When Agent 0 v1's rejection logs reveal
   a class of recurring failures attributable to non-standard genetic codes
   on novel clades, add Codetta as an opt-in pre-batch mode.

## Tests

Run from `src/`:

```bash
pip install pytest biopython
python -m pytest agent_0/ -v
```

17 fast-path smoke tests, no Modal/GPU dependencies. Slow-path testing
requires actual GPU and is deferred to deployed-environment validation.
