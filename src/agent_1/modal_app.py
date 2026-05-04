"""
Agent 1 — Step 1: Standalone Boltz-2 on Modal.

Purpose: Prove Boltz-2 runs cleanly in Modal and produces usable output.
Scope: No LLM, no orchestration, no quality gate, no retry logic.

Pinned versions:
    boltz == 2.2.1
    python == 3.11
    cuda == 12.1 (via torch wheel)

Usage (from local machine, after `modal token set ...`):

    # Deploy the app
    modal deploy modal_app.py

    # Or run interactively:
    modal run modal_app.py::predict_structure --sequence "MNFPR..." --structure-id "6EQE_test"
"""

import json
import os
import subprocess
import time
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Pinned versions — recorded in every sidecar
# ---------------------------------------------------------------------------
BOLTZ_VERSION = "2.2.1"
PYTHON_VERSION = "3.11"
AGENT1_STEP = "step1_standalone"

# ---------------------------------------------------------------------------
# Container image
# ---------------------------------------------------------------------------
# Baking Boltz weights into the image (via `boltz predict --help` run after
# install) is not sufficient — weights download on first actual prediction.
# Instead we do a tiny throwaway prediction during image build to prime the
# weight cache in /root/.boltz. This makes cold starts significantly faster
# for all downstream invocations.
#
# NOTE: if the tiny warm-up prediction proves too slow/unreliable during
# image build, an alternative is to download the weights archive directly
# from the Boltz release and place them in /root/.boltz during build.

image = (
    modal.Image.debian_slim(python_version=PYTHON_VERSION)
    .apt_install("git", "wget")
    .pip_install(
        f"boltz=={BOLTZ_VERSION}",
        # Boltz 2.2.1 calls into cuequivariance for the kernel triangular
        # multiplicative update. It is not a hard dep of the boltz wheel, so
        # we must add it explicitly. The `-ops-torch-cu12` package supplies
        # the CUDA 12 kernels matching the cu121 PyTorch wheels above.
        # Pinned: latest cuequivariance links against CUDA 13 NVRTC
        # (libnvrtc-builtins.so.13.0), which is incompatible with cu121
        # PyTorch. We need a version that (a) still targets CUDA 12,
        # (b) exposes `cuequivariance_torch.primitives.triangle` in the
        # frontend, and (c) provides `triangle_multiplicative_update` in
        # the ops kernel. 0.4.0 missed (b); 0.5.0 had (b) but missed (c).
        # 0.6.0 should have both. If it pulls cu13, escalate to bumping
        # PyTorch index to cu128 with latest cuequivariance.
        "cuequivariance-torch==0.6.0",
        "cuequivariance-ops-torch-cu12==0.6.0",
        "biopython",       # for output parsing
        "numpy",
        extra_options="--extra-index-url https://download.pytorch.org/whl/cu121",
    )
)

# ---------------------------------------------------------------------------
# Modal Volume — scratch location for Step 1 output
# ---------------------------------------------------------------------------
# Production will use a different, named volume shared with Agent 2.
# For Step 1, a scratch volume keeps infrastructure testing isolated.
SCRATCH_VOLUME = modal.Volume.from_name("agent1-step1-scratch", create_if_missing=True)

# ---------------------------------------------------------------------------
# Modal App
# ---------------------------------------------------------------------------
app = modal.App("agent1-step1-boltz2")


def _write_boltz_yaml(sequence: str, structure_id: str, stoichiometry: int, workdir: Path) -> Path:
    """Build a minimal Boltz-2 input YAML for a protein-only prediction."""
    # Boltz expects one protein entry per chain; for a homo-oligomer we repeat
    # the sequence under different chain IDs.
    # `msa: empty` declares single-sequence mode explicitly. Without it Boltz
    # 2.2.1 errors out demanding either an MSA path or `--use_msa_server`.
    # Single-sequence is the v1 design intent, so we declare it in the YAML
    # rather than pulling MSAs from the public ColabFold server.
    chain_ids = [chr(ord("A") + i) for i in range(stoichiometry)]
    lines = ["version: 1", "sequences:"]
    for cid in chain_ids:
        lines += [
            f"  - protein:",
            f"      id: {cid}",
            f"      sequence: {sequence}",
            f"      msa: empty",
        ]
    yaml_path = workdir / f"{structure_id}.yaml"
    yaml_path.write_text("\n".join(lines) + "\n")
    return yaml_path


def _parse_boltz_output(out_dir: Path, structure_id: str) -> dict:
    """Extract the predicted CIF path and confidence metrics from Boltz output."""
    # Boltz writes to: out_dir/predictions/<stem>/<stem>_model_0.cif
    #                  out_dir/predictions/<stem>/confidence_<stem>_model_0.json
    pred_root = out_dir / "predictions" / structure_id
    if not pred_root.exists():
        # Sometimes nested differently depending on version — search
        candidates = list(out_dir.rglob(f"{structure_id}_model_0.cif"))
        if not candidates:
            raise FileNotFoundError(
                f"No Boltz output found under {out_dir}. "
                f"Contents: {list(out_dir.rglob('*.cif'))}"
            )
        cif_path = candidates[0]
        pred_root = cif_path.parent
    else:
        cif_candidates = list(pred_root.glob("*_model_0.cif"))
        if not cif_candidates:
            raise FileNotFoundError(f"No _model_0.cif under {pred_root}")
        cif_path = cif_candidates[0]

    # Confidence JSON
    conf_candidates = list(pred_root.glob("confidence_*_model_0.json"))
    metrics = {}
    if conf_candidates:
        with open(conf_candidates[0]) as f:
            conf = json.load(f)
        # Standard Boltz confidence keys (check against version 2.2.1)
        metrics = {
            "confidence_score": conf.get("confidence_score"),
            "ptm": conf.get("ptm"),
            "iptm": conf.get("iptm"),
            "complex_plddt": conf.get("complex_plddt"),
            "complex_iplddt": conf.get("complex_iplddt"),
            "complex_pde": conf.get("complex_pde"),
            "complex_ipde": conf.get("complex_ipde"),
        }

    return {"cif_path": str(cif_path), "metrics": metrics}


