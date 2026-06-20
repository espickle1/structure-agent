# APSARA — Running the pipeline

Sequences (or structures) in → predicted structures + an interpretive report out.

## Run

```bash
# macOS / Linux
./run_pipeline.sh --input input/example_4/three_environmental_samples.fasta --prompt prompts/report.md
```

```powershell
# Windows
.\run_pipeline.ps1 -Input input\example_4\three_environmental_samples.fasta -Prompt prompts\report.md
```

Run from a **plain shell, not inside Claude Code** — the synthesis step launches its own `claude` process.

## Input (`--input`)

- **One FASTA file** — may hold many records; mix DNA/RNA/protein, unique headers. Records outside 50–2000 aa are skipped. Runs the full pipeline.
- **`.cif` / `.pdb`** (or a directory of them) — BYO mode, skips Agents 0/1. Auto-detected by extension.

## Output

`results/run_YYYYMMDD_HHMMSS/` (override with `--output-dir` / `-OutputDir`) — holds `agent_0/1/2/` and per-protein report `.zip`s.

## Prerequisites

- Python: `biopython numpy scipy pandas matplotlib seaborn gemmi`
- Modal auth (prediction half; apps run ephemerally — no deploy)
- `claude` CLI, installed and authenticated (synthesis shells out to it)
- `mkdssp` optional — a `pydssp` fallback runs without it

Full argument table and the cloud path: see [EXECUTION_SUMMARY.md](EXECUTION_SUMMARY.md).
