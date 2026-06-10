#!/usr/bin/env python3
"""
compare_structures.py — Phase 1 standardized multi-structure comparison.

Compares one or more query structures against a reference structure.
All comparisons are reference-vs-query (not all-vs-all).

Chain matching is by sequence length: chains are paired greedily by closest
length (within 5% tolerance). Ties broken by sequence identity. Unmatched
chains are flagged as absent.

Produces per comparison:
  - Global Cα RMSD and core RMSD (excluding high-deviation regions)
  - Per-residue Cα deviation CSV
  - Deviation profile plot (PNG, 300 DPI)
  - B-factor/pLDDT comparison plot (PNG, 300 DPI)
  - Combined JSON with all statistics

Usage:
    python compare_structures.py <reference> <query1> [query2 ...] [--output-dir <dir>]

Exit codes:
    0 — success
    1 — fatal error
"""

import argparse
import json
import sys
from pathlib import Path
from itertools import product as iter_product

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from Bio.PDB import PDBParser, MMCIFParser, Superimposer
    from Bio.PDB.Polypeptide import is_aa
    from cif_io import read_structure
except ImportError:
    print("ERROR: BioPython is required.", file=sys.stderr)
    sys.exit(1)


THREE_TO_ONE = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
    "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
    "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
    "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
    "MSE": "M", "SEC": "U", "PYL": "O",
}

DEVIATION_THRESHOLD = 2.0  # Å — defines "high-deviation" regions


def detect_format(filepath: Path) -> str:
    ext = filepath.suffix.lower()
    if ext in (".cif", ".mmcif"):
        return "mmcif"
    return "pdb"


def load_structure(filepath: Path):
    fmt = detect_format(filepath)
    return read_structure(filepath.stem, filepath, fmt)


def get_chain_info(model) -> list[dict]:
    """Extract chain ID, sequence, length, and Cα atoms for each chain."""
    chains = []
    for chain in model:
        aa_residues = [r for r in chain.get_residues() if is_aa(r, standard=True)]
        if not aa_residues:
            continue
        seq = ""
        ca_atoms = []
        residue_ids = []
        bfactors = []
        for r in aa_residues:
            rn = r.get_resname().strip()
            seq += THREE_TO_ONE.get(rn, "X")
            ca = r["CA"] if r.has_id("CA") else None
            ca_atoms.append(ca)
            residue_ids.append(r.get_id()[1])
            if ca is not None:
                bfactors.append(ca.get_bfactor())
            else:
                bfactors.append(np.nan)
        chains.append({
            "chain_id": chain.get_id(),
            "sequence": seq,
            "length": len(seq),
            "ca_atoms": ca_atoms,
            "residue_ids": residue_ids,
            "bfactors": np.array(bfactors),
        })
    return chains


def sequence_identity(seq1: str, seq2: str) -> float:
    """Simple identity score between equal-length sequences."""
    if len(seq1) != len(seq2):
        min_len = min(len(seq1), len(seq2))
        seq1 = seq1[:min_len]
        seq2 = seq2[:min_len]
    if not seq1:
        return 0.0
    matches = sum(1 for a, b in zip(seq1, seq2) if a == b)
    return matches / len(seq1)


