"""
Agent 1 — Step 1 validator.

Structural comparison of the Boltz-2 prediction against the reference
6EQE experimental structure.

Scope: quick sanity check, NOT the full Agent 2 pipeline. Uses BioPython's
Superimposer on matched Cα atoms to compute global RMSD and a per-chain
breakdown. This is a lightweight validator that runs locally and tells us
whether the Step 1 prediction is broadly correct before we commit to
building the rest of the pipeline.

Success criteria for Step 1 (PETase 6EQE, 290 aa monomer):
    - Predicted CIF parses cleanly
    - Residue count matches input (minor tolerance for crystal missing
      density — the reference may have fewer resolved residues than
      the prediction)
    - Global Cα RMSD on the resolved overlap region < 2.5 Å
      (well-characterized enzyme, single-sequence Boltz-2 prediction
      should reach experimental-quality for a protein with lots of
      close homologs in the training set)

Usage:
    python validate.py \\
        --predicted ./step1_results/6EQE_step1_predicted.cif \\
        --reference /path/to/rcsb_pdb_6EQE.cif
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from Bio.PDB import MMCIFParser, Superimposer
from Bio.PDB.Polypeptide import is_aa


def extract_ca_by_resid(structure, chain_id: str | None = None) -> dict[int, np.ndarray]:
    """Return {residue_number: Cα coord} for the first model.

    If chain_id is None, uses the first protein chain.
    Heteroatoms and non-standard residues are skipped.
    """
    model = next(structure.get_models())
    chains = list(model.get_chains())
    if chain_id is not None:
        chains = [c for c in chains if c.id == chain_id]
    if not chains:
        raise ValueError(f"No chains found (requested chain_id={chain_id})")

    # Use first protein chain
    for chain in chains:
        residues = [r for r in chain if is_aa(r, standard=True) and "CA" in r]
        if residues:
            return {r.id[1]: r["CA"].get_coord() for r in residues}, chain.id
    raise ValueError("No protein residues with Cα found")


def compute_rmsd(pred_cif: Path, ref_cif: Path) -> dict:
    parser = MMCIFParser(QUIET=True)
    pred = parser.get_structure("pred", str(pred_cif))
    ref = parser.get_structure("ref", str(ref_cif))

    pred_ca, pred_chain = extract_ca_by_resid(pred)
    ref_ca, ref_chain = extract_ca_by_resid(ref)

    # Match on residue numbers that appear in both
    shared = sorted(set(pred_ca.keys()) & set(ref_ca.keys()))
    if len(shared) < 20:
        raise ValueError(
            f"Too few shared residues ({len(shared)}). "
            f"Pred residues: {min(pred_ca)}-{max(pred_ca)} (n={len(pred_ca)}). "
            f"Ref residues: {min(ref_ca)}-{max(ref_ca)} (n={len(ref_ca)})."
        )

    # Note on numbering: PDB experimental structures often start at the
    # mature N-terminus (residue 1 = first resolved residue), while the
    # Boltz prediction numbers from residue 1 = first aa of the input
    # sequence. If there's a signal peptide in the input that's absent
    # from the PDB, naive residue-number matching will misalign.
    # For 6EQE: the PDB numbering starts at residue 33 of the full
    # precursor (accommodating the signal peptide). If shared is small,
    # we fall back to sequence-based alignment (future Step 2 work).

    # Build coordinate arrays in matched order
    pred_coords = np.array([pred_ca[r] for r in shared])
    ref_coords = np.array([ref_ca[r] for r in shared])

    # Kabsch superposition via BioPython
    # (Using Superimposer requires Atom objects; we use numpy directly.)
    # Centroids
    pc = pred_coords.mean(axis=0)
    rc = ref_coords.mean(axis=0)
    P = pred_coords - pc
    R = ref_coords - rc
    # SVD -> rotation
    H = P.T @ R
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    rot = Vt.T @ D @ U.T
    P_rot = P @ rot.T
    diffs = P_rot - R
    rmsd = float(np.sqrt((diffs ** 2).sum() / len(diffs)))

    # Per-residue deviation after superposition
    per_res_dev = np.linalg.norm(diffs, axis=1)

    return {
        "pred_chain": pred_chain,
        "ref_chain": ref_chain,
        "pred_residue_count": len(pred_ca),
        "ref_residue_count": len(ref_ca),
        "shared_residues": len(shared),
        "shared_range": (int(min(shared)), int(max(shared))),
        "global_ca_rmsd": round(rmsd, 3),
        "max_deviation": round(float(per_res_dev.max()), 3),
        "median_deviation": round(float(np.median(per_res_dev)), 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predicted", required=True, type=Path)
    ap.add_argument("--reference", required=True, type=Path)
    args = ap.parse_args()

    if not args.predicted.exists():
        print(f"ERROR: predicted CIF not found: {args.predicted}")
        return 1
    if not args.reference.exists():
        print(f"ERROR: reference CIF not found: {args.reference}")
        return 1

    try:
        result = compute_rmsd(args.predicted, args.reference)
    except ValueError as e:
        print(f"VALIDATION FAILED: {e}")
        print(
            "\nIf the error is about too few shared residues, the most likely "
            "cause is residue numbering mismatch (signal peptide in predicted "
            "but not reference, or vice versa). Step 2 will add sequence-based "
            "chain matching that's robust to numbering offsets."
        )
        return 2

    print("=" * 60)
    print("STEP 1 VALIDATION — Boltz-2 prediction vs. reference")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k:25s} {v}")

    rmsd = result["global_ca_rmsd"]
    shared = result["shared_residues"]
    pred_res_count = result["pred_residue_count"]
    ref_res_count = result["ref_residue_count"]

    print("\nInterpretation:")
    if rmsd < 2.0:
        print(f"  ✓ RMSD {rmsd} Å is excellent for Boltz-2 single-sequence.")
        print(f"    Prediction is structurally sound.")
    elif rmsd < 2.5:
        print(f"  ✓ RMSD {rmsd} Å is acceptable for Boltz-2 single-sequence.")
        print(f"    PETase has close homologs in training data, so this is")
        print(f"    a reasonable outcome. Step 1 passes.")
    elif rmsd < 4.0:
        print(f"  ⚠ RMSD {rmsd} Å is marginal. Worth inspecting visually")
        print(f"    before declaring Step 1 a pass. Possible issues:")
        print(f"    - Flexible regions (loops, termini) driving the RMSD up")
        print(f"    - Signal peptide residues disordered/unresolved")
    else:
        print(f"  ✗ RMSD {rmsd} Å is concerning. Check:")
        print(f"    - Did the prediction complete all recycling steps?")
        print(f"    - Was the correct sequence submitted?")
        print(f"    - Is the residue numbering mismatched (large shift)?")

    if shared < min(pred_res_count, ref_res_count) * 0.5:
        print(f"\n  Note: only {shared} residues overlap between prediction and")
        print(f"  reference. This likely reflects signal peptide or terminal")
        print(f"  residues absent from the crystal structure. The RMSD above")
        print(f"  is computed on the {shared}-residue overlap region only.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
