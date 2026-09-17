"""
guardrails/guardrail.py
-----------------------
GuardrailPipeline — orchestrates all input and output guards.

Usage:
    pipeline = GuardrailPipeline()

    # Input check (before RAG)
    result = pipeline.check_input(query)
    if not result.passed:
        return blocked_response(result.reason)

    # Output check (after RAG)
    result = pipeline.check_output(answer, context, context_available)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from guardrails.input_guards import (
    GuardResult, ScopeGuard, InputLengthGuard, ContentGuard, PIIGuard
)
from guardrails.output_guards import (
    RefusalConsistencyGuard, ContextGroundingGuard,
    MinimumLengthGuard, SourceCitationGuard
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Aggregated result from all guards in the pipeline."""
    passed: bool
    blocked_by: Optional[str]          = None   # Guard name that blocked
    reason: Optional[str]              = None   # Human-readable explanation
    severity: str                      = "info"
    all_results: List[GuardResult]     = field(default_factory=list)
    warnings: List[GuardResult]        = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed":     self.passed,
            "blocked_by": self.blocked_by,
            "reason":     self.reason,
            "severity":   self.severity,
            "warnings":   [
                {"guard": w.guard_name, "reason": w.reason}
                for w in self.warnings
            ],
        }


class GuardrailPipeline:
    """
    Runs all configured input and output guards in sequence.
    Short-circuits on the first blocking failure.
    Collects non-blocking warnings from all guards.
    """

    def __init__(self):
        # Input guards — order matters: length first (cheap), then content, scope, PII
        self.input_guards = [
            InputLengthGuard(),
            ContentGuard(),
            PIIGuard(),
            ScopeGuard(),
        ]

        # Output guards — grounding guard is lazy (loads model on first use)
        self.output_guards_nomodel = [
            MinimumLengthGuard(),
            RefusalConsistencyGuard(),
            SourceCitationGuard(),
        ]
        self._grounding_guard = ContextGroundingGuard()

    # ── Input pipeline ─────────────────────────────────────────────────────────
    def check_input(self, query: str) -> PipelineResult:
        """Run all input guards. Returns PipelineResult (passed=False if any guard blocks)."""
        all_results: List[GuardResult] = []
        warnings:    List[GuardResult] = []

        for guard in self.input_guards:
            result = guard.check(query)
            all_results.append(result)

            if not result.passed:
                if result.severity == "block":
                    logger.info(f"Input BLOCKED by {result.guard_name}: {result.reason[:80]}")
                    return PipelineResult(
                        passed=False,
                        blocked_by=result.guard_name,
                        reason=result.reason,
                        severity=result.severity,
                        all_results=all_results,
                        warnings=warnings,
                    )
                else:
                    # Non-blocking warning
                    warnings.append(result)

        return PipelineResult(
            passed=True,
            blocked_by=None,
            reason="All input guards passed.",
            severity="info",
            all_results=all_results,
            warnings=warnings,
        )

    # ── Output pipeline ────────────────────────────────────────────────────────
    def check_output(
        self,
        answer: str,
        context: str,
        context_available: bool,
    ) -> PipelineResult:
        """Run all output guards. Returns PipelineResult with warnings and blocks."""
        all_results: List[GuardResult] = []
        warnings:    List[GuardResult] = []

        # Length check
        r = MinimumLengthGuard().check(answer)
        all_results.append(r)
        if not r.passed:
            if r.severity == "block":
                return PipelineResult(passed=False, blocked_by=r.guard_name,
                                      reason=r.reason, severity=r.severity,
                                      all_results=all_results, warnings=warnings)
            warnings.append(r)

        # Refusal consistency
        r = RefusalConsistencyGuard().check(answer, context_available)
        all_results.append(r)
        if not r.passed:
            warnings.append(r)

        # Source citation
        r = SourceCitationGuard().check(answer, context_available)
        all_results.append(r)
        if not r.passed:
            warnings.append(r)

        # Context grounding (semantic — slightly heavier)
        r = self._grounding_guard.check(answer, context)
        all_results.append(r)
        if not r.passed:
            warnings.append(r)

        return PipelineResult(
            passed=True,
            blocked_by=None,
            reason="Output validation complete.",
            severity="info" if not warnings else "warning",
            all_results=all_results,
            warnings=warnings,
        )


# ── Convenience: blocked response helper ──────────────────────────────────────
def build_blocked_response(result: PipelineResult) -> dict:
    """Build a standardised blocked-query response for the API."""
    return {
        "query":      "",
        "answer":     result.reason or "Your query could not be processed.",
        "sources":    [],
        "retrieval_results": [],
        "guardrail":  result.to_dict(),
    }
