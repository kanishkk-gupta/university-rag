"""
evaluation/runner_parallel.py
------------------------------
Optimized batched evaluation runner.

Key optimization vs. runner.py:
  - Processes ALL questions per model before switching (better Ollama cache locality)
  - Judge calls and semantic similarity run in a ThreadPoolExecutor (overlap with retrieval)
  - Progress bar via tqdm (or fallback print)
  - Produces same output files: summary_latest.json + category_summary_latest.json

Usage:
  python3 -m evaluation.runner_parallel
"""

import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

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

EVAL_CATEGORIES = [
    "Explanation", "Code Retrieval", "Dependency Understanding",
    "Bug Analysis", "Code Generation", "Refactoring", "RAG based Question",
]

# Thread-safe write lock for the JSONL file
_write_lock = threading.Lock()


# ─── Summary builders (same as runner.py) ────────────────────────────────────

def _build_empty_model_summary():
    return {
        "correct": 0, "total": 0, "latencies": [],
        "relevance_sum": 0.0, "hallucination_sum": 0.0, "recall_sum": 0.0,
        "semantic_sim_sum": 0.0, "judge_score_sum": 0.0, "correctness_sum": 0.0,
        "groundedness_sum": 0.0, "completeness_sum": 0.0, "hallucination_flag_count": 0,
    }


def _finalise_overall_summary(summary: dict) -> dict:
    final = {}
    for model, s in summary.items():
        total = s["total"] or 1
        lats  = s["latencies"]
        final[model] = {
            "total_questions":           s["total"],
            "correct":                   s["correct"],
            "token_f1_accuracy":         round(s["correct"] / total, 4),
            "avg_relevance_token":       round(s["relevance_sum"] / total, 4),
            "avg_hallucination_numeric": round(s["hallucination_sum"] / total, 4),
            "avg_recall_at_k":           round(s["recall_sum"] / total, 4),
            "avg_semantic_similarity":   round(s["semantic_sim_sum"] / total, 4),
            "avg_judge_score":           round(s["judge_score_sum"] / total, 4),
            "avg_correctness_llm":       round(s["correctness_sum"] / total, 4),
            "avg_groundedness_llm":      round(s["groundedness_sum"] / total, 4),
            "avg_completeness_llm":      round(s["completeness_sum"] / total, 4),
            "hallucination_flag_rate":   round(s["hallucination_flag_count"] / total, 4),
            "avg_generation_latency_s":  round(sum(lats) / len(lats), 3) if lats else 0.0,
            "p95_generation_latency_s":  round(sorted(lats)[int(len(lats)*0.95)-1], 3) if lats else 0.0,
        }
    return final


def _build_category_structure(models):
    return {cat: {m: build_category_summary_record() for m in models} for cat in EVAL_CATEGORIES}


def _finalise_category_summary(raw: dict) -> dict:
    return {
        cat: {m: finalize_category_record(rec) for m, rec in model_map.items()}
        for cat, model_map in raw.items()
    }


def _accumulate(cat_summary, overall_summary, category, model_name,
                judge_scores, sem_sim, token_acc, recall, gen_latency, tokens):
    # Overall
    s = overall_summary[model_name]
    s["total"]            += 1
    if token_acc: s["correct"] += 1
    s["latencies"].append(gen_latency)
    s["relevance_sum"]     += calculate_relevance_placeholder()  # placeholder
    s["hallucination_sum"] += 0.0
    s["recall_sum"]        += recall
    s["semantic_sim_sum"]  += sem_sim
    s["judge_score_sum"]   += judge_scores["normalized_score"]
    s["correctness_sum"]   += judge_scores["correctness"] / 5.0
    s["groundedness_sum"]  += judge_scores["groundedness"] / 5.0
    s["completeness_sum"]  += judge_scores["completeness"] / 5.0
    if judge_scores.get("hallucination_flag"): s["hallucination_flag_count"] += 1

    # Category
    if category not in cat_summary: return
    rec = cat_summary[category][model_name]
    rec["total"]                += 1
    rec["correctness_sum"]      += judge_scores["correctness"] / 5.0
    rec["relevance_sum"]        += judge_scores["relevance"] / 5.0
    rec["groundedness_sum"]     += judge_scores["groundedness"] / 5.0
    rec["completeness_sum"]     += judge_scores["completeness"] / 5.0
    if judge_scores.get("hallucination_flag"): rec["hallucination_count"] += 1
    if judge_scores["correctness"] >= 3:       rec["llm_correct"]         += 1
    rec["semantic_sim_sum"]     += sem_sim
    rec["token_f1_sum"]         += 1.0 if token_acc else 0.0
    rec["recall_sum"]           += recall
    rec["latency_sum"]          += gen_latency
    rec["latencies"].append(gen_latency)
    rec["prompt_tokens_sum"]    += tokens.get("prompt_tokens", 0)
    rec["completion_tokens_sum"]+= tokens.get("completion_tokens", 0)
    rec["total_tokens_sum"]     += tokens.get("total_tokens", 0)


def calculate_relevance_placeholder():
    return 0.0  # will be filled properly


# ─── Worker: judge + semantic similarity (runs in thread) ─────────────────────

