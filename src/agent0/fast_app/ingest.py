"""FASTA ingest and normalization (fast path, CPU).

Tolerates malformed records, mixed line endings, gaps, mixed case.
Records every transformation in the audit trail.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from Bio import SeqIO

from agent0.shared.schemas import InputRecord, NormalizedRecord


_GAP_CHARS = set("-.~ ")


def parse_fasta(path: Path) -> Iterator[InputRecord]:
    """Stream FASTA records from disk.

    Headers are taken verbatim (full description, not just ID), with leading
    '>' already stripped by SeqIO. Empty records are skipped.
    """
    for rec in SeqIO.parse(str(path), "fasta"):
        seq = str(rec.seq)
        if not seq.strip():
            continue
        # Use full description so the original header survives. Client metadata
        # may be embedded in headers (e.g., "id key=val key=val") — preserved
        # but not parsed at this stage.
        record_id = rec.description if rec.description else rec.id
        yield InputRecord(
            record_id=record_id,
            sequence=seq,
            client_metadata={},  # Client supplies separately, not from header.
        )


def normalize_record(record: InputRecord) -> NormalizedRecord:
    """Apply deterministic normalization: uppercase, strip gaps/whitespace.

    All transformations are recorded in the audit trail. Original sequence
    is preserved on the returned record.
    """
    raw = record.sequence
    transformations: list[str] = []

    # 1. Strip whitespace and line endings.
    cleaned = "".join(raw.split())
    if cleaned != raw:
        transformations.append("strip_whitespace")

    # 2. Remove gap characters (FASTA may carry alignment artifacts).
    no_gaps = "".join(c for c in cleaned if c not in _GAP_CHARS)
    if no_gaps != cleaned:
        transformations.append("strip_gaps")

    # 3. Uppercase.
    upper = no_gaps.upper()
    if upper != no_gaps:
        transformations.append("uppercase")

    return NormalizedRecord(
        record_id=record.record_id,
        original_sequence=raw,
        normalized_sequence=upper,
        transformations=transformations,
        client_metadata=record.client_metadata,
    )
