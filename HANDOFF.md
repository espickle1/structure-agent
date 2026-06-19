# Handoff — release cleanup landed + force-pushed; continuing at home

**For:** next session (James / Claude Code), resuming at home.
**Date:** 2026-06-18.
**State:** `main` history was rewritten for release and **force-pushed** to
`origin` (`3151168`). Local and origin are in sync.

## ⚠ First thing at home: fresh clone

The history was rewritten — every commit hash changed. An existing clone will
**not** `git pull` cleanly. **Delete any old local copy and re-clone** from
GitHub. Do not try to pull/merge an old clone; it would drag the purged
artifacts back or fail on unrelated histories.

## What landed this session

- **Headless synthesis hardened** — `run_pipeline.ps1/.sh` synthesis step now has
  a `claude` PATH preflight, an exit-code check, `--model` (default
  `claude-opus-4-8[1m]`), and `--max-turns` (default 50).
- **Release cleanup:**
  - Purged committed pipeline artifacts from the working tree **and all history**
    (`runs/a3·a4·a5·demo`, `data/new_results`, `data/esmfold2_validation`,
    `src/agent_1/step1_results`, stray `data/*`, root `report.md`,
    `DIRECTORY_STRUCTURE.md`, old `HANDOFF.md`, dead `agent_2_web_handoff.py`).
    Kept `runs/stress_test/` as validation evidence. Repo 12.2 → ~4.3 MiB
    (`git-filter-repo`).
  - Doc/prompt drift fixes: `README`, `EXECUTION_SUMMARY`, `agent_2/README`,
    `CLAUDE.md` (markdown report, not PDF), `agent_0/README` (slow path marked
    not-implemented). Prompt + SKILL: dropped the old "What cannot be determined"
    section and "Zone" wording in favour of a one-line scope statement.
  - **Identity-agnostic guards (new):** the synthesis `claude` call runs with
    `--disallowedTools WebSearch,WebFetch`, and `prompts/report.md` + `SKILL.md`
    forbid looking up or importing outside knowledge about any PDB ID / protein
    name in the metadata. Verified working.
  - Added `data/demo/stress_test_mix_blinded.fasta` (blinded mixed-type demo input).
- **Validated** with a BYO Agent 2 trial (`2E7L`): report assembled correctly and
  identity-agnostic behaviour held.

## Open — start here (prioritized)

1. **Decide the discarded GitHub reorg.** The force-push overwrote a GitHub commit
   "Reorganizing directories" (`ab4ea4e`); its directory reorganization is **not**
   in what is on `origin` now. It is saved as local branch `reorg-backup` — **but
   that branch and `../structure-agent-pre-rewrite.bundle` live only on the OFFICE
   machine and will NOT be at home.** If you want the option to replay that reorg
   from home, push `reorg-backup` (or copy the bundle) before leaving the office.
2. **Workstream D** (not done): de-dup the `has_ligands` probe across
   `run_pipeline.sh`/`.ps1`; run a `ruff` pass.
3. **Tag `v1.0`** when ready to mark the release.
4. **HANDOFF.md is internal** — re-added to public `main` here for cross-machine
   continuity. Strip it again before tagging a clean release (or gitignore it and
   sync notes another way) if you want `main` pristine.
5. Confirm the **blinded demo FASTA** is intended to be public.
6. Pre-existing: Agent 0 slow path still unimplemented (documented); the
   provenance-boolean follow-up in `parse_structure.py`; Agent 1 pLDDT
   confidence-tier recalibration.

## Notes

- `git-filter-repo` was pip-installed on the office machine but isn't on PATH —
  invoke as `python -m git_filter_repo`. Install fresh at home if more history
  surgery is needed.
- Run the pipeline from a **plain terminal**, not inside a Claude Code session
  (the synthesis step spawns its own `claude`).
- Full pipeline needs Modal auth (the `agent_0-fast` / `agent1-esmfold2` apps run
  ephemerally — no deploy step); Agent 2 / BYO runs need neither.
