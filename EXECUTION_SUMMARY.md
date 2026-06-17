# structure-agent — Execution Summary
## Running on claude.ai/code (web) and local CLI

---

## The core insight

Local CLI and claude.ai/code are **the same workflow with one flag**.
Everything else — repo clone, `CLAUDE.md` loading, script invocations,
Modal dispatch for GPU work, output artifacts — is identical.

```bash
# Local
claude "$(cat prompts/report.md)"

# Cloud (claude.ai/code)
claude --remote "$(cat prompts/report.md)"
```

Develop and test locally; the cloud version works without modification.

---

## What claude.ai/code actually is

`claude.ai/code` is **Claude Code on the web** — not claude.ai chat.
It is a separate surface:

| Surface | What it is | Execution locus |
|---|---|---|
| `claude.ai/code` | Claude Code in Anthropic-managed VM; GitHub-backed; sessions persist | Anthropic's cloud |
| Local CLI (`claude`) | Claude Code on your machine | Your machine |
| `claude.ai` chat | Ephemeral chat; analysis-only via SKILL.md | Anthropic's servers (no persistent VM) |

---

## Pipeline architecture

Two halves with different compute requirements:

**Prediction half — Agents 0 and 1 (needs GPU → Modal)**
- Agent 0: sequence QC and preprocessing (CPU, dispatches to `agent_0-fast` Modal app)
- Agent 1: structure prediction (GPU, dispatches to `agent1-esmfold2` Modal app via ESMFold2-Fast)
- Both orchestrators dispatch remotely; the machine running them only needs Modal auth

**Analysis half — Agent 2 (CPU only, no Modal needed)**
- Deterministic scripts: parse, surface analysis, shape, renders, binding site, comparison
- Claude synthesis: fills `<!-- SYNTHESIS -->` placeholders in the assembled report
- Can run standalone on any CIF/PDB — no Agents 0/1 required (BYO path)

---

## Two input modes

**Full pipeline** — input is a FASTA file (nucleotide or protein):
```
FASTA → Agent 0 → cleaned.faa → Agent 1 → *.cif → Agent 2 → report
```

**BYO structure** — input is an already-predicted or experimentally solved structure:
```
*.cif / *.pdb → Agent 2 → report
```

BYO is auto-detected from file extension. Sources accepted for BYO:
- AlphaFold Server, ColabFold, ESMFold web, or any other predictor
- Retrieved from PDB or other structural databases
- Your own experimental structure (X-ray, cryo-EM)

BYO structures skip confidence reasoning in the synthesis step (no
pipeline-generated pLDDT to assess). The shell script passes a provenance
note to Claude automatically.

---

## The coordinator script

`run_pipeline.sh` at repo root sequences all steps:

```bash
# Full pipeline
./run_pipeline.sh \
  --input data/demo/rbp.fasta \
  --output-dir results/run_001 \
  --prompt prompts/report.md

# BYO structure
./run_pipeline.sh \
  --input data/demo/reference.cif \
  --output-dir results/run_001 \
  --prompt prompts/report.md \
  --profile src/agent_2/references/profiles/globular_enzyme.md
```

Arguments:

| Flag | Required | Description |
|---|---|---|
| `--input` | yes | FASTA (full pipeline) or CIF/PDB (BYO) |
| `--output-dir` | no | Defaults to `results/run_YYYYMMDD_HHMMSS/` |
| `--prompt` | yes | Markdown synthesis prompt (edit before running) |
| `--profile` | no | Expected-parameter profile; repeatable |
| `--metadata` | no | Client metadata JSON for Agent 0 |
| `--byo` | no | Force BYO mode even for non-CIF/PDB extensions |

The final step invokes `claude "$TASK"` where `$TASK` is the prompt file
content plus a context block (output directory, repo root, provenance note)
appended by the script.

---

## The synthesis prompt

`prompts/report.md` is the file passed to Claude at the end of the pipeline.
**Edit the User context block before each run:**

