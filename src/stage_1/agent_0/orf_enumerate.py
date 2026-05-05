"""ORF enumeration across all 6 frames under a given genetic code.

Wraps `orfipy_core.orfs` and converts results into ORFCandidate dataclasses.
No selection logic here — that's `orf_select.py`. No biological interpretation.
"""

from __future__ import annotations

import re

from Bio.Data import CodonTable
from Bio.Seq import Seq

from agent_0.config import (
    AMBIGUITY_RESIDUES,
    MAX_ORF_LENGTH_NT,
    MIN_ORF_LENGTH_NT,
)
from agent_0.schemas import ORFCandidate


_FRAME_RE = re.compile(r"ORF_frame=(-?\d+)")


def _parse_frame(description: str) -> int:
    """orfipy emits 'ID=...;ORF_frame=N;...'; extract N."""
    m = _FRAME_RE.search(description)
    if not m:
        return 0
    return int(m.group(1))


def _translate(nt: str, genetic_code: int) -> str:
    """Translate; tolerate ambiguous bases by emitting X."""
    try:
        aa = str(Seq(nt).translate(table=genetic_code, to_stop=False))
    except CodonTable.TranslationError:
        # Fall back to manual translation with X for unknown codons.
        aa = _safe_translate(nt, genetic_code)
    return aa.rstrip("*")  # Drop terminal stop if present.


def _safe_translate(nt: str, genetic_code: int) -> str:
    """Manual codon-by-codon translation, emitting X for any non-resolvable codon."""
    table = CodonTable.unambiguous_dna_by_id[genetic_code].forward_table
    stops = set(CodonTable.unambiguous_dna_by_id[genetic_code].stop_codons)
    out: list[str] = []
    for i in range(0, len(nt) - 2, 3):
        codon = nt[i : i + 3]
        if codon in stops:
            out.append("*")
        else:
            out.append(table.get(codon, "X"))
    return "".join(out)


def enumerate_orfs(dna: str, genetic_code: int) -> list[ORFCandidate]:
    """Enumerate ORFs across all 6 frames using orfipy.

    Filtering at this stage is purely length-based; perplexity scoring and
    selection happen in downstream modules.
    """
    # Lazy import so the CPU app does not need orfipy.
    import orfipy_core

    candidates: list[ORFCandidate] = []
    for start, stop, strand, description in orfipy_core.orfs(
        dna,
        minlen=MIN_ORF_LENGTH_NT,
        maxlen=MAX_ORF_LENGTH_NT,
        table=str(genetic_code),
        starts=None,        # Allow alternative starts; default IUPAC.
        stops=None,
        partial3=False,     # Reject partial ORFs at this stage.
        partial5=False,
        between_stops=False,
    ):
        frame = _parse_frame(description) if strand == "+" else -_parse_frame(description)
        nt_segment = dna[start:stop] if strand == "+" else str(
            Seq(dna[start:stop]).reverse_complement()
        )
        aa = _translate(nt_segment, genetic_code)

        candidates.append(
            ORFCandidate(
                frame=frame,
                genetic_code=genetic_code,
                nt_start=start,
                nt_end=stop,
                nt_length=stop - start,
                aa_sequence=aa,
                aa_length=len(aa),
                has_start_codon="Start:" in description and "Start:NA" not in description,
                has_stop_codon="Stop:" in description and "Stop:NA" not in description,
            )
        )
    return candidates


def filter_translatable(candidates: list[ORFCandidate]) -> list[ORFCandidate]:
    """Drop candidates with no chance of passing AA gates (cheap pre-filter).

    Conservative: only filter out the egregious cases. Final rejection lives
    in the quality gate after selection.
    """
    out = []
    for c in candidates:
        if not c.aa_sequence:
            continue
        # Reject candidates dominated by ambiguity (saves perplexity compute).
        n_amb = sum(1 for r in c.aa_sequence if r in AMBIGUITY_RESIDUES)
        if n_amb / max(len(c.aa_sequence), 1) > 0.5:
            continue
        out.append(c)
    return out
