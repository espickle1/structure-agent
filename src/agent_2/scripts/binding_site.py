#!/usr/bin/env python3
"""
binding_site.py — Phase 1 standardized binding site and ligand interaction analysis.

Identifies all non-solvent HETATM groups as ligands, defines binding pockets via
KD-tree neighbor search, classifies interactions (H-bonds, salt bridges, hydrophobic
contacts, π-stacking), and computes pocket composition.

Usage:
    python binding_site.py <structure_file> [--output-dir <dir>] [--cutoff 5.0]
                           [--exclude-ligands HOH,SO4,GOL]

Exit codes:
    0 — success (including structures with no ligands — reports "no ligands found")
    1 — fatal error (file not found, parse failure)
"""

import argparse
import json
import sys
from pathlib import Path
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from Bio.PDB import PDBParser, MMCIFParser, NeighborSearch, Selection
    from Bio.PDB.Polypeptide import is_aa
    from cif_io import read_structure
except ImportError:
    print("ERROR: BioPython is required.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Default exclusion list — matches parse_structure.py
# ---------------------------------------------------------------------------
DEFAULT_EXCLUDED = {
    "HOH", "WAT", "H2O", "DOD",
    "NA", "CL", "K", "CA", "MG", "ZN", "FE", "MN", "CO", "CU", "NI", "CD",
    "SO4", "PO4", "NO3",
    "GOL", "EDO", "PEG", "PGE", "MPD", "DMS", "ACT", "FMT", "TRS", "CIT",
    "BME", "EOH", "IMD", "EPE", "MES", "IPA", "CAC",
    "HED", "TAR", "MLI", "BIG", "BCT",
    "UNX", "UNL", "UNK",
}

METAL_IONS = {
    "NA", "K", "CA", "MG", "ZN", "FE", "FE2", "MN", "CO", "CU", "CU1",
    "NI", "CD", "HG", "PT", "AU", "AG", "PB", "SR", "BA", "CS", "RB",
    "MO", "W", "V", "CR", "SE",
}

# Residue classification
HYDROPHOBIC_RESIDUES = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO"}
POLAR_RESIDUES = {"SER", "THR", "ASN", "GLN", "TYR", "CYS", "HIS"}
POSITIVE_RESIDUES = {"ARG", "LYS"}
NEGATIVE_RESIDUES = {"ASP", "GLU"}
AROMATIC_RESIDUES = {"PHE", "TYR", "TRP", "HIS"}

THREE_TO_ONE = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
    "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
    "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
    "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
}

# Interaction geometry thresholds (fixed Phase 1 parameters)
HBOND_DIST_CUTOFF = 3.5      # Å — donor/acceptor heavy atom distance
SALT_BRIDGE_CUTOFF = 4.0     # Å — charged group centroid distance
HYDROPHOBIC_CUTOFF = 4.5     # Å — carbon-carbon contact
PI_STACK_CUTOFF = 5.5        # Å — ring centroid distance
POCKET_CUTOFF = 5.0          # Å — default pocket definition radius


def detect_format(filepath: Path) -> str:
    ext = filepath.suffix.lower()
    if ext in (".cif", ".mmcif"):
        return "mmcif"
    return "pdb"


def load_structure(filepath: Path):
    fmt = detect_format(filepath)
    return read_structure(filepath.stem, filepath, fmt)


def find_ligands(model, excluded: set) -> list:
    """Find all non-excluded HETATM residues."""
    ligands = []
    for chain in model:
        for res in chain:
            hetflag = res.get_id()[0]
            resname = res.get_resname().strip()
            if hetflag.startswith("H") and resname not in excluded and resname not in METAL_IONS:
                ligands.append({
                    "residue": res,
                    "resname": resname,
                    "chain_id": chain.get_id(),
                    "resid": res.get_id()[1],
                    "num_atoms": len(list(res.get_atoms())),
                })
    return ligands


