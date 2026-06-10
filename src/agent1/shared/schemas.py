"""Agent 1 record schema (Agent 1 → Agent 2 handoff).

Mirrors Agent 0's contract: record_id / parent_id threading, and upstream
metadata (Agent 0's sidecar record) passed through unmodified. No module reads
another's internal state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class ConfidenceTier(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def classify_confidence(plddt_mean: float, high: float, medium: float) -> ConfidenceTier:
    """Advisory tier from mean pLDDT. Agent 1 annotates; it never rejects."""
    if plddt_mean >= high:
        return ConfidenceTier.HIGH
    if plddt_mean >= medium:
        return ConfidenceTier.MEDIUM
    return ConfidenceTier.LOW


@dataclass
class StructureRecord:
    """A folded structure + confidence. One line in structures.jsonl."""

    record_id: str
    parent_id: str
    cif_path: str                       # path to the CIF, relative to the output dir
    plddt_mean: float
    ptm: float
    iptm: float
    confidence_tier: ConfidenceTier
    sequence_length: int
    model: str                          # e.g. "biohub/ESMFold2-Fast"
    model_revision: Optional[str]
    fold_params: dict[str, Any]
    upstream: dict[str, Any] = field(default_factory=dict)  # Agent 0 sidecar, verbatim

    def to_sidecar_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["confidence_tier"] = self.confidence_tier.value
        return d


@dataclass
class FoldFailure:
    """A fold that errored. One line in rejections.jsonl. Logged, not escalated."""

    record_id: str
    parent_id: str
    stage: str                          # module/step where the failure occurred
    detail: str                         # free-text specifics (exception summary)
    upstream: dict[str, Any] = field(default_factory=dict)

    def to_log_dict(self) -> dict[str, Any]:
        return asdict(self)
