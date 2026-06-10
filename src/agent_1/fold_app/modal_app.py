"""Agent 1 fold app — ESMFold2-Fast on Modal (production batch engine).

Warm ``@app.cls``: the model loads once per container (``@modal.enter``) and
serves many folds via ``.map()`` from the orchestrator, so the per-fold cost is
just inference. Single-sequence, no MSA — the ESMFold2-Fast design point for
novel / metagenomic / low-homology targets.

Model / fold / GPU constants are defined HERE rather than imported from
``shared/config.py`` so the app is self-contained inside the container (no
package-mounting dependency). The orchestrator-side knobs live in config.py.

Deploy:  modal deploy src/agent_1/fold_app/modal_app.py
"""

from pathlib import Path

import modal

MINUTES = 60  # seconds

APP_NAME = "agent1-esmfold2"
app = modal.App(name=APP_NAME)

# ---------------------------------------------------------------------------
# Image — only the Biohub `esm` library (pulls a custom transformers fork).
# Pin the upstream commit for reproducible builds.
# ---------------------------------------------------------------------------
ESM_REVISION = "81b3646c9429ea8458918415ad6a46178cb59833"

image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("git")
    .uv_pip_install(f"esm @ git+https://github.com/Biohub/esm.git@{ESM_REVISION}")
)

with image.imports():
    from esm.models.esmfold2 import (
        ESMFold2InputBuilder,
        ProteinInput,
        StructurePredictionInput,
    )
    from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

# Weights cached on a Volume (shared with the eval script); HF cache points at it.
volume = modal.Volume.from_name("esmfold2-models", create_if_missing=True)
models_dir = Path("/models")
image = image.env({"HF_HOME": str(models_dir), "HF_XET_HIGH_PERFORMANCE": "1"})

# ESMFold2-Fast: 0.2B, single-sequence, no MSA. Fold params + GPU are tunable.
ESMFOLD2_REPO = "biohub/ESMFold2-Fast"
ESMFOLD2_REVISION = None  # latest; pin to a commit before production
NUM_LOOPS = 3
NUM_SAMPLING_STEPS = 50
NUM_DIFFUSION_SAMPLES = 1
SEED = 0
# H100 was over-provisioned for a 0.2B model; L4 (24 GB) is the cost-efficient
# default — ample headroom even for Agent 0's 2000-aa length ceiling. Bump to
# A10G / A100 only if throughput testing on real batches argues for it.
GPU = "L4"


@app.cls(image=image, volumes={models_dir: volume}, gpu=GPU, timeout=20 * MINUTES)
class ESMFold2Inference:
    @modal.enter()
    def load_model(self):
        print(f"🧬 loading {ESMFOLD2_REPO} onto the GPU")
        kwargs = {"revision": ESMFOLD2_REVISION} if ESMFOLD2_REVISION else {}
        self.model = ESMFold2Model.from_pretrained(ESMFOLD2_REPO, **kwargs).cuda().eval()

    @modal.method()
    def fold(self, request: dict) -> dict:
        """Fold one single-chain request.

        request: {"record_id": str, "aa_sequence": str}
        Returns a result dict; on error returns {"status": "failed", ...} rather
        than raising — failures are logged by the orchestrator, not escalated.
        """
        rid = request.get("record_id", "?")
        seq = request["aa_sequence"].strip()
        try:
            spi = StructurePredictionInput(
                sequences=[ProteinInput(id="A", sequence=seq)]
            )
            result = ESMFold2InputBuilder().fold(
                self.model,
                spi,
                num_loops=NUM_LOOPS,
                num_sampling_steps=NUM_SAMPLING_STEPS,
                num_diffusion_samples=NUM_DIFFUSION_SAMPLES,
                seed=SEED,
            )
            return {
                "record_id": rid,
                "status": "folded",
                "cif": result.complex.to_mmcif(),
                "plddt_mean": float(result.plddt.mean()),
                "ptm": float(result.ptm),
                "iptm": float(result.iptm),
                "model": ESMFOLD2_REPO,
                "model_revision": ESMFOLD2_REVISION,
                "fold_params": {
                    "num_loops": NUM_LOOPS,
                    "num_sampling_steps": NUM_SAMPLING_STEPS,
                    "num_diffusion_samples": NUM_DIFFUSION_SAMPLES,
                    "seed": SEED,
                },
            }
        except Exception as e:  # noqa: BLE001 — errors are logged, not escalated
            return {
                "record_id": rid,
                "status": "failed",
                "detail": f"{type(e).__name__}: {e}",
            }


@app.local_entrypoint()
def smoke(sequence: str = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQA"):
    """Quick single-fold smoke test: modal run src/agent_1/fold_app/modal_app.py"""
    import json

    result = ESMFold2Inference().fold.remote({"record_id": "smoke", "aa_sequence": sequence})
    result.pop("cif", None)  # don't dump the whole CIF
    print(json.dumps(result, indent=2))
