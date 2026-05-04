"""Type detection: classify a normalized record as DNA / RNA / protein / ambiguous.

Pure alphabet-composition analysis. No biological identity, no homology.
"""

from __future__ import annotations

from collections import Counter

from agent_0.config import (
    IUPAC_NUCLEOTIDE_ALPHABET,
    NUCLEOTIDE_PURITY_MIN,
    PROTEIN_PURITY_MIN,
)
from agent_0.schemas import NormalizedRecord, SequenceType, TypedRecord


# Canonical 20 AAs plus selenocysteine and pyrrolysine (rare but real).
_CANONICAL_AA = frozenset("ACDEFGHIKLMNPQRSTVWYUO")
# Letters unique to protein alphabet (cannot appear in DNA or RNA).
_PROTEIN_ONLY = frozenset("EFILPQZ")


def composition(seq: str) -> dict[str, float]:
    """Per-letter fraction of the sequence."""
    if not seq:
        return {}
    n = len(seq)
    return {letter: count / n for letter, count in Counter(seq).items()}


def detect_type(seq: str) -> SequenceType:
    """Classify by alphabet purity.

    Decision order:
    1. If protein-only letters appear above noise (>1%), call protein.
    2. If composition is dominated by ACGT(U), call DNA or RNA based on T vs U.
    3. If canonical AA set covers >= PROTEIN_PURITY_MIN, call protein.
    4. Otherwise, ambiguous.
    """
    if not seq:
        return SequenceType.AMBIGUOUS

    comp = composition(seq)
    n = len(seq)

    protein_only_fraction = sum(comp.get(c, 0.0) for c in _PROTEIN_ONLY)
    if protein_only_fraction > 0.01:
        return SequenceType.PROTEIN

    nuc_fraction = sum(comp.get(c, 0.0) for c in "ACGT") + comp.get("U", 0.0)
    if nuc_fraction >= NUCLEOTIDE_PURITY_MIN:
        # Resolve T vs U. Both present is allowed (treated as DNA after RNA→DNA).
        u_count = comp.get("U", 0.0) * n
        t_count = comp.get("T", 0.0) * n
        if u_count > t_count:
            return SequenceType.RNA
        return SequenceType.DNA

    canonical_aa_fraction = sum(comp.get(c, 0.0) for c in _CANONICAL_AA)
    if canonical_aa_fraction >= PROTEIN_PURITY_MIN:
        return SequenceType.PROTEIN

    return SequenceType.AMBIGUOUS


def classify_record(record: NormalizedRecord) -> TypedRecord:
    """Wrap detect_type into the schema transition."""
    seq_type = detect_type(record.normalized_sequence)
    comp = composition(record.normalized_sequence)
    return TypedRecord(
        record_id=record.record_id,
        original_sequence=record.original_sequence,
        normalized_sequence=record.normalized_sequence,
        transformations=record.transformations,
        sequence_type=seq_type,
        composition=comp,
        client_metadata=record.client_metadata,
    )


def has_non_iupac_nucleotide(seq: str) -> tuple[bool, set[str]]:
    """Return (True, offending_chars) if non-IUPAC characters are present."""
    seen = set(seq)
    bad = seen - IUPAC_NUCLEOTIDE_ALPHABET
    return (len(bad) > 0, bad)
