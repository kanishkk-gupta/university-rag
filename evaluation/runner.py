"""
evaluation/runner.py
--------------------
Evaluation runner for the BMU University RAG system.

Implements:
  - Category-wise quantitative model comparison across the 7 professor-defined
    categories (Explanation, Code Retrieval, Dependency Understanding,
    Bug Analysis, Code Generation, Refactoring, RAG based Question)
  - LLM-as-Judge semantic scoring (correctness, relevance, groundedness,
    completeness, hallucination_flag) via OllamaJudge
  - Legacy token-F1 and semantic similarity scores stored alongside judge scores
  - Per-record JSONL output and two summary files:
      * summary_latest.json         — overall per-model summary
      * category_summary_latest.json — per-category × per-model breakdown
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from config import RAG_TOP_K
from rag.pipeline import RAGPipeline
from rag.context_builder import ContextBuilder
from rag.prompt import RAG_SYSTEM_PROMPT, build_user_prompt
from evaluation.models import get_dataset, get_available_models
from evaluation.llm_judge import OllamaJudge
from evaluation.metrics import (
    calculate_accuracy,
    calculate_relevance,
    calculate_recall_at_k,
    check_hallucination,
    calculate_semantic_similarity,
    aggregate_judge_scores,
    build_category_summary_record,
    finalize_category_record,
    get_system_resources,
)

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "reports"

# The 7 professor-defined evaluation categories
EVAL_CATEGORIES = [
    "Explanation",
    "Code Retrieval",
    "Dependency Understanding",
    "Bug Analysis",
    "Code Generation",
    "Refactoring",
    "RAG based Question",
]


# ─── Per-model overall summary builders ───────────────────────────────────────

def _build_empty_model_summary():
    return {
        "correct":            0,
        "total":              0,
        "latencies":          [],
        "relevance_sum":      0.0,
        "hallucination_sum":  0.0,
        "recall_sum":         0.0,
        "semantic_sim_sum":   0.0,
        "judge_score_sum":    0.0,
        "correctness_sum":    0.0,
        "groundedness_sum":   0.0,
        "completeness_sum":   0.0,
        "hallucination_flag_count": 0,
    }


def _finalise_overall_summary(summary: dict) -> dict:
    """Replace raw accumulators with human-readable averages."""
    final = {}
    for model, s in summary.items():
        total    = s["total"] or 1
        latencies = s["latencies"]
        final[model] = {
            "total_questions":          s["total"],
            "correct":                  s["correct"],
            "token_f1_accuracy":        round(s["correct"] / total, 4),
            "avg_relevance_token":      round(s["relevance_sum"] / total, 4),
            "avg_hallucination_numeric": round(s["hallucination_sum"] / total, 4),
            "avg_recall_at_k":          round(s["recall_sum"] / total, 4),
            "avg_semantic_similarity":  round(s["semantic_sim_sum"] / total, 4),
            "avg_judge_score":          round(s["judge_score_sum"] / total, 4),
            "avg_correctness_llm":      round(s["correctness_sum"] / total, 4),
            "avg_groundedness_llm":     round(s["groundedness_sum"] / total, 4),
            "avg_completeness_llm":     round(s["completeness_sum"] / total, 4),
            "hallucination_flag_rate":  round(s["hallucination_flag_count"] / total, 4),
            "avg_generation_latency_s": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
            "p95_generation_latency_s": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 3) if latencies else 0.0,
        }
    return final


# ─── Category summary builders ────────────────────────────────────────────────

def _build_category_summary_structure(models):
    """{ category: { model: accumulator_record } }"""
    return {
        cat: {m: build_category_summary_record() for m in models}
        for cat in EVAL_CATEGORIES
    }


def _finalise_category_summary(raw: dict) -> dict:
    return {
        cat: {model: finalize_category_record(rec) for model, rec in model_map.items()}
        for cat, model_map in raw.items()
    }


def _accumulate_into_category(
    cat_summary: dict,
    category: str,
    model_name: str,
    *,
    judge_scores: dict,
    sem_sim: float,
    token_f1_acc: float,
    recall: float,
    gen_latency: float,
    tokens: dict,
):
    """Update a category×model accumulator in place."""
    if category not in cat_summary:
        logger.warning(f"Unknown category '{category}' — skipping category accumulation.")
        return
    rec = cat_summary[category][model_name]
    rec["total"]                 += 1
    # LLM judge dimensions (normalized 0-1 via /5)
    rec["correctness_sum"]       += judge_scores["correctness"] / 5.0
    rec["relevance_sum"]         += judge_scores["relevance"] / 5.0
    rec["groundedness_sum"]      += judge_scores["groundedness"] / 5.0
    rec["completeness_sum"]      += judge_scores["completeness"] / 5.0
    if judge_scores.get("hallucination_flag"):
        rec["hallucination_count"] += 1
    if judge_scores["correctness"] >= 3:
        rec["llm_correct"]         += 1
    rec["semantic_sim_sum"]      += sem_sim
    rec["token_f1_sum"]          += token_f1_acc
    rec["recall_sum"]            += recall
    rec["latency_sum"]           += gen_latency
    rec["latencies"].append(gen_latency)
    rec["prompt_tokens_sum"]     += tokens.get("prompt_tokens", 0)
    rec["completion_tokens_sum"] += tokens.get("completion_tokens", 0)
    rec["total_tokens_sum"]      += tokens.get("total_tokens", 0)


# ─── Main evaluation function ─────────────────────────────────────────────────

def run_evaluation(mode: str = "end_to_end"):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    dataset = get_dataset()
    models  = get_available_models()

    if not models:
        logger.error("No OOM-safe models found in MODEL_CONFIGS. Aborting evaluation.")
        return

    # Initialise components
    rag   = RAGPipeline()
    judge = OllamaJudge()

    judge_available = judge.is_available()
    logger.info(
        f"LLM-as-Judge: {'ENABLED (model: ' + judge.model + ')' if judge_available else 'UNAVAILABLE — using token-F1 fallback'}"
    )

    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"run_{timestamp}.jsonl"

    # Summary accumulators
    overall_summary  = {m: _build_empty_model_summary() for m in models}
    category_summary = _build_category_summary_structure(models)

    logger.info(
        f"Starting evaluation: {len(dataset)} questions × {len(models)} model(s), "
        f"top_k={RAG_TOP_K}, mode={mode}."
    )
    logger.info(f"Categories covered: {list({q.get('category','?') for q in dataset})}")

    with open(results_file, "w") as f:
        for q in dataset:
            question   = q["question"]
            answerable = q["answerable"]
            expected   = q["expected_source"]
            category   = q.get("category", "Unknown")
            rubric     = q.get("judge_rubric", "")

            # 1. Retrieve once per question (fair cross-model comparison)
            t0 = time.time()
            retrieval_results         = rag.retriever.retrieve(question, top_k=RAG_TOP_K)
            context_str, sources      = ContextBuilder.build_context(retrieval_results)
            t_retrieval               = time.time() - t0

            recall = calculate_recall_at_k(retrieval_results, expected)

            # 2. Evaluate each model
            for model_name in models:
                sys_res = get_system_resources()
                t1      = time.time()

                system_prompt = RAG_SYSTEM_PROMPT.format(context=context_str)
                user_prompt   = build_user_prompt(question)

                if not context_str:
                    answer = "I couldn't find enough information in the BMU knowledge base to answer that reliably."
                    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                else:
                    try:
                        answer, tokens = rag.generator.generate(
                            system_prompt, user_prompt,
                            model_name=model_name,
                            return_usage=True,
                        )
                    except Exception as e:
                        logger.error(f"Generation error for model '{model_name}': {e}")
                        answer = f"Error: {e}"
                        tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

                t2          = time.time()
                gen_latency = t2 - t1

                # ── Legacy (token-F1) metrics ───────────────────────────────
                token_acc = calculate_accuracy(answer, q["reference_answer"], answerable)
                token_rel = calculate_relevance(answer, question)
                hal_num   = check_hallucination(answer, context_str)

                # ── New: semantic similarity ────────────────────────────────
                sem_sim = calculate_semantic_similarity(answer, q["reference_answer"])

                # ── New: LLM-as-Judge scores ────────────────────────────────
                judge_raw = judge.judge(
                    question        = question,
                    candidate_answer= answer,
                    reference_answer= q["reference_answer"],
                    context         = context_str,
                    category        = category,
                    rubric          = rubric,
                )
                judge_agg = aggregate_judge_scores(judge_raw)

                # ── Build per-record output ─────────────────────────────────
                record = {
                    "question_id":        q["id"],
                    "question":           question,
                    "category":           category,
                    "model":              model_name,
                    "mode":               mode,
                    "answerable":         answerable,
                    "answer":             answer,
                    "reference_answer":   q["reference_answer"],
                    "retrieval_latency_s": round(t_retrieval, 4),
                    "generation_latency_s": round(gen_latency, 4),
                    "total_latency_s":    round(gen_latency + t_retrieval, 4),
                    "tokens":             tokens,
                    "resources":          sys_res,
                    "metrics": {
                        # Legacy token-F1 metrics
                        "token_f1_accuracy": 1 if token_acc else 0,
                        "relevance_token":   token_rel,
                        "hallucination_numeric": hal_num,
                        "recall_at_k":       recall,
                        # Semantic similarity
                        "semantic_similarity": sem_sim,
                        # LLM-as-Judge scores (0-5 raw, 0-1 normalized)
                        "judge_correctness":  judge_raw["correctness"],
                        "judge_relevance":    judge_raw["relevance"],
                        "judge_groundedness": judge_raw["groundedness"],
                        "judge_completeness": judge_raw["completeness"],
                        "judge_hallucination_flag": judge_raw["hallucination_flag"],
                        "judge_normalized_score":   judge_raw["normalized_score"],
                        "judge_source":       judge_raw.get("judge_source", "unknown"),
                        "judge_reasoning":    judge_raw.get("reasoning", ""),
                    },
                    "timestamp": datetime.now().isoformat(),
                }

                # ── Accumulate overall per-model summary ────────────────────
                s = overall_summary[model_name]
                s["total"]            += 1
                if token_acc:
                    s["correct"]      += 1
                s["latencies"].append(gen_latency)
                s["relevance_sum"]    += token_rel
                s["hallucination_sum"] += hal_num
                s["recall_sum"]       += recall
                s["semantic_sim_sum"] += sem_sim
                s["judge_score_sum"]  += judge_raw["normalized_score"]
                s["correctness_sum"]  += judge_raw["correctness"] / 5.0
                s["groundedness_sum"] += judge_raw["groundedness"] / 5.0
                s["completeness_sum"] += judge_raw["completeness"] / 5.0
                if judge_raw.get("hallucination_flag"):
                    s["hallucination_flag_count"] += 1

                # ── Accumulate category × model summary ─────────────────────
                _accumulate_into_category(
                    category_summary, category, model_name,
                    judge_scores=judge_raw,
                    sem_sim=sem_sim,
                    token_f1_acc=1.0 if token_acc else 0.0,
                    recall=recall,
                    gen_latency=gen_latency,
                    tokens=tokens,
                )

                f.write(json.dumps(record) + "\n")
                f.flush()
                logger.info(
                    f"[{q['id']}] {category} | {model_name} | "
                    f"judge={judge_raw['normalized_score']:.2f} "
                    f"sem_sim={sem_sim:.2f} latency={gen_latency:.1f}s"
                )

    logger.info("Evaluation complete.")

    # ── Write overall summary ─────────────────────────────────────────────────
    final_overall = _finalise_overall_summary(overall_summary)
    summary_file  = RESULTS_DIR / "summary_latest.json"
    with open(summary_file, "w") as f:
        json.dump(final_overall, f, indent=2)

    # ── Write category summary ────────────────────────────────────────────────
    final_category = _finalise_category_summary(category_summary)
    cat_file       = RESULTS_DIR / "category_summary_latest.json"
    with open(cat_file, "w") as f:
        json.dump(final_category, f, indent=2)

    logger.info(f"Per-record results : {results_file}")
    logger.info(f"Overall summary    : {summary_file}")
    logger.info(f"Category summary   : {cat_file}")

    return {
        "overall":  final_overall,
        "category": final_category,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_evaluation()
