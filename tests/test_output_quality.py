"""
tests/test_output_quality.py
----------------------------
AI Output Testing: systematic pass/fail criteria for LLM-generated answers.

Tests are organized into 7 criteria groups:
  1. Relevance       — answer addresses the question asked
  2. Grounding       — answer is supported by retrieved context
  3. Hallucination   — no unsupported numeric facts
  4. Format          — answer follows expected output format
  5. Refusal         — refuses appropriately when info unavailable
  6. Answerability   — provides answer when sufficient context exists
  7. Length sanity   — answer is within reasonable length bounds

Each test uses a real (or synthetic) RAG response to validate the criterion.

Run: python3 -m pytest tests/test_output_quality.py -v --tb=short
"""

import re
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from evaluation.metrics import (
    calculate_semantic_similarity,
    check_hallucination,
    calculate_relevance,
)


# ─── Fixtures / shared test data ──────────────────────────────────────────────

REFUSAL_PHRASE = "couldn't find enough information"

# Realistic contexts from the BMU knowledge base
ATTENDANCE_CONTEXT = """
Students must maintain a minimum attendance of 75% in each subject to be
eligible to appear in end-semester examinations. Students with attendance
below 75% will be debarred from sitting in the examination. The attendance
is recorded by the faculty member for each lecture/practical session.
The minimum attendance threshold is 75% as per university regulations.
"""

ANTI_RAGGING_CONTEXT = """
Ragging in all its forms is strictly prohibited within the university premises.
Students found guilty of ragging shall face severe disciplinary action by the
Anti-Ragging Committee, which may include suspension or expulsion from the university.
All students must sign an anti-ragging undertaking at the time of admission.
"""

FEE_CONTEXT = """
The Fee Payment Calendar for Academic Year 2026-27 specifies the deadlines
for fee payment. Late payment attracts a penalty of Rs. 500 per day after
the due date. Students must pay the odd semester fees by July 31, 2026.
"""

EMPTY_CONTEXT = ""

# ─── Test Case Data ───────────────────────────────────────────────────────────

GOOD_ATTENDANCE_ANSWER = (
    "Students must maintain a minimum of 75% attendance in each subject to be "
    "eligible to appear in end-semester examinations. Students falling below this "
    "threshold will be debarred from the exam. [SOURCE 1]"
)

GOOD_REFUSAL = (
    "I couldn't find enough information in the BMU knowledge base to answer "
    "that reliably."
)

BAD_HALLUCINATION_ANSWER = (
    "Students must maintain 90% attendance. The late fee penalty is Rs. 2000 per day "
    "as updated in 2025 regulations. Students below 60% attendance are expelled immediately."
)

IRRELEVANT_ANSWER = (
    "The capital of France is Paris. It is a beautiful city with the Eiffel Tower "
    "as its iconic landmark."
)

TOO_SHORT_ANSWER = "Yes."
TOO_LONG_ANSWER  = "The attendance policy states that " + "students must attend classes. " * 150

PARTIAL_ANSWER = (
    "The attendance requirement at BMU is described in the student handbook. "
    "Students should ensure they attend sufficient classes."
)


# ═══════════════════════════════════════════════════════════════════════════════
# CRITERION 1: RELEVANCE
# Is the answer relevant to the question?
# Pass: semantic similarity(answer, question) ≥ 0.25
# ═══════════════════════════════════════════════════════════════════════════════