def get_pocket_residues(model, ligand_res, cutoff: float) -> list:
    """
    Find protein residues within cutoff of any ligand atom using KD-tree.
    Returns list of unique protein residues.
    """
    # Build atom list from protein residues only
    protein_atoms = []
    for chain in model:
        for res in chain:
            if is_aa(res, standard=True):
                for atom in res:
                    protein_atoms.append(atom)

    if not protein_atoms:
        return []

    ns = NeighborSearch(protein_atoms)

    # Search around each ligand atom
    pocket_residues = set()
    for atom in ligand_res.get_atoms():
        nearby = ns.search(atom.get_vector().get_array(), cutoff, level="R")
        for res in nearby:
            if is_aa(res, standard=True):
                pocket_residues.add(res)

    return sorted(pocket_residues, key=lambda r: (r.get_parent().get_id(), r.get_id()[1]))


def classify_residue(resname: str) -> str:
    """Classify residue by chemical property."""
    resname = resname.strip()
    if resname in HYDROPHOBIC_RESIDUES:
        return "hydrophobic"
    elif resname in POLAR_RESIDUES:
        return "polar"
    elif resname in POSITIVE_RESIDUES:
        return "positive"
    elif resname in NEGATIVE_RESIDUES:
        return "negative"
    elif resname == "GLY":
        return "glycine"
    return "other"


def compute_pocket_composition(pocket_residues: list) -> dict:
    """Compute pocket residue composition by chemical class."""
    classes = Counter()
    for res in pocket_residues:
        classes[classify_residue(res.get_resname())] += 1

    total = sum(classes.values())
    composition = {}
    for cls in ["hydrophobic", "polar", "positive", "negative", "glycine", "other"]:
        count = classes.get(cls, 0)
        composition[cls] = {
            "count": count,
            "fraction": round(count / total, 4) if total > 0 else 0,
        }
    composition["total_residues"] = total
    return composition


def detect_hbonds(ligand_res, pocket_residues: list) -> list:
    """
    Detect potential hydrogen bonds between ligand and pocket residues.
    Uses heavy-atom distance (N, O, S) as proxy — no explicit hydrogens needed.
    """
    hbond_donors_acceptors = {"N", "O", "S"}
    hbonds = []

    lig_atoms = [a for a in ligand_res.get_atoms()
                 if a.element.strip() in hbond_donors_acceptors]

    for res in pocket_residues:
        res_atoms = [a for a in res.get_atoms()
                     if a.element.strip() in hbond_donors_acceptors]
        for la in lig_atoms:
            for ra in res_atoms:
                dist = la - ra
                if dist <= HBOND_DIST_CUTOFF and dist > 0.5:
                    hbonds.append({
                        "ligand_atom": la.get_name(),
                        "protein_chain": res.get_parent().get_id(),
                        "protein_resname": res.get_resname().strip(),
                        "protein_resid": res.get_id()[1],
                        "protein_atom": ra.get_name(),
                        "distance": round(float(dist), 3),
                        "type": "hydrogen_bond",
                    })

    return hbonds


def detect_salt_bridges(ligand_res, pocket_residues: list) -> list:
    """Detect salt bridges between charged ligand atoms and charged residues."""
    bridges = []

    # Charged atoms in ligand (N+ and O- are common)
    lig_charged = [a for a in ligand_res.get_atoms()
                   if a.element.strip() in ("N", "O")]

    charged_residues = [r for r in pocket_residues
                        if r.get_resname().strip() in POSITIVE_RESIDUES | NEGATIVE_RESIDUES]

    for res in charged_residues:
        resname = res.get_resname().strip()
        # Get charged group atoms
        if resname in ("ASP", "GLU"):
            target_atoms = [a for a in res if a.get_name() in ("OD1", "OD2", "OE1", "OE2")]
        elif resname == "ARG":
            target_atoms = [a for a in res if a.get_name() in ("NH1", "NH2", "NE")]
        elif resname == "LYS":
            target_atoms = [a for a in res if a.get_name() == "NZ"]
        else:
            continue

        for la in lig_charged:
            for ta in target_atoms:
                dist = la - ta
                if dist <= SALT_BRIDGE_CUTOFF and dist > 0.5:
                    bridges.append({
                        "ligand_atom": la.get_name(),
                        "protein_chain": res.get_parent().get_id(),
                        "protein_resname": resname,
                        "protein_resid": res.get_id()[1],
                        "protein_atom": ta.get_name(),
                        "distance": round(float(dist), 3),
                        "type": "salt_bridge",
                    })

    return bridges


