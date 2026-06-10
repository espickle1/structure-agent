#!/usr/bin/env python3
"""Agent 2.2 — Cα backbone trace (matplotlib, system-agnostic placeholder).

A pure-Python fallback renderer for when Agent 2.1's Mol* cartoons are
unavailable (no GL / Node / Modal). It reads Cα coordinates directly, rotates
into the inertia eigenbasis, and draws three principal-axis 3D backbone-trace
views with matplotlib's Agg backend. Output matches Agent 2.1's contract —
``<stem>_axis{1,2,3}.png`` + ``<stem>_render_views.json`` — so the report
embeds it as a drop-in fallback. It's a worm trace, not a publication cartoon:
no side chains, no secondary-structure ribbons.

Deps: biopython (MMCIF2Dict), numpy, matplotlib. CPU only; runs anywhere.

Usage:
    python render_trace.py <structure.cif|.pdb> [--output-dir <dir>]
                           [--color {index,pLDDT}] [--size 1024x1024]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MIN_CA = 10


def detect_format(path: Path) -> str:
    return "mmcif" if path.suffix.lower() in (".cif", ".mmcif") else "pdb"


def read_ca(path: Path):
    """Return (coords Nx3, bfactors N) for protein Cα atoms.

    Reads atom records directly — no occupancy column needed, so it tolerates
    minimal predicted mmCIFs (ESMFold2 / AlphaFold) that omit it.
    """
    xs, ys, zs, bs = [], [], [], []
    if detect_format(path) == "mmcif":
        from Bio.PDB.MMCIF2Dict import MMCIF2Dict

        d = MMCIF2Dict(str(path))

        def col(key):
            v = d.get(key)
            return v if isinstance(v, list) else ([v] if v is not None else None)

        atom = col("_atom_site.label_atom_id")
        if not atom:
            raise SystemExit("ERROR: no _atom_site.label_atom_id in mmCIF")
        cx, cy, cz = col("_atom_site.Cartn_x"), col("_atom_site.Cartn_y"), col("_atom_site.Cartn_z")
        group = col("_atom_site.group_PDB") or ["ATOM"] * len(atom)
        bf = col("_atom_site.B_iso_or_equiv") or ["0"] * len(atom)
        for i, name in enumerate(atom):
            if name == "CA" and group[i] != "HETATM":
                xs.append(float(cx[i])); ys.append(float(cy[i])); zs.append(float(cz[i]))
                try:
                    bs.append(float(bf[i]))
                except (TypeError, ValueError):
                    bs.append(0.0)
    else:
        for line in path.read_text(errors="replace").splitlines():
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                xs.append(float(line[30:38])); ys.append(float(line[38:46])); zs.append(float(line[46:54]))
                try:
                    bs.append(float(line[60:66]))
                except ValueError:
                    bs.append(0.0)
    return np.array(list(zip(xs, ys, zs)), dtype=float), np.array(bs, dtype=float)


def principal_frame(coords):
    """Rotate centered coords into the inertia eigenbasis (col0 long … col2 short)."""
    c = coords - coords.mean(axis=0)
    evals, evecs = np.linalg.eigh((c.T @ c) / len(c))
    evecs = evecs[:, np.argsort(evals)[::-1]]   # columns: long, mid, short
    rot = c @ evecs
    dims = rot.max(axis=0) - rot.min(axis=0)
    return rot, dims


# Look down long / mid / short axis (matplotlib elev, azim) on rotated coords.
VIEWS = {
    "axis1": ("down long axis", 0, 0),
    "axis2": ("down mid axis", 0, -90),
    "axis3": ("down short axis", 90, -90),
}


def _render(coords, vals, cmap, out_png, title, elev, azim):
    n = len(coords)
    fig = plt.figure(figsize=(6, 5))
    ax = fig.add_subplot(111, projection="3d")
    for i in range(n - 1):
        ax.plot(coords[i:i + 2, 0], coords[i:i + 2, 1], coords[i:i + 2, 2],
                color=cmap(float(vals[i])), lw=2.0)
    sc = ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2], c=vals, cmap=cmap, s=8)
    fig.colorbar(sc, ax=ax, shrink=0.55, pad=0.1)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title, fontsize=9)
    try:
        ax.set_box_aspect(np.ptp(coords, axis=0))
    except Exception:
        pass
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def render_structure(path: Path, output_dir: Path, color: str = "index",
                     size: tuple[int, int] = (1024, 1024)) -> dict:
    coords, bfac = read_ca(path)
    if len(coords) < MIN_CA:
        raise SystemExit(f"ERROR: too few Cα atoms ({len(coords)} < {MIN_CA})")
    rot, dims = principal_frame(coords)
    n = len(rot)

    if color == "pLDDT":
        vmax = 100.0 if (bfac.size and bfac.max() > 1.5) else 1.0   # pLDDT may be 0–1 or 0–100
        vals = np.clip(bfac / vmax, 0, 1) if bfac.size else np.zeros(n)
        cmap, legend = plt.get_cmap("viridis"), "pLDDT"
    else:
        vals = np.linspace(0, 1, n)
        cmap, legend = plt.get_cmap("rainbow"), "residue N→C"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    views, cameras = {}, {}
    for name, (label, elev, azim) in VIEWS.items():
        out = output_dir / f"{stem}_{name}.png"
        _render(rot, vals, cmap, out, f"{stem} — Cα trace ({label}; {legend})", elev, azim)
        views[name] = out.name
        cameras[name] = {"label": label, "elev": elev, "azim": azim}

    result = {
        "file": path.name,
        "renderer": "matplotlib-ca-trace",
        "color_mode": color,
        "size": list(size),
        "n_ca": n,
        "approx_dimensions": {"long_axis": round(float(dims[0]), 1),
                              "mid_axis": round(float(dims[1]), 1),
                              "short_axis": round(float(dims[2]), 1), "unit": "Å"},
        "views": views,
        "cameras": cameras,
        "failures": {},
    }
    (output_dir / f"{stem}_render_views.json").write_text(json.dumps(result, indent=2))
    return result


def _size(text: str) -> tuple[int, int]:
    w, h = text.lower().split("x")
    return (int(w), int(h))


def main():
    ap = argparse.ArgumentParser(description="Cα backbone trace (matplotlib placeholder renderer).")
    ap.add_argument("structure_file", type=Path)
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--color", choices=["index", "pLDDT"], default="index")
    ap.add_argument("--size", type=_size, default=(1024, 1024))
    args = ap.parse_args()
    if not args.structure_file.exists():
        print(f"ERROR: file not found: {args.structure_file}", file=sys.stderr)
        sys.exit(1)
    out_dir = args.output_dir or args.structure_file.parent
    res = render_structure(args.structure_file, out_dir, args.color, args.size)
    print(f"[render_trace] {res['n_ca']} Cα → {len(res['views'])} views in {out_dir}")
    for name, png in res["views"].items():
        print(f"  {name}: {png}")


if __name__ == "__main__":
    main()
