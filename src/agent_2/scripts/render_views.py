#!/usr/bin/env python3
"""
render_views.py — Phase 1 standardized 3D structure renders.

Produces three axis-aligned cartoon views per structure using Mol* (mvs-render)
driven by molviewspec scenes:

  axis1 — view down the long principal axis (canonical front)
  axis2 — view down the mid principal axis (orthogonal to axis1)
  axis3 — view down the short principal axis (orthogonal to axis1 and axis2)

Camera vectors are derived from the inertia tensor of the Cα coordinates.
The script computes them itself; it does NOT consume any other Agent 2
output (module independence).

Default coloring is pLDDT via the mmCIF atom_site.B_iso_or_equiv field —
matches Boltz-2 outputs where pLDDT is stored in the B-factor column.

Usage:
    python render_views.py <structure_file> [--output-dir <dir>]
                           [--color {pLDDT,chain}] [--size 1024x1024]

Exit codes:
    0 — success (some views may have soft-failed; see JSON `failures` field)
    1 — fatal error (file not found, parse failure, no CA atoms)

Dependencies:
    pip install biopython numpy molviewspec
    npm install -g molstar       # provides `mvs-render`
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

try:
    from Bio.PDB import MMCIFParser, PDBParser
    from Bio.PDB.Polypeptide import is_aa
except ImportError:
    print("ERROR: BioPython is required. pip install biopython", file=sys.stderr)
    sys.exit(1)

try:  # tolerant mmCIF loader — works run as a script (scripts/ on path)…
    from cif_io import read_structure
except ImportError:  # …or imported as agent_2.scripts.render_views (Modal container)
    from agent_2.scripts.cif_io import read_structure

try:
    import molviewspec as mvs
except ImportError:
    print("ERROR: molviewspec is required. pip install molviewspec", file=sys.stderr)
    sys.exit(1)


# Vertical FOV used for camera distance calculation. Half-angle 15° → 30° FOV.
FOV_HALF_DEG = 15.0
DEFAULT_SIZE = (1024, 1024)
MIN_CA_ATOMS = 10

# Distinct palette for per-chain coloring.
CHAIN_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


class RenderError(Exception):
    pass


def detect_format(filepath: Path) -> str:
    ext = filepath.suffix.lower()
    if ext in (".cif", ".mmcif"):
        return "mmcif"
    return "pdb"


def load_structure(filepath: Path):
    fmt = detect_format(filepath)
    return read_structure(filepath.stem, filepath, fmt), fmt


# =========================================================================
# Camera math — Cα-based gyration tensor
# =========================================================================
def compute_camera_views(structure):
    """
    Return three (view_name, position, target, up, distance) tuples for the
    long / mid / short principal axes of the structure.

    Mirrors the math in surface_analysis.py:compute_shape_metrics. Re-implemented
    here intentionally so this module does not depend on any other Agent 2
    script's output.
    """
    model = list(structure.get_models())[0]
    ca_coords = []
    for chain in model:
        for res in chain.get_residues():
            if is_aa(res, standard=True) and res.has_id("CA"):
                ca_coords.append(res["CA"].get_vector().get_array())

    if len(ca_coords) < MIN_CA_ATOMS:
        raise RenderError(
            f"Too few CA atoms for camera math ({len(ca_coords)} < {MIN_CA_ATOMS})"
        )

    coords = np.asarray(ca_coords)
    centroid = coords.mean(axis=0)
    centered = coords - centroid

    # Inertia-like covariance tensor (Σ outer(r, r) / N).
    inertia = (centered.T @ centered) / len(centered)

    # eigh returns ascending eigenvalues. We want long axis first.
    eigvals, eigvecs = np.linalg.eigh(inertia)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]  # columns are unit eigenvectors

    # Per-axis projections → full extents (signed min/max).
    projections = centered @ eigvecs  # (N, 3)
    ext_min = projections.min(axis=0)
    ext_max = projections.max(axis=0)

    tan_half_fov = np.tan(np.radians(FOV_HALF_DEG))

    views = []
    for i, name in enumerate(("axis1", "axis2", "axis3")):
        view_dir = eigvecs[:, i]
        # Up vector: next eigenvector in cyclic order — guaranteed orthogonal
        # to view_dir because eigenvectors of a symmetric matrix are orthogonal.
        up = eigvecs[:, (i + 1) % 3]

        # Distance: fit the largest perpendicular half-extent into the FOV.
        perp_axes = [j for j in range(3) if j != i]
        max_perp = max(max(abs(ext_min[j]), abs(ext_max[j])) for j in perp_axes)
        distance = max_perp / tan_half_fov if tan_half_fov > 0 else max_perp * 5

        position = centroid + distance * view_dir
        target = centroid

        views.append((name, position, target, up, distance))

    return views


# =========================================================================
# Scene construction
# =========================================================================
def _chain_ids(structure) -> list[str]:
    model = list(structure.get_models())[0]
    return [chain.id for chain in model]


def build_scene(
    structure_path: Path,
    fmt: str,
    position: np.ndarray,
    target: np.ndarray,
    up: np.ndarray,
    color_mode: str,
    chain_ids: list[str],
) -> str:
    """Build a molviewspec MVS state for a single view. Returns serialized JSON."""
    builder = mvs.create_builder()

    parsed = (
        builder
        .download(url=f"file://{structure_path}")
        .parse(format=fmt)
        .model_structure()
    )

    if color_mode == "chain":
        # One cartoon component per chain, distinct color.
        for idx, cid in enumerate(chain_ids):
            color = CHAIN_PALETTE[idx % len(CHAIN_PALETTE)]
            (
                parsed.component(selector={"label_asym_id": cid})
                      .representation(type="cartoon")
                      .color(color=color)
            )
    else:
        # Default: pLDDT-style coloring from the B-factor column.
        # mmCIF: atom_site.B_iso_or_equiv directly. For PDB, molstar still
        # exposes B-factors via the same logical schema.
        polymer = parsed.component(selector="polymer")
        rep = polymer.representation(type="cartoon")
        try:
            rep.color_from_source(
                schema="all_atomic",
                category_name="atom_site",
                field_name="B_iso_or_equiv",
            )
        except Exception:
            # Older molviewspec versions / API drift: fall back to a uniform
            # color rather than fail the render.
            rep.color(color="#4682B4")

    builder.camera(
        position=[float(x) for x in position],
        target=[float(x) for x in target],
        up=[float(x) for x in up],
    )
    # State is a Pydantic model — serialize via its own JSON encoder, since
    # it contains enum/special types that json.dumps can't handle.
    return builder.get_state().json()


# =========================================================================
# Render primitive
# =========================================================================
def run_mvs_render(scene_json: str, output_path: Path, size: tuple[int, int]):
    """Single render call. Raises RenderError on any failure."""
    if shutil.which("mvs-render") is None:
        raise RenderError("mvs-render not on PATH (npm install -g molstar)")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".mvsj", delete=False
    ) as tmp:
        tmp.write(scene_json)
        scene_path = Path(tmp.name)

    try:
        # Canonical mvs-render CLI: positional input output, --size WxH.
        cmd = [
            "mvs-render",
            "-i", str(scene_path),
            "-o", str(output_path),
            "--size", f"{size[0]}x{size[1]}",
        ]
        # Headless WebGL (node `gl`) needs an X display on Linux servers; run it
        # under a throwaway virtual framebuffer when xvfb-run is available.
        if shutil.which("xvfb-run"):
            cmd = ["xvfb-run", "-a"] + cmd
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RenderError(
                f"mvs-render exit {result.returncode}: "
                f"{result.stderr.decode(errors='replace').strip()[:500]}"
            )
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RenderError("mvs-render produced no output")
    except subprocess.TimeoutExpired:
        raise RenderError("mvs-render timed out after 120s")
    finally:
        scene_path.unlink(missing_ok=True)


def log_render_failure(
    failure_dir: Path, view_name: str, scene_json: str, error: Exception
):
    failure_dir.mkdir(parents=True, exist_ok=True)
    (failure_dir / f"{view_name}.mvsj").write_text(scene_json)
    (failure_dir / f"{view_name}.error").write_text(str(error))


# =========================================================================
# Public entrypoint (used by both CLI and the Modal wrapper)
# =========================================================================
def render_structure(
    structure_path: Path,
    output_dir: Path,
    color: str = "pLDDT",
    size: tuple[int, int] = DEFAULT_SIZE,
) -> dict:
    """
    Render three axis-aligned views of one structure.

    Returns a dict with file path, color mode, per-view PNG paths, and per-view
    camera params. Per-view failures are logged and recorded under "failures";
    they do not raise.
    """
    structure_path = Path(structure_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not structure_path.exists():
        raise RenderError(f"Structure file not found: {structure_path}")

    structure, fmt = load_structure(structure_path)
    views = compute_camera_views(structure)
    chain_ids = _chain_ids(structure)

    stem = structure_path.stem
    failure_dir = output_dir / "render_failures" / stem

    pngs: dict[str, str] = {}
    cameras: dict[str, dict] = {}
    failures: dict[str, str] = {}

    for view_name, position, target, up, distance in views:
        cameras[view_name] = {
            "position": [round(float(x), 3) for x in position],
            "target": [round(float(x), 3) for x in target],
            "up": [round(float(x), 3) for x in up],
            "distance": round(float(distance), 3),
        }

        scene = build_scene(
            structure_path, fmt, position, target, up, color, chain_ids
        )
        png_path = output_dir / f"{stem}_{view_name}.png"
        try:
            run_mvs_render(scene, png_path, size)
            pngs[view_name] = png_path.name
        except RenderError as e:
            log_render_failure(failure_dir, view_name, scene, e)
            failures[view_name] = str(e)

    result = {
        "file": structure_path.name,
        "format": fmt,
        "color_mode": color,
        "size": list(size),
        "views": pngs,
        "cameras": cameras,
        "failures": failures,
    }

    json_path = output_dir / f"{stem}_render_views.json"
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


# =========================================================================
# CLI
# =========================================================================
def _parse_size(text: str) -> tuple[int, int]:
    try:
        w, h = text.lower().split("x")
        return (int(w), int(h))
    except ValueError:
        raise argparse.ArgumentTypeError(f"--size must be WxH (got {text!r})")


def main():
    parser = argparse.ArgumentParser(description="Render axis-aligned cartoon views.")
    parser.add_argument("structure_file", type=Path, help="PDB or mmCIF file")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--color", choices=["pLDDT", "chain"], default="pLDDT")
    parser.add_argument("--size", type=_parse_size, default=DEFAULT_SIZE,
                        help="Image size as WxH (default 1024x1024)")
    args = parser.parse_args()

    filepath = args.structure_file
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir or filepath.parent
    stem = filepath.stem

    print("=" * 60)
    print(f"STRUCTURE RENDER: {filepath.name}")
    print("=" * 60)

    try:
        result = render_structure(filepath, output_dir, args.color, args.size)
    except RenderError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    n_ok = len(result["views"])
    n_fail = len(result["failures"])
    print(f"\nViews rendered: {n_ok}/3  (failed: {n_fail})")
    for name, png in result["views"].items():
        print(f"  {name}: {png}")
    for name, err in result["failures"].items():
        print(f"  {name} FAILED: {err}")
    print(f"\nMetadata: {output_dir / (stem + '_render_views.json')}")


if __name__ == "__main__":
    main()