```markdown
## User context
Organism or source:        [fill in]
Expected function:         [fill in]
Known structural features: [fill in]
Analysis goals:            [fill in]
```

Leave blank if unknown. Claude proceeds with identity-agnostic analysis.

The prompt instructs Claude to:
1. Read `src/agent_2/references/interpretation_guide.md`
2. Assess disorder from outputs before writing
3. Fill each `<!-- SYNTHESIS -->` section: executive summary, user context,
   coherence assessment, independent observations, what cannot be determined
4. Cite every claim to a specific measurement
5. Stay in Zone 1–2 (describe/compare; no identity or function claims)

---

## claude.ai/code specifics

**Setup script** (one-time, in environment settings):
```bash
#!/bin/bash
apt update && apt install -y dssp || true
pip install biopython numpy scipy pandas matplotlib seaborn gemmi molviewspec
```

This is cached after the first run — subsequent sessions start with
dependencies already installed.

**Network access:** set to **Trusted** (default). PyPI and Ubuntu apt repos
are on the default allowlist. Modal's API (`*.modal.run` or similar) may
need adding under Custom if Modal dispatch is required from the cloud session.

**Secrets:** add Modal credentials as environment variables:
```
MODAL_TOKEN_ID=<your token id>
MODAL_TOKEN_SECRET=<your token secret>
```
Note: environment variables in cloud sessions are visible to anyone who
can edit the environment. Treat accordingly.

**CLAUDE.md** is loaded automatically from the repo clone. SKILL.md at
`src/agent_2/SKILL.md` is accessible; point Claude at it explicitly or
symlink to `.claude/skills/protein-analysis/SKILL.md`.

**Sessions persist** even if you close the browser. Monitor from the
Claude mobile app or `claude /tasks` in the local CLI.

**Output:** results land in the repo's `results/` directory. Claude creates
a PR with the report and output artifacts when the task is done.

---

## Local CLI specifics

**Prerequisites:**
```bash
# Python dependencies
pip install modal biopython numpy scipy pandas matplotlib seaborn gemmi molviewspec

# DSSP binary
apt install -y dssp          # Linux
brew install brewsci/bio/dssp  # macOS

# Modal auth (one-time)
modal token set --token-id <id> --token-secret <secret>

# Deploy Modal apps (one-time, or after image changes)
modal deploy src/agent_1/fold_app/modal_app.py
python -m modal deploy -m agent_0.modal_app   # run from src/
```

**Run from repo root:**
```bash
./run_pipeline.sh --input data/demo/rbp.fasta --prompt prompts/report.md
```

**Outputs** persist in `results/` under version control (gitignored).
Re-runs are diffable. Scripts are editable and version-controlled.

---

## Scalability and automation limits

| Dimension | Assessment |
|---|---|
| Single structure | Good — designed for this |
| Small batch (handful) | Workable; parallel `--remote` sessions or sequential |
| Large batch | Not this surface — rate limits bind before compute does |
| Automation | Partial — deterministic half fully automated; synthesis consumes active token budget |
| Routines (scheduled) | Possible via claude.ai/code Routines; one structure per trigger |

For large batch work, the local CLI dispatching to Modal is the right shape,
not cloud sessions.

---

## Pending before first run

1. **`data/demo/rbp.fasta`** — canonical homotrimeric RBP sequence to commit.
   Current unblock.
2. **ESMFold2 pLDDT scale** — confirm 0–1 or 0–100. Affects Agent 1
   `classify_confidence` tiers and report's predicted-ness detection.
3. **Provenance boolean** — plumb into sidecar (orchestrator sets on
   pipeline-predicted path; absent on BYO). Switch `detect_alphafold`
   heuristic in report to use flag instead of B-factor sniffing.
4. **`surface_analysis.py` `classify_fold`** — remove per HANDOFF Task A.
5. **`README.md`** — update to reflect merged architecture, retired
   Stage/Zone vocabulary, `run_pipeline.sh` as entry point.
