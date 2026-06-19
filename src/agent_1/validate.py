"""
Agent 1 — structure prediction validator.

Lightweight structural sanity check: compares a predicted structure against a
reference experimental structure by global Cα RMSD over the residue-number
overlap, with a per-residue deviation breakdown. This is NOT the full Agent 2
pipeline — just a fast "is the fold broadly right?" check.

Parses the mmCIF ``_atom_site`` loop directly via BioPython's ``MMCIF2Dict``
rather than the full structure builder, so it tolerates minimal mmCIF files —
notably ESMFold2 output, which omits the ``_atom_site.occupancy`` column that
BioPython's ``MMCIFParser`` hard-requires.

Reference RMSD bands (Cα, over the resolved overlap region):
    < 2.0 Å   excellent — prediction is structurally sound
    < 2.5 Å   acceptable
    < 4.0 Å   marginal — inspect before trusting (flexible loops/termini?)
    >= 4.0 Å  concerning — likely a genuinely wrong fold or a numbering mismatch

Usage:
    python validate.py \\
        --predicted ./step1_results/prediction.cif \\
        --reference /path/to/reference.cif
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from Bio.PDB.MMCIF2Dict import MMCIF2Dict


def extract_ca_by_resid(
    cif_path: Path, chain_id: str | None = None
) -> tuple[dict[int, np.ndarray], str]:
    """Return ``({auth_seq_id: Cα coord}, chain_id)`` from the mmCIF atom loop.

    Reads ``_atom_site`` directly with ``MMCIF2Dict`` so it works on minimal
    mmCIF files that lack columns the full ``MMCIFParser`` requires (e.g.
    ESMFold2 output has no ``_atom_site.occupancy``). Only ATOM records are
    considered; HETATM (waters, ligands, modified residues) are skipped. If
    ``chain_id`` is None, the chain with the most Cα atoms is used.
    """
    d = MMCIF2Dict(str(cif_path))
    group = d["_atom_site.group_PDB"]
    atom = d["_atom_site.label_atom_id"]
    chain = d["_atom_site.auth_asym_id"]
    seq = d["_atom_site.auth_seq_id"]
    xs, ys, zs = (
        d["_atom_site.Cartn_x"],
        d["_atom_site.Cartn_y"],
        d["_atom_site.Cartn_z"],
    )

    ca_counts = Counter(
        chain[i]
        for i in range(len(atom))
        if group[i] == "ATOM" and atom[i] == "CA"
    )
    if not ca_counts:
        raise ValueError("No protein Cα atoms found")
    target = chain_id if chain_id is not None else ca_counts.most_common(1)[0][0]

    coords: dict[int, np.ndarray] = {}
    for i in range(len(atom)):
        if group[i] != "ATOM" or atom[i] != "CA" or chain[i] != target:
            continue
        try:
            resid = int(seq[i])
        except ValueError:
            continue
        if resid not in coords:  # first altloc wins
            coords[resid] = np.array([float(xs[i]), float(ys[i]), float(zs[i])])
    if not coords:
        raise ValueError(f"No Cα atoms for chain {target!r}")
    return coords, target


def compute_rmsd(pred_cif: Path, ref_cif: Path) -> dict:
    pred_ca, pred_chain = extract_ca_by_resid(pred_cif)
    ref_ca, ref_chain = extract_ca_by_resid(ref_cif)

    # Match on residue numbers present in both structures.
    shared = sorted(set(pred_ca) & set(ref_ca))
    if len(shared) < 20:
        raise ValueError(
            f"Too few shared residues ({len(shared)}). "
            f"Pred residues: {min(pred_ca)}-{max(pred_ca)} (n={len(pred_ca)}). "
            f"Ref residues: {min(ref_ca)}-{max(ref_ca)} (n={len(ref_ca)})."
        )

    # Numbering note: experimental structures often start at the first resolved
    # residue, while a prediction numbers from residue 1 of the input sequence.
    # If the input carries a signal peptide / tag absent from the crystal,
    # naive residue-number matching can misalign. We raise above when the
    # overlap is small; sequence-based chain matching is future work.

    pred_coords = np.array([pred_ca[r] for r in shared])
    ref_coords = np.array([ref_ca[r] for r in shared])

    # Kabsch superposition (numpy directly).
    P = pred_coords - pred_coords.mean(axis=0)
    R = ref_coords - ref_coords.mean(axis=0)
    H = P.T @ R
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    rot = Vt.T @ np.diag([1, 1, d]) @ U.T
    diffs = (P @ rot.T) - R
    rmsd = float(np.sqrt((diffs ** 2).sum() / len(diffs)))
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
    except (ValueError, KeyError) as e:
        print(f"VALIDATION FAILED: {e}")
        print(
            "\nIf this is about too few shared residues, the likely cause is a "
            "residue-numbering mismatch (a signal peptide or tag present in the "
            "prediction but not the reference, or vice versa). Sequence-based "
            "chain matching robust to numbering offsets is future work."
        )
        return 2

    print("=" * 60)
    print("STRUCTURE VALIDATION — prediction vs. reference")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k:25s} {v}")

    rmsd = result["global_ca_rmsd"]
    shared = result["shared_residues"]
    pred_res_count = result["pred_residue_count"]
    ref_res_count = result["ref_residue_count"]

    print("\nInterpretation:")
    if rmsd < 2.0:
        print(f"  ✓ Cα RMSD {rmsd} Å is excellent — prediction is structurally sound.")
    elif rmsd < 2.5:
        print(f"  ✓ Cα RMSD {rmsd} Å is acceptable.")
    elif rmsd < 4.0:
        print(f"  ⚠ Cα RMSD {rmsd} Å is marginal. Inspect before trusting:")
        print("    - flexible regions (loops, termini) inflating the RMSD")
        print("    - disordered / unresolved residues in the overlap")
    else:
        print(f"  ✗ Cα RMSD {rmsd} Å is concerning. Check:")
        print("    - did the prediction converge?")
        print("    - was the correct sequence submitted?")
        print("    - is the residue numbering mismatched (large shift)?")

    if shared < min(pred_res_count, ref_res_count) * 0.5:
        print(f"\n  Note: only {shared} residues overlap between prediction and")
        print("  reference — likely signal-peptide or terminal residues absent")
        print(f"  from the crystal. RMSD is over the {shared}-residue overlap only.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
