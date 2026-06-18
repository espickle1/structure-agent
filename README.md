# structure-agent

Multi-agent pipeline for high-throughput protein structure prediction and
analysis, focused on novel and metagenomic single-chain proteins — targets
where homologs and MSAs are scarce. Sequences in, structures + analysis out.

## What it does

Heterogeneous FASTA (DNA / RNA / protein, mixed quality) goes in. The
pipeline cleans and translates it to amino-acid sequences, predicts
structures with ESMFold2-Fast (single-sequence, no MSA — suited to
low-homology targets; Boltz-2 stays a documented fallback for multimers),
takes deterministic geometric and surface measurements, and writes an
interpretive report that separates what was measured from what is inferred.
The motivating use case is novel and metagenomic proteins, where sequences
arrive far faster than humans can analyse them; this repo is the automation
layer between "we have sequences" and "we have something worth reading."

## Agents

| Agent | Role | Status |
| --- | --- | --- |
| Agent 0 | Input preprocessing — FASTA cleanup, ORF selection, ESM-2 perplexity gate | Complete |
| Agent 1 | Structure prediction orchestrator — ESMFold2-Fast on Modal (single-sequence); Boltz-2 fallback for multimers | Operational |
| Agent 2 | Final stage — measurement through interpretation. Deterministic scripts measure geometry, surface, secondary structure, shape, and renders (JSON / CSV / PNG); an interpretive `SKILL.md` reads those outputs and writes the report | Complete |

Agent 2 is the end of the pipeline. The interpretation once scoped as a
separate "Agent 3" is merged into Agent 2's `SKILL.md` — one skill, one
deliverable. Homolog- and literature-grounded interpretation (Foldseek +
PubMed) is deferred to a possible separate project; it is not part of this
repo.

## Architectural rules

- **Measured vs inferred.** The report separates what was directly measured
  from what is inferred, and states "insufficient structural evidence to
  assign function" when the structure does not support a call. Fold and
  function are inference — they live in the report's prose, never as fields
  emitted by a measurement script. This boundary prevents biologically
  plausible but incorrect outputs.
- **Identity-agnostic measurement.** Filenames are opaque labels; never
  parsed for biological meaning.
- **Module independence.** Modules within an agent don't depend on each
  other's outputs.
- **Metadata passthrough.** Upstream metadata is forwarded unmodified;
  it never influences geometric measurements.
- **Errors logged, not escalated.** Full automation, no human-in-the-loop.

## Stack

Python · BioPython · orfipy · ESM-2 650M · ESMFold2-Fast · Boltz-2 ·
Modal (CPU + A100 GPU) · DSSP · matplotlib (Cα-trace) / Mol\*. Outputs:
PDB / mmCIF, JSON sidecars, CSV, PNG, markdown report.

## Running from a shell

Drive the pipeline from your own terminal with the coordinator script —
`run_pipeline.ps1` (PowerShell) or `run_pipeline.sh` (bash). Run it from a
plain shell, **not** from inside an interactive Claude Code session: the
synthesis step launches its own `claude` process, and running the script
inside Claude Code would nest a second one.

```powershell
# Windows (PowerShell)
.\run_pipeline.ps1 -Input data\demo\rbp.fasta -Prompt prompts\report.md
```

```bash
# macOS / Linux
./run_pipeline.sh --input data/demo/rbp.fasta --prompt prompts/report.md
```

`--input` takes a FASTA (full pipeline) or a `.cif` / `.pdb` (BYO — Agents 0/1
are skipped, auto-detected from the extension). Results land in
`results/run_YYYYMMDD_HHMMSS/` unless an output directory is given
(`--output-dir` / `-OutputDir`).

**Input format (full pipeline).** `--input` is a **single FASTA file that may
contain many records** — not a directory of one-sequence files. The coordinator
reads exactly one file, so concatenate first if you have several
(`Get-Content *.fasta | Set-Content combined.fasta`, or `cat *.fasta >
combined.fasta`). You can **mix DNA, RNA, and protein records** in that one
file: Agent 0 classifies each record independently, passes protein through, and
translates nucleotide records (genetic code 11 by default, with a fallback
cascade). Give every record a unique FASTA header — it becomes the record ID.
Records outside 50–2000 aa (after translation) are logged to `rejections.jsonl`
and skipped, not folded. BYO mode is a single `.cif` / `.pdb` and skips Agent 0
entirely.

**Prerequisites:** Python deps (`biopython numpy scipy pandas matplotlib
seaborn gemmi`), `mkdssp` for reference-grade secondary structure (optional — a
`pydssp` fallback runs if it's absent, but is less accurate on predicted
backbones), Modal auth + deployed apps (prediction half only — Agents 0/1), and
the **`claude` CLI installed and authenticated** (the synthesis step shells out
to it).

**Synthesis runs two ways.** By default the report-writing step runs
**non-interactively** (`claude -p --permission-mode acceptEdits`) — no permission
prompts, suited to most users, CI, and batch. Pass `--interactive`
(`-Interactive` on PowerShell) to drive it as a supervised `claude` session
instead (useful during development):

```bash
./run_pipeline.sh --input structure.cif --prompt prompts/report.md --interactive
```

Full setup, the complete argument table, and the cloud (`claude.ai/code`) path
are in [EXECUTION_SUMMARY.md](EXECUTION_SUMMARY.md).

## Scope & limitations

These reports describe **structure**, not biology. By design, a report describes
the geometry, surface, secondary-structure content, and coarse structural class
of a model — and explicitly states "insufficient structural evidence to assign
function" when the structure does not support a call. What a report **cannot**
establish, and never claims to:

- **Identity** — what protein this is. Filenames are opaque labels, never read
  for biological meaning.
- **A specific fold or superfamily.** The coarse structural class (all-α, all-β,
  α/β, α+β) is the ceiling; naming a named fold or a SCOP / CATH / Pfam family
  would require a database search (e.g. Foldseek), which this pipeline does not run.
- **Biological function or mechanism.** Surface charge, pockets, and shape are
  reported as structural observations — never read as a functional assignment.
- **Homology / evolutionary relationships** — out of reach without a
  sequence/structure search.
- **Oligomeric state, biological assembly, or ligand/cofactor binding** beyond
  what is explicitly modeled in the input. A single-chain predicted model says
  nothing about its assembly.

These limits are generic, so they live here rather than being restated in every
report; each report keeps only a one-line scope statement. A report is structural
evidence to reason *from*, not an identification.

## Pointers

- Per-agent setup and invocation: [src/agent_0/README.md](src/agent_0/README.md),
  [src/agent_1/README.md](src/agent_1/README.md),
  [src/agent_2/README.md](src/agent_2/README.md).
- Worked examples / end-to-end validation: [runs/stress_test/](runs/stress_test/) —
  eight sequences folded and analysed Agent 1 → Agent 2, with five full Agent 2 reports.
- Architectural rules and working style: [CLAUDE.md](CLAUDE.md).
- License: Apache 2.0 — see [LICENSE](LICENSE).