def detect_hydrophobic_contacts(ligand_res, pocket_residues: list) -> list:
    """Detect hydrophobic carbon-carbon contacts."""
    contacts = []

    lig_carbons = [a for a in ligand_res.get_atoms() if a.element.strip() == "C"]
    hydrophobic_res = [r for r in pocket_residues
                       if r.get_resname().strip() in HYDROPHOBIC_RESIDUES]

    for res in hydrophobic_res:
        res_carbons = [a for a in res if a.element.strip() == "C"]
        min_dist = float("inf")
        best_pair = None
        for lc in lig_carbons:
            for rc in res_carbons:
                dist = lc - rc
                if dist < min_dist:
                    min_dist = dist
                    best_pair = (lc, rc)

        if min_dist <= HYDROPHOBIC_CUTOFF and best_pair is not None:
            contacts.append({
                "ligand_atom": best_pair[0].get_name(),
                "protein_chain": res.get_parent().get_id(),
                "protein_resname": res.get_resname().strip(),
                "protein_resid": res.get_id()[1],
                "protein_atom": best_pair[1].get_name(),
                "distance": round(float(min_dist), 3),
                "type": "hydrophobic",
            })

    return contacts


def get_ring_centroid(residue, ring_atoms: list) -> np.ndarray | None:
    """Compute centroid of specified ring atoms."""
    coords = []
    for aname in ring_atoms:
        a = residue[aname] if residue.has_id(aname) else None
        if a is not None:
            coords.append(a.get_vector().get_array())
    if len(coords) < 3:
        return None
    return np.mean(coords, axis=0)


def detect_pi_stacking(ligand_res, pocket_residues: list) -> list:
    """Detect potential π-stacking between aromatic systems."""
    stacking = []

    aromatic_res = [r for r in pocket_residues
                    if r.get_resname().strip() in AROMATIC_RESIDUES]

    # Ring atom definitions for protein aromatic residues
    ring_defs = {
        "PHE": ["CG", "CD1", "CD2", "CE1", "CE2", "CZ"],
        "TYR": ["CG", "CD1", "CD2", "CE1", "CE2", "CZ"],
        "TRP": ["CG", "CD1", "CD2", "NE1", "CE2", "CE3", "CZ2", "CZ3", "CH2"],
        "HIS": ["CG", "ND1", "CD2", "CE1", "NE2"],
    }

    # Try to find aromatic atoms in ligand (any 5-6 membered ring with C/N)
    lig_coords = []
    for a in ligand_res.get_atoms():
        if a.element.strip() in ("C", "N"):
            lig_coords.append(a.get_vector().get_array())
    if len(lig_coords) < 5:
        return stacking
    lig_centroid = np.mean(lig_coords, axis=0)

    for res in aromatic_res:
        resname = res.get_resname().strip()
        if resname not in ring_defs:
            continue
        ring_centroid = get_ring_centroid(res, ring_defs[resname])
        if ring_centroid is None:
            continue

        dist = float(np.linalg.norm(lig_centroid - ring_centroid))
        if dist <= PI_STACK_CUTOFF:
            stacking.append({
                "protein_chain": res.get_parent().get_id(),
                "protein_resname": resname,
                "protein_resid": res.get_id()[1],
                "centroid_distance": round(dist, 3),
                "type": "pi_stacking",
            })

    return stacking