def match_chains(ref_chains: list[dict], query_chains: list[dict],
                 length_tolerance: float = 0.05) -> list[dict]:
    """
    Match chains by sequence length, greedily. Ties broken by sequence identity.
    Returns list of dicts with ref_chain, query_chain, and match quality.
    """
    matches = []
    used_query = set()

    # Sort ref chains by length (descending) for greedy matching
    ref_sorted = sorted(ref_chains, key=lambda c: c["length"], reverse=True)

    for ref_ch in ref_sorted:
        best_match = None
        best_score = -1

        for i, q_ch in enumerate(query_chains):
            if i in used_query:
                continue
            # Length tolerance check
            max_len = max(ref_ch["length"], q_ch["length"])
            if max_len == 0:
                continue
            length_diff = abs(ref_ch["length"] - q_ch["length"]) / max_len
            if length_diff > length_tolerance:
                continue
            # Score by sequence identity
            score = sequence_identity(ref_ch["sequence"], q_ch["sequence"])
            if score > best_score:
                best_score = score
                best_match = i

        if best_match is not None:
            used_query.add(best_match)
            matches.append({
                "ref_chain_id": ref_ch["chain_id"],
                "query_chain_id": query_chains[best_match]["chain_id"],
                "ref_chain": ref_ch,
                "query_chain": query_chains[best_match],
                "sequence_identity": round(best_score, 4),
                "ref_length": ref_ch["length"],
                "query_length": query_chains[best_match]["length"],
            })
        else:
            matches.append({
                "ref_chain_id": ref_ch["chain_id"],
                "query_chain_id": None,
                "ref_chain": ref_ch,
                "query_chain": None,
                "sequence_identity": None,
                "ref_length": ref_ch["length"],
                "query_length": None,
                "status": "unmatched_in_query",
            })

    # Report query chains not matched to any reference chain
    for i, q_ch in enumerate(query_chains):
        if i not in used_query:
            matches.append({
                "ref_chain_id": None,
                "query_chain_id": q_ch["chain_id"],
                "ref_chain": None,
                "query_chain": q_ch,
                "sequence_identity": None,
                "ref_length": None,
                "query_length": q_ch["length"],
                "status": "absent_in_reference",
            })

    return matches


def superpose_chains(ref_chain: dict, query_chain: dict) -> dict:
    """
    Superpose query onto reference using paired Cα atoms.
    Returns RMSD statistics and per-residue deviations.
    """
    ref_cas = ref_chain["ca_atoms"]
    query_cas = query_chain["ca_atoms"]

    # Pair by position (both should be similar length after matching)
    min_len = min(len(ref_cas), len(query_cas))
    ref_paired = []
    query_paired = []
    paired_resids = []

    for i in range(min_len):
        if ref_cas[i] is not None and query_cas[i] is not None:
            ref_paired.append(ref_cas[i])
            query_paired.append(query_cas[i])
            paired_resids.append(ref_chain["residue_ids"][i])

    if len(ref_paired) < 3:
        return {
            "error": "Fewer than 3 paired Cα atoms — cannot superpose.",
            "num_paired": len(ref_paired),
        }

    # SVD superposition
    sup = Superimposer()
    sup.set_atoms(ref_paired, query_paired)
    sup.apply([a.get_parent().get_parent() for a in query_paired])

    # Per-residue Cα deviation
    deviations = []
    for ref_a, query_a, resid in zip(ref_paired, query_paired, paired_resids):
        dist = ref_a - query_a
        deviations.append({
            "resid": resid,
            "deviation": round(float(dist), 4),
        })

    dev_values = np.array([d["deviation"] for d in deviations])

    # Global RMSD
    global_rmsd = float(np.sqrt(np.mean(dev_values ** 2)))

    # Core RMSD (excluding residues > threshold)
    core_mask = dev_values <= DEVIATION_THRESHOLD
    if np.sum(core_mask) >= 3:
        core_rmsd = float(np.sqrt(np.mean(dev_values[core_mask] ** 2)))
        core_fraction = float(np.sum(core_mask) / len(dev_values))
    else:
        core_rmsd = None
        core_fraction = None

    # Detect high-deviation regions (contiguous stretches)
    high_dev_regions = []
    in_region = False
    region_start = None
    for i, d in enumerate(deviations):
        if d["deviation"] > DEVIATION_THRESHOLD:
            if not in_region:
                in_region = True
                region_start = i
        else:
            if in_region:
                high_dev_regions.append({
                    "start_resid": deviations[region_start]["resid"],
                    "end_resid": deviations[i - 1]["resid"],
                    "length": i - region_start,
                    "max_deviation": round(float(max(
                        deviations[k]["deviation"] for k in range(region_start, i)
                    )), 4),
                })
                in_region = False
    if in_region:
        high_dev_regions.append({
            "start_resid": deviations[region_start]["resid"],
            "end_resid": deviations[-1]["resid"],
            "length": len(deviations) - region_start,
            "max_deviation": round(float(max(
                deviations[k]["deviation"] for k in range(region_start, len(deviations))
            )), 4),
        })

    return {
        "num_paired_residues": len(ref_paired),
        "global_rmsd": round(global_rmsd, 4),
        "core_rmsd": round(core_rmsd, 4) if core_rmsd is not None else None,
        "core_fraction": round(core_fraction, 4) if core_fraction is not None else None,
        "deviation_threshold": DEVIATION_THRESHOLD,
        "per_residue_deviations": deviations,
        "high_deviation_regions": high_dev_regions,
        "deviation_stats": {
            "mean": round(float(np.mean(dev_values)), 4),
            "median": round(float(np.median(dev_values)), 4),
            "max": round(float(np.max(dev_values)), 4),
            "std": round(float(np.std(dev_values)), 4),
        },
    }


