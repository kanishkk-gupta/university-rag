"""
guardrails/output_guards.py
---------------------------
Output guardrails for the BMU University RAG system.

Guards:
  1. RefusalConsistencyGuard — if no context retrieved, answer MUST be a refusal
  2. ContextGroundingGuard   — answer must be semantically similar to context
  3. MinimumLengthGuard      — flags suspiciously short / empty answers
  4. SourceCitationGuard     — answer should cite at least one [SOURCE X] tag
"""

import re
import logging
from typing import Optional

from guardrails.input_guards import GuardResult

logger = logging.getLogger(__name__)

REFUSAL_PHRASE    = "couldn't find enough information"
MIN_ANSWER_CHARS  = 20
MAX_ANSWER_CHARS  = 3000
MIN_GROUNDING_SIM = 0.15   # cosine similarity threshold (permissive)


class RefusalConsistencyGuard:
    """
    When no context was retrieved, the answer MUST contain the refusal phrase.
    When context IS retrieved, the answer must NOT be an empty refusal.
    """
    name = "RefusalConsistencyGuard"

    def check(self, answer: str, context_available: bool) -> GuardResult:
        has_refusal = REFUSAL_PHRASE in answer.lower()

        if not context_available and not has_refusal:
            return GuardResult(
                passed=False, guard_name=self.name,
                reason=(
                    "The model produced an answer despite no relevant context being retrieved. "
                    "This response may be hallucinated and has been flagged."
                ),
                severity="warning"
            )

        if context_available and has_refusal and len(answer.strip()) < 80:
            return GuardResult(
                passed=False, guard_name=self.name,
                reason=(
                    "The model refused to answer despite relevant context being available. "
                    "This may indicate under-performance or overly conservative behavior."
                ),
                severity="warning"
            )

        return GuardResult(
            passed=True, guard_name=self.name,
            reason="Refusal/answer consistency check passed.",
            severity="info"
        )


class ContextGroundingGuard:
    """
    Checks that the answer is semantically grounded in the retrieved context.
    Uses cosine similarity between the answer and context via sentence-transformers.
    Falls back gracefully if embedding model is unavailable.
    """
    name = "ContextGroundingGuard"

    def __init__(self, min_similarity: float = MIN_GROUNDING_SIM):
        self.min_similarity = min_similarity
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(f"ContextGroundingGuard: could not load model — {e}")
        return self._model

    def _cosine_sim(self, a: str, b: str) -> float:
        model = self._get_model()
        if model is None:
            return 1.0  # fail-open: assume grounded if we can't check
        try:
            import torch.nn.functional as F
            embs = model.encode([a, b], convert_to_tensor=True)
            sim = F.cosine_similarity(embs[0].unsqueeze(0), embs[1].unsqueeze(0))
            return max(0.0, float(sim.item()))
        except Exception as e:
            logger.warning(f"ContextGroundingGuard similarity failed: {e}")
            return 1.0  # fail-open

    def check(self, answer: str, context: str) -> GuardResult:
        # Skip grounding check for refusal answers
        if REFUSAL_PHRASE in answer.lower():
            return GuardResult(
                passed=True, guard_name=self.name,
                reason="Refusal answer — grounding check skipped.",
                severity="info"
            )

        if not context or not context.strip():
            return GuardResult(
                passed=True, guard_name=self.name,
                reason="No context provided — grounding check skipped.",
                severity="info"
            )

        sim = self._cosine_sim(answer, context)
        if sim >= self.min_similarity:
            return GuardResult(
                passed=True, guard_name=self.name,
                reason=f"Answer is grounded in context (similarity={sim:.3f}).",
                severity="info"
            )

        return GuardResult(
            passed=False, guard_name=self.name,
            reason=(
                f"Answer may not be grounded in the retrieved context "
                f"(similarity={sim:.3f} < threshold={self.min_similarity}). "
                "The response may contain information not supported by the knowledge base."
            ),
            severity="warning"
        )


class MinimumLengthGuard:
    """Flags answers that are suspiciously short or excessively long."""
    name = "MinimumLengthGuard"

    def __init__(self, min_chars: int = MIN_ANSWER_CHARS, max_chars: int = MAX_ANSWER_CHARS):
        self.min_chars = min_chars
        self.max_chars = max_chars

    def check(self, answer: str) -> GuardResult:
        n = len(answer.strip())
        if n < self.min_chars:
            return GuardResult(
                passed=False, guard_name=self.name,
                reason=f"Answer is too short ({n} chars < {self.min_chars}). Likely an empty or failed response.",
                severity="warning"
            )
        if n > self.max_chars:
            return GuardResult(
                passed=False, guard_name=self.name,
                reason=f"Answer is excessively long ({n} chars > {self.max_chars}). May be repetitive or looping.",
                severity="warning"
            )
        return GuardResult(
            passed=True, guard_name=self.name,
            reason=f"Answer length {n} chars is within acceptable range.",
            severity="info"
        )


class SourceCitationGuard:
    """
    Checks that the answer includes a [SOURCE X] citation tag.
    Only applies when context was available (answerable questions).
    """
    name = "SourceCitationGuard"

    def check(self, answer: str, context_available: bool) -> GuardResult:
        if not context_available or REFUSAL_PHRASE in answer.lower():
            return GuardResult(
                passed=True, guard_name=self.name,
                reason="Citation check skipped (no context or refusal).",
                severity="info"
            )

        has_citation = bool(re.search(r"\[SOURCE\s*\d+\]", answer, re.IGNORECASE))
        if has_citation:
            return GuardResult(
                passed=True, guard_name=self.name,
                reason="Answer contains source citation.",
                severity="info"
            )

        return GuardResult(
            passed=False, guard_name=self.name,
            reason=(
                "Answer does not include a [SOURCE X] citation. "
                "Responses should cite the source document for traceability."
            ),
            severity="info"   # info-level: useful warning but not a hard block
        )
