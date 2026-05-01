"""Agent 0 orchestrator. Entry point for batch processing.

Reads a FASTA file, optionally with per-record client metadata, fans out
through fast_app, routes ambiguous records to slow_app with the genetic
code cascade, and writes:
    <output_dir>/cleaned.faa        — AA FASTA for Agent 1
    <output_dir>/sidecar.jsonl      — per-record provenance (handoff schema)
    <output_dir>/rejections.jsonl   — audit log of all rejections

Usage:
    python -m agent0.orchestrator \\
        --input /path/to/input.fasta \\
        --output-dir /path/to/output \\
        [--client-metadata /path/to/metadata.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import modal

from agent0.fast_app.ingest import parse_fasta
from agent0.shared.config import (
    DEFAULT_GENETIC_CODE,
    FALLBACK_GENETIC_CODES,
    OUTPUT_FASTA_NAME,
    OUTPUT_REJECTIONS_NAME,
    OUTPUT_SIDECAR_NAME,
)
from agent0.shared.schemas import InputRecord


def _load_client_metadata(path: Path | None) -> dict[str, dict]:
    """Optional per-record metadata, keyed by record_id."""
    if path is None:
        return {}
    with path.open() as f:
        return json.load(f)


def _attach_metadata(records: list[InputRecord], metadata: dict[str, dict]) -> list[InputRecord]:
    if not metadata:
        return records
    out = []
    for r in records:
        # Try full description, then first whitespace-delimited token.
        meta = metadata.get(r.record_id) or metadata.get(r.record_id.split()[0], {})
        out.append(InputRecord(
            record_id=r.record_id,
            sequence=r.sequence,
            client_metadata=meta,
        ))
    return out


def _write_fasta(path: Path, records: list[dict]) -> None:
    """Write cleaned AA FASTA."""
    with path.open("w") as f:
        for r in records:
            f.write(f">{r['record_id']}\n")
            seq = r["aa_sequence"]
            # 60-char wrap.
            for i in range(0, len(seq), 60):
                f.write(seq[i : i + 60] + "\n")


def _write_jsonl(path: Path, items: list[dict]) -> None:
    with path.open("w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")


def run(input_path: Path, output_dir: Path, metadata_path: Path | None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Parse + attach metadata.
    raw = list(parse_fasta(input_path))
    metadata = _load_client_metadata(metadata_path)
    inputs = _attach_metadata(raw, metadata)
    print(f"[orchestrator] loaded {len(inputs)} records", file=sys.stderr)

    # 2. Fast-path fanout. Look up the deployed function by app+name.
    process_record = modal.Function.from_name("agent0-fast", "process_record")
    fast_results = list(
        process_record.map([asdict(r) for r in inputs])
    )

    translated: list[dict] = []
    rejections: list[dict] = []
    slow_payloads: list[dict] = []

    for res in fast_results:
        kind = res["kind"]
        if kind == "translated":
            translated.append(res["payload"])
        elif kind == "rejected":
            rejections.append(res["payload"])
        elif kind == "slow_needed":
            slow_payloads.append(res["payload"])
        else:
            raise RuntimeError(f"unexpected fast-path verdict: {kind}")

    print(
        f"[orchestrator] fast-path: {len(translated)} translated, "
        f"{len(slow_payloads)} → slow path, {len(rejections)} rejected",
        file=sys.stderr,
    )

    # 3. Slow-path with code cascade. The cascade runs *inside* each container
    # so ESM-2 loads once per worker.
    if slow_payloads:
        SlowPathWorker = modal.Cls.from_name("agent0-slow", "SlowPathWorker")
        worker = SlowPathWorker()
        code_cascade = [DEFAULT_GENETIC_CODE, *FALLBACK_GENETIC_CODES]

        # .map over payloads; code_cascade is a constant kwarg on every call.
        slow_results = list(
            worker.process_with_cascade.map(
                slow_payloads,
                kwargs={"code_cascade": code_cascade},
            )
        )

        n_resolved = sum(1 for r in slow_results if "translated" in r["kind"])
        n_rejected = sum(1 for r in slow_results if r["kind"] == "rejected")
        for res in slow_results:
            kind = res["kind"]
            if kind in ("translated_single", "translated_multi"):
                translated.extend(res["payload"])
            elif kind == "rejected":
                rejections.append(res["payload"])
            else:
                raise RuntimeError(f"unexpected slow-path verdict: {kind}")

        print(
            f"[orchestrator] slow-path: {n_resolved} resolved, {n_rejected} rejected",
            file=sys.stderr,
        )

    # 4. Emit outputs.
    fasta_path = output_dir / OUTPUT_FASTA_NAME
    sidecar_path = output_dir / OUTPUT_SIDECAR_NAME
    rejections_path = output_dir / OUTPUT_REJECTIONS_NAME

    _write_fasta(fasta_path, translated)
    _write_jsonl(sidecar_path, translated)
    _write_jsonl(rejections_path, rejections)

    print(
        f"[orchestrator] wrote {len(translated)} AA records to {fasta_path}",
        file=sys.stderr,
    )
    print(
        f"[orchestrator] wrote {len(rejections)} rejections to {rejections_path}",
        file=sys.stderr,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Agent 0 orchestrator")
    p.add_argument("--input", required=True, type=Path,
                   help="Path to input FASTA (DNA, RNA, or protein).")
    p.add_argument("--output-dir", required=True, type=Path,
                   help="Directory for cleaned.faa, sidecar.jsonl, rejections.jsonl.")
    p.add_argument("--client-metadata", type=Path, default=None,
                   help="Optional JSON dict {record_id: metadata_dict}.")
    args = p.parse_args()
    run(args.input, args.output_dir, args.client_metadata)


if __name__ == "__main__":
    main()
