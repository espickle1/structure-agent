# HANDOFF — structure-agent (Agent 1 / 2 / 2.1 / 2.2 work)

**Date:** 2026-06-10 · **Branch:** `esmfold2-onto-main` (10 commits ahead of `origin/main`, pushed) · **Owner:** James Chang / `espickle1`

A fresh chat should read this top-to-bottom, then skim the "Open items" and "How to resume" sections. The detailed render recipe in Open item #18 is hard-won — don't re-derive it.

---

## 1. TL;DR — current state

- All work is on branch **`esmfold2-onto-main`**, pushed to origin, **not merged to `main`**. It is a clean 10-commit PR candidate.
- **Done:** Agent 1 (ESMFold2-Fast primary engine), Agent 2 (deterministic-facts + Claude-synthesis **markdown report pipeline**), Agent 2.2 (matplotlib Cα-trace **placeholder renderer**, embedded in the reports).
- **Open (2):** **#15** — real secondary structure (needs DSSP, missing on the Mac); **#18** — Agent 2.1 Mol\* cartoons (blocked on one molstar↔molviewspec version pin).
- Example deliverable: `data/esmfold2_validation/{6EQE,1UBQ}/REPORT.md` — full synthesized reports with embedded Cα-trace renders.

## 2. ⚠️ Critical context — the branch situation (read before merging anything)

- `origin/main` was **force-pushed** (by a collaborator) to a history that shares only the initial commit with our line. That `main` is framed around **phage RBPs + Boltz-2 as production** and has a **more advanced Agent 2 (v4.0)** + a `STAGE_SPLIT.md` (a planned reorg into `src/stage_1/` + `src/stage_2/`).
- `origin/stage-separation` is a **separate live branch** (8 commits) that actually executes the stage split (`src/stage_1/agent_{0,1,2}`, `src/stage_2/...`) — likely the real near-term `main`.
- Our branch **`esmfold2-onto-main`** was cut from the force-pushed `main` and carries the ESMFold2 pivot + the Agent 2 report work. Per James's decision, README/CLAUDE.md were **reframed** to "ESMFold2-Fast primary, Boltz-2 multimer fallback, novel/metagenomic single-chain focus."
- **Do NOT force-push or blind-merge.** The `main` vs `stage-separation` reconciliation is the collaborator's call. When this work merges, it will likely need to move into the `src/stage_1/agent_2/` layout.

## 3. What was built this session (the 10 commits)

| Commit | Summary |
|---|---|
| `85774ae` | Agent 1: ESMFold2-Fast primary engine; Boltz-2 → `boltz_fallback/`; GPU pinned **L4** |
| `78a9f98` | gitignore Agent 1 local test fixtures |
| `ce92ea2` | Agent 2 → portable **markdown report** (assemble_report.py + profile library + SKILL.md rewire) |
| `9f4d197` | Agent 2 SS/DSSP **reliability hardening** + Python 3.9 compat |
| `cfa8323` | Agent 2.1 **spec** (Mol\* rendering as a presentation service) |
| `b9852a4` | **Tolerant mmCIF loader** (`cif_io.py`) — ESMFold2 minimal CIFs omit `_atom_site.occupancy` |
| `88c1065` | Agent 2.1 render groundwork (headless deps + correct CLI) |
| `0ecb897` | Agent 2.1: pin **molstar@4.11.0** (fixes headless `document` bug) |
| `6a69570` | **Agent 2.2** matplotlib Cα-trace + embed in reports |
| `03dc713` | chore: drop stray `.DS_Store`, ignore it |

## 4. Validation results (real ESMFold2 output, on Modal)

- Agent 1 live `.map()` batch fold works: **6EQE** pLDDT 0.894, **1UBQ** pLDDT 0.829 (2/2, 0 fail).
- RMSD vs crystal (validate.py): **6EQE 0.886 Å**, **1UBQ 0.662 Å** — both sub-Å.
- Agent 2 chain (parse→surface→assemble) runs clean on the ESMFold2 mmCIFs (after the `cif_io` occupancy fix); `is_predicted`/pLDDT detected.
- **Calibration data points** surfaced (CLAUDE.md defers thresholds to real data):
  - `PLDDT_HIGH=0.90` looks **too strict** — 6EQE folded to 0.886 Å yet pLDDT 0.894 reads "medium."
  - The shape classifier **over-calls "prolate (elongated)"** — 6EQE (compact α/β hydrolase) labeled prolate at asphericity 0.17, while the profile reads 0.17 as "within globular." (The Cα trace shows why: a low-confidence terminal arm makes the whole thing read elongated.)

## 5. Open items / deferred (with resume detail)

### #15 — Real secondary structure (DSSP)
`surface_analysis.py` shells out to the `mkdssp` binary for SS (helix/sheet/coil) + fold class. DSSP is **absent on the Mac**, so local runs report "SS unavailable / fold undetermined" (the safeguard added in `9f4d197`). DSSP **is** present in the claude.ai/Modal containers (`apt-get install dssp`).
**Resume:** run the Agent 2 chain where DSSP exists (container — system-agnostic, no Mac install) and regenerate the SS/fold sections of the reports. `brew install dssp` is the local alternative but a per-machine install James has been avoiding.