def analyze_binding_site(model, ligand_info: dict, cutoff: float) -> dict:
    """Complete binding site analysis for one ligand."""
    lig_res = ligand_info["residue"]

    # Find pocket residues
    pocket_residues = get_pocket_residues(model, lig_res, cutoff)

    if not pocket_residues:
        return {
            "ligand": ligand_info["resname"],
            "chain_id": ligand_info["chain_id"],
            "resid": ligand_info["resid"],
            "num_ligand_atoms": ligand_info["num_atoms"],
            "pocket_residues": [],
            "composition": {},
            "interactions": [],
            "warning": "No protein residues found within cutoff.",
        }

    # Pocket composition
    composition = compute_pocket_composition(pocket_residues)

    # Detect interactions
    hbonds = detect_hbonds(lig_res, pocket_residues)
    salt_bridges = detect_salt_bridges(lig_res, pocket_residues)
    hydrophobic = detect_hydrophobic_contacts(lig_res, pocket_residues)
    pi_stacking = detect_pi_stacking(lig_res, pocket_residues)

    all_interactions = hbonds + salt_bridges + hydrophobic + pi_stacking

    # Pocket residue details
    pocket_details = []
    for res in pocket_residues:
        resname = res.get_resname().strip()
        pocket_details.append({
            "chain_id": res.get_parent().get_id(),
            "resname": resname,
            "resid": res.get_id()[1],
            "one_letter": THREE_TO_ONE.get(resname, "X"),
            "classification": classify_residue(resname),
        })

    # Ligand B-factor statistics
    lig_bfactors = [a.get_bfactor() for a in lig_res.get_atoms()]
    lig_bf_stats = {}
    if lig_bfactors:
        lig_bf_stats = {
            "mean": round(float(np.mean(lig_bfactors)), 2),
            "max": round(float(np.max(lig_bfactors)), 2),
            "min": round(float(np.min(lig_bfactors)), 2),
        }

    # Interaction summary counts
    interaction_counts = Counter(i["type"] for i in all_interactions)

    return {
        "ligand": ligand_info["resname"],
        "chain_id": ligand_info["chain_id"],
        "resid": ligand_info["resid"],
        "num_ligand_atoms": ligand_info["num_atoms"],
        "pocket_cutoff": cutoff,
        "pocket_residues": pocket_details,
        "composition": composition,
        "interactions": all_interactions,
        "interaction_counts": dict(interaction_counts),
        "ligand_bfactor_stats": lig_bf_stats,
    }


