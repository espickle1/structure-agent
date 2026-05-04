"""Record dataclasses and sidecar JSON schema for Agent 0 → Agent 1.

Module independence rule: each downstream module receives one of these
dataclasses and produces another. No module reads internal state of
another's records.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class SequenceType(str, Enum):
    DNA = "dna"
    RNA = "rna"
    PROTEIN = "protein"
    AMBIGUOUS = "ambiguous"


class RejectionReason(str, Enum):
    NON_IUPAC_CHARACTERS = "non_iupac_characters"
    AMBIGUOUS_TYPE = "ambiguous_type"
    LENGTH_OUT_OF_BOUNDS = "length_out_of_bounds"
    X_FRACTION_EXCEEDED = "x_fraction_exceeded"
    X_RUN_EXCEEDED = "x_run_exceeded"
    X_AT_TERMINUS = "x_at_terminus"
    NO_VIABLE_ORF = "no_viable_orf"
    PERPLEXITY_BELOW_THRESHOLD = "perplexity_below_threshold"
    SLOW_PATH_UNAVAILABLE = "slow_path_unavailable"
    INTERNAL_ERROR = "internal_error"


class Verdict(str, Enum):
    FAST_PATH_PASS = "fast_path_pass"     # Clean CDS, translated under code 11.
    SLOW_PATH_NEEDED = "slow_path_needed" # Send to GPU app for ORF resolution.
    SLOW_PATH_PASS = "slow_path_pass"     # Resolved via ORF + perplexity filter.
    PROTEIN_PASSTHROUGH = "protein_passthrough"  # Client supplied AA directly.
    REJECTED = "rejected"


# -----------------------------------------------------------------------------
# Stage 1: ingest output
# -----------------------------------------------------------------------------
@dataclass
class InputRecord:
    """Raw FASTA record as parsed from client input."""
    record_id: str            # Original FASTA header (after ">").
    sequence: str             # Original sequence, untouched.
    client_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedRecord:
    """After uppercase, gap removal, whitespace cleanup."""
    record_id: str
    original_sequence: str
    normalized_sequence: str
    transformations: list[str]   # Audit trail: ["uppercase", "strip_gaps", ...]
    client_metadata: dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Stage 2: type detection
# -----------------------------------------------------------------------------
@dataclass
class TypedRecord:
    """Classified by alphabet composition."""
    record_id: str
    original_sequence: str
    normalized_sequence: str
    transformations: list[str]
    sequence_type: SequenceType
    composition: dict[str, float]   # Per-letter fraction of normalized seq.
    client_metadata: dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Stage 3+: candidate ORF (slow path output)
# -----------------------------------------------------------------------------
@dataclass
class ORFCandidate:
    """One candidate ORF + translation under one genetic code."""
    frame: int                   # 1, 2, 3 (forward) or -1, -2, -3 (reverse).
    genetic_code: int            # NCBI table number.
    nt_start: int                # 0-indexed inclusive start in normalized seq.
    nt_end: int                  # 0-indexed exclusive end.
    nt_length: int
    aa_sequence: str
    aa_length: int
    perplexity: Optional[float] = None  # Filled in by ESM-2 scorer.
    has_start_codon: bool = False
    has_stop_codon: bool = False


# -----------------------------------------------------------------------------
# Stage 4: final emission record (handoff to Agent 1)
# -----------------------------------------------------------------------------
@dataclass
class TranslatedRecord:
    """Final record passed to Agent 1.

    Multi-ORF case: emitted once per accepted ORF, with shared `parent_id`
    linking back to the original input.
    """
    record_id: str               # Output ID; for multi-ORF, suffixed e.g. "_orf1".
    parent_id: str               # Always the original input ID.
    aa_sequence: str             # Final clean translation.
    verdict: Verdict
    sequence_type: SequenceType
    selected_frame: Optional[int]
    selected_genetic_code: Optional[int]
    nt_coordinates: Optional[tuple[int, int]]  # (start, end) in original input.
    perplexity: Optional[float]
    transformations: list[str]
    is_multi_orf: bool = False
    sibling_orfs: list[str] = field(default_factory=list)  # Other parent_id sibs.
    original_sequence: str = ""
    client_metadata: dict[str, Any] = field(default_factory=dict)

    def to_sidecar_dict(self) -> dict[str, Any]:
        """Serialize for sidecar JSONL emission."""
        d = asdict(self)
        d["verdict"] = self.verdict.value
        d["sequence_type"] = self.sequence_type.value
        return d


@dataclass
class RejectedRecord:
    """Logged rejection. Original sequence preserved for audit."""
    record_id: str
    parent_id: str
    reason: RejectionReason
    stage: str                   # Module/function name where rejection occurred.
    detail: str                  # Free-text specifics (e.g., "X run length 7").
    original_sequence: str
    client_metadata: dict[str, Any] = field(default_factory=dict)

    def to_log_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["reason"] = self.reason.value
        return d
