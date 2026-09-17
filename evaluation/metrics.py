"""
evaluation/metrics.py
---------------------
Metric functions for the BMU University RAG evaluation pipeline.

Contains:
  - Token-F1 based metrics (legacy, kept for backward compatibility)
  - Semantic similarity via sentence-transformers (cosine similarity)
  - LLM-judge score aggregation helpers
  - System resource monitoring
"""

import re
import psutil
import logging
from collections import Counter
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ─── Lazy-loaded semantic model ───────────────────────────────────────────────
_semantic_model = None


def _get_semantic_model():
    """Load sentence-transformers model lazily (avoids loading at import time)."""
    global _semantic_model
    if _semantic_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            _semantic_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded all-MiniLM-L6-v2 for semantic similarity.")
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer: {e}. Semantic similarity will fall back to token-F1.")
    return _semantic_model


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _tokenize(text: str) -> Counter:
    """Lowercase word-token bag-of-words, filtering single-char tokens."""
    return Counter(t for t in re.findall(r"\b\w+\b", text.lower()) if len(t) > 1)


def _token_f1(pred: str, ref: str) -> float:
    """
    Micro-averaged token F1 between prediction and reference strings.
    Returns a float in [0.0, 1.0].
    """
    pred_tokens = _tokenize(pred)
    ref_tokens  = _tokenize(ref)
    common = sum((pred_tokens & ref_tokens).values())
    if common == 0:
        return 0.0
    precision = common / max(sum(pred_tokens.values()), 1)
    recall    = common / max(sum(ref_tokens.values()), 1)
    return 2 * precision * recall / (precision + recall)


# ─── Public metric functions ──────────────────────────────────────────────────

def calculate_accuracy(answer: str, reference_answer: str, answerable: bool) -> bool:
    """
    Returns True if the answer is considered correct.

    For unanswerable questions: checks that the model produced the canonical
    refusal phrase rather than a hallucinated answer.

    For answerable questions: uses token-overlap F1 against the reference answer
    (threshold 0.10 — deliberately low because reference answers are short
    gold-standard summaries, not verbatim transcripts).
    """
    refusal_phrase = "couldn't find enough information"

    if not answerable:
        # Correct iff the model declined to answer
        return refusal_phrase in answer.lower()

    # Answered an answerable question with a refusal → wrong
    if refusal_phrase in answer.lower():
        return False

    f1 = _token_f1(answer, reference_answer)
    return f1 > 0.10


def calculate_relevance(answer: str, question: str) -> int:
    """
    0 = irrelevant, 1 = partially relevant, 2 = directly relevant.

    Computed via token F1 between the answer and the question.
    Answers that are refusals are always 0.
    """
    refusal_phrase = "couldn't find enough information"

    if refusal_phrase in answer.lower():
        return 0

    overlap = _token_f1(answer, question)
    if overlap >= 0.25:
        return 2
    if overlap >= 0.08:
        return 1
    return 0


def calculate_semantic_similarity(answer: str, reference: str) -> float:
    """
    Cosine similarity between sentence-transformer embeddings of answer and reference.
    Returns a float in [0.0, 1.0].

    Falls back to token-F1 if the embedding model cannot be loaded.
    """
    if not answer.strip() or not reference.strip():
        return 0.0

    model = _get_semantic_model()
    if model is None:
        return _token_f1(answer, reference)

    try:
        import torch
        import torch.nn.functional as F
        embeddings = model.encode([answer, reference], convert_to_tensor=True)
        sim = F.cosine_similarity(embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0))
        score = float(sim.item())
        # Cosine similarity can be negative; clamp to [0, 1]
        return round(max(0.0, min(1.0, score)), 4)
    except Exception as e:
        logger.warning(f"Semantic similarity computation failed: {e}. Falling back to token-F1.")
        return _token_f1(answer, reference)


def calculate_recall_at_k(retrieved_docs: List[Dict[str, Any]], expected_docs: List[str]) -> float:
    """
    Checks what fraction of expected source documents appear in the retrieved set.
    Trivially 1.0 for unanswerable questions (empty expected_docs list).
    """
    if not expected_docs:
        return 1.0

    # Retriever always returns flat dicts; document_name is always top-level
    retrieved_names = [d.get("document_name", "") or "" for d in retrieved_docs]
    hits = sum(1 for e in expected_docs if e in retrieved_names)
    return hits / len(expected_docs)


