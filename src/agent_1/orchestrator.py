"""Agent 1 orchestrator — Agent 0 output → folded, confidence-annotated structures.

Reads Agent 0's ``cleaned.faa`` (and, optionally, its ``sidecar.jsonl`` for
metadata passthrough), fans folds across the deployed ESMFold2-Fast app on
Modal, annotates each fold with a confidence tier (NO rejection on quality —
only genuine fold failures are logged), and writes:

  <output_dir>/structures/<record_id>.cif   one CIF per folded record
  <output_dir>/structures.jsonl             StructureRecord per fold + Agent 0 passthrough
  <output_dir>/rejections.jsonl             FoldFailure per errored fold (logged, not escalated)

Deploy the fold app first:
    modal deploy src/agent_1/fold_app/modal_app.py

Then run from src/ (so the agent_1 package is importable):
    python -m agent_1.orchestrator \\
        --input-fasta /path/to/cleaned.faa \\
        [--sidecar /path/to/sidecar.jsonl] \\
        --output-dir /path/to/out/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import modal

from agent_1.shared import config
from agent_1.shared.schemas import (
    FoldFailure,
    StructureRecord,
    classify_confidence,
)


def read_fasta(path: Path) -> list[tuple[str, str]]:
    """Parse a (multi-record) FASTA. record_id = first whitespace token of header."""
    records: list[tuple[str, str]] = []
    rid: str | None = None
    seq: list[str] = []
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            if rid is not None:
                records.append((rid, "".join(seq)))
            rid = line[1:].strip().split()[0]
            seq = []
        elif line.strip():
            seq.append(line.strip())
    if rid is not None:
        records.append((rid, "".join(seq)))
    return records


def read_sidecar(path: Path) -> dict[str, dict]:
    """Read Agent 0's sidecar.jsonl into {record_id: record} for passthrough."""
    upstream: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        upstream[obj["record_id"]] = obj
    return upstream


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-fasta", required=True, type=Path)
    ap.add_argument("--sidecar", type=Path, default=None)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()

    records = read_fasta(args.input_fasta)
    upstream = read_sidecar(args.sidecar) if args.sidecar else {}
    seq_len = {rid: len(seq) for rid, seq in records}
    print(f"[agent1] {len(records)} sequences to fold")

    cif_dir = args.output_dir / config.OUTPUT_CIF_SUBDIR
    cif_dir.mkdir(parents=True, exist_ok=True)

    inference = modal.Cls.from_name(config.FOLD_APP_NAME, config.FOLD_CLASS_NAME)()
    requests = [{"record_id": rid, "aa_sequence": seq} for rid, seq in records]

    structures_path = args.output_dir / config.OUTPUT_STRUCTURES_NAME
    rejections_path = args.output_dir / config.OUTPUT_REJECTIONS_NAME
    n_ok = n_fail = 0

    with open(structures_path, "w") as sf, open(rejections_path, "w") as rf:
        for result in inference.fold.map(requests):
            rid = result["record_id"]
            up = upstream.get(rid, {})
            pid = up.get("parent_id", rid)

            if result.get("status") != "folded":
                fail = FoldFailure(
                    record_id=rid,
                    parent_id=pid,
                    stage="fold",
                    detail=result.get("detail", "unknown"),
                    upstream=up,
                )
                rf.write(json.dumps(fail.to_log_dict()) + "\n")
                n_fail += 1
                print(f"[agent1] FAILED {rid}: {result.get('detail')}")
                continue

            cif_rel = f"{config.OUTPUT_CIF_SUBDIR}/{rid}.cif"
            (args.output_dir / cif_rel).write_text(result["cif"])
            tier = classify_confidence(
                result["plddt_mean"], config.PLDDT_HIGH, config.PLDDT_MEDIUM
            )
            rec = StructureRecord(
                record_id=rid,
                parent_id=pid,
                cif_path=cif_rel,
                plddt_mean=round(result["plddt_mean"], 4),
                ptm=round(result["ptm"], 4),
                iptm=round(result["iptm"], 4),
                confidence_tier=tier,
                sequence_length=seq_len[rid],
                model=result["model"],
                model_revision=result.get("model_revision"),
                fold_params=result["fold_params"],
                upstream=up,
            )
            sf.write(json.dumps(rec.to_sidecar_dict()) + "\n")
            n_ok += 1
            print(f"[agent1] {rid}: pLDDT {result['plddt_mean']:.3f} ({tier.value})")

    print(f"[agent1] done: {n_ok} folded, {n_fail} failed → {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
