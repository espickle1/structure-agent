"""Rejection log writer. Append-only JSONL for audit trail."""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import RejectedRecord


def write_rejection(log_path: Path, rejection: RejectedRecord) -> None:
    """Append a single rejection record as JSONL."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(rejection.to_log_dict()) + "\n")


def write_rejections(log_path: Path, rejections: list[RejectedRecord]) -> None:
    """Append many rejections in a single open()."""
    if not rejections:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        for r in rejections:
            f.write(json.dumps(r.to_log_dict()) + "\n")


def read_rejections(log_path: Path) -> list[dict]:
    """Read back the rejection log (for inspection / tests)."""
    if not log_path.exists():
        return []
    with log_path.open() as f:
        return [json.loads(line) for line in f if line.strip()]
