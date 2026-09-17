"""
evaluation/llm_judge.py
-----------------------
LLM-as-Judge: uses a local Ollama model to semantically evaluate model answers
against a reference answer and rubric.

Judging dimensions (each scored 0-5):
  - correctness  : semantic accuracy compared to the reference answer
  - relevance    : how well the answer addresses the question
  - groundedness : how well grounded the answer is in the provided context
  - completeness : whether all key aspects of the question were addressed
  - hallucination: boolean flag — did the answer contain unsupported facts?

Falls back to token-F1 heuristics if the judge model is unavailable or the
judge response cannot be parsed.
"""

import json
import re
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from config import OLLAMA_BASE_URL, JUDGE_MODEL, JUDGE_TIMEOUT

logger = logging.getLogger(__name__)

# ── Scoring ranges ─────────────────────────────────────────────────────────────
SCORE_MIN = 0
SCORE_MAX = 5

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for a university Retrieval-Augmented Generation (RAG) system.

Your task is to score an AI model's answer against a reference answer based on a provided rubric.

Evaluate STRICTLY on:
1. correctness  (0-5): How semantically accurate is the answer compared to the reference?
2. relevance    (0-5): How relevant is the answer to the question asked?
3. groundedness (0-5): Is the answer grounded in the provided context (no hallucinations)?
4. completeness (0-5): Does the answer cover all required aspects?
5. hallucination_flag (true/false): Did the answer state facts not supported by the context?

SCORING GUIDE:
  5 = Perfect / Excellent
  4 = Good, minor gaps
  3 = Adequate, notable gaps
  2 = Poor, major gaps or errors
  1 = Very poor, mostly wrong
  0 = Completely wrong or refused when it should have answered

IMPORTANT: Respond ONLY with a valid JSON object. No explanation text outside JSON.
Example format:
{
  "correctness": 4,
  "relevance": 5,
  "groundedness": 4,
  "completeness": 3,
  "hallucination_flag": false,
  "reasoning": "One sentence explaining the scores"
}
"""


def _build_judge_prompt(
    question: str,
    candidate_answer: str,
    reference_answer: str,
    context: str,
    category: str,
    rubric: str,
) -> str:
    context_excerpt = context[:2000] if context else "(no context provided)"
    return f"""CATEGORY: {category}

QUESTION: {question}

RUBRIC: {rubric}

REFERENCE ANSWER: {reference_answer}

CANDIDATE ANSWER: {candidate_answer}

CONTEXT (first 2000 chars): {context_excerpt}