def check_hallucination(answer: str, context: str) -> float:
    """
    Estimates hallucination rate in [0.0, 1.0].

    Strategy: extract numeric facts (numbers, dates, percentages) from the
    answer. Any fact that does NOT appear verbatim in the context is considered
    unsupported. The score is the fraction of unsupported facts.

    0.0 = fully grounded, 1.0 = fully hallucinated.
    """
    refusal_phrase = "couldn't find enough information"

    if refusal_phrase in answer.lower():
        return 0.0

    # Extract numeric tokens (integers, decimals, percentages, dates like "2026")
    fact_pattern = r"\b\d[\d,./%-]*\b"
    answer_facts = set(re.findall(fact_pattern, answer))
    if not answer_facts:
        return 0.0

    context_facts = set(re.findall(fact_pattern, context))
    unsupported = answer_facts - context_facts
    return round(len(unsupported) / len(answer_facts), 4)


# ─── LLM Judge score aggregation ─────────────────────────────────────────────

def aggregate_judge_scores(judge_output: Dict[str, Any]) -> Dict[str, float]:
    """
    Normalize judge output scores to [0, 1] range for consistent comparison.

    Input: judge dict with keys correctness, relevance, groundedness, completeness (0-5)
    Output: dict with same keys normalized to [0, 1], plus the existing normalized_score
    """
    dims = ["correctness", "relevance", "groundedness", "completeness"]
    result = {}
    for dim in dims:
        raw = judge_output.get(dim, 0)
        result[f"{dim}_norm"] = round(max(0.0, min(1.0, raw / 5.0)), 4)
    result["hallucination_flag"] = judge_output.get("hallucination_flag", False)
    result["normalized_score"]   = judge_output.get("normalized_score", 0.0)
    result["judge_source"]       = judge_output.get("judge_source", "unknown")
    return result


def build_category_summary_record() -> Dict[str, Any]:
    """Return an empty per-category accumulator record."""
    return {
        "total":                  0,
        "llm_correct":            0,     # correctness >= 3 from LLM judge
        "correctness_sum":        0.0,
        "relevance_sum":          0.0,
        "groundedness_sum":       0.0,
        "completeness_sum":       0.0,
        "hallucination_count":    0,
        "semantic_sim_sum":       0.0,
        "token_f1_sum":           0.0,
        "recall_sum":             0.0,
        "latency_sum":            0.0,
        "latencies":              [],
        "prompt_tokens_sum":      0,
        "completion_tokens_sum":  0,
        "total_tokens_sum":       0,
    }


def finalize_category_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Compute averages and clean up accumulator record."""
    n = rec["total"] or 1
    lats = rec["latencies"]
    return {
        "total_questions":           rec["total"],
        "llm_accuracy":              round(rec["llm_correct"] / n, 4),
        "avg_correctness":           round(rec["correctness_sum"] / n, 4),
        "avg_relevance":             round(rec["relevance_sum"] / n, 4),
        "avg_groundedness":          round(rec["groundedness_sum"] / n, 4),
        "avg_completeness":          round(rec["completeness_sum"] / n, 4),
        "hallucination_rate":        round(rec["hallucination_count"] / n, 4),
        "avg_semantic_similarity":   round(rec["semantic_sim_sum"] / n, 4),
        "avg_token_f1":              round(rec["token_f1_sum"] / n, 4),
        "avg_recall_at_k":           round(rec["recall_sum"] / n, 4),
        "avg_latency_s":             round(rec["latency_sum"] / n, 4),
        "p95_latency_s":             round(sorted(lats)[int(len(lats) * 0.95) - 1], 3) if lats else 0.0,
        "avg_prompt_tokens":         round(rec["prompt_tokens_sum"] / n),
        "avg_completion_tokens":     round(rec["completion_tokens_sum"] / n),
        "avg_total_tokens":          round(rec["total_tokens_sum"] / n),
    }


def get_system_resources() -> Dict[str, Any]:
    return {
        "cpu_percent":    psutil.cpu_percent(),
        "ram_mb":         round(psutil.virtual_memory().used / (1024 * 1024), 1),
        "gpu_utilization": "unavailable",
        "gpu_memory":      "unavailable",
    }