def plot_deviation_profile(deviations: list, ref_name: str, query_name: str,
                           chain_id: str, output_path: Path):
    """Plot per-residue Cα deviation after superposition."""
    resids = [d["resid"] for d in deviations]
    devs = [d["deviation"] for d in deviations]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(resids, devs, width=1.0, color="steelblue", edgecolor="none", alpha=0.8)
    ax.axhline(y=DEVIATION_THRESHOLD, color="red", linestyle="--", linewidth=1,
               label=f"Threshold ({DEVIATION_THRESHOLD} Å)")
    ax.set_xlabel("Residue number")
    ax.set_ylabel("Cα deviation (Å)")
    ax.set_title(f"Per-residue deviation: {ref_name} vs {query_name} (chain {chain_id})")
    ax.legend()
    ax.set_xlim(min(resids) - 1, max(resids) + 1)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_bfactor_comparison(ref_chain: dict, query_chain: dict,
                            ref_name: str, query_name: str,
                            chain_id: str, output_path: Path,
                            is_predicted: bool = False):
    """Plot B-factor / pLDDT comparison between structures."""
    min_len = min(len(ref_chain["residue_ids"]), len(query_chain["residue_ids"]))
    resids = ref_chain["residue_ids"][:min_len]
    ref_bf = ref_chain["bfactors"][:min_len]
    query_bf = query_chain["bfactors"][:min_len]

    ylabel = "pLDDT" if is_predicted else "B-factor (Å²)"

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(resids, ref_bf, color="steelblue", linewidth=0.8, alpha=0.8,
            label=f"{ref_name}")
    ax.plot(resids, query_bf, color="coral", linewidth=0.8, alpha=0.8,
            label=f"{query_name}")
    ax.set_xlabel("Residue number")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{ylabel} comparison: chain {chain_id}")
    ax.legend()
    ax.set_xlim(min(resids) - 1, max(resids) + 1)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_deviation_csv(deviations: list, output_path: Path):
    """Write per-residue deviations to CSV."""
    with open(output_path, "w") as f:
        f.write("resid,deviation_angstrom\n")
        for d in deviations:
            f.write(f"{d['resid']},{d['deviation']}\n")


def compare_pair(ref_structure, query_structure, ref_path: Path, query_path: Path,
                 output_dir: Path) -> dict:
    """Compare a single reference-query pair."""
    ref_model = list(ref_structure.get_models())[0]
    query_model = list(query_structure.get_models())[0]

    ref_chains = get_chain_info(ref_model)
    query_chains = get_chain_info(query_model)

    chain_matches = match_chains(ref_chains, query_chains)

    # Determine if structures are AlphaFold predictions (heuristic: check B-factor range)
    all_bf = []
    for ch in ref_chains:
        all_bf.extend(ch["bfactors"][~np.isnan(ch["bfactors"])].tolist())
    is_predicted = (len(all_bf) > 0 and all(0 <= b <= 100 for b in all_bf)
                    and np.median(all_bf) > 50)

    comparison_results = {
        "reference": ref_path.name,
        "query": query_path.name,
        "chain_matching": [],
        "superpositions": [],
    }

    for match in chain_matches:
        match_summary = {
            "ref_chain_id": match["ref_chain_id"],
            "query_chain_id": match["query_chain_id"],
            "sequence_identity": match["sequence_identity"],
            "ref_length": match["ref_length"],
            "query_length": match["query_length"],
        }
        if "status" in match:
            match_summary["status"] = match["status"]
        comparison_results["chain_matching"].append(match_summary)

        # Skip if no match
        if match["query_chain"] is None or match["ref_chain"] is None:
            continue

        chain_id = match["ref_chain_id"]
        sup_result = superpose_chains(match["ref_chain"], match["query_chain"])

        if "error" in sup_result:
            comparison_results["superpositions"].append({
                "chain_id": chain_id,
                "error": sup_result["error"],
            })
            continue

        # Save per-residue CSV
        csv_name = f"{ref_path.stem}_vs_{query_path.stem}_chain{chain_id}_deviations.csv"
        write_deviation_csv(sup_result["per_residue_deviations"], output_dir / csv_name)

        # Plot deviation profile
        plot_name = f"{ref_path.stem}_vs_{query_path.stem}_chain{chain_id}_deviation.png"
        plot_deviation_profile(
            sup_result["per_residue_deviations"],
            ref_path.stem, query_path.stem, chain_id,
            output_dir / plot_name,
        )

        # Plot B-factor comparison
        bf_plot_name = f"{ref_path.stem}_vs_{query_path.stem}_chain{chain_id}_bfactor.png"
        plot_bfactor_comparison(
            match["ref_chain"], match["query_chain"],
            ref_path.stem, query_path.stem, chain_id,
            output_dir / bf_plot_name,
            is_predicted=is_predicted,
        )

        # Store result (without full per-residue array in summary)
        sup_summary = {k: v for k, v in sup_result.items()
                       if k != "per_residue_deviations"}
        sup_summary["chain_id"] = chain_id
        sup_summary["deviation_csv"] = csv_name
        sup_summary["deviation_plot"] = plot_name
        sup_summary["bfactor_plot"] = bf_plot_name
        comparison_results["superpositions"].append(sup_summary)

    return comparison_results


