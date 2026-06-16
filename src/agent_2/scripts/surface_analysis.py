#!/usr/bin/env python3
"""
surface_analysis.py — Phase 1 standardized surface, secondary-structure, and shape analysis.

Computes:
  1. Per-residue SASA (solvent accessible surface area)
  2. Surface hydrophobicity mapping (Kyte-Doolittle)
  3. Surface charge distribution
  4. Secondary structure content and per-residue assignment
  5. Overall shape metrics (Rg, asphericity, principal axes)
  6. Surface topology — exposed clefts and protrusions

Usage:
    python surface_analysis.py <structure_file> [--output-dir <dir>]

Exit codes:
    0 — success
    1 — fatal error
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from Bio.PDB import MMCIFParser, PDBParser, NeighborSearch, PDBIO
    from Bio.PDB.DSSP import make_dssp_dict
    from Bio.PDB.Polypeptide import is_aa
    from Bio.PDB.ResidueDepth import get_surface
    from cif_io import read_structure
except ImportError:
    print("ERROR: BioPython is required.", file=sys.stderr)
    sys.exit(1)

THREE_TO_ONE = {
    "ALA":"A","CYS":"C","ASP":"D","GLU":"E","PHE":"F","GLY":"G","HIS":"H",
    "ILE":"I","LYS":"K","LEU":"L","MET":"M","ASN":"N","PRO":"P","GLN":"Q",
    "ARG":"R","SER":"S","THR":"T","VAL":"V","TRP":"W","TYR":"Y",
    "MSE":"M","SEC":"U","PYL":"O",
}

# Kyte-Doolittle hydrophobicity scale
KYTE_DOOLITTLE = {
    "ILE": 4.5, "VAL": 4.2, "LEU": 3.8, "PHE": 2.8, "CYS": 2.5,
    "MET": 1.9, "ALA": 1.8, "GLY": -0.4, "THR": -0.7, "SER": -0.8,
    "TRP": -0.9, "TYR": -1.3, "PRO": -1.6, "HIS": -3.2, "GLU": -3.5,
    "GLN": -3.5, "ASP": -3.5, "ASN": -3.5, "LYS": -3.9, "ARG": -4.5,
}

# Charge assignments at pH 7
CHARGE_MAP = {
    "ARG": +1, "LYS": +1, "HIS": +0.1,  # His partially protonated
    "ASP": -1, "GLU": -1,
}


def detect_format(filepath: Path) -> str:
    ext = filepath.suffix.lower()
    if ext in (".cif", ".mmcif"):
        return "mmcif"
    return "pdb"


def load_structure(filepath: Path):
    fmt = detect_format(filepath)
    return read_structure(filepath.stem, filepath, fmt), fmt


# =========================================================================
# SASA computation (Shrake-Rupley via BioPython)
# =========================================================================
def compute_sasa(structure):
    """Compute per-residue SASA using BioPython's ShrakeRupley."""
    from Bio.PDB.SASA import ShrakeRupley
    sr = ShrakeRupley()
    model = list(structure.get_models())[0]
    sr.compute(model, level="R")

    per_residue = []
    for chain in model:
        for res in chain:
            if not is_aa(res, standard=True):
                continue
            rn = res.get_resname().strip()
            rid = res.get_id()[1]
            sasa = round(res.sasa, 2) if hasattr(res, 'sasa') else 0
            per_residue.append({
                "chain_id": chain.get_id(),
                "resid": rid,
                "resname": rn,
                "one_letter": THREE_TO_ONE.get(rn, "X"),
                "sasa": sasa,
            })
    return per_residue


# Max SASA reference values (Gly-X-Gly tripeptide, Å²)
MAX_SASA = {
    "ALA": 129, "ARG": 274, "ASN": 195, "ASP": 193, "CYS": 167,
    "GLU": 223, "GLN": 225, "GLY": 104, "HIS": 224, "ILE": 197,
    "LEU": 201, "LYS": 236, "MET": 224, "PHE": 240, "PRO": 159,
    "SER": 155, "THR": 172, "TRP": 285, "TYR": 263, "VAL": 174,
}


