"""
Agent 2 — structure render Modal app.

Wraps `agent_2.scripts.render_views.render_structure` in a Modal function so
batches of structures can be rendered in parallel via `.map()`. The container
ships Mol* (`mvs-render`, installed via the molstar npm package) and the
molviewspec Python builder; the rest of the rendering logic lives in
`scripts/render_views.py` and is imported here unchanged.

Usage:

    # Single structure (CIF must be reachable from inside the container —
    # i.e. on the mounted Modal Volume):
    modal run src/agent_2/modal_app.py \\
        --structure-path /scratch/<stem>.cif

    # Programmatic batch fan-out: see render_batch().

Volume layout:
    /scratch/<...>.cif                   — input structures
    /scratch/renders/<stem>_axis{1,2,3}.png  — output renders (default)
    /scratch/renders/<stem>_render_views.json
"""

from __future__ import annotations

import json
from pathlib import Path

import modal


# ---------------------------------------------------------------------------
# Container image
# ---------------------------------------------------------------------------
# Node 20 + headless GL libs for mvs-render. molstar is the npm package that
# ships the `mvs-render` CLI binary.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "curl",
        "build-essential",
        "pkg-config",
        "xvfb",                  # virtual framebuffer — node-gl needs an X display
        "libgl1",
        "libglu1-mesa",
        "libxi6",
        "libxext6",
        "libgl1-mesa-dev",       # headers to build the node `gl` (headless-gl) module
        "libxi-dev",
        "libxext-dev",
        "libcairo2-dev",         # node-canvas build deps (molstar's image backend)
        "libpango1.0-dev",
        "libjpeg-dev",
        "libgif-dev",
        "librsvg2-dev",
    )
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        # `gl` (headless-gl) is the WebGL backend mvs-render requires; install it
        # in the same global node_modules as molstar.
        "npm install -g molstar@latest canvas gl jpeg-js pngjs",
    )
    .env({"NODE_PATH": "/usr/lib/node_modules"})  # let mvs-render resolve global `gl`
    .pip_install(
        "molviewspec",
        "biopython",
        "numpy",
    )
    # Mount the agent_2 namespace package so we can import render_views.
    .add_local_python_source("agent_2")
)


# ---------------------------------------------------------------------------
# Volume — shares the agent_1 step1 scratch volume so renders land alongside
# the CIFs Agent 1 produced. Production may rename this to a shared
# pipeline volume.
# ---------------------------------------------------------------------------
SCRATCH_VOLUME = modal.Volume.from_name("agent1-step1-scratch", create_if_missing=True)


app = modal.App("agent_2-render")


@app.function(
    image=image,
    cpu=2,
    memory=2048,
    timeout=600,
    volumes={"/scratch": SCRATCH_VOLUME},
)
def render_structure_remote(
    structure_path: str,
    output_dir: str = "/scratch/renders",
    color: str = "pLDDT",
    size: tuple[int, int] = (1024, 1024),
) -> dict:
    """Render one structure on Modal. Returns the same dict as the local script."""
    from agent_2.scripts.render_views import render_structure

    SCRATCH_VOLUME.reload()
    result = render_structure(
        Path(structure_path),
        Path(output_dir),
        color=color,
        size=size,
    )
    SCRATCH_VOLUME.commit()
    return result


@app.function(
    image=image,
    cpu=1,
    memory=1024,
    timeout=60 * 30,
    volumes={"/scratch": SCRATCH_VOLUME},
)
def render_batch(items: list[dict]) -> list[dict]:
    """
    Fan out renders across `items`. Each item is a dict with:
        structure_path: str   (required)
        output_dir:     str   (optional, default /scratch/renders)
        color:          str   (optional, default 'pLDDT')

    Returns the per-structure results in input order.
    """
    paths = [it["structure_path"] for it in items]
    output_dirs = [it.get("output_dir", "/scratch/renders") for it in items]
    colors = [it.get("color", "pLDDT") for it in items]
    sizes = [it.get("size", (1024, 1024)) for it in items]

    results = list(
        render_structure_remote.map(paths, output_dirs, colors, sizes)
    )
    return results


@app.local_entrypoint()
def main(
    structure_path: str,
    output_dir: str = "/scratch/renders",
    color: str = "pLDDT",
):
    """Smoke-test entrypoint.

    Example:
        modal run src/agent_2/modal_app.py \\
            --structure-path /scratch/step1_runs/foo/out/predictions/foo/foo_model_0.cif
    """
    print(f"[render] {structure_path} → {output_dir} (color={color})")
    result = render_structure_remote.remote(
        structure_path=structure_path,
        output_dir=output_dir,
        color=color,
    )
    print(json.dumps(result, indent=2))
    return result