def plot_interaction_summary(site_result: dict, output_dir: Path, stem: str):
    """Generate interaction summary plots for one binding site."""
    lig_name = site_result["ligand"]
    chain = site_result["chain_id"]
    resid = site_result["resid"]
    prefix = f"{stem}_{lig_name}_{chain}{resid}"

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # 1. Interaction type counts
    ax = axes[0]
    counts = site_result["interaction_counts"]
    if counts:
        types = list(counts.keys())
        vals = list(counts.values())
        colors = {"hydrogen_bond": "#4682B4", "salt_bridge": "#DC143C",
                  "hydrophobic": "#228B22", "pi_stacking": "#9370DB"}
        bar_colors = [colors.get(t, "#888888") for t in types]
        ax.barh(types, vals, color=bar_colors)
        ax.set_xlabel("Count")
        ax.set_title(f"Interactions: {lig_name}")
    else:
        ax.text(0.5, 0.5, "No interactions\ndetected", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title(f"Interactions: {lig_name}")

    # 2. Pocket composition pie chart
    ax = axes[1]
    comp = site_result["composition"]
    if comp and comp.get("total_residues", 0) > 0:
        labels = []
        sizes = []
        pie_colors = {
            "hydrophobic": "#228B22", "polar": "#4682B4",
            "positive": "#DC143C", "negative": "#FF6347",
            "glycine": "#FFD700", "other": "#888888",
        }
        c_list = []
        for cls in ["hydrophobic", "polar", "positive", "negative", "glycine", "other"]:
            if cls in comp and comp[cls]["count"] > 0:
                labels.append(f"{cls} ({comp[cls]['count']})")
                sizes.append(comp[cls]["count"])
                c_list.append(pie_colors.get(cls, "#888888"))
        ax.pie(sizes, labels=labels, colors=c_list, autopct="%1.0f%%", startangle=90)
        ax.set_title("Pocket composition")
    else:
        ax.text(0.5, 0.5, "Empty pocket", ha="center", va="center",
                transform=ax.transAxes)

    # 3. Distance distribution
    ax = axes[2]
    distances = [i["distance"] for i in site_result["interactions"]
                 if "distance" in i]
    if distances:
        ax.hist(distances, bins=15, color="steelblue", edgecolor="white", alpha=0.8)
        ax.set_xlabel("Distance (Å)")
        ax.set_ylabel("Count")
        ax.set_title("Interaction distance distribution")
    else:
        ax.text(0.5, 0.5, "No distances\nto plot", ha="center", va="center",
                transform=ax.transAxes)

    fig.suptitle(f"Binding site: {lig_name} (chain {chain}, res {resid})", fontsize=13)
    fig.tight_layout()
    plot_path = output_dir / f"{prefix}_summary.png"
    fig.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return plot_path.name


def write_pocket_csv(site_result: dict, output_dir: Path, stem: str) -> str:
    """Write pocket residues to CSV."""
    lig = site_result["ligand"]
    chain = site_result["chain_id"]
    resid = site_result["resid"]
    prefix = f"{stem}_{lig}_{chain}{resid}"
    csv_path = output_dir / f"{prefix}_pocket.csv"

    with open(csv_path, "w") as f:
        f.write("chain_id,resname,resid,one_letter,classification\n")
        for r in site_result["pocket_residues"]:
            f.write(f"{r['chain_id']},{r['resname']},{r['resid']},"
                    f"{r['one_letter']},{r['classification']}\n")
    return csv_path.name


def print_site_summary(site: dict):
    """Print human-readable binding site summary."""
    print(f"\n  Ligand: {site['ligand']} (chain {site['chain_id']}, "
          f"res {site['resid']}, {site['num_ligand_atoms']} atoms)")
    print(f"  Pocket cutoff: {site['pocket_cutoff']} Å")

    comp = site.get("composition", {})
    total = comp.get("total_residues", 0)
    print(f"  Pocket residues: {total}")

    if total > 0:
        parts = []
        for cls in ["hydrophobic", "polar", "positive", "negative", "glycine"]:
            if cls in comp and comp[cls]["count"] > 0:
                parts.append(f"{cls}={comp[cls]['count']} ({comp[cls]['fraction']:.0%})")
        print(f"    Composition: {', '.join(parts)}")

    counts = site.get("interaction_counts", {})
    if counts:
        parts = [f"{k}={v}" for k, v in counts.items()]
        print(f"  Interactions: {', '.join(parts)}")
    else:
        print(f"  Interactions: none detected")

    bf = site.get("ligand_bfactor_stats", {})
    if bf:
        print(f"  Ligand B-factors: mean={bf['mean']}, range=[{bf['min']}, {bf['max']}]")

    if site.get("warning"):
        print(f"  WARNING: {site['warning']}")


def main():
    parser = argparse.ArgumentParser(description="Binding site analysis.")
    parser.add_argument("structure_file", type=Path, help="PDB or mmCIF file")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--cutoff", type=float, default=POCKET_CUTOFF,
                        help=f"Pocket distance cutoff (default: {POCKET_CUTOFF} Å)")
    parser.add_argument("--exclude-ligands", type=str, default=None,
                        help="Comma-separated additional ligand names to exclude")
    args = parser.parse_args()

    filepath = args.structure_file
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir or filepath.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build exclusion set
    excluded = DEFAULT_EXCLUDED.copy()
    if args.exclude_ligands:
        for name in args.exclude_ligands.split(","):
            excluded.add(name.strip().upper())

    structure = load_structure(filepath)
    model = list(structure.get_models())[0]

    ligands = find_ligands(model, excluded)

    if not ligands:
        print("=" * 60)
        print(f"BINDING SITE ANALYSIS: {filepath.name}")
        print("=" * 60)
        print("No non-solvent ligands found.")

        result = {"file": filepath.name, "ligands_found": 0, "sites": []}
        json_path = output_dir / f"{filepath.stem}_binding_sites.json"
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results written to: {json_path}")
        return

    all_sites = []
    for lig_info in ligands:
        site = analyze_binding_site(model, lig_info, args.cutoff)

        # Generate outputs
        plot_name = plot_interaction_summary(site, output_dir, filepath.stem)
        csv_name = write_pocket_csv(site, output_dir, filepath.stem)
        site["summary_plot"] = plot_name
        site["pocket_csv"] = csv_name

        # Remove BioPython residue object before JSON serialization
        all_sites.append(site)

    # Write combined JSON (strip non-serializable fields)
    json_sites = []
    for s in all_sites:
        js = {k: v for k, v in s.items() if k != "residue"}
        json_sites.append(js)

    result = {
        "file": filepath.name,
        "ligands_found": len(ligands),
        "pocket_cutoff": args.cutoff,
        "excluded_hetresidues": sorted(excluded),
        "sites": json_sites,
    }

    json_path = output_dir / f"{filepath.stem}_binding_sites.json"
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Print summary
    print("=" * 60)
    print(f"BINDING SITE ANALYSIS: {filepath.name}")
    print("=" * 60)
    print(f"Ligands found: {len(ligands)}")
    for site in all_sites:
        print_site_summary(site)
    print(f"\nResults written to: {output_dir}")


if __name__ == "__main__":
    main()