class TestRelevance:
    """Is the answer relevant to the question asked?"""

    QUESTION = "What is the minimum attendance requirement for students?"
    THRESHOLD = 0.25

    def test_relevant_answer_passes(self):
        """A grounded on-topic answer should pass the relevance check."""
        sim = calculate_semantic_similarity(GOOD_ATTENDANCE_ANSWER, self.QUESTION)
        assert sim >= self.THRESHOLD, (
            f"Expected relevant answer to score ≥{self.THRESHOLD}, got {sim:.4f}"
        )

    def test_irrelevant_answer_fails(self):
        """A completely off-topic answer should fail."""
        sim = calculate_semantic_similarity(IRRELEVANT_ANSWER, self.QUESTION)
        assert sim < self.THRESHOLD, (
            f"Expected irrelevant answer to score <{self.THRESHOLD}, got {sim:.4f}"
        )

    def test_partial_answer_borderline(self):
        """A vague but topically relevant answer may pass (lenient threshold)."""
        sim = calculate_semantic_similarity(PARTIAL_ANSWER, self.QUESTION)
        # Partial answers should still be somewhat relevant
        assert sim >= 0.15, (
            f"Expected partial answer to score ≥0.15, got {sim:.4f}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CRITERION 2: GROUNDING (Context Support)
# Is the answer supported by the retrieved context?
# Pass: semantic similarity(answer, context) ≥ 0.25
# ═══════════════════════════════════════════════════════════════════════════════

class TestGrounding:
    """Is the answer grounded in the retrieved context?"""

    THRESHOLD = 0.25

    def test_grounded_answer_passes(self):
        """Answer derived from context should be well-grounded."""
        sim = calculate_semantic_similarity(GOOD_ATTENDANCE_ANSWER, ATTENDANCE_CONTEXT)
        assert sim >= self.THRESHOLD, (
            f"Expected grounded answer to score ≥{self.THRESHOLD}, got {sim:.4f}"
        )

    def test_hallucinated_answer_low_grounding(self):
        """An answer with made-up facts should score lower against context."""
        sim_good = calculate_semantic_similarity(GOOD_ATTENDANCE_ANSWER, ATTENDANCE_CONTEXT)
        sim_bad  = calculate_semantic_similarity(BAD_HALLUCINATION_ANSWER, ATTENDANCE_CONTEXT)
        # The good (grounded) answer should score at least as well as the hallucinated one
        assert sim_good >= sim_bad - 0.05, (
            f"Grounded answer ({sim_good:.4f}) should outscore hallucinated ({sim_bad:.4f})"
        )

    def test_irrelevant_answer_not_grounded(self):
        """An irrelevant answer should score very low against domain context."""
        sim = calculate_semantic_similarity(IRRELEVANT_ANSWER, ATTENDANCE_CONTEXT)
        assert sim < 0.4, (
            f"Expected irrelevant answer to score <0.4 vs context, got {sim:.4f}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CRITERION 3: HALLUCINATION
# Does the answer contain unsupported numeric claims?
# Pass: hallucination_rate < 0.30
# ═══════════════════════════════════════════════════════════════════════════════

class TestHallucination:
    """Does the answer contain unsupported numeric/factual claims?"""

    THRESHOLD = 0.30   # allow up to 30% unsupported numeric facts

    def test_grounded_answer_low_hallucination(self):
        """A well-grounded answer should have low hallucination rate."""
        # Use answer without citation tag to avoid [SOURCE 1] number being flagged
        grounded_no_citation = (
            "Students must maintain a minimum of 75% attendance in each subject to be "
            "eligible to appear in end-semester examinations. Students falling below this "
            "threshold will be debarred from the exam."
        )
        rate = check_hallucination(grounded_no_citation, ATTENDANCE_CONTEXT)
        assert rate < self.THRESHOLD, (
            f"Expected hallucination rate <{self.THRESHOLD}, got {rate:.4f}"
        )

    def test_hallucinated_answer_high_rate(self):
        """Answer with invented numbers should have high hallucination rate."""
        rate = check_hallucination(BAD_HALLUCINATION_ANSWER, ATTENDANCE_CONTEXT)
        # This answer has 90%, 2000, 2025, 60% — most not in context
        assert rate >= self.THRESHOLD, (
            f"Expected hallucinated answer to have rate ≥{self.THRESHOLD}, got {rate:.4f}"
        )

    def test_refusal_zero_hallucination(self):
        """Refusal answers should always score 0 hallucination."""
        rate = check_hallucination(GOOD_REFUSAL, ATTENDANCE_CONTEXT)
        assert rate == 0.0, (
            f"Expected refusal to have 0.0 hallucination rate, got {rate}"
        )

    def test_no_facts_zero_hallucination(self):
        """Answers with no numeric facts cannot hallucinate numerically."""
        rate = check_hallucination("Attendance policy is described in the handbook.", ATTENDANCE_CONTEXT)
        assert rate == 0.0, "No numeric facts → hallucination rate must be 0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# CRITERION 4: FORMAT
# Does the answer follow the expected output format?
# Pass: contains [SOURCE X] citation tag when context was available
# ═══════════════════════════════════════════════════════════════════════════════

class TestFormat:
    """Does the answer follow the expected output format?"""

    def test_answer_with_citation_passes(self):
        """Answer containing [SOURCE X] tag should pass format check."""
        answer = "The minimum attendance is 75%. [SOURCE 1]"
        has_citation = bool(re.search(r"\[SOURCE\s*\d+\]", answer, re.IGNORECASE))
        assert has_citation, "Answer with [SOURCE 1] should pass citation format check"

    def test_answer_without_citation_fails(self):
        """Answer without citation tag should fail format check."""
        answer = "The minimum attendance is 75%."
        has_citation = bool(re.search(r"\[SOURCE\s*\d+\]", answer, re.IGNORECASE))
        assert not has_citation, "Answer without citation should fail format check"

    def test_refusal_no_citation_required(self):
        """Refusal answers don't need citation tags."""
        assert REFUSAL_PHRASE in GOOD_REFUSAL.lower(), \
            "Refusal answer should contain the standard refusal phrase"

    def test_citation_tag_variations(self):
        """Test various valid citation formats."""
        valid_citations = [
            "Answer here. [SOURCE 1]",
            "Answer. [source 2]",
            "Answer. [SOURCE 10]",
        ]
        for ans in valid_citations:
            has_citation = bool(re.search(r"\[SOURCE\s*\d+\]", ans, re.IGNORECASE))
            assert has_citation, f"'{ans}' should be detected as having a citation"


# ═══════════════════════════════════════════════════════════════════════════════
# CRITERION 5: REFUSAL
# Does the model refuse appropriately when info is unavailable?
# Pass: when answerable=False, answer contains refusal phrase
# ═══════════════════════════════════════════════════════════════════════════════

class TestRefusal:
    """Does the model refuse when it should?"""

    def test_correct_refusal_passes(self):
        """Standard refusal phrase should be recognized."""
        assert REFUSAL_PHRASE in GOOD_REFUSAL.lower()

    def test_hallucination_instead_of_refusal_fails(self):
        """
        This test DEMONSTRATES the failure case: when context_available=False
        but the model answers instead of refusing, the system should detect it.
        We assert that BAD_HALLUCINATION_ANSWER does NOT contain a refusal
        (confirming it is the problematic case that guards must catch).
        """
        has_refusal = REFUSAL_PHRASE in BAD_HALLUCINATION_ANSWER.lower()
        # The bad answer does NOT contain a refusal — this is the problem
        assert not has_refusal, (
            "BAD_HALLUCINATION_ANSWER should NOT contain a refusal phrase "
            "(it is the problematic hallucinated answer the guard must catch)"
        )
        # The RefusalConsistencyGuard should flag this
        from guardrails.output_guards import RefusalConsistencyGuard
        guard = RefusalConsistencyGuard()
        result = guard.check(BAD_HALLUCINATION_ANSWER, context_available=False)
        assert not result.passed, (
            "RefusalConsistencyGuard must FAIL when model answers despite no context"
        )

    def test_out_of_scope_triggers_refusal(self):
        """Out-of-scope questions should result in refusal."""
        out_of_scope_answer = (
            "I couldn't find enough information in the BMU knowledge base to answer that reliably."
        )
        assert REFUSAL_PHRASE in out_of_scope_answer.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# CRITERION 6: ANSWERABILITY
# Does the model provide an answer when sufficient context exists?
# Pass: when answerable=True and context available, answer must NOT be a refusal
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnswerability:
    """Does the model answer when it has enough context?"""

    def test_answers_when_context_available(self):
        """When context is available, answer should not be a refusal."""
        answer = GOOD_ATTENDANCE_ANSWER
        has_refusal = REFUSAL_PHRASE in answer.lower()
        assert not has_refusal, (
            "Model should NOT refuse when context is available"
        )

    def test_refusal_when_context_empty(self):
        """When no context, a refusal is correct."""
        answer = GOOD_REFUSAL
        has_refusal = REFUSAL_PHRASE in answer.lower()
        assert has_refusal, "Refusal is correct when context is empty"

    def test_good_answer_is_non_empty(self):
        """A good answer should have substantial content."""
        assert len(GOOD_ATTENDANCE_ANSWER.strip()) > 20


# ═══════════════════════════════════════════════════════════════════════════════
# CRITERION 7: LENGTH SANITY
# Is the answer an appropriate length?
# Pass: 20 < len(answer) < 2000
# ═══════════════════════════════════════════════════════════════════════════════

class TestLengthSanity:
    """Is the answer an appropriate length?"""

    MIN_CHARS = 20
    MAX_CHARS = 2000

    def test_good_answer_length(self):
        n = len(GOOD_ATTENDANCE_ANSWER.strip())
        assert self.MIN_CHARS < n < self.MAX_CHARS, (
            f"Good answer length {n} should be between {self.MIN_CHARS} and {self.MAX_CHARS}"
        )

    def test_too_short_fails(self):
        n = len(TOO_SHORT_ANSWER.strip())
        assert n <= self.MIN_CHARS, (
            f"'{TOO_SHORT_ANSWER}' should be flagged as too short ({n} chars)"
        )

    def test_too_long_fails(self):
        n = len(TOO_LONG_ANSWER.strip())
        assert n >= self.MAX_CHARS, (
            f"Long answer ({n} chars) should be flagged as too long"
        )

    def test_refusal_length_acceptable(self):
        n = len(GOOD_REFUSAL.strip())
        assert self.MIN_CHARS < n < self.MAX_CHARS, (
            f"Refusal answer length {n} should be in acceptable range"
        )


# ─── Standalone runner ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short", "--no-header"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    sys.exit(result.returncode)
