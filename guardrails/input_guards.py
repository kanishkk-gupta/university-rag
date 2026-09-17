"""
guardrails/input_guards.py
--------------------------
Input guardrails for the BMU University RAG system.

Guards:
  1. ScopeGuard       — reject questions outside BMU university domain
  2. InputLengthGuard — reject queries > MAX_QUERY_CHARS
  3. ContentGuard     — reject offensive / inappropriate language
  4. PIIGuard         — reject inputs containing personal identifiable info
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

MAX_QUERY_CHARS = 500  # configurable

# ── BMU-domain keyword anchors ─────────────────────────────────────────────────
BMU_TOPIC_KEYWORDS = [
    # Policies
    "ragging", "anti-ragging", "dac", "disciplinary", "conduct", "drug",
    "attendance", "fee", "payment", "hostel", "campus", "student",
    "handbook", "exam", "examination", "semester", "calendar", "holiday",
    "policy", "university", "bmu", "bharat", "manav", "uchchatar",
    # Academic
    "course", "grade", "cgpa", "marks", "assignment", "lecture", "faculty",
    "department", "library", "scholarship", "internship", "placement",
    # Admin
    "transcript", "certificate", "registration", "admission", "portal",
    "canteen", "mess", "sports", "club", "event",
]

# ── Offensive / inappropriate content keywords ─────────────────────────────────
INAPPROPRIATE_KEYWORDS = [
    "fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dick", "pussy",
    "nigger", "faggot", "slut", "whore", "rape", "kill yourself", "suicide",
    "bomb", "terrorist", "jihad", "hack", "exploit", "ddos",
]

# ── PII patterns ───────────────────────────────────────────────────────────────
PII_PATTERNS = [
    (r"\b[A-Z]{5}\d{4}[A-Z]\b",              "PAN card number"),
    (r"\b\d{4}\s?\d{4}\s?\d{4}\b",           "Aadhaar-like number"),
    (r"\b[6-9]\d{9}\b",                       "Indian phone number"),
    (r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b", "email address"),
    (r"\b\d{3}-\d{2}-\d{4}\b",               "SSN-like pattern"),
]


@dataclass
class GuardResult:
    passed: bool
    guard_name: str
    reason: str
    severity: str  # "info" | "warning" | "block"


class ScopeGuard:
    """
    Rejects questions that are clearly outside the BMU university domain.
    Uses keyword matching + a short-circuit bypass for obvious BMU topics.
    """
    name = "ScopeGuard"

    def __init__(self, keywords: List[str] = None):
        self.keywords = [k.lower() for k in (keywords or BMU_TOPIC_KEYWORDS)]

    def check(self, query: str) -> GuardResult:
        q_lower = query.lower()

        # If any BMU keyword is present → in scope
        if any(kw in q_lower for kw in self.keywords):
            return GuardResult(
                passed=True, guard_name=self.name,
                reason="Query contains BMU-domain keywords.",
                severity="info"
            )

        # Very short queries might just be greetings — allow
        if len(query.strip()) < 15:
            return GuardResult(
                passed=True, guard_name=self.name,
                reason="Short query — allowed through scope guard.",
                severity="info"
            )

        # No BMU keywords found — likely out of scope
        return GuardResult(
            passed=False, guard_name=self.name,
            reason=(
                "Your question appears to be outside the scope of the BMU University "
                "knowledge base. Please ask questions about university policies, "
                "fees, attendance, examinations, hostel rules, or academic calendar."
            ),
            severity="block"
        )


class InputLengthGuard:
    """Rejects queries that are excessively long (potential prompt injection)."""
    name = "InputLengthGuard"

    def __init__(self, max_chars: int = MAX_QUERY_CHARS):
        self.max_chars = max_chars

    def check(self, query: str) -> GuardResult:
        if len(query) <= self.max_chars:
            return GuardResult(
                passed=True, guard_name=self.name,
                reason=f"Query length {len(query)} ≤ {self.max_chars} chars.",
                severity="info"
            )
        return GuardResult(
            passed=False, guard_name=self.name,
            reason=(
                f"Your query is too long ({len(query)} characters). "
                f"Please limit your question to {self.max_chars} characters."
            ),
            severity="block"
        )


class ContentGuard:
    """Rejects queries containing offensive or inappropriate language."""
    name = "ContentGuard"

    def __init__(self, keywords: List[str] = None):
        self.keywords = [k.lower() for k in (keywords or INAPPROPRIATE_KEYWORDS)]

    def check(self, query: str) -> GuardResult:
        q_lower = query.lower()
        for kw in self.keywords:
            if kw in q_lower:
                return GuardResult(
                    passed=False, guard_name=self.name,
                    reason=(
                        "Your query contains inappropriate language. "
                        "Please rephrase your question respectfully."
                    ),
                    severity="block"
                )
        return GuardResult(
            passed=True, guard_name=self.name,
            reason="No inappropriate content detected.",
            severity="info"
        )


class PIIGuard:
    """Rejects queries that contain personally identifiable information."""
    name = "PIIGuard"

    def check(self, query: str) -> GuardResult:
        for pattern, label in PII_PATTERNS:
            if re.search(pattern, query):
                return GuardResult(
                    passed=False, guard_name=self.name,
                    reason=(
                        f"Your query appears to contain personal information ({label}). "
                        "Please do not share personal data. "
                        "Ask about university policies in general terms."
                    ),
                    severity="block"
                )
        return GuardResult(
            passed=True, guard_name=self.name,
            reason="No PII detected.",
            severity="info"
        )