def classify_exposure(sasa_data):
    """Add relative SASA and exposure classification."""
    for r in sasa_data:
        max_sasa = MAX_SASA.get(r["resname"], 200)
        rel_sasa = r["sasa"] / max_sasa if max_sasa > 0 else 0
        r["relative_sasa"] = round(rel_sasa, 4)
        if rel_sasa > 0.40:
            r["exposure"] = "exposed"
        elif rel_sasa > 0.15:
            r["exposure"] = "partial"
        else:
            r["exposure"] = "buried"
    return sasa_data


# =========================================================================
# Surface property mapping
# =========================================================================
def compute_surface_properties(sasa_data):
    """Compute surface hydrophobicity and charge from exposed residues."""
    for r in sasa_data:
        rn = r["resname"]
        r["hydrophobicity"] = KYTE_DOOLITTLE.get(rn, 0)
        r["charge"] = CHARGE_MAP.get(rn, 0)

    # Surface statistics (exposed residues only)
    exposed = [r for r in sasa_data if r["exposure"] == "exposed"]
    partial = [r for r in sasa_data if r["exposure"] == "partial"]
    buried = [r for r in sasa_data if r["exposure"] == "buried"]

    total = len(sasa_data)
    surface_hydro = [r["hydrophobicity"] for r in exposed]
    surface_charge = [r["charge"] for r in exposed]

    stats = {
        "total_residues": total,
        "exposed": {"count": len(exposed), "fraction": round(len(exposed)/total, 3)},
        "partial": {"count": len(partial), "fraction": round(len(partial)/total, 3)},
        "buried": {"count": len(buried), "fraction": round(len(buried)/total, 3)},
        "surface_hydrophobicity": {
            "mean": round(float(np.mean(surface_hydro)), 3) if surface_hydro else 0,
            "std": round(float(np.std(surface_hydro)), 3) if surface_hydro else 0,
        },
        "surface_net_charge": round(sum(surface_charge), 1) if surface_charge else 0,
        "surface_positive_residues": sum(1 for c in surface_charge if c > 0),
        "surface_negative_residues": sum(1 for c in surface_charge if c < 0),
        "total_sasa": round(sum(r["sasa"] for r in sasa_data), 1),
    }

    # Identify hydrophobic patches (contiguous exposed hydrophobic residues)
    hydrophobic_patches = []
    in_patch = False
    patch_start = None
    for i, r in enumerate(sasa_data):
        if r["exposure"] in ("exposed", "partial") and r["hydrophobicity"] > 1.5:
            if not in_patch:
                in_patch = True
                patch_start = i
        else:
            if in_patch and (i - patch_start) >= 3:
                hydrophobic_patches.append({
                    "start_resid": sasa_data[patch_start]["resid"],
                    "end_resid": sasa_data[i-1]["resid"],
                    "length": i - patch_start,
                    "mean_hydrophobicity": round(float(np.mean(
                        [sasa_data[k]["hydrophobicity"] for k in range(patch_start, i)]
                    )), 2),
                })
            in_patch = False
    if in_patch and (len(sasa_data) - patch_start) >= 3:
        hydrophobic_patches.append({
            "start_resid": sasa_data[patch_start]["resid"],
            "end_resid": sasa_data[-1]["resid"],
            "length": len(sasa_data) - patch_start,
            "mean_hydrophobicity": round(float(np.mean(
                [sasa_data[k]["hydrophobicity"] for k in range(patch_start, len(sasa_data))]
            )), 2),
        })

    # Charged clusters (3+ charged residues within 8 Å)
    stats["hydrophobic_patches"] = hydrophobic_patches
    return sasa_data, stats


