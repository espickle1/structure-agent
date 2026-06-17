#!/usr/bin/env python3
"""Agent 2 — deterministic markdown report assembler.

Reads a structure's measurement bundle (the JSON/CSV/PNG written by the other
Agent 2 scripts) and emits a single markdown report. Every FACT is pulled
straight from the script JSON — no LLM, no transcription, no network — and the
figures are embedded by relative path. The interpretive sections (executive
summary, independent observations, the prediction-quality divergence call, and
"what cannot be determined") are emitted as clearly-marked SYNTHESIS
placeholders for the Claude session to fill per ``SKILL.md`` Step 9, so the seam
between measurement and judgment stays visible in the file.

Pure standard library. CPU only.

Usage:
    python assemble_report.py <stem> --results-dir results/ \
        [--profile references/profiles/globular_enzyme.md ...] \
        [--output results/<stem>_analysis.md]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Expected-parameter vocabulary. Profiles reference these canonical names; each
# maps to an observed value extracted from the bundle, plus a label and unit.
# Keep this in sync with references/profiles/README.md.
# --------------------------------------------------------------------------- #
def _dig(d: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


PARAM_REGISTRY: dict[str, dict[str, Any]] = {
    "radius_of_gyration":          {"label": "Radius of gyration", "unit": "Å",
                                    "get": lambda m, s: _dig(s, "shape", "radius_of_gyration")},
    "asphericity":                 {"label": "Asphericity", "unit": "",
                                    "get": lambda m, s: _dig(s, "shape", "asphericity")},
    "helix_fraction":              {"label": "Helix fraction", "unit": "",
                                    "get": lambda m, s: _dig(s, "secondary_structure_content", "helix", "fraction")},
    "sheet_fraction":              {"label": "Sheet fraction", "unit": "",
                                    "get": lambda m, s: _dig(s, "secondary_structure_content", "sheet", "fraction")},
    "coil_fraction":               {"label": "Coil fraction", "unit": "",
                                    "get": lambda m, s: _dig(s, "secondary_structure_content", "coil", "fraction")},
    "buried_fraction":             {"label": "Buried fraction", "unit": "",
                                    "get": lambda m, s: _dig(s, "surface_stats", "buried", "fraction")},
    "exposed_fraction":            {"label": "Exposed fraction", "unit": "",
                                    "get": lambda m, s: _dig(s, "surface_stats", "exposed", "fraction")},
    "surface_net_charge":          {"label": "Surface net charge", "unit": "e",
                                    "get": lambda m, s: _dig(s, "surface_stats", "surface_net_charge")},
    "surface_hydrophobicity_mean": {"label": "Mean surface hydrophobicity (KD)", "unit": "",
                                    "get": lambda m, s: _dig(s, "surface_stats", "surface_hydrophobicity", "mean")},
    "total_sasa":                  {"label": "Total SASA", "unit": "Å²",
                                    "get": lambda m, s: _dig(s, "surface_stats", "total_sasa")},
    "num_chains":                  {"label": "Chain count", "unit": "",
                                    "get": lambda m, s: m.get("num_chains")},
    "total_residues":              {"label": "Total residues", "unit": "",
                                    "get": lambda m, s: m.get("total_residues")},
}


# --------------------------------------------------------------------------- #
# Small formatting / parsing helpers
# --------------------------------------------------------------------------- #
def _num(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fmt(x: Any, nd: int = 2) -> str:
    f = _num(x)
    if f is None:
        return "—" if x in (None, "") else str(x)
    return f"{f:.{nd}f}".rstrip("0").rstrip(".") if isinstance(x, float) or "." in str(x) else str(x)


def fmt_pct(frac: Any) -> str:
    f = _num(frac)
    return "—" if f is None else f"{f * 100:.1f}%"


def fmt_range(lo: str, hi: str, unit: str) -> str:
    lo, hi, unit = (lo or "").strip(), (hi or "").strip(), (unit or "").strip()
    u = f" {unit}" if unit else ""
    if lo and hi:
        return f"{lo}–{hi}{u}"
    if lo:
        return f"≥ {lo}{u}"
    if hi:
        return f"≤ {hi}{u}"
    return "(unbounded)"


def parse_profile(path: Path) -> dict:
    """Parse a markdown-table profile file.

    Recognised table columns (header row, case-insensitive): parameter | min |
    max | unit | note. Empty min/max means unbounded on that side.
    """
    text = path.read_text()
    name = path.stem
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        name = m.group(1).strip()
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or cells[0].lower() == "parameter":
            continue
        if set("".join(cells)) <= set("-: "):  # markdown separator row
            continue
        cells += [""] * (5 - len(cells))
        rows.append({"parameter": cells[0], "min": cells[1], "max": cells[2],
                     "unit": cells[3], "note": cells[4]})
    return {"name": name, "path": str(path), "rows": rows}


def compare_to_profile(profile: dict, meta: dict, surf: dict) -> list[dict]:
    out = []
    for row in profile["rows"]:
        reg = PARAM_REGISTRY.get(row["parameter"])
        observed = reg["get"](meta, surf) if reg else None
        lo, hi = _num(row["min"]), _num(row["max"])
        obs = _num(observed)
        if reg is None:
            verdict = "unknown parameter"
        elif obs is None:
            verdict = "not measured"
        elif (lo is not None and obs < lo) or (hi is not None and obs > hi):
            verdict = "**deviates**"
        else:
            verdict = "within"
        out.append({
            "label": reg["label"] if reg else row["parameter"],
            "observed": fmt(observed) + (f" {reg['unit']}" if reg and reg["unit"] else ""),
            "expected": fmt_range(row["min"], row["max"], row["unit"]),
            "verdict": verdict,
            "note": row["note"],
        })
    return out


# --------------------------------------------------------------------------- #
# Report sections
# --------------------------------------------------------------------------- #
SYNTH = (
    "<!-- SYNTHESIS ({who}): {what} "
    "Structural observations only; cite the measurement(s) each claim rests on. "
    "Replace this comment. -->"
)


def synth(what: str, who: str = "Claude, per SKILL.md Step 9") -> str:
    return SYNTH.format(who=who, what=what)


def overview_section(meta: dict) -> str:
    af = meta.get("alphafold_detection", {})
    predicted = af.get("is_predicted")
    lines = ["## Structure overview", ""]
    lines.append(f"- **Source:** {'predicted model' if predicted else 'experimental'}"
                 + (f" (resolution {meta['resolution']} Å)" if meta.get("resolution") else "")
                 + (" — pLDDT in the B-factor column" if _dig(af, "detection_signals", "bfactor_is_plddt") else ""))
    lines.append(f"- **Chains:** {meta.get('num_chains')} "
                 f"({'oligomeric' if meta.get('is_oligomeric') else 'single chain'})")
    lines.append(f"- **Residues / atoms:** {meta.get('total_residues')} / {meta.get('total_atoms')}")
    miss = meta.get("total_missing_residues", 0)
    lines.append(f"- **Missing residues:** {miss}")
    ligs = meta.get("unique_ligands") or []
    lines.append(f"- **Non-solvent ligands:** {', '.join(ligs) if ligs else 'none'}")
    for ch in meta.get("chains", []):
        breaks = ch.get("chain_breaks") or []
        mods = ch.get("modified_residues") or []
        lines.append(f"  - chain **{ch.get('chain_id')}**: {ch.get('num_residues')} res"
                     + (f", {len(breaks)} chain break(s)" if breaks else "")
                     + (f", {len(mods)} modified residue(s)" if mods else ""))
    return "\n".join(lines) + "\n"


def views_section(stem: str, results_dir: Path, img_prefix: str) -> str:
    lines = ["## Structural views", ""]
    axes = [results_dir / f"{stem}_axis{i}.png" for i in (1, 2, 3)]
    present = [a for a in axes if a.exists()]
    if not present:
        lines.append("_Renders unavailable for this structure (Mol*/headless GL not "
                     "present, or rendering was skipped)._")
        return "\n".join(lines) + "\n"
    rv = results_dir / f"{stem}_render_views.json"
    meta = {}
    if rv.exists():
        try:
            meta = json.loads(rv.read_text())
        except (json.JSONDecodeError, OSError):
            meta = {}
    cams = meta.get("cameras", {})
    default_caps = {"axis1": "down long axis", "axis2": "down mid axis", "axis3": "down short axis"}
    for a in present:
        key = a.stem.split("_")[-1]
        label = (cams.get(key) or {}).get("label") or default_caps.get(key, key)
        lines.append(f"![{stem} — {label}]({img_prefix}{a.name})")
        lines.append("")
    color = meta.get("color_mode") or "pLDDT"
    kind = ("Cα backbone trace (Agent 2.2 matplotlib placeholder)"
            if meta.get("renderer") == "matplotlib-ca-trace" else "Mol* cartoon views")
    lines.append(f"_{kind}, down the long / mid / short principal axes; coloured by {color}._")
    return "\n".join(lines) + "\n"


def shape_ss_section(surf: dict) -> str:
    sh = surf.get("shape", {})
    ss = surf.get("secondary_structure_content", {})
    lines = ["## Shape & secondary structure", ""]
    lines.append(f"- **Shape:** {sh.get('shape_classification', '—')} "
                 f"(asphericity {fmt(sh.get('asphericity'))}, "
                 f"Rg {fmt(sh.get('radius_of_gyration'))} Å)")
    dims = sh.get("approximate_dimensions", {})
    if dims:
        lines.append(f"- **Approx. dimensions:** {fmt(dims.get('long_axis'))} × "
                     f"{fmt(dims.get('mid_axis'))} × {fmt(dims.get('short_axis'))} "
                     f"{dims.get('unit', 'Å')}")
    lines.append(f"- **Secondary structure:** helix {fmt_pct(_dig(ss, 'helix', 'fraction'))}, "
                 f"sheet {fmt_pct(_dig(ss, 'sheet', 'fraction'))}, "
                 f"coil {fmt_pct(_dig(ss, 'coil', 'fraction'))}")
    if ss.get("reliable") is False:
        lines.append("- **⚠ Secondary structure unavailable** "
                     f"(source: {ss.get('source', '?')}) — the SS fractions above are "
                     "not a real measurement (DSSP missing); any disorder assessment "
                     "is unreliable until DSSP is installed.")
    return "\n".join(lines) + "\n"


def surface_section(surf: dict, img_prefix: str) -> str:
    st = surf.get("surface_stats", {})
    plots = surf.get("plots", {})
    lines = ["## Surface properties", ""]
    lines.append(f"- **Exposure:** buried {fmt_pct(_dig(st, 'buried', 'fraction'))}, "
                 f"partial {fmt_pct(_dig(st, 'partial', 'fraction'))}, "
                 f"exposed {fmt_pct(_dig(st, 'exposed', 'fraction'))}")
    lines.append(f"- **Total SASA:** {fmt(st.get('total_sasa'))} Å²")
    lines.append(f"- **Surface hydrophobicity (KD):** mean {fmt(_dig(st, 'surface_hydrophobicity', 'mean'))} "
                 f"± {fmt(_dig(st, 'surface_hydrophobicity', 'std'))}")
    lines.append(f"- **Surface charge (pH 7):** net {st.get('surface_net_charge')} e "
                 f"({st.get('surface_positive_residues')} +, {st.get('surface_negative_residues')} −)")
    patches = st.get("hydrophobic_patches") or []
    lines.append(f"- **Hydrophobic patches:** {len(patches)}"
                 + (":" if patches else ""))
    for p in patches:
        lines.append(f"  - residues {p.get('start_resid')}–{p.get('end_resid')} "
                     f"(len {p.get('length')}, mean KD {fmt(p.get('mean_hydrophobicity'))})")
    for key, cap in (("surface_profile", "Per-residue SASA & hydrophobicity"),
                     ("exposure_pie", "Exposure breakdown")):
        fn = plots.get(key)
        if fn:
            lines.append("")
            lines.append(f"![{cap}]({img_prefix}{fn})")
    return "\n".join(lines) + "\n"


def quality_section(meta: dict, surf: dict) -> str:
    """Deterministic prediction-quality signals. The divergence *call* (does
    structural coherence contradict a low confidence score?) is left to the
    Claude synthesis — but every signal it needs is laid out here."""
    af = meta.get("alphafold_detection", {})
    is_plddt = bool(_dig(af, "detection_signals", "bfactor_is_plddt"))
    metric = "pLDDT" if is_plddt else "B-factor"
    lines = ["## Prediction quality / structural coherence", ""]
    lines.append(f"Confidence is **reported, never gated** — these signals are inputs for the "
                 f"synthesis below, not a pass/fail.")
    lines.append("")
    # confidence
    for ch in meta.get("chains", []):
        bs = ch.get("bfactor_stats") or {}
        if bs:
            lines.append(f"- **{metric} (chain {ch.get('chain_id')}):** mean {fmt(bs.get('mean'))}, "
                         f"median {fmt(bs.get('median'))}, range {fmt(bs.get('min'))}–{fmt(bs.get('max'))}, "
                         f"std {fmt(bs.get('std'))}")
    # structural-coherence signals (orthogonal to confidence)
    n = _num(meta.get("total_residues"))
    rg = _num(_dig(surf, "shape", "radius_of_gyration"))
    if n and n > 0:
        rg_exp = 2.5 * (n ** 0.4)
        flag = "" if (rg is None) else (" — consistent" if rg <= rg_exp * 1.25 else " — larger than expected")
        lines.append(f"- **Compactness:** Rg {fmt(rg)} Å vs ~{rg_exp:.1f} Å expected for "
                     f"{int(n)} residues (2.5·N^0.4){flag}")
    lines.append(f"- **Core present:** buried fraction {fmt_pct(_dig(surf, 'surface_stats', 'buried', 'fraction'))}")
    lines.append(f"- **Coil fraction:** {fmt_pct(_dig(surf, 'secondary_structure_content', 'coil', 'fraction'))}")
    lines.append("")
    lines.append("### Coherence assessment")
    lines.append("")
    lines.append(synth("Do the structural-coherence signals (compactness, core, coil) "
                       "agree with the confidence score, or does a low "
                       f"{metric} sit alongside a coherent fold (common for low-homology "
                       "targets)? State which, citing the signals above."))
    return "\n".join(lines) + "\n"


def profiles_section(profiles: list[dict], meta: dict, surf: dict) -> str:
    lines = ["## Expected-parameter comparison", ""]
    if not profiles:
        lines.append("_No expected-parameter profile supplied — this is the default for novel / "
                     "low-homology targets. See the independent observations below._")
        return "\n".join(lines) + "\n"
    for prof in profiles:
        rows = compare_to_profile(prof, meta, surf)
        lines.append(f"### vs `{prof['name']}`")
        lines.append("")
        lines.append("| Parameter | Observed | Expected | Verdict | Note |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r in rows:
            lines.append(f"| {r['label']} | {r['observed']} | {r['expected']} | "
                         f"{r['verdict']} | {r['note']} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def methods_section(profiles: list[dict]) -> str:
    lines = ["## Methods", ""]
    lines.append("- **Measurements (deterministic):** `parse_structure.py` (metadata, "
                 "confidence stats), `surface_analysis.py` (Shrake–Rupley SASA, Kyte–Doolittle "
                 "hydrophobicity, charge at pH 7, DSSP secondary structure, shape metrics), "
                 "`render_trace.py` (Agent 2.2 Cα-trace figures; "
                 "`render_views.py` Mol* cartoons when Agent 2.1 is available).")
    lines.append("- **Report facts** below the synthesis sections are emitted verbatim from the "
                 "above scripts' JSON by `assemble_report.py` — no transcription.")
    lines.append("- **Synthesis** sections (executive summary, independent observations, "
                 "coherence assessment, cannot-determine) are authored by Claude per `SKILL.md` "
                 "Step 9, each claim cited to a measurement.")
    if profiles:
        lines.append("- **Expected-parameter profiles:** "
                     + ", ".join(f"`{p['name']}`" for p in profiles) + ".")
    return "\n".join(lines) + "\n"


def build_report(stem: str, meta: dict, surf: dict, profiles: list[dict],
                 results_dir: Path, img_prefix: str) -> str:
    parts = [
        f"# Structural analysis — `{stem}`\n",
        "> Facts are emitted deterministically from the measurement scripts. "
        "Sections marked with a SYNTHESIS comment are authored by the Claude session "
        "(judgment), kept visibly separate from the measured facts.\n",
        "## Executive summary\n",
        synth("3–5 sentences: the most notable structural observations.") + "\n",
        "## User-provided context\n",
        synth("State any context the user gave (organism, goal, expected features), "
              "verbatim and clearly separated from observations; else \"None provided.\"") + "\n",
        overview_section(meta),
        views_section(stem, results_dir, img_prefix),
        shape_ss_section(surf),
        surface_section(surf, img_prefix),
        quality_section(meta, surf),
        profiles_section(profiles, meta, surf),
        "## Independent observations\n",
        synth("What is notable or unexpected from the measurements + generic physical "
              "baselines ALONE (do NOT consult the expected-parameter profiles here). "
              "Flag internal inconsistencies. Anchor 'unexpected' to a stated baseline.") + "\n",
        "## What cannot be determined from structure alone\n",
        synth("Enumerate what this structural analysis cannot establish — identity, "
              "function, mechanism, homology. State these as the limits of structural "
              "analysis; database verification (Foldseek/CATH) would be needed to go "
              "further.") + "\n",
        methods_section(profiles),
    ]
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble the Agent 2 markdown report.")
    ap.add_argument("stem", help="structure stem, e.g. 6EQE (matches <stem>_metadata.json)")
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--profile", type=Path, action="append", default=[],
                    help="expected-parameter profile (repeatable)")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    rd: Path = args.results_dir
    meta_path = rd / f"{args.stem}_metadata.json"
    surf_path = rd / f"{args.stem}_surface_analysis.json"
    for p in (meta_path, surf_path):
        if not p.exists():
            ap.error(f"required input not found: {p}")
    meta = json.loads(meta_path.read_text())
    surf = json.loads(surf_path.read_text())
    profiles = [parse_profile(p) for p in args.profile]

    out_path: Path = args.output or (rd / f"{args.stem}_analysis.md")
    # images live in results-dir; make refs relative to the report's directory
    img_prefix = os.path.relpath(rd.resolve(), out_path.parent.resolve())
    img_prefix = "" if img_prefix == "." else img_prefix.rstrip("/") + "/"

    report = build_report(args.stem, meta, surf, profiles, rd, img_prefix)
    out_path.write_text(report)
    n_synth = report.count("<!-- SYNTHESIS")
    print(f"[assemble_report] wrote {out_path} "
          f"({len(profiles)} profile(s), {n_synth} synthesis section(s) to fill)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
