"""ESM-2 perplexity scoring for ORF candidates.

Single full-pass perplexity (not pseudo-perplexity). Real proteins typically
score < 10 under ESM-2 650M; random sequences score > 20. This is a filter,
not a fine-grained signal — full-pass loss is sufficient and ~10× cheaper
than masked pseudo-perplexity.

Usage:
    scorer = ESM2Scorer()
    scorer.load()             # heavy; do at container startup
    perps = scorer.score_batch(["MKTAYIA...", "MGNFAEM..."])
"""

from __future__ import annotations

import math

from agent_0.config import ESM_BATCH_SIZE, ESM_MODEL_NAME
from agent_0.schemas import ORFCandidate


class ESM2Scorer:
    """Encapsulates model + tokenizer. Construct once per container."""

    def __init__(self, model_name: str = ESM_MODEL_NAME):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = None

    def load(self) -> None:
        """Load tokenizer and model onto GPU. Idempotent."""
        if self.model is not None:
            return
        import torch
        from transformers import EsmTokenizer, EsmForMaskedLM

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = EsmTokenizer.from_pretrained(self.model_name)
        self.model = EsmForMaskedLM.from_pretrained(self.model_name).to(self.device).eval()

    def score_batch(self, sequences: list[str]) -> list[float]:
        """Compute per-sequence perplexity. Empty input returns [].

        Sequences longer than the model's max length are truncated; this
        should not occur given LENGTH_MAX_AA = 2000 and ESM-2 max = 1024
        — TODO: handle long-sequence chunking before production.
        """
        if not sequences:
            return []
        if self.model is None:
            self.load()

        import torch

        out: list[float] = []
        for i in range(0, len(sequences), ESM_BATCH_SIZE):
            batch = sequences[i : i + ESM_BATCH_SIZE]
            enc = self.tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=1024,
            ).to(self.device)

            with torch.inference_mode():
                logits = self.model(**enc).logits  # [B, L, V]

            # Cross-entropy at each non-pad position vs the input token itself.
            # ESM-2 was trained with MLM; full-pass logits at unmasked positions
            # give a usable approximation of token plausibility.
            input_ids = enc["input_ids"]
            attention_mask = enc["attention_mask"]
            log_probs = torch.log_softmax(logits, dim=-1)
            token_ll = log_probs.gather(2, input_ids.unsqueeze(-1)).squeeze(-1)
            # Mask special tokens (CLS, EOS, PAD).
            special = torch.zeros_like(attention_mask, dtype=torch.bool)
            for tok_id in self.tokenizer.all_special_ids:
                special |= input_ids == tok_id
            valid = attention_mask.bool() & ~special

            for b in range(token_ll.shape[0]):
                v = valid[b]
                if v.sum() == 0:
                    out.append(float("inf"))
                    continue
                mean_ll = token_ll[b][v].mean().item()
                out.append(math.exp(-mean_ll))
        return out


def attach_perplexities(
    candidates: list[ORFCandidate], scorer: ESM2Scorer
) -> list[ORFCandidate]:
    """Score all candidates in one batched pass and attach perplexity."""
    if not candidates:
        return []
    seqs = [c.aa_sequence for c in candidates]
    perps = scorer.score_batch(seqs)
    for c, p in zip(candidates, perps):
        c.perplexity = p
    return candidates