# =========================================================================
# Secondary structure
# =========================================================================
def compute_secondary_structure(structure, filepath, fmt):
    """Compute per-residue secondary structure.

    Returns (assignments, content). `content` carries `source` and `reliable`:
    DSSP is the only path that yields trustworthy SS here. The mmCIF fallback in
    `extract_ss_from_file` does NOT parse SS records, so a DSSP failure on an
    mmCIF (e.g. an ESMFold2 / AlphaFold prediction) yields all-coil — which is
    not a measurement. Downstream consumers (fold-class interpretation, disorder
    gate) must not trust SS when `reliable` is False.
    """
    model = list(structure.get_models())[0]

    ss_assignments = []
    dssp_success = False

    # Try DSSP first. Two wrinkles with DSSP 4.x (mkdssp, libcifpp-based):
    #   1. It rebuilds its residue model from mmCIF polymer metadata that
    #      ESMFold2/AlphaFold coordinate-only CIFs omit, yielding 0 residues. So
    #      we hand it a PDB written from the already-loaded structure — ATOM
    #      records are self-contained and need no polymer metadata.
    #   2. It defaults to mmCIF output, which BioPython can't parse, so we force
    #      the legacy fixed-width format and read it with make_dssp_dict.
    # dssp_success is gated on ACTUAL assignments, never on a clean exit: a
    # silent 0-residue result must not read as a real measurement.
    try:
        mkdssp = shutil.which("mkdssp") or "mkdssp"
        tmpdir = tempfile.mkdtemp()
        pdb_in = os.path.join(tmpdir, "input.pdb")
        dssp_out = os.path.join(tmpdir, "out.dssp")
        try:
            io = PDBIO()
            io.set_structure(structure)
            io.save(pdb_in)
            # cifpp (DSSP 4.x) sniffs input by the first line: a HEADER record
            # marks it PDB, else mmCIF is assumed and parsing fails. PDBIO omits
            # HEADER, so prepend a minimal valid one.
            with open(pdb_in) as fh:
                body = fh.read()
            header = "HEADER    " + "PREDICTED MODEL".ljust(40) + "01-JAN-00" + "   " + "XXXX"
            with open(pdb_in, "w") as fh:
                fh.write(header + "\n" + body)
            subprocess.run(
                [mkdssp, "--output-format", "dssp", pdb_in, dssp_out],
                check=True, capture_output=True, text=True,
            )
            dssp_dict, _ = make_dssp_dict(dssp_out)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        for (chain_id, res_id), val in dssp_dict.items():
            ss = val[1]  # make_dssp_dict value layout: (aa, ss, acc, phi, psi, ...)
            rid = res_id[1]
            # Simplify DSSP codes: H,G,I -> H (helix), E,B -> E (sheet), rest -> C (coil)
            if ss in ("H", "G", "I"):
                ss_simple = "H"
            elif ss in ("E", "B"):
                ss_simple = "E"
            else:
                ss_simple = "C"
            ss_assignments.append({
                "chain_id": chain_id,
                "resid": rid,
                "dssp_code": ss,
                "ss_simple": ss_simple,
            })
        dssp_success = len(ss_assignments) > 0
    except Exception as e:
        print(f"  DSSP failed ({e}), falling back to file-level annotation", file=sys.stderr)

    # Fallback: extract from file records if DSSP fails
    if not dssp_success:
        ss_assignments = extract_ss_from_file(filepath, fmt, model)

    # Reliability. DSSP is trustworthy. The PDB-record fallback is trustworthy
    # only if it actually found helix/sheet; the mmCIF fallback never does, so
    # all-coil-without-DSSP is NOT a real measurement.
    found_ss = any(s["ss_simple"] in ("H", "E") for s in ss_assignments)
    if dssp_success:
        ss_source, reliable = "DSSP", True
    elif found_ss:
        ss_source, reliable = "file_records", True
    else:
        ss_source, reliable = "unavailable", False

    if not reliable:
        print(
            "  WARNING: secondary structure UNAVAILABLE (DSSP missing and no SS "
            "records parsed). All residues default to coil — this is NOT a real "
            "measurement. Fold-class interpretation and the disorder gate are UNRELIABLE "
            "for this structure; install DSSP (mkdssp) for valid SS.",
            file=sys.stderr,
        )

    # Compute content ratios
    if ss_assignments:
        codes = [s["ss_simple"] for s in ss_assignments]
        total = len(codes)
        helix_count = codes.count("H")
        sheet_count = codes.count("E")
        coil_count = codes.count("C")
        content = {
            "helix": {"count": helix_count, "fraction": round(helix_count/total, 3)},
            "sheet": {"count": sheet_count, "fraction": round(sheet_count/total, 3)},
            "coil": {"count": coil_count, "fraction": round(coil_count/total, 3)},
            "total_assigned": total,
        }
    else:
        content = {"helix": {"count": 0, "fraction": 0},
                   "sheet": {"count": 0, "fraction": 0},
                   "coil": {"count": 0, "fraction": 0}, "total_assigned": 0}

    content["source"] = ss_source
    content["reliable"] = reliable
    return ss_assignments, content


