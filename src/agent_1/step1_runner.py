"""
Agent 1 — Step 1 runner.

Submits the 6EQE test sequence to Modal, downloads the predicted CIF,
writes a minimal result record, and prints a summary.

Usage (from local machine):

    # Ensure Modal auth is set:
    #   modal token set --token-id ... --token-secret ...
    #
    # Then from this directory:
    python step1_runner.py --fasta /path/to/rcsb_pdb_6EQE.fasta \
                           --output-dir ./step1_results/

Design notes:
- This is a local driver, not deployed to Modal. It invokes the remote
  function via `modal_app.predict_structure.remote(...)`.
- The CIF is written to the local output dir so validate.py can run
  without any Modal dependency.
- Boltz runtime and GPU cost are logged for the beta-calibration record.
"""

import argparse
import json
import time
from pathlib import Path

import modal

# Look up the deployed Modal functions by name. The app must already be
# deployed (`modal deploy modal_app.py`) before running this script — calling
# `.remote()` on a locally-imported function raises ExecutionError because the
# function is not hydrated with deployment metadata.
_APP_NAME = "agent1-step1-boltz2"
predict_structure = modal.Function.from_name(_APP_NAME, "predict_structure")
fetch_cif = modal.Function.from_name(_APP_NAME, "fetch_cif")


def parse_fasta(fasta_path: Path) -> tuple[str, str]:
    """Parse a single-record FASTA. Returns (header, sequence)."""
    text = fasta_path.read_text().strip()
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines or not lines[0].startswith(">"):
        raise ValueError(f"Not a FASTA file: {fasta_path}")
    header = lines[0][1:].strip()
    sequence = "".join(lines[1:]).replace(" ", "").replace("\t", "")
    # sanity check: only canonical AAs + X
    bad = set(sequence) - set("ACDEFGHIKLMNPQRSTVWYX")
    if bad:
        raise ValueError(f"Unexpected residues in sequence: {bad}")
    return header, sequence


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fasta", required=True, type=Path)
    ap.add_argument("--output-dir", type=Path, default=Path("step1_results"))
    ap.add_argument("--structure-id", default="6EQE_step1")
    ap.add_argument("--stoichiometry", type=int, default=1)
    args = ap.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    header, sequence = parse_fasta(args.fasta)
    print(f"[step1] FASTA header: {header}")
    print(f"[step1] Sequence length: {len(sequence)} aa")
    print(f"[step1] Structure ID: {args.structure_id}")
    print(f"[step1] Stoichiometry: {args.stoichiometry}")
    print(f"[step1] Submitting to Modal (Boltz-2 A100)...")

    t_submit = time.time()
    result = predict_structure.remote(
        sequence=sequence,
        structure_id=args.structure_id,
        stoichiometry=args.stoichiometry,
    )
    t_total = time.time() - t_submit

    # Save the result record
    result["local_wall_clock_seconds"] = round(t_total, 2)
    result["input_fasta_header"] = header
    result_path = args.output_dir / f"{args.structure_id}_result.json"
    result_path.write_text(json.dumps(result, indent=2))
    print(f"[step1] Result JSON: {result_path}")

    if not result.get("success"):
        print(f"[step1] FAILED: {result.get('error')}")
        print(json.dumps(result, indent=2))
        return 1

    # Download the CIF back locally
    print(f"[step1] Fetching predicted CIF from scratch volume...")
    cif_bytes = fetch_cif.remote(result["cif_path"])
    local_cif = args.output_dir / f"{args.structure_id}_predicted.cif"
    local_cif.write_bytes(cif_bytes)
    print(f"[step1] Local CIF: {local_cif}")

    # Summary
    print("\n" + "=" * 60)
    print("STEP 1 RESULT SUMMARY")
    print("=" * 60)
    print(f"Boltz version:       {result['boltz_version']}")
    print(f"Structure ID:        {result['structure_id']}")
    print(f"GPU runtime (s):     {result['runtime_seconds']}")
    print(f"Wall-clock (s):      {result['local_wall_clock_seconds']}")
    print(f"Confidence metrics:")
    for k, v in (result.get("metrics") or {}).items():
        if v is not None:
            print(f"  {k:25s} {v}")
    print(f"\nNext: python validate.py --predicted {local_cif} --reference <6EQE.cif>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