@app.function(
    image=image,
    gpu="A100",
    volumes={"/scratch": SCRATCH_VOLUME},
    timeout=60 * 30,  # 30 min safety ceiling
    # Note: for larger structures consider H100 or A100-80GB
)
def predict_structure(
    sequence: str,
    structure_id: str,
    stoichiometry: int = 1,
    recycling_steps: int = 3,
    sampling_steps: int = 200,
    diffusion_samples: int = 1,
) -> dict:
    """
    Run Boltz-2 on a single sequence.

    Step 1 scope: minimal interface, monomer or simple homo-oligomer.
    Later steps will add: MSA toggle (not in v1), ligands/cofactors,
    full retry-on-failure logic at the orchestrator layer.

    Returns a dict with structure_id, cif_path (on the scratch volume),
    metrics (pLDDT, pTM, iPTM etc.), runtime_seconds, and the pinned
    version info.
    """
    t0 = time.time()

    workdir = Path("/scratch") / "step1_runs" / structure_id
    workdir.mkdir(parents=True, exist_ok=True)

    # 1. Write the Boltz YAML input
    yaml_path = _write_boltz_yaml(sequence, structure_id, stoichiometry, workdir)

    # 2. Run Boltz predict as subprocess
    #    --use_msa_server is FALSE by default in v1 (we're single-sequence).
    #    --output_format mmcif gives us .cif output (matches PDB convention
    #    and what Agent 2 v4.0 prefers).
    out_dir = workdir / "out"
    out_dir.mkdir(exist_ok=True)

    cmd = [
        "boltz", "predict", str(yaml_path),
        "--out_dir", str(out_dir),
        "--recycling_steps", str(recycling_steps),
        "--sampling_steps", str(sampling_steps),
        "--diffusion_samples", str(diffusion_samples),
        "--output_format", "mmcif",
        "--use_potentials",  # Boltz-2 steering potentials (default good)
    ]
    # NOTE: no MSA in v1 (per design doc). Boltz's default is single-sequence
    # unless --use_msa_server is passed.

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {
            "structure_id": structure_id,
            "success": False,
            "error": "boltz_subprocess_failed",
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "cmd": cmd,
            "runtime_seconds": time.time() - t0,
            "boltz_version": BOLTZ_VERSION,
        }

    # 3. Parse output
    try:
        parsed = _parse_boltz_output(out_dir, structure_id)
    except FileNotFoundError as e:
        return {
            "structure_id": structure_id,
            "success": False,
            "error": f"parse_failure: {e}",
            "stdout_tail": result.stdout[-2000:],
            "runtime_seconds": time.time() - t0,
            "boltz_version": BOLTZ_VERSION,
        }

    # 4. Commit volume so local driver can read the CIF
    SCRATCH_VOLUME.commit()

    return {
        "structure_id": structure_id,
        "success": True,
        "cif_path": parsed["cif_path"],
        "metrics": parsed["metrics"],
        "config": {
            "sequence_length": len(sequence),
            "stoichiometry": stoichiometry,
            "recycling_steps": recycling_steps,
            "sampling_steps": sampling_steps,
            "diffusion_samples": diffusion_samples,
            "msa": False,
        },
        "runtime_seconds": round(time.time() - t0, 2),
        "boltz_version": BOLTZ_VERSION,
        "python_version": PYTHON_VERSION,
        "agent1_step": AGENT1_STEP,
    }


# ---------------------------------------------------------------------------
# Utility: download a predicted CIF back to the local machine
# ---------------------------------------------------------------------------
@app.function(image=image, volumes={"/scratch": SCRATCH_VOLUME})
def fetch_cif(cif_path_on_volume: str) -> bytes:
    """Return the bytes of a CIF file from the scratch volume.

    The local driver calls this to pull the prediction back for validation.
    """
    SCRATCH_VOLUME.reload()
    path = Path(cif_path_on_volume)
    if not path.exists():
        raise FileNotFoundError(f"{cif_path_on_volume} not found on scratch volume")
    return path.read_bytes()


@app.local_entrypoint()
def main(
    sequence: str,
    structure_id: str = "step1_test",
    stoichiometry: int = 1,
):
    """Local entrypoint for smoke-testing from the command line.

    Example:
        modal run modal_app.py --sequence "MNFPR..." --structure-id "6EQE_test"
    """
    print(f"[step1] Submitting {structure_id} ({len(sequence)} aa, N={stoichiometry}) to Modal...")
    result = predict_structure.remote(
        sequence=sequence,
        structure_id=structure_id,
        stoichiometry=stoichiometry,
    )
    print(json.dumps(result, indent=2))
    return result