def extract_ss_from_file(filepath, fmt, model):
    """Extract secondary structure from PDB HELIX/SHEET or mmCIF records."""
    ss_ranges = []
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()

        if fmt == "pdb":
            for line in content.splitlines():
                if line.startswith("HELIX"):
                    chain = line[19].strip()
                    start = int(line[21:25].strip())
                    end = int(line[33:37].strip())
                    ss_ranges.append(("H", chain, start, end))
                elif line.startswith("SHEET"):
                    chain = line[21].strip()
                    start = int(line[22:26].strip())
                    end = int(line[33:37].strip())
                    ss_ranges.append(("E", chain, start, end))
        elif fmt == "mmcif":
            # Parse _struct_conf for helices and _struct_sheet_range for sheets
            for line in content.splitlines():
                if "_struct_conf." in line or "_struct_sheet_range." in line:
                    # Simplified mmCIF parsing — flag that file has SS records
                    pass
    except Exception:
        pass

    # Map ranges to per-residue assignments
    assignments = []
    for chain in model:
        for res in chain.get_residues():
            if not is_aa(res, standard=True):
                continue
            rid = res.get_id()[1]
            cid = chain.get_id()
            ss = "C"
            for ss_type, ss_chain, ss_start, ss_end in ss_ranges:
                if cid == ss_chain and ss_start <= rid <= ss_end:
                    ss = ss_type
                    break
            assignments.append({"chain_id": cid, "resid": rid, "dssp_code": ss, "ss_simple": ss})

    return assignments


# =========================================================================
# Shape metrics
# =========================================================================
def compute_shape_metrics(structure):
    """Compute radius of gyration, asphericity, and principal axes from Cα atoms."""
    model = list(structure.get_models())[0]

    ca_coords = []
    for chain in model:
        for res in chain.get_residues():
            if is_aa(res, standard=True) and res.has_id("CA"):
                ca_coords.append(res["CA"].get_vector().get_array())

    if len(ca_coords) < 10:
        return {"error": "Too few CA atoms for shape analysis"}

    coords = np.array(ca_coords)
    centroid = np.mean(coords, axis=0)
    centered = coords - centroid

    # Radius of gyration
    rg = float(np.sqrt(np.mean(np.sum(centered**2, axis=1))))

    # Inertia tensor → principal axes
    inertia = np.zeros((3, 3))
    for c in centered:
        inertia += np.outer(c, c)
    inertia /= len(centered)

    eigenvalues = np.sort(np.linalg.eigvalsh(inertia))[::-1]
    # Asphericity: 0 = perfect sphere, >0 = elongated
    trace = np.sum(eigenvalues)
    asphericity = 1.0 - 3.0 * (
        eigenvalues[0]*eigenvalues[1] +
        eigenvalues[1]*eigenvalues[2] +
        eigenvalues[0]*eigenvalues[2]
    ) / (trace**2) if trace > 0 else 0

    # Axis ratios
    ratio_1_2 = eigenvalues[0] / eigenvalues[1] if eigenvalues[1] > 0 else float("inf")
    ratio_1_3 = eigenvalues[0] / eigenvalues[2] if eigenvalues[2] > 0 else float("inf")

    # Dimensions: approximate extents along principal axes
    eigvecs = np.linalg.eigh(inertia)[1]
    projections = centered @ eigvecs
    extents = np.ptp(projections, axis=0)  # range along each axis
    extents = sorted(extents, reverse=True)

    # Shape classification
    if asphericity < 0.05:
        shape = "spherical/globular"
    elif asphericity < 0.15:
        shape = "roughly globular"
    elif ratio_1_2 < 1.5:
        shape = "oblate (disc-like)"
    else:
        shape = "prolate (elongated)"

    return {
        "radius_of_gyration": round(rg, 2),
        "asphericity": round(float(asphericity), 4),
        "principal_eigenvalues": [round(float(e), 2) for e in eigenvalues],
        "axis_ratios": {"long_mid": round(float(ratio_1_2), 2),
                        "long_short": round(float(ratio_1_3), 2)},
        "approximate_dimensions": {
            "long_axis": round(float(extents[0]), 1),
            "mid_axis": round(float(extents[1]), 1),
            "short_axis": round(float(extents[2]), 1),
            "unit": "Å",
        },
        "shape_classification": shape,
        "num_ca_atoms": len(ca_coords),
    }


