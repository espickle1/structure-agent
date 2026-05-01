"""Fast-path translation. Handles the clean majority of inputs.

Eligibility for the fast path:
- Type is DNA or RNA
- Length divisible by 3
- Starts with ATG (or AUG for RNA)
- Ends with a single terminal stop under code 11
- No internal stops
- All bases are canonical ACGT(U), no IUPAC ambiguity codes

If any check fails, the record is marked SLOW_PATH_NEEDED and forwarded
to the GPU app for ORF resolution.
"""

from __future__ import annotations

from Bio.Data import CodonTable
from Bio.Seq import Seq

from agent0.shared.config import DEFAULT_GENETIC_CODE
from agent0.shared.schemas import (
    SequenceType,
    TypedRecord,
)


_CODE_11_TABLE = CodonTable.unambiguous_dna_by_id[DEFAULT_GENETIC_CODE]
_CODE_11_STARTS = set(_CODE_11_TABLE.start_codons)
_CODE_11_STOPS = set(_CODE_11_TABLE.stop_codons)
_CANONICAL_NUCLEOTIDES = frozenset("ACGT")


def rna_to_dna(seq: str) -> str:
    """Replace U with T for downstream DNA tooling."""
    return seq.replace("U", "T")


def is_clean_cds(dna_seq: str) -> tuple[bool, str]:
    """Check whether `dna_seq` is a clean CDS under code 11.

    Returns (True, "") if eligible for fast path; otherwise (False, reason).
    """
    if len(dna_seq) < 6:
        return False, "too_short_for_fast_path"
    if len(dna_seq) % 3 != 0:
        return False, "length_not_divisible_by_3"

    if not set(dna_seq).issubset(_CANONICAL_NUCLEOTIDES):
        return False, "non_canonical_bases"

    start = dna_seq[:3]
    stop = dna_seq[-3:]
    if start not in _CODE_11_STARTS:
        return False, "missing_start_codon"
    if stop not in _CODE_11_STOPS:
        return False, "missing_terminal_stop"

    # Internal stop check: scan codons except the last.
    for i in range(0, len(dna_seq) - 3, 3):
        codon = dna_seq[i : i + 3]
        if codon in _CODE_11_STOPS:
            return False, "internal_stop_codon"

    return True, ""


def translate_clean(dna_seq: str) -> str:
    """Translate a verified-clean CDS under code 11. Drops the terminal stop."""
    aa = str(Seq(dna_seq).translate(table=DEFAULT_GENETIC_CODE, to_stop=False))
    # `translate(to_stop=False)` includes the terminal '*'; strip it.
    if aa.endswith("*"):
        aa = aa[:-1]
    return aa


def attempt_fast_path(record: TypedRecord) -> tuple[bool, str, str]:
    """Try fast-path translation.

    Returns (success, aa_sequence, dna_used).
    On failure, aa_sequence is empty and dna_used contains the post-RNA→DNA
    sequence for use by the slow path (avoids redundant conversion).
    """
    if record.sequence_type not in (SequenceType.DNA, SequenceType.RNA):
        return False, "", record.normalized_sequence

    dna = (
        rna_to_dna(record.normalized_sequence)
        if record.sequence_type == SequenceType.RNA
        else record.normalized_sequence
    )

    eligible, _reason = is_clean_cds(dna)
    if not eligible:
        return False, "", dna

    aa = translate_clean(dna)
    return True, aa, dna
