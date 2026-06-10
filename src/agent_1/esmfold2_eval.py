"""
Agent 1 — ESMFold2-Fast head-to-head evaluation on Modal.

Folds a single protein chain from a FASTA with Biohub's ESMFold2-Fast — the
inference-optimized, single-sequence (no-MSA) config suited to high-throughput,
metagenomic, and low-homology targets — and writes the predicted CIF so it can
be compared against a reference structure with validate.py.

This is an EVALUATION script, not the production Agent 1. Its purpose is the
6EQE head-to-head against the Boltz-2 single-sequence result (7.85 A Ca RMSD,
core plddt 0.55). Adapted from the ESMFold2 Modal example
(github.com/espickle1/esmc-esmfold2), trimmed to single-chain + FASTA input.

Usage (from src/agent_1/):

    modal run esmfold2_eval.py \
        --fasta test_data/rcsb_pdb_6EQE.fasta \
        --output-path step1_results/6EQE_esmfold2fast_predicted.cif

    python3 validate.py \
        --predicted step1_results/6EQE_esmfold2fast_predicted.cif \
        --reference test_data/6EQE.cif
"""

from pathlib import Path
from typing import Optional

import modal

MINUTES = 60  # seconds

app = modal.App(name="agent1-esmfold2-eval")

# ---------------------------------------------------------------------------
# Container image — only the Biohub `esm` library is needed; it pulls a custom
# transformers fork that provides the ESMFold2 model classes. Pin the upstream
# commit so builds are reproducible (matches the known-good example).
# ---------------------------------------------------------------------------
ESM_REVISION = "81b3646c9429ea8458918415ad6a46178cb59833"

esmfold2_image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("git")
    .uv_pip_install(f"esm @ git+https://github.com/Biohub/esm.git@{ESM_REVISION}")
)

with esmfold2_image.imports():
    from esm.models.esmfold2 import (
        ESMFold2InputBuilder,
        ProteinInput,
        StructurePredictionInput,
    )
    from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

# ---------------------------------------------------------------------------
# Weight cache on a Modal Volume; point the HF cache at it.
# ---------------------------------------------------------------------------
esmfold2_volume = modal.Volume.from_name("esmfold2-models", create_if_missing=True)
models_dir = Path("/models")
esmfold2_image = esmfold2_image.env(
    {
        "HF_HOME": str(models_dir),
        "HF_XET_HIGH_PERFORMANCE": "1",  # speed up downloads
    }
)

# ESMFold2-Fast: 0.2B params, single-sequence, inference-optimized. Loads with
# the same ESMFold2Model.from_pretrained syntax as the full model. Left
# unpinned (no revision) for the eval — pin to a commit before production.
ESMFOLD2_REPO = "biohub/ESMFold2-Fast"


@app.cls(
    image=esmfold2_image,
    volumes={models_dir: esmfold2_volume},
    gpu="H100",  # overkill for a 0.2B model; right-size before throughput use
    timeout=20 * MINUTES,
)
class ESMFold2FastInference:
    @modal.enter()
    def load_model(self):
        # Loaded once per container (warm in GPU memory across folds) — the
        # pattern that makes this attractive for high-throughput batches.
        print(f"🧬 loading {ESMFOLD2_REPO} onto the GPU")
        self.model = ESMFold2Model.from_pretrained(ESMFOLD2_REPO).cuda().eval()

    @modal.method()
    def fold(
        self,
        sequence: str,
        num_loops: int = 3,
        num_sampling_steps: int = 50,
        num_diffusion_samples: int = 1,
        seed: int = 0,
    ) -> tuple[str, float, float, float]:
        spi = StructurePredictionInput(
            sequences=[ProteinInput(id="A", sequence=sequence.strip())]
        )
        print(
            f"🧬 folding {len(sequence)} aa (num_loops={num_loops}, "
            f"num_sampling_steps={num_sampling_steps})"
        )
        result = ESMFold2InputBuilder().fold(
            self.model,
            spi,
            num_loops=num_loops,
            num_sampling_steps=num_sampling_steps,
            num_diffusion_samples=num_diffusion_samples,
            seed=seed,
        )
        return (
            result.complex.to_mmcif(),
            float(result.plddt.mean()),
            float(result.ptm),
            float(result.iptm),
        )


def _parse_fasta(fasta_path: str) -> tuple[str, str]:
    """Parse a single-record FASTA. Returns (header, sequence)."""
    text = Path(fasta_path).read_text().strip()
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines or not lines[0].startswith(">"):
        raise ValueError(f"Not a FASTA file: {fasta_path}")
    header = lines[0][1:].strip()
    sequence = "".join(lines[1:]).replace(" ", "").replace("\t", "")
    return header, sequence


@app.local_entrypoint()
def main(fasta: str, output_path: Optional[str] = None):
    header, sequence = _parse_fasta(fasta)
    print(f"🧬 ESMFold2-Fast | {header} | {len(sequence)} aa")

    cif_text, plddt, ptm, iptm = ESMFold2FastInference().fold.remote(sequence)
    print(f"🧬 pLDDT mean: {plddt:.3f}, pTM: {ptm:.3f}, ipTM: {iptm:.3f}")

    out = Path(output_path) if output_path else Path("/tmp/esmfold2/prediction.cif")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cif_text)
    print(f"🧬 wrote predicted structure to {out}")