# =========================================================================
# Plots
# =========================================================================
def plot_surface_profile(sasa_data, ss_assignments, output_dir, stem):
    """Multi-panel surface property profile."""
    resids = [r["resid"] for r in sasa_data]
    sasa_vals = [r["sasa"] for r in sasa_data]
    hydro_vals = [r["hydrophobicity"] for r in sasa_data]
    charge_vals = [r["charge"] for r in sasa_data]

    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

    # Panel 1: SASA
    ax = axes[0]
    exposure_colors = {"exposed": "#4682B4", "partial": "#87CEEB", "buried": "#D3D3D3"}
    colors = [exposure_colors.get(r["exposure"], "#888") for r in sasa_data]
    ax.bar(resids, sasa_vals, width=1.0, color=colors, edgecolor="none")
    ax.set_ylabel("SASA (Å²)", fontsize=10)
    ax.set_title(f"{stem} — Surface Analysis Profile", fontsize=13)
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(facecolor="#4682B4", label="Exposed (>40% relSASA)"),
        Patch(facecolor="#87CEEB", label="Partial (15-40%)"),
        Patch(facecolor="#D3D3D3", label="Buried (<15%)"),
    ], loc="upper right", fontsize=8)

    # Panel 2: Hydrophobicity
    ax = axes[1]
    hcolors = ["#228B22" if h > 0 else "#DC143C" for h in hydro_vals]
    ax.bar(resids, hydro_vals, width=1.0, color=hcolors, edgecolor="none", alpha=0.8)
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.set_ylabel("Hydrophobicity\n(Kyte-Doolittle)", fontsize=10)

    # Panel 3: Charge
    ax = axes[2]
    ccolors = ["#DC143C" if c > 0 else "#4682B4" if c < 0 else "#D3D3D3" for c in charge_vals]
    ax.bar(resids, charge_vals, width=1.0, color=ccolors, edgecolor="none", alpha=0.8)
    ax.set_ylabel("Charge (pH 7)", fontsize=10)
    ax.set_ylim(-1.3, 1.3)

    # Panel 4: Secondary structure strip
    ax = axes[3]
    ss_map = {s["resid"]: s["ss_simple"] for s in ss_assignments} if ss_assignments else {}
    ss_colors_map = {"H": "#FF6B6B", "E": "#4ECDC4", "C": "#F5F5DC"}
    ss_colors = [ss_colors_map.get(ss_map.get(rid, "C"), "#F5F5DC") for rid in resids]
    ax.bar(resids, [1]*len(resids), width=1.0, color=ss_colors, edgecolor="none")
    ax.set_ylim(0, 1.2)
    ax.set_yticks([])
    ax.set_ylabel("Secondary\nstructure", fontsize=10)
    ax.set_xlabel("Residue number", fontsize=10)
    ax.legend(handles=[
        Patch(facecolor="#FF6B6B", label="Helix"),
        Patch(facecolor="#4ECDC4", label="Sheet"),
        Patch(facecolor="#F5F5DC", label="Coil/loop"),
    ], loc="upper right", fontsize=8)

    fig.tight_layout()
    plot_path = output_dir / f"{stem}_surface_profile.png"
    fig.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return plot_path.name


def plot_exposure_pie(stats, output_dir, stem):
    """Pie chart of surface exposure distribution."""
    fig, ax = plt.subplots(figsize=(5, 5))
    labels = ["Exposed", "Partial", "Buried"]
    sizes = [stats["exposed"]["count"], stats["partial"]["count"], stats["buried"]["count"]]
    colors = ["#4682B4", "#87CEEB", "#D3D3D3"]
    ax.pie(sizes, labels=[f"{l} ({s})" for l, s in zip(labels, sizes)],
           colors=colors, autopct="%1.0f%%", startangle=90)
    ax.set_title("Residue Exposure Distribution")
    fig.tight_layout()
    plot_path = output_dir / f"{stem}_exposure_pie.png"
    fig.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return plot_path.name