def print_comparison_summary(results: list[dict]):
    """Print human-readable comparison summary."""
    for comp in results:
        print("=" * 60)
        print(f"COMPARISON: {comp['reference']} vs {comp['query']}")
        print("=" * 60)

        print("\nChain matching:")
        for m in comp["chain_matching"]:
            if m.get("status") == "unmatched_in_query":
                print(f"  Ref chain {m['ref_chain_id']} ({m['ref_length']} res) — "
                      f"NO MATCH in query")
            elif m.get("status") == "absent_in_reference":
                print(f"  Query chain {m['query_chain_id']} ({m['query_length']} res) — "
                      f"ABSENT in reference")
            else:
                print(f"  Ref chain {m['ref_chain_id']} ({m['ref_length']} res) ↔ "
                      f"Query chain {m['query_chain_id']} ({m['query_length']} res) — "
                      f"identity={m['sequence_identity']:.1%}")

        for sup in comp["superpositions"]:
            if "error" in sup:
                print(f"\n  Chain {sup['chain_id']}: {sup['error']}")
                continue
            print(f"\n  Chain {sup['chain_id']}:")
            print(f"    Paired residues:  {sup['num_paired_residues']}")
            print(f"    Global RMSD:      {sup['global_rmsd']:.3f} Å")
            if sup["core_rmsd"] is not None:
                print(f"    Core RMSD:        {sup['core_rmsd']:.3f} Å "
                      f"({sup['core_fraction']:.0%} of residues)")
            print(f"    Max deviation:    {sup['deviation_stats']['max']:.3f} Å")
            if sup["high_deviation_regions"]:
                print(f"    High-deviation regions (>{DEVIATION_THRESHOLD} Å):")
                for r in sup["high_deviation_regions"]:
                    print(f"      Residues {r['start_resid']}–{r['end_resid']} "
                          f"({r['length']} res, max={r['max_deviation']:.2f} Å)")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Compare protein structures against a reference.")
    parser.add_argument("reference", type=Path,
                        help="Reference structure file (PDB or mmCIF)")
    parser.add_argument("queries", type=Path, nargs="+",
                        help="One or more query structure files")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: reference file directory)")
    args = parser.parse_args()

    output_dir = args.output_dir or args.reference.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate inputs
    for f in [args.reference] + args.queries:
        if not f.exists():
            print(f"ERROR: File not found: {f}", file=sys.stderr)
            sys.exit(1)

    ref_structure = load_structure(args.reference)

    all_results = []
    for query_path in args.queries:
        query_structure = load_structure(query_path)
        result = compare_pair(ref_structure, query_structure,
                              args.reference, query_path, output_dir)
        all_results.append(result)

    # Write combined JSON
    json_path = output_dir / f"{args.reference.stem}_comparisons.json"
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print_comparison_summary(all_results)
    print(f"Results written to: {output_dir}")


if __name__ == "__main__":
    main()
