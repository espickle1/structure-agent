"""Quality gates on translated AA sequences.

Each gate is a standalone function. `gate_translation` composes them in
order of severity (cheapest checks first).
"""

from __future__ import annotations

from agent0.shared.config import (
    AMBIGUITY_RESIDUES,
    LENGTH_MAX_AA,
    LENGTH_MIN_AA,
    X_FRACTION_MAX,
    X_RUN_MAX,
    X_TERMINAL_BUFFER,
)
from agent0.shared.schemas import RejectionReason


def gate_length(aa_seq: str) -> tuple[bool, str]:
    n = len(aa_seq)
    if n < LENGTH_MIN_AA:
        return False, f"length {n} < {LENGTH_MIN_AA}"
    if n > LENGTH_MAX_AA:
        return False, f"length {n} > {LENGTH_MAX_AA}"
    return True, ""


def gate_x_terminal(aa_seq: str) -> tuple[bool, str]:
    """Reject if any ambiguity residue is in first or last X_TERMINAL_BUFFER."""
    head = aa_seq[:X_TERMINAL_BUFFER]
    tail = aa_seq[-X_TERMINAL_BUFFER:]
    for region, name in [(head, "N-terminus"), (tail, "C-terminus")]:
        for c in region:
            if c in AMBIGUITY_RESIDUES:
                return False, f"ambiguity '{c}' in {name} (first/last {X_TERMINAL_BUFFER} aa)"
    return True, ""


def gate_x_run(aa_seq: str) -> tuple[bool, str]:
    """Reject if any consecutive run of ambiguity residues exceeds X_RUN_MAX."""
    longest = 0
    current = 0
    for c in aa_seq:
        if c in AMBIGUITY_RESIDUES:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    if longest > X_RUN_MAX:
        return False, f"ambiguity run length {longest} > {X_RUN_MAX}"
    return True, ""


def gate_x_fraction(aa_seq: str) -> tuple[bool, str]:
    """Reject if total ambiguity residue fraction exceeds X_FRACTION_MAX."""
    if not aa_seq:
        return False, "empty sequence"
    n_amb = sum(1 for c in aa_seq if c in AMBIGUITY_RESIDUES)
    frac = n_amb / len(aa_seq)
    if frac > X_FRACTION_MAX:
        return False, f"ambiguity fraction {frac:.3f} > {X_FRACTION_MAX}"
    return True, ""


# Order: length first (cheapest), then terminal X, then runs, then fraction.
# Each gate returns the reason key so the caller can attribute the rejection.
_GATES: list[tuple[str, RejectionReason, callable]] = [
    ("length", RejectionReason.LENGTH_OUT_OF_BOUNDS, gate_length),
    ("x_terminal", RejectionReason.X_AT_TERMINUS, gate_x_terminal),
    ("x_run", RejectionReason.X_RUN_EXCEEDED, gate_x_run),
    ("x_fraction", RejectionReason.X_FRACTION_EXCEEDED, gate_x_fraction),
]


def gate_translation(aa_seq: str) -> tuple[bool, RejectionReason | None, str]:
    """Run all gates in order. Returns (passed, reason_if_failed, detail)."""
    for _name, reason, gate_fn in _GATES:
        ok, detail = gate_fn(aa_seq)
        if not ok:
            return False, reason, detail
    return True, None, ""
