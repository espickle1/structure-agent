"""Selection policy applied to perplexity-scored ORF candidates.

Decision logic:
    1. If best perplexity > PERPLEXITY_REJECT_ABOVE → no viable ORF, reject.
    2. Otherwise, accept all candidates within (1 + PERPLEXITY_TIE_FRACTION)
       of the best score (i.e., "plausibility tie").
    3. Single accepted → emit one TranslatedRecord.
    4. Multiple accepted → emit each as a sibling TranslatedRecord with
       shared parent_id and is_multi_orf=True.

Safety valve: handled by the orchestrator. If selection here returns no
viable ORFs, the orchestrator retries with the next genetic code in the
fallback cascade. If the cascade exhausts, the record is rejected.
"""

from __future__ import annotations

from agent_0.config import (
    PERPLEXITY_REJECT_ABOVE,
    PERPLEXITY_TIE_FRACTION,
)
from agent_0.schemas import ORFCandidate


def select_orfs(
    candidates: list[ORFCandidate],
) -> tuple[list[ORFCandidate], str]:
    """Apply selection policy.

    Returns (accepted_candidates, reason_if_empty).
    accepted_candidates is empty iff no viable ORF found at this code.
    """
    if not candidates:
        return [], "no candidates produced by enumeration"

    scored = [c for c in candidates if c.perplexity is not None and c.perplexity > 0]
    if not scored:
        return [], "no candidates received perplexity scores"

    best = min(c.perplexity for c in scored)
    if best > PERPLEXITY_REJECT_ABOVE:
        return [], f"best perplexity {best:.2f} > {PERPLEXITY_REJECT_ABOVE}"

    # Accept all candidates within the tie band.
    threshold = best * (1.0 + PERPLEXITY_TIE_FRACTION)
    accepted = [c for c in scored if c.perplexity <= threshold]
    # Sort by perplexity ascending for deterministic output ordering.
    accepted.sort(key=lambda c: c.perplexity)
    return accepted, ""