Evaluate the CANDIDATE ANSWER against the REFERENCE ANSWER using the rubric. 
Return ONLY the JSON object with scores."""


def _clamp(value: Any, lo: int = SCORE_MIN, hi: int = SCORE_MAX) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return lo


def _fallback_scores(candidate: str, reference: str, question: str) -> Dict[str, Any]:
    """Token-F1 based fallback when LLM judge is unavailable."""
    import re as _re
    from collections import Counter

    def _tok(s: str) -> Counter:
        return Counter(t for t in _re.findall(r"\b\w+\b", s.lower()) if len(t) > 1)

    def _f1(a: str, b: str) -> float:
        ta, tb = _tok(a), _tok(b)
        common = sum((ta & tb).values())
        if common == 0:
            return 0.0
        p = common / max(sum(ta.values()), 1)
        r = common / max(sum(tb.values()), 1)
        return 2 * p * r / (p + r)

    f1_ref = _f1(candidate, reference)
    f1_q   = _f1(candidate, question)
    refusal = "couldn't find enough information" in candidate.lower()

    correctness  = round(f1_ref * 5)
    relevance    = 0 if refusal else round(min(f1_q * 5 * 2, 5))
    groundedness = 3  # unknown without context comparison
    completeness = round(f1_ref * 5)
    hallucination_flag = False  # conservative default

    return {
        "correctness":       _clamp(correctness),
        "relevance":         _clamp(relevance),
        "groundedness":      _clamp(groundedness),
        "completeness":      _clamp(completeness),
        "hallucination_flag": hallucination_flag,
        "reasoning":         f"Fallback (token-F1): ref_f1={f1_ref:.2f}, q_f1={f1_q:.2f}",
        "judge_source":      "fallback_token_f1",
    }


class OllamaJudge:
    """
    Sends a judging request to a local Ollama model and parses the JSON scores.
    Falls back gracefully to token-F1 heuristics if Ollama is unreachable.
    """

    def __init__(
        self,
        model: str = JUDGE_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: int = JUDGE_TIMEOUT,
    ):
        self.model    = model
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

    # ── Health ──────────────────────────────────────────────────────────────────
    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(self.base_url)
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    # ── Core judge call ─────────────────────────────────────────────────────────
    def _call_ollama(self, user_prompt: str) -> Optional[str]:
        endpoint = f"{self.base_url}/api/generate"
        payload  = {
            "model":  self.model,
            "system": JUDGE_SYSTEM_PROMPT,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "top_p": 0.9,
                "num_predict": 300,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            endpoint, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("response", "")
        except Exception as e:
            logger.warning(f"OllamaJudge: call failed — {e}")
            return None

    # ── Parse JSON from LLM response ────────────────────────────────────────────
    @staticmethod
    def _parse_response(raw: str) -> Optional[Dict[str, Any]]:
        """Extract and validate the JSON block from the judge's response."""
        # Try to find a JSON object in the response
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
            required = {"correctness", "relevance", "groundedness", "completeness", "hallucination_flag"}
            if not required.issubset(data.keys()):
                return None
            return data
        except json.JSONDecodeError:
            return None

    # ── Public API ───────────────────────────────────────────────────────────────
    def judge(
        self,
        question: str,
        candidate_answer: str,
        reference_answer: str,
        context: str,
        category: str,
        rubric: str,
    ) -> Dict[str, Any]:
        """
        Evaluate a candidate answer and return a dict with numeric scores.

        Returns:
            {
                "correctness":       int (0-5),
                "relevance":         int (0-5),
                "groundedness":      int (0-5),
                "completeness":      int (0-5),
                "hallucination_flag": bool,
                "reasoning":         str,
                "judge_source":      "llm" | "fallback_token_f1",
                "normalized_score":  float (0-1),  # avg of 4 numeric dims
            }
        """
        scores: Optional[Dict[str, Any]] = None

        if self.is_available():
            user_prompt = _build_judge_prompt(
                question, candidate_answer, reference_answer, context, category, rubric
            )
            raw = self._call_ollama(user_prompt)
            if raw:
                scores = self._parse_response(raw)
                if scores:
                    scores["judge_source"] = "llm"
                    logger.debug(f"OllamaJudge: parsed scores for '{question[:40]}...'")
                else:
                    logger.warning(
                        f"OllamaJudge: could not parse JSON from response — using fallback.\n"
                        f"Raw: {raw[:200]}"
                    )

        if scores is None:
            scores = _fallback_scores(candidate_answer, reference_answer, question)

        # Clamp numeric dims
        for dim in ("correctness", "relevance", "groundedness", "completeness"):
            scores[dim] = _clamp(scores.get(dim, 0))

        # Ensure hallucination_flag is bool
        scores["hallucination_flag"] = bool(scores.get("hallucination_flag", False))

        # Composite normalized score [0,1]
        numeric_dims = [scores["correctness"], scores["relevance"],
                        scores["groundedness"], scores["completeness"]]
        scores["normalized_score"] = round(sum(numeric_dims) / (4 * SCORE_MAX), 4)

        return scores


# ── Convenience: score-to-label ──────────────────────────────────────────────
def score_label(score: float) -> str:
    """Convert a normalized [0,1] score to a human-readable label."""
    if score >= 0.8:
        return "Excellent"
    if score >= 0.6:
        return "Good"
    if score >= 0.4:
        return "Adequate"
    if score >= 0.2:
        return "Poor"
    return "Very Poor"
