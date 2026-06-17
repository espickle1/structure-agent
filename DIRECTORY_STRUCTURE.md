# structure-agent — Directory Structure Plan

## Repository layout

```
structure-agent/
│
├── run_pipeline.sh              ← pipeline coordinator (new)
├── CLAUDE.md                    ← session-priming file (update: retire Stage/Zone vocab)
├── HANDOFF.md
├── LICENSE
├── README.md                    ← needs updating (retire Stage/Zone/Agent 3/4 refs)
├── .gitignore                   ← two additions needed (see below)
│
├── prompts/                     ← new; user-facing, not source code
│   └── report.md               ← synthesis prompt template (edit before each run)
│
├── data/                        ← new; partially tracked
│   └── demo/
│       └── rbp.fasta           ← canonical homotrimeric RBP demo sequence (tracked)
│       (*.cif / *.pdb          ← gitignored — large, regenerable)
│
├── results/                     ← gitignored; auto-created at runtime
│   └── run_YYYYMMDD_HHMMSS/    ← timestamped per run (default if --output-dir omitted)
│       ├── agent_0/
│       │   ├── cleaned.faa
│       │   ├── sidecar.jsonl
│       │   └── rejections.jsonl
│       ├── agent_1/
│       │   ├── structures/
│       │   │   └── <record_id>.cif
│       │   ├── structures.jsonl
│       │   └── rejections.jsonl
│       └── agent_2/
│           ├── <stem>_metadata.json
│           ├── <stem>_surface_analysis.json
│           ├── <stem>_surface.csv
│           ├── <stem>_render_views.json
│           ├── <stem>_axis1.png
│           ├── <stem>_axis2.png
│           ├── <stem>_axis3.png
│           ├── <stem>_surface_profile.png
│           ├── <stem>_exposure_pie.png
│           ├── <stem>_binding_sites.json    (only if ligands present)
│           ├── <stem>_comparisons.json      (only if multiple structures)
│           └── <stem>_analysis.md          ← primary deliverable
│
└── src/
    ├── agent_0/
    ├── agent_1/
    │   ├── fold_app/
    │   ├── shared/
    │   ├── boltz_fallback/
    │   ├── orchestrator.py
    │   └── validate.py
    └── agent_2/
        ├── SKILL.md
        ├── modal_app.py
        ├── references/
        │   ├── interpretation_guide.md
        │   └── profiles/
        │       ├── README.md
        │       ├── globular_enzyme.md
        │       └── denovo_monomer.md
        └── scripts/
            ├── cif_io.py
            ├── parse_structure.py
            ├── surface_analysis.py
            ├── binding_site.py
            ├── compare_structures.py
            ├── render_trace.py
            ├── render_views.py
            └── assemble_report.py
```

---

## .gitignore additions

Add to the existing `.gitignore`:

```gitignore
# Runtime outputs — regenerable, never commit
results/

# Structure files in data/ — large, regenerable
data/**/*.cif
data/**/*.pdb
data/**/*.mmcif
```

The existing `src/agent_1/test_data/` entry stays untouched.

---

## Key layout decisions

**`prompts/` at repo root, not in `src/`.**
User-facing configuration. Someone adopting the pipeline edits
`prompts/report.md`; they should not be navigating into source directories.

**`data/demo/` is tracked; `results/` is not.**
The demo FASTA is small and worth versioning — it makes the demo
reproducible for anyone who clones the repo. Structure files (CIF/PDB)
are large and regenerable; gitignore them. `results/` is pure runtime
output; nothing there belongs in version control.

**Timestamped run directories under `results/`.**
Prevents collisions when running the pipeline multiple times.
`run_pipeline.sh` defaults to `results/run_YYYYMMDD_HHMMSS/` when
`--output-dir` is not specified. Pass `--output-dir` explicitly when
you want a stable path (e.g. for re-running a specific batch).

---

## Shell script default invocation

```bash
# Full pipeline — output goes to results/run_YYYYMMDD_HHMMSS/
./run_pipeline.sh \
  --input data/demo/rbp.fasta \
  --prompt prompts/report.md

# BYO structure (auto-detected from .cif extension)
./run_pipeline.sh \
  --input data/demo/reference.cif \
  --prompt prompts/report.md \
  --profile src/agent_2/references/profiles/globular_enzyme.md

# Explicit output directory
./run_pipeline.sh \
  --input data/demo/rbp.fasta \
  --output-dir results/rbp_demo \
  --prompt prompts/report.md
```

---

## Pending before first run

1. **`data/demo/rbp.fasta`** — canonical homotrimeric RBP demo sequence
   needs to be committed. This is the current unblock.
2. **`README.md`** — update to reflect merged Agent 2/3 architecture,
   retired Stage/Zone vocabulary, and the new `run_pipeline.sh` entry point.
   (HANDOFF item.)
3. **`mkdssp` installed locally** — `apt install dssp` (Linux) or
   `brew install brewsci/bio/dssp` (macOS). Without it, surface analysis
   runs but fold classification is unreliable.
4. **Modal auth confirmed** — `modal token set` done and both apps deployed:
   `agent_0-fast` and `agent1-esmfold2`.
5. **ESMFold2 pLDDT scale check** — confirm whether ESMFold2-Fast emits
   pLDDT on a 0–1 or 0–100 scale. This affects Agent 1's `classify_confidence`
   tiers (`PLDDT_HIGH = 0.90`) and the report's predicted-ness detection.
