import logging
import json
from pathlib import Path
from typing import List, Dict, Any

from retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

# Single source of truth — same dataset used by evaluation/runner.py
DATASET_PATH = Path(__file__).parent.parent / "evaluation" / "dataset.json"


def _load_retrieval_queries() -> List[Dict[str, str]]:
    """
    Load evaluation queries from the shared dataset.json.

    Filters out unanswerable questions (no expected source document) since
    retrieval evaluation is only meaningful when a ground-truth document exists.
    For multi-source questions the first listed source is used as the primary
    expected document.
    """
    with open(DATASET_PATH, "r") as f:
        dataset = json.load(f)

    queries = []
    for item in dataset:
        sources = item.get("expected_source", [])
        if not sources:
            continue  # skip unanswerable / out-of-scope questions
        queries.append({
            "query": item["question"],
            "expected_document": sources[0],
            # Carry all expected sources for multi-doc recall
            "all_expected_documents": sources,
        })
    return queries


def run_evaluation():
    retriever = Retriever.get_instance()

    eval_queries = _load_retrieval_queries()
    total_queries = len(eval_queries)

    recall_at_1 = 0
    recall_at_3 = 0
    recall_at_5 = 0
    mrr_sum     = 0.0

    failures = []

    print("\n" + "=" * 60)
    print("RETRIEVAL EVALUATION")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Questions: {total_queries}")
    print("=" * 60)

    for eval_data in eval_queries:
        query        = eval_data["query"]
        expected_doc = eval_data["expected_document"]
        all_expected = eval_data["all_expected_documents"]

        results = retriever.retrieve(query, top_k=5)

        # Find rank of the primary expected document
        rank = -1
        for i, res in enumerate(results):
            doc_name = res.get("document_name", "") or ""
            if expected_doc in doc_name:
                rank = i + 1
                break

        # Recall@K uses the primary expected document
        if rank == 1:
            recall_at_1 += 1
        if 1 <= rank <= 3:
            recall_at_3 += 1
        if 1 <= rank <= 5:
            recall_at_5 += 1

        if rank > 0:
            mrr_sum += 1.0 / rank
        else:
            top_doc  = results[0]["document_name"] if results else "None"
            top_text = results[0]["text"][:150]     if results else "None"
            failures.append({
                "query":    query,
                "expected": expected_doc,
                "top_1_doc":  top_doc,
                "top_1_text": top_text,
            })

        is_correct = "YES" if rank > 0 else "NO"
        print(f"\nQUERY:\n{query}")
        print(f"EXPECTED: {expected_doc}")
        if len(all_expected) > 1:
            print(f"  (also expects: {', '.join(all_expected[1:])})")
        print("TOP 5:")
        for i, res in enumerate(results):
            doc   = res.get("document_name", "Unknown")
            page  = res.get("page_start", "?")
            score = res.get("distance", 0)
            print(f"  {i+1}. {doc} / page {page} / dist={score:.4f}")
        print(f"CORRECT SOURCE: {is_correct}")

    print("\n" + "=" * 60)
    print("EVALUATION METRICS")
    print("=" * 60)
    print(f"Total Queries : {total_queries}")
    print(f"Recall@1      : {recall_at_1 / total_queries:.2%}")
    print(f"Recall@3      : {recall_at_3 / total_queries:.2%}")
    print(f"Recall@5      : {recall_at_5 / total_queries:.2%}")
    print(f"MRR           : {mrr_sum / total_queries:.4f}")

    if failures:
        print("\n" + "=" * 60)
        print(f"FAILURES ({len(failures)}/{total_queries})")
        print("=" * 60)
        for fail in failures:
            print(f"\nQuery    : {fail['query']}")
            print(f"Expected : {fail['expected']}")
            print(f"Got (#1) : {fail['top_1_doc']}")
            print(f"Snippet  : {fail['top_1_text']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_evaluation()