def _score_answer(judge: OllamaJudge, question: str, answer: str,
                  reference: str, context: str, category: str, rubric: str):
    """Compute judge scores and semantic similarity concurrently."""
    sem_sim    = calculate_semantic_similarity(answer, reference)
    judge_raw  = judge.judge(question, answer, reference, context, category, rubric)
    return sem_sim, judge_raw


# ─── Phase 1: Retrieve all contexts ──────────────────────────────────────────

def _retrieve_all(rag: RAGPipeline, dataset: list) -> list:
    """Retrieve context for every question upfront (sequential — fast)."""
    enriched = []
    for q in dataset:
        t0 = time.time()
        ret   = rag.retriever.retrieve(q["question"], top_k=RAG_TOP_K)
        ctx, srcs = ContextBuilder.build_context(ret)
        t_ret = time.time() - t0
        recall = calculate_recall_at_k(ret, q["expected_source"])
        enriched.append({
            **q,
            "context_str":      ctx,
            "sources":          srcs,
            "retrieval_results": ret,
            "retrieval_latency": round(t_ret, 4),
            "recall":           recall,
        })
    logger.info(f"Retrieval complete for {len(enriched)} questions.")
    return enriched


# ─── Phase 2: Generate — one model at a time (best for Ollama CPU) ────────────

def _generate_for_model(rag: RAGPipeline, enriched: list, model_name: str,
                        mode: str) -> list:
    """Generate answers for all questions with one model (batch per model)."""
    records = []
    for q in enriched:
        question   = q["question"]
        context_str = q["context_str"]

        sys_prompt  = RAG_SYSTEM_PROMPT.format(context=context_str)
        user_prompt = build_user_prompt(question)

        sys_res = get_system_resources()
        t1 = time.time()

        if not context_str:
            answer = "I couldn't find enough information in the BMU knowledge base to answer that reliably."
            tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        else:
            try:
                answer, tokens = rag.generator.generate(
                    sys_prompt, user_prompt, model_name=model_name, return_usage=True
                )
            except Exception as e:
                logger.error(f"Generation error [{model_name}] {q['id']}: {e}")
                answer = f"Error: {e}"
                tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        gen_latency = round(time.time() - t1, 4)
        token_acc   = calculate_accuracy(answer, q["reference_answer"], q["answerable"])

        records.append({
            "q":           q,
            "model":       model_name,
            "mode":        mode,
            "answer":      answer,
            "tokens":      tokens,
            "gen_latency": gen_latency,
            "token_acc":   token_acc,
            "sys_res":     sys_res,
        })

        logger.info(f"  [{q['id']}] {q['category']} | {model_name} | latency={gen_latency:.1f}s")

    return records


# ─── Phase 3: Score — parallel judge + semantic similarity ────────────────────

