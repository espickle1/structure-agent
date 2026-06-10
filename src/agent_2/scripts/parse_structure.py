#!/usr/bin/env python3
"""
parse_structure.py — Phase 1 standardized structure parsing and metadata extraction.

Reads a PDB or mmCIF file and produces:
  1. A JSON metadata file (<stem>_metadata.json)
  2. A human-readable summary to stdout

Auto-detects file format, identifies AlphaFold predictions, catalogs chains,
residues, ligands, metals, waters, chain breaks, and modified residues.

Usage:
    python parse_structure.py <structure_file> [--output-dir <dir>]

Exit codes:
    0 — success
    1 — fatal error (file not found, parse failure, no valid models)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import Counter

import numpy as np

try:
    from Bio.PDB import PDBParser, MMCIFParser
    from Bio.PDB.Polypeptide import is_aa
    from cif_io import read_structure
except ImportError:
    print("ERROR: BioPython is required. Install with: pip install biopython", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Ligand exclusion list — common solvents, ions, crystallization additives
# ---------------------------------------------------------------------------
EXCLUDED_HETRESIDUES = {
    # Water
    "HOH", "WAT", "H2O", "DOD",
    # Common ions
    "NA", "CL", "K", "CA", "MG", "ZN", "FE", "MN", "CO", "CU", "NI", "CD",
    "SO4", "PO4", "NO3",
    # Crystallization additives / cryoprotectants
    "GOL", "EDO", "PEG", "PGE", "MPD", "DMS", "ACT", "FMT", "TRS", "CIT",
    "BME", "EOH", "IMD", "EPE", "MES", "IPA", "CAC",
    # Buffer components
    "HED", "TAR", "MLI", "BIG", "BCT",
    # Other common artifacts
    "UNX", "UNL", "UNK",
}

# Metals reported separately from ligands
METAL_IONS = {
    "NA", "K", "CA", "MG", "ZN", "FE", "FE2", "MN", "CO", "CU", "CU1",
    "NI", "CD", "HG", "PT", "AU", "AG", "PB", "SR", "BA", "CS", "RB",
    "MO", "W", "V", "CR", "SE",
}


def detect_format(filepath: Path) -> str:
    """Detect file format from extension and content."""
    ext = filepath.suffix.lower()
    if ext in (".cif", ".mmcif"):
        return "mmcif"
    if ext == ".pdb":
        return "pdb"
    # Fallback: check first few lines for data_ (mmCIF) or ATOM/HEADER (PDB)
    with open(filepath, "r", errors="replace") as f:
        head = f.read(2000)
    if head.strip().startswith("data_"):
        return "mmcif"
    return "pdb"


def load_structure(filepath: Path):
    """Load structure with appropriate parser. Returns (structure, format_str)."""
    fmt = detect_format(filepath)
    structure = read_structure(filepath.stem, filepath, fmt)
    return structure, fmt


def detect_alphafold(filepath: Path, structure) -> dict:
    """Heuristic detection of AlphaFold predictions."""
    signals = {
        "filename_match": False,
        "no_resolution": True,
        "bfactor_is_plddt": False,
    }

    # Filename heuristic
    name_lower = filepath.stem.lower()
    if "af-" in name_lower or "alphafold" in name_lower or "af_" in name_lower:
        signals["filename_match"] = True

    # Check for resolution in header (PDB files)
    try:
        with open(filepath, "r", errors="replace") as f:
            for line in f:
                if line.startswith("REMARK   2 RESOLUTION"):
                    signals["no_resolution"] = False
                    break
                if line.startswith("ATOM"):
                    break
    except Exception:
        pass

    # B-factor distribution: pLDDT is 0-100, clustered high
    bfactors = []
    model = list(structure.get_models())[0]
    for atom in model.get_atoms():
        bfactors.append(atom.get_bfactor())
    if bfactors:
        bfactors = np.array(bfactors)
        in_range = np.all((bfactors >= 0) & (bfactors <= 100))
        median_high = np.median(bfactors) > 50
        signals["bfactor_is_plddt"] = bool(in_range and median_high)

    is_predicted = (
        signals["filename_match"]
        or (signals["no_resolution"] and signals["bfactor_is_plddt"])
    )

    return {"is_predicted": is_predicted, "detection_signals": signals}


def extract_resolution(filepath: Path, fmt: str) -> float | None:
    """Extract resolution from file."""
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
        if fmt == "pdb":
            for line in content.splitlines():
                if line.startswith("REMARK   2 RESOLUTION"):
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "RESOLUTION." or p == "RESOLUTION":
                            try:
                                return float(parts[i + 1])
                            except (IndexError, ValueError):
                                pass
        elif fmt == "mmcif":
            for line in content.splitlines():
                if "_refine.ls_d_res_high" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            return float(parts[1])
                        except ValueError:
                            pass
    except Exception:
        pass
    return None


def extract_experimental_method(filepath: Path, fmt: str) -> str | None:
    """Extract experimental method."""
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
        if fmt == "pdb":
            for line in content.splitlines():
                if line.startswith("EXPDTA"):
                    return line[10:].strip()
        elif fmt == "mmcif":
            for line in content.splitlines():
                if "_exptl.method" in line:
                    parts = line.split("'")
                    if len(parts) >= 2:
                        return parts[1]
                    parts = line.split()
                    if len(parts) >= 2:
                        return " ".join(parts[1:])
    except Exception:
        pass
    return None


def analyze_chain(chain) -> dict:
    """Analyze a single chain."""
    residues = list(chain.get_residues())
    
    standard_residues = []
    het_residues = []
    waters = []
    metals = []
    ligands = []
    modified_residues = []

    for res in residues:
        resname = res.get_resname().strip()
        hetflag = res.get_id()[0]

        if hetflag == " " or hetflag == "A":
            # Standard residue or first altloc
            if is_aa(res, standard=True):
                standard_residues.append(res)
            elif is_aa(res, standard=False):
                modified_residues.append({
                    "resname": resname,
                    "resid": res.get_id()[1],
                    "icode": res.get_id()[2].strip(),
                })
                standard_residues.append(res)  # count in total
            else:
                standard_residues.append(res)
        elif hetflag == "W":
            waters.append(res)
        elif hetflag.startswith("H"):
            if resname in METAL_IONS:
                metals.append({"resname": resname, "resid": res.get_id()[1]})
            elif resname in EXCLUDED_HETRESIDUES:
                pass  # skip solvents/additives
            else:
                ligands.append({
                    "resname": resname,
                    "resid": res.get_id()[1],
                    "num_atoms": len(list(res.get_atoms())),
                })

    # Detect chain breaks (gaps in residue numbering > 1 for sequential residues)
    chain_breaks = []
    aa_residues = [r for r in standard_residues if is_aa(r)]
    for i in range(1, len(aa_residues)):
        prev_id = aa_residues[i - 1].get_id()[1]
        curr_id = aa_residues[i].get_id()[1]
        if curr_id - prev_id > 1:
            chain_breaks.append({
                "after_resid": prev_id,
                "before_resid": curr_id,
                "gap_size": curr_id - prev_id - 1,
            })

    # Extract sequence
    three_to_one = {
        "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
        "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
        "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
        "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
        "MSE": "M", "SEC": "U", "PYL": "O",
    }
    sequence = ""
    for r in aa_residues:
        rn = r.get_resname().strip()
        sequence += three_to_one.get(rn, "X")

    # B-factor / pLDDT statistics
    bfactors = []
    for r in aa_residues:
        ca = r["CA"] if r.has_id("CA") else None
        if ca is not None:
            bfactors.append(ca.get_bfactor())

    bfactor_stats = {}
    if bfactors:
        bfactors = np.array(bfactors)
        bfactor_stats = {
            "mean": round(float(np.mean(bfactors)), 2),
            "median": round(float(np.median(bfactors)), 2),
            "min": round(float(np.min(bfactors)), 2),
            "max": round(float(np.max(bfactors)), 2),
            "std": round(float(np.std(bfactors)), 2),
        }

    return {
        "chain_id": chain.get_id(),
        "num_residues": len(aa_residues),
        "num_atoms": sum(1 for _ in chain.get_atoms()),
        "sequence": sequence,
        "sequence_length": len(sequence),
        "ligands": ligands,
        "metals": metals,
        "num_waters": len(waters),
        "modified_residues": modified_residues,
        "chain_breaks": chain_breaks,
        "bfactor_stats": bfactor_stats,
    }


def parse_structure(filepath: Path, output_dir: Path) -> dict:
    """Main parsing function. Returns metadata dict and writes JSON."""
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    structure, fmt = load_structure(filepath)
    models = list(structure.get_models())

    if not models:
        print("ERROR: No models found in structure file.", file=sys.stderr)
        sys.exit(1)

    model = models[0]
    af_info = detect_alphafold(filepath, structure)
    resolution = extract_resolution(filepath, fmt)
    exp_method = extract_experimental_method(filepath, fmt)

    chains_data = []
    for chain in model:
        chains_data.append(analyze_chain(chain))

    # Aggregate
    total_residues = sum(c["num_residues"] for c in chains_data)
    total_atoms = sum(c["num_atoms"] for c in chains_data)
    all_ligands = []
    all_metals = []
    for c in chains_data:
        for lig in c["ligands"]:
            lig_with_chain = {**lig, "chain_id": c["chain_id"]}
            all_ligands.append(lig_with_chain)
        for met in c["metals"]:
            met_with_chain = {**met, "chain_id": c["chain_id"]}
            all_metals.append(met_with_chain)

    # Unique ligand names
    unique_ligands = sorted(set(lig["resname"] for lig in all_ligands))

    # Count total missing residues from chain breaks
    total_missing = sum(
        b["gap_size"] for c in chains_data for b in c["chain_breaks"]
    )

    metadata = {
        "file": filepath.name,
        "format": fmt,
        "num_models": len(models),
        "num_chains": len(chains_data),
        "total_residues": total_residues,
        "total_atoms": total_atoms,
        "total_missing_residues": total_missing,
        "experimental_method": exp_method,
        "resolution": resolution,
        "alphafold_detection": af_info,
        "chains": chains_data,
        "unique_ligands": unique_ligands,
        "all_ligands": all_ligands,
        "all_metals": all_metals,
        "has_ligands": len(all_ligands) > 0,
        "is_oligomeric": len(chains_data) > 1,
    }

    # Write JSON
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{filepath.stem}_metadata.json"
    with open(json_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Print human-readable summary
    print_summary(metadata)

    return metadata


def print_summary(meta: dict):
    """Print human-readable summary to stdout."""
    print("=" * 60)
    print(f"STRUCTURE SUMMARY: {meta['file']}")
    print("=" * 60)
    print(f"Format:              {meta['format'].upper()}")
    print(f"Models:              {meta['num_models']}")
    print(f"Chains:              {meta['num_chains']}")
    print(f"Total residues:      {meta['total_residues']}")
    print(f"Total atoms:         {meta['total_atoms']}")

    if meta["total_missing_residues"] > 0:
        print(f"Missing residues:    {meta['total_missing_residues']} (from chain breaks)")

    if meta["experimental_method"]:
        print(f"Method:              {meta['experimental_method']}")
    if meta["resolution"] is not None:
        print(f"Resolution:          {meta['resolution']} Å")

    af = meta["alphafold_detection"]
    if af["is_predicted"]:
        print(f"Source:              AlphaFold prediction (pLDDT in B-factor)")
    else:
        print(f"Source:              Experimental")

    print(f"\n--- Chains ---")
    for ch in meta["chains"]:
        label = f"  Chain {ch['chain_id']}"
        print(f"{label}: {ch['num_residues']} residues, {ch['num_atoms']} atoms")
        if ch["bfactor_stats"]:
            bf = ch["bfactor_stats"]
            col = "pLDDT" if af["is_predicted"] else "B-factor"
            print(f"    {col}: mean={bf['mean']}, median={bf['median']}, "
                  f"range=[{bf['min']}, {bf['max']}]")
        if ch["ligands"]:
            lig_names = [l["resname"] for l in ch["ligands"]]
            print(f"    Ligands: {', '.join(lig_names)}")
        if ch["metals"]:
            met_names = [m["resname"] for m in ch["metals"]]
            print(f"    Metals: {', '.join(met_names)}")
        if ch["modified_residues"]:
            mods = [f"{m['resname']}{m['resid']}" for m in ch["modified_residues"]]
            print(f"    Modified residues: {', '.join(mods)}")
        if ch["chain_breaks"]:
            breaks = [f"{b['after_resid']}..{b['before_resid']} (gap={b['gap_size']})"
                      for b in ch["chain_breaks"]]
            print(f"    Chain breaks: {', '.join(breaks)}")

    if meta["unique_ligands"]:
        print(f"\n--- Ligands (non-solvent) ---")
        print(f"  {', '.join(meta['unique_ligands'])}")
    else:
        print(f"\nNo non-solvent ligands detected.")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Parse protein structure file.")
    parser.add_argument("structure_file", type=Path, help="Path to PDB or mmCIF file")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: same as input file)")
    args = parser.parse_args()

    output_dir = args.output_dir or args.structure_file.parent
    parse_structure(args.structure_file, output_dir)


if __name__ == "__main__":
    main()