# =========================================================================
# Printing
# =========================================================================
def print_summary(shape, ss_content, surface_stats):
    """Print human-readable summary."""
    print("\n--- Overall Shape ---")
    print(f"  Classification: {shape['shape_classification']}")
    print(f"  Radius of gyration: {shape['radius_of_gyration']} Å")
    print(f"  Asphericity: {shape['asphericity']}")
    dims = shape["approximate_dimensions"]
    print(f"  Approximate dimensions: {dims['long_axis']} × {dims['mid_axis']} × {dims['short_axis']} Å")

    print(f"\n--- Secondary Structure ---")
    print(f"  Helix: {ss_content['helix']['count']} residues ({ss_content['helix']['fraction']:.0%})")
    print(f"  Sheet: {ss_content['sheet']['count']} residues ({ss_content['sheet']['fraction']:.0%})")
    print(f"  Coil:  {ss_content['coil']['count']} residues ({ss_content['coil']['fraction']:.0%})")

    print(f"\n--- Surface Properties ---")
    print(f"  Total SASA: {surface_stats['total_sasa']} Å²")
    print(f"  Exposed: {surface_stats['exposed']['count']} ({surface_stats['exposed']['fraction']:.0%}), "
          f"Partial: {surface_stats['partial']['count']} ({surface_stats['partial']['fraction']:.0%}), "
          f"Buried: {surface_stats['buried']['count']} ({surface_stats['buried']['fraction']:.0%})")
    print(f"  Surface hydrophobicity (mean): {surface_stats['surface_hydrophobicity']['mean']}")
    print(f"  Surface net charge: {surface_stats['surface_net_charge']}")
    print(f"  Exposed positive residues: {surface_stats['surface_positive_residues']}")
    print(f"  Exposed negative residues: {surface_stats['surface_negative_residues']}")
    if surface_stats["hydrophobic_patches"]:
        print(f"  Hydrophobic patches ({len(surface_stats['hydrophobic_patches'])}):")
        for p in surface_stats["hydrophobic_patches"]:
            print(f"    Residues {p['start_resid']}–{p['end_resid']} "
                  f"({p['length']} res, mean hydro={p['mean_hydrophobicity']})")


# =========================================================================
# Main
# =========================================================================
def main():
    parser = argparse.ArgumentParser(description="Surface, secondary-structure, and shape analysis.")
    parser.add_argument("structure_file", type=Path, help="PDB or mmCIF file")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    filepath = args.structure_file
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir or filepath.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = filepath.stem

    print("=" * 60)
    print(f"SURFACE & FOLD ANALYSIS: {filepath.name}")
    print("=" * 60)

    structure, fmt = load_structure(filepath)

    # 1. SASA
    print("\nComputing SASA...")
    sasa_data = compute_sasa(structure)
    sasa_data = classify_exposure(sasa_data)

    # 2. Surface properties
    sasa_data, surface_stats = compute_surface_properties(sasa_data)

    # 3. Secondary structure
    print("Computing secondary structure...")
    # Reload structure for DSSP (it needs unmodified coords)
    structure2, _ = load_structure(filepath)
    ss_assignments, ss_content = compute_secondary_structure(structure2, filepath, fmt)

    # 4. Shape metrics
    print("Computing shape metrics...")
    structure3, _ = load_structure(filepath)
    shape = compute_shape_metrics(structure3)

    # Print summary
    print_summary(shape, ss_content, surface_stats)

    # 5. Plots
    print("\nGenerating plots...")
    profile_plot = plot_surface_profile(sasa_data, ss_assignments, output_dir, stem)
    exposure_plot = plot_exposure_pie(surface_stats, output_dir, stem)

    # 6. Write outputs
    # Per-residue CSV
    csv_path = output_dir / f"{stem}_surface.csv"
    with open(csv_path, "w") as f:
        f.write("resid,resname,one_letter,sasa,relative_sasa,exposure,hydrophobicity,charge,ss\n")
        ss_map = {s["resid"]: s["ss_simple"] for s in ss_assignments}
        for r in sasa_data:
            ss = ss_map.get(r["resid"], "C")
            f.write(f"{r['resid']},{r['resname']},{r['one_letter']},"
                    f"{r['sasa']},{r['relative_sasa']},{r['exposure']},"
                    f"{r['hydrophobicity']},{r['charge']},{ss}\n")

    # Combined JSON
    result = {
        "file": filepath.name,
        "shape": shape,
        "secondary_structure_content": ss_content,
        "surface_stats": surface_stats,
        "plots": {"surface_profile": profile_plot, "exposure_pie": exposure_plot},
        "surface_csv": csv_path.name,
    }

    json_path = output_dir / f"{stem}_surface_analysis.json"
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"\nResults written to: {output_dir}")


if __name__ == "__main__":
    main()