### #18 — Agent 2.1 Mol\* cartoons (BLOCKED, one step from done)
The containerized Mol\* render path. **Everything is solved except one version pin** — do NOT re-derive:
- **Headless dep recipe (solved):** image installs `molstar canvas gl jpeg-js pngjs` (npm) + GL/build libs (`libgl1*`, `libxi*`, `libxext*`, cairo/pango/jpeg/gif/rsvg) + `xvfb`, sets `NODE_PATH=/usr/lib/node_modules`. (`src/agent_2/modal_app.py`.)
- **CLI (solved):** `mvs-render -i IN -o OUT --size WxH` (render_views.py).
- **Tolerant CIF (solved):** render_views uses `cif_io.read_structure`.
- **`document is not defined` (solved):** molstar `@latest` (5.9.0) regressed the headless DOM path; **pin `molstar@4.11.0`** fixes it.
- **REMAINING blocker:** with molstar pinned to 4.11.0 but `molviewspec` (the Python builder) unpinned/latest, the builder emits an MVS tree (`ref:null` on every node) that molstar 4.11.0 rejects → `"Invalid MVS tree"`. **Fix = pin `molviewspec` to molstar 4.11.0's MVS-spec version** (or find a molstar version that fixes `document` AND matches latest molviewspec), then one confirming build. molstar mvs-render added in 3.44.0; doc-shim in 3.37.0; latest is 5.9.0.

### Other parked
- Add a "headless render recipe + blocker" note to `src/agent_2_1/README.md` (offered, not done).
- The PR `esmfold2-onto-main` → `main` (clean candidate; `gh` not installed, use the GitHub PR URL).
- Agent 0 placeholder thresholds + Agent 1 pLDDT tiers still calibrate-on-real-data.

## 6. Key design decisions (so a new chat doesn't relitigate)

- **Zone discipline.** Agents 0–2 are Zone 1 (measurement) / Zone 2 (pattern) only. Identity/function/mechanism = Zone 3 = Agent 3. The reports end with an explicit "what cannot be determined → Agent 3 handoff."
- **Deterministic facts + Claude synthesis.** `assemble_report.py` emits the measured facts verbatim from script JSON (no LLM transcription); Claude fills the marked synthesis sections (exec summary, independent observations, coherence call, cannot-determine), **each claim cited to a measurement**.
- **Two-lens synthesis.** "Independent observations" (from measurements + generic baselines, ignoring profiles) **plus** "against expected parameters" (vs a profile). Keeps an unbiased lens — divergence between them is the signal.
- **Expected-parameter profiles.** Optional hand-editable markdown tables (`src/agent_2/references/profiles/`) — a target-class baseline so "unexpected" is anchored to an explicit, cited artifact, not the LLM's latent knowledge. Multi-profile comparison is the intended pattern.
- **Annotate, don't gate.** Agent 1 tags pLDDT tiers but never rejects; Agent 2 flags SS reliability (DSSP-absent → "unreliable", not a fake all-coil measurement). pLDDT is reported context, not a gate (per James: low pLDDT ≠ wrong fold for small viral/bacterial targets).
- **System-agnostic (see memory).** No local desktop renderers (ChimeraX/PyMOL/VMD ruled out). Containerize heavy deps (Mol\*, DSSP) via Modal; matplotlib Cα trace (Agent 2.2) is the pure-Python local fallback.

## 7. Environment & gotchas

- **Local Mac:** system `python3` = **3.9** (parse_structure needs the `from __future__ import annotations`, added). A **venv at `/tmp/a2venv`** (python3.12 + biopython/numpy/scipy/matplotlib) is what I used to run Agent 2 locally — **ephemeral, will vanish on reboot**; recreate with `python3.12 -m venv` + `pip install biopython numpy scipy matplotlib`.
- **DSSP** and **GL/Node** are NOT on the Mac (→ #15 and #18).
- **Modal:** authenticated (`~/.modal.toml`, `espickle1`). Deployed apps: `agent1-esmfold2` (fold), `agent_2-render` (render, build OK / render blocked). Volume `agent1-step1-scratch` holds the CIFs + `renders/`.
- **esm dependency** `git+https://github.com/Biohub/esm.git@81b3646…` is **public + valid**; HF model `biohub/ESMFold2-Fast` valid. (Earlier worry was unfounded.)
- **Test outputs in `/tmp` are ephemeral** (`/tmp/agent1_out`, `/tmp/a2_esmfold`, `/tmp/a2trace`). The **persistent** example bundle is committed at `data/esmfold2_validation/`.

## 8. File map (key paths)

```
src/agent_1/            ESMFold2 fold app + orchestrator + validate.py; boltz_fallback/
src/agent_2/
  SKILL.md              Agent 2 orchestration (Step 9 → markdown synthesis)
  scripts/              parse_structure, surface_analysis, binding_site,
                        compare_structures, render_views (2.1), cif_io (tolerant load),
                        assemble_report (deterministic report)
  references/profiles/  expected-parameter profiles + schema README
  modal_app.py          Agent 2.1 Mol* render Modal app (blocked)
src/agent_2_1/README.md Agent 2.1 spec (Mol* rendering presentation service)
src/agent_2_2/          render_trace.py (matplotlib Cα trace) + README  ← working render
data/esmfold2_validation/{6EQE,1UBQ}/  example reports + bundle (committed)
data/new_results/       collaborator's prior MHPk example (committed, pre-existing)
HANDOFF.md              this file
```

## 9. How to resume (suggested order)

1. **Decide the merge story** — PR `esmfold2-onto-main` → `main`, or wait for the collaborator to reconcile `main` ↔ `stage-separation` (then re-home into `src/stage_1/agent_2/`).
2. **#18 (closest to done):** pin `molviewspec` to molstar 4.11.0's MVS spec → one Modal build of `agent_2-render` → if the 3 axis PNGs land, pull them into the report folders (they overwrite the 2.2 traces, same filenames) and the reports upgrade to cartoons automatically.
3. **#15:** re-run Agent 2 in a DSSP-equipped container to get real SS/fold into the reports.
4. **Calibration:** revisit `PLDDT_HIGH` (0.90 too strict) and the shape classifier's prolate threshold using the 6EQE/1UBQ data points.