def _score_all(judge: OllamaJudge, records: list, max_workers: int = 4) -> list:
    """
    Score all records using ThreadPoolExecutor.
    Judge calls and semantic similarity can run in parallel since they don't
    block Ollama generation (they are separate API calls / local model calls).
    """
    scored = [None] * len(records)

    def _score_one(i, rec):
        q   = rec["q"]
        sem_sim, judge_raw = _score_answer(
            judge, q["question"], rec["answer"],
            q["reference_answer"], q["context_str"],
            q.get("category", "Unknown"), q.get("judge_rubric", "")
        )
        hal = check_hallucination(rec["answer"], q["context_str"])
        return i, sem_sim, judge_raw, hal

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_score_one, i, rec): i for i, rec in enumerate(records)}
        for future in as_completed(futures):
            i, sem_sim, judge_raw, hal = future.result()
            records[i]["sem_sim"]   = sem_sim
            records[i]["judge_raw"] = judge_raw
            records[i]["hal"]       = hal
            logger.info(
                f"  Scored [{records[i]['q']['id']}] {records[i]['model']} | "
                f"judge={judge_raw['normalized_score']:.2f} sem={sem_sim:.2f}"
            )

    return records


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_parallel_evaluation(mode: str = "end_to_end"):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    dataset = get_dataset()
    models  = get_available_models()

    if not models:
        logger.error("No OOM-safe models found. Aborting.")
        return

    rag   = RAGPipeline()
    judge = OllamaJudge()

    judge_available = judge.is_available()
    logger.info(f"LLM Judge: {'ENABLED (' + judge.model + ')' if judge_available else 'FALLBACK mode'}")
    logger.info(f"Batched mode: {len(models)} model(s) × {len(dataset)} questions")

    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"run_{timestamp}.jsonl"

    overall_summary  = {m: _build_empty_model_summary() for m in models}
    category_summary = _build_category_structure(models)

    # ── Phase 1: Retrieve all contexts (fast) ─────────────────────────────────
    logger.info("Phase 1: Retrieving contexts for all questions...")
    t_start   = time.time()
    enriched  = _retrieve_all(rag, dataset)
    t_retrieve = time.time() - t_start
    logger.info(f"Phase 1 complete in {t_retrieve:.1f}s")

    # ── Phase 2+3: Generate + Score, one model at a time ─────────────────────
    all_scored_records = []
    for model_name in models:
        logger.info(f"\nPhase 2: Generating with {model_name}...")
        t_gen_start = time.time()
        gen_records = _generate_for_model(rag, enriched, model_name, mode)
        logger.info(f"  Generation done in {time.time()-t_gen_start:.1f}s")

        logger.info(f"Phase 3: Scoring {len(gen_records)} answers (parallel threads)...")
        t_score_start = time.time()
        scored = _score_all(judge, gen_records, max_workers=3)
        logger.info(f"  Scoring done in {time.time()-t_score_start:.1f}s")

        all_scored_records.extend(scored)

    # ── Phase 4: Write results and build summaries ────────────────────────────
    logger.info("Phase 4: Writing results...")
    with open(results_file, "w") as f:
        for rec in all_scored_records:
            q           = rec["q"]
            category    = q.get("category", "Unknown")
            judge_raw   = rec["judge_raw"]
            sem_sim     = rec["sem_sim"]
            hal         = rec["hal"]
            gen_latency = rec["gen_latency"]
            token_acc   = rec["token_acc"]
            tokens      = rec["tokens"]

            record = {
                "question_id":        q["id"],
                "question":           q["question"],
                "category":           category,
                "model":              rec["model"],
                "mode":               rec["mode"],
                "answerable":         q["answerable"],
                "answer":             rec["answer"],
                "reference_answer":   q["reference_answer"],
                "retrieval_latency_s": q["retrieval_latency"],
                "generation_latency_s": gen_latency,
                "total_latency_s":    round(gen_latency + q["retrieval_latency"], 4),
                "tokens":             tokens,
                "resources":          rec["sys_res"],
                "metrics": {
                    "token_f1_accuracy":     1 if token_acc else 0,
                    "hallucination_numeric": hal,
                    "recall_at_k":           q["recall"],
                    "semantic_similarity":   sem_sim,
                    "judge_correctness":     judge_raw["correctness"],
                    "judge_relevance":       judge_raw["relevance"],
                    "judge_groundedness":    judge_raw["groundedness"],
                    "judge_completeness":    judge_raw["completeness"],
                    "judge_hallucination_flag": judge_raw["hallucination_flag"],
                    "judge_normalized_score":   judge_raw["normalized_score"],
                    "judge_source":          judge_raw.get("judge_source", "unknown"),
                    "judge_reasoning":       judge_raw.get("reasoning", ""),
                },
                "timestamp": datetime.now().isoformat(),
            }
            f.write(json.dumps(record) + "\n")

            # Accumulate
            s = overall_summary[rec["model"]]
            s["total"]            += 1
            if token_acc: s["correct"] += 1
            s["latencies"].append(gen_latency)
            s["recall_sum"]        += q["recall"]
            s["semantic_sim_sum"]  += sem_sim
            s["judge_score_sum"]   += judge_raw["normalized_score"]
            s["correctness_sum"]   += judge_raw["correctness"] / 5.0
            s["groundedness_sum"]  += judge_raw["groundedness"] / 5.0
            s["completeness_sum"]  += judge_raw["completeness"] / 5.0
            if judge_raw.get("hallucination_flag"): s["hallucination_flag_count"] += 1

            if category in category_summary:
                cr = category_summary[category][rec["model"]]
                cr["total"]               += 1
                cr["correctness_sum"]     += judge_raw["correctness"] / 5.0
                cr["relevance_sum"]       += judge_raw["relevance"] / 5.0
                cr["groundedness_sum"]    += judge_raw["groundedness"] / 5.0
                cr["completeness_sum"]    += judge_raw["completeness"] / 5.0
                if judge_raw.get("hallucination_flag"): cr["hallucination_count"] += 1
                if judge_raw["correctness"] >= 3:       cr["llm_correct"]         += 1
                cr["semantic_sim_sum"]    += sem_sim
                cr["token_f1_sum"]        += 1.0 if token_acc else 0.0
                cr["recall_sum"]          += q["recall"]
                cr["latency_sum"]         += gen_latency
                cr["latencies"].append(gen_latency)
                cr["prompt_tokens_sum"]   += tokens.get("prompt_tokens", 0)
                cr["completion_tokens_sum"]+= tokens.get("completion_tokens", 0)
                cr["total_tokens_sum"]    += tokens.get("total_tokens", 0)

    # ── Write summaries ───────────────────────────────────────────────────────
    final_overall  = _finalise_overall_summary(overall_summary)
    final_category = _finalise_category_summary(category_summary)

    summary_file = RESULTS_DIR / "summary_latest.json"
    cat_file     = RESULTS_DIR / "category_summary_latest.json"

    with open(summary_file, "w") as f:  json.dump(final_overall, f, indent=2)
    with open(cat_file, "w") as f:      json.dump(final_category, f, indent=2)

    total_time = time.time() - t_start
    logger.info(f"\n{'='*60}")
    logger.info(f"Evaluation complete in {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"Per-record results : {results_file}")
    logger.info(f"Overall summary    : {summary_file}")
    logger.info(f"Category summary   : {cat_file}")

    return {"overall": final_overall, "category": final_category}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_parallel_evaluation()
