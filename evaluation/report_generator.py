"""
evaluation/report_generator.py
------------------------------
Generates a structured Markdown report from evaluation results.

Reads:
  - evaluation/reports/category_summary_latest.json  (category × model breakdowns)
  - evaluation/reports/summary_latest.json           (overall per-model totals)

Writes:
  - WEEK4_CATEGORY_REPORT.md  (in the project root)

The report includes:
  - Executive summary with overall rankings
  - Per-category winner tables with all metric comparisons
  - Token-F1 vs. LLM-Judge vs. Semantic Similarity comparison
  - ASCII bar charts for key metrics
  - Methodology notes explaining LLM-as-Judge
"""

import json
import math
from pathlib import Path
from datetime import datetime

REPORTS_DIR  = Path(__file__).parent / "reports"
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_FILE  = PROJECT_ROOT / "WEEK4_CATEGORY_REPORT.md"

EVAL_CATEGORIES = [
    "Explanation",
    "Code Retrieval",
    "Dependency Understanding",
    "Bug Analysis",
    "Code Generation",
    "Refactoring",
    "RAG based Question",
]

METRIC_LABELS = {
    "llm_accuracy":            "LLM Accuracy (judge≥3/5)",
    "avg_correctness":         "Avg Correctness (0→1)",
    "avg_relevance":           "Avg Relevance (0→1)",
    "avg_groundedness":        "Avg Groundedness (0→1)",
    "avg_completeness":        "Avg Completeness (0→1)",
    "hallucination_rate":      "Hallucination Rate (lower=better)",
    "avg_semantic_similarity": "Avg Semantic Similarity (0→1)",
    "avg_token_f1":            "Avg Token-F1 (0→1)",
    "avg_recall_at_k":         "Retrieval Recall@K (0→1)",
    "avg_latency_s":           "Avg Latency (s)",
    "avg_total_tokens":        "Avg Token Usage",
}

HIGHER_IS_BETTER = {
    "llm_accuracy", "avg_correctness", "avg_relevance", "avg_groundedness",
    "avg_completeness", "avg_semantic_similarity", "avg_token_f1", "avg_recall_at_k",
}
LOWER_IS_BETTER = {"hallucination_rate", "avg_latency_s", "avg_total_tokens"}


# ─── Utility helpers ──────────────────────────────────────────────────────────

def _bar(value: float, max_val: float = 1.0, width: int = 20) -> str:
    """ASCII progress bar."""
    filled = math.floor((value / max(max_val, 1e-9)) * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _winner(model_scores: dict, metric: str) -> str:
    """Return the model name that wins for a given metric."""
    if not model_scores:
        return "N/A"
    if metric in HIGHER_IS_BETTER:
        return max(model_scores, key=lambda m: model_scores[m].get(metric, 0))
    if metric in LOWER_IS_BETTER:
        return min(model_scores, key=lambda m: model_scores[m].get(metric, float("inf")))
    return "N/A"


def _format_val(metric: str, value) -> str:
    if metric in ("avg_latency_s",):
        return f"{value:.2f}s"
    if metric in ("avg_total_tokens", "avg_prompt_tokens", "avg_completion_tokens"):
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _medal(model: str, winner: str) -> str:
    return " 🏆" if model == winner else ""


# ─── Section builders ─────────────────────────────────────────────────────────

def _overall_ranking_section(overall: dict) -> str:
    models = list(overall.keys())
    lines  = ["## 📊 Overall Model Rankings\n"]
    lines.append("> Ranked by **LLM-Judge normalized score** (semantic quality).\n")

    # Sort by avg_judge_score
    ranked = sorted(models, key=lambda m: overall[m].get("avg_judge_score", 0), reverse=True)

    header  = "| Rank | Model | LLM Judge ↑ | Semantic Sim ↑ | Token-F1 ↑ | Recall@K ↑ | Hallucination ↓ | Avg Latency |\n"
    divider = "|------|-------|------------|----------------|-----------|-----------|-----------------|-------------|\n"
    lines.append(header)
    lines.append(divider)

    rank_emojis = ["🥇", "🥈", "🥉"] + ["  "] * 10
    for i, m in enumerate(ranked):
        s = overall[m]
        lines.append(
            f"| {rank_emojis[i]} {i+1} | **{m}** "
            f"| {s.get('avg_judge_score', 0):.4f} "
            f"| {s.get('avg_semantic_similarity', 0):.4f} "
            f"| {s.get('token_f1_accuracy', 0):.4f} "
            f"| {s.get('avg_recall_at_k', 0):.4f} "
            f"| {s.get('hallucination_flag_rate', 0):.4f} "
            f"| {s.get('avg_generation_latency_s', 0):.2f}s |\n"
        )
    lines.append("\n")
    return "".join(lines)


def _category_winner_matrix(category_data: dict) -> str:
    lines  = ["## 🏅 Category Winner Matrix\n"]
    lines.append(
        "> For each category, the metric determines which model is **best suited** for that task type.\n\n"
    )
    models = []
    for cat in EVAL_CATEGORIES:
        if cat in category_data:
            models = list(category_data[cat].keys())
            break

    # Header
    col_heads = " | ".join([f"**{m}** (Judge↑)" for m in models])
    lines.append(f"| Category | {col_heads} | 🏆 Winner |\n")
    lines.append("|" + "---|" * (len(models) + 2) + "\n")

    for cat in EVAL_CATEGORIES:
        if cat not in category_data:
            lines.append(f"| {cat} | " + " | ".join(["N/A"] * len(models)) + " | N/A |\n")
            continue
        model_scores = category_data[cat]
        scores_str   = " | ".join(
            [f"{model_scores[m].get('avg_correctness', 0):.3f}" for m in models]
        )
        win_model    = _winner(model_scores, "avg_correctness")
        lines.append(f"| {cat} | {scores_str} | **{win_model}** |\n")

    lines.append("\n")
    return "".join(lines)


def _category_detail_section(cat: str, model_scores: dict) -> str:
    models = list(model_scores.keys())
    lines  = [f"### 🔷 {cat}\n\n"]

    # Key metrics table
    key_metrics = [
        "llm_accuracy", "avg_correctness", "avg_relevance",
        "avg_groundedness", "avg_completeness",
        "hallucination_rate", "avg_semantic_similarity",
        "avg_recall_at_k", "avg_latency_s", "avg_total_tokens",
    ]
    header  = "| Metric | " + " | ".join([f"**{m}**" for m in models]) + " | Winner |\n"
    divider = "|--------|" + "--------|" * len(models) + "--------|\n"
    lines.append(header)
    lines.append(divider)

    for metric in key_metrics:
        label   = METRIC_LABELS.get(metric, metric)
        win_m   = _winner(model_scores, metric)
        vals    = []
        for m in models:
            v      = model_scores[m].get(metric, 0)
            medal  = _medal(m, win_m)
            vals.append(f"{_format_val(metric, v)}{medal}")
        lines.append(f"| {label} | " + " | ".join(vals) + f" | **{win_m}** |\n")

    lines.append("\n")

    # ASCII bar charts for top 3 key metrics
    bar_metrics = [
        ("LLM Correctness", "avg_correctness", 1.0),
        ("Semantic Similarity", "avg_semantic_similarity", 1.0),
        ("Avg Latency (s)", "avg_latency_s", None),
    ]
    lines.append("**Visual Comparison (LLM Correctness | Semantic Similarity | Latency)**\n\n")
    lines.append("```\n")
    for bm_label, bm_key, bm_max in bar_metrics:
        vals_raw = {m: model_scores[m].get(bm_key, 0) for m in models}
        max_val  = bm_max or max(vals_raw.values(), default=1)
        lines.append(f"{bm_label}:\n")
        for m in models:
            v = vals_raw[m]
            lines.append(f"  {m:<28} {_bar(v, max_val)} {v:.3f}\n")
        lines.append("\n")
    lines.append("```\n\n")

    return "".join(lines)


def _methodology_section() -> str:
    return """## 🔬 Methodology

### Evaluation Approach
This report compares models using **two complementary scoring systems**:

| Approach | Method | What it measures |
|----------|--------|-----------------|
| **Token-F1 (legacy)** | Bag-of-words overlap | Lexical keyword overlap with reference |
| **Semantic Similarity** | Sentence-transformer cosine similarity (`all-MiniLM-L6-v2`) | Meaning-preserving similarity |
| **LLM-as-Judge** | Local Ollama LLM scores answers on 4 dimensions | Semantic correctness, relevance, groundedness, completeness |

### LLM-as-Judge Dimensions
| Dimension | Scale | Description |
|-----------|-------|-------------|
| Correctness | 0–5 | Semantic accuracy vs. reference answer |
| Relevance | 0–5 | How well the answer addresses the question |
| Groundedness | 0–5 | Grounded in retrieved context (anti-hallucination) |
| Completeness | 0–5 | Coverage of all required answer aspects |
| Hallucination Flag | bool | Whether the answer contains unsupported facts |

### Why LLM-as-Judge is Superior to Token-F1
- **Token-F1** fails when the answer is semantically correct but uses different wording
- **Semantic similarity** captures meaning but not correctness nuances
- **LLM-as-Judge** evaluates rubric-guided multi-dimensional quality, matching human judgment

### Category Definitions
| Category | Description |
|----------|-------------|
| Explanation | Questions requiring clear explanation of university policies |
| Code Retrieval | Questions requiring identification of the correct source document |
| Dependency Understanding | Questions requiring cross-document reasoning |
| Bug Analysis | Questions about edge cases, exceptions, and special scenarios |
| Code Generation | Questions requiring structured, formatted output (lists, tables) |
| Refactoring | Questions requiring simplification/rephrasing of policy text |
| RAG based Question | Multi-document retrieval and synthesis questions |

"""


def _old_vs_new_comparison(overall: dict) -> str:
    models = list(overall.keys())
    lines  = ["## 📈 Old (Token-F1) vs. New (LLM-Judge + Semantic) Comparison\n\n"]
    lines.append("> This table directly shows why the old approach was inadequate.\n\n")
    header  = "| Model | Old Token-F1 ↑ | New Semantic Sim ↑ | New LLM Judge ↑ | Difference |\n"
    divider = "|-------|---------------|-------------------|----------------|------------|\n"
    lines.append(header)
    lines.append(divider)
    for m in models:
        s      = overall[m]
        old_f1 = s.get("token_f1_accuracy", 0)
        new_ss = s.get("avg_semantic_similarity", 0)
        new_lj = s.get("avg_judge_score", 0)
        diff   = new_lj - old_f1
        arrow  = "↑" if diff > 0 else "↓"
        lines.append(
            f"| **{m}** | {old_f1:.4f} | {new_ss:.4f} | {new_lj:.4f} | {diff:+.4f} {arrow} |\n"
        )
    lines.append(
        "\n> **Interpretation**: A large difference between Token-F1 and LLM-Judge scores "
        "reveals cases where models are semantically correct but lexically different from the "
        "reference, which Token-F1 would incorrectly penalize.\n\n"
    )
    return "".join(lines)


def _answer_quality_summary(overall: dict) -> str:
    models = list(overall.keys())
    lines  = ["## 📋 Per-Model Detailed Summary\n\n"]
    for m in models:
        s = overall[m]
        lines.append(f"### {m}\n")
        lines.append(f"- **Questions evaluated**: {s.get('total_questions', 0)}\n")
        lines.append(f"- **LLM Judge Score** (normalized 0→1): `{s.get('avg_judge_score', 0):.4f}`\n")
        lines.append(f"- **Semantic Similarity** (0→1): `{s.get('avg_semantic_similarity', 0):.4f}`\n")
        lines.append(f"- **Token-F1 Accuracy** (legacy): `{s.get('token_f1_accuracy', 0):.4f}`\n")
        lines.append(f"- **Avg Correctness** (LLM): `{s.get('avg_correctness_llm', 0):.4f}`\n")
        lines.append(f"- **Avg Groundedness** (LLM): `{s.get('avg_groundedness_llm', 0):.4f}`\n")
        lines.append(f"- **Avg Completeness** (LLM): `{s.get('avg_completeness_llm', 0):.4f}`\n")
        lines.append(f"- **Hallucination Flag Rate**: `{s.get('hallucination_flag_rate', 0):.4f}`\n")
        lines.append(f"- **Retrieval Recall@K**: `{s.get('avg_recall_at_k', 0):.4f}`\n")
        lines.append(f"- **Avg Generation Latency**: `{s.get('avg_generation_latency_s', 0):.2f}s`\n")
        lines.append(f"- **P95 Generation Latency**: `{s.get('p95_generation_latency_s', 0):.2f}s`\n\n")
    return "".join(lines)


# ─── Main report generator ────────────────────────────────────────────────────

def generate_report(
    category_summary_path: Path = None,
    overall_summary_path: Path  = None,
    output_path: Path            = None,
) -> Path:
    cat_path  = category_summary_path or REPORTS_DIR / "category_summary_latest.json"
    over_path = overall_summary_path  or REPORTS_DIR / "summary_latest.json"
    out_path  = output_path           or OUTPUT_FILE

    if not cat_path.exists():
        raise FileNotFoundError(f"Category summary not found: {cat_path}")
    if not over_path.exists():
        raise FileNotFoundError(f"Overall summary not found: {over_path}")

    with open(cat_path) as f:
        category_data = json.load(f)
    with open(over_path) as f:
        overall_data = json.load(f)

    models = list(overall_data.keys())
    ts     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections = []

    # ── Title ──────────────────────────────────────────────────────────────────
    sections.append(f"""# Week 4: Category-Wise Model Comparison Report

**Generated**: {ts}  
**Models Evaluated**: {', '.join(f'`{m}`' for m in models)}  
**Evaluation Dataset**: 35 questions across 7 categories (5 per category)  
**Scoring**: LLM-as-Judge + Sentence-Transformer Semantic Similarity + Token-F1 (legacy)  

---

""")

    # ── Methodology (before results) ───────────────────────────────────────────
    sections.append(_methodology_section())
    sections.append("---\n\n")

    # ── Overall ranking ────────────────────────────────────────────────────────
    sections.append(_overall_ranking_section(overall_data))
    sections.append("---\n\n")

    # ── Old vs New comparison ──────────────────────────────────────────────────
    sections.append(_old_vs_new_comparison(overall_data))
    sections.append("---\n\n")

    # ── Category winner matrix ─────────────────────────────────────────────────
    sections.append(_category_winner_matrix(category_data))
    sections.append("---\n\n")

    # ── Per-category detailed breakdowns ──────────────────────────────────────
    sections.append("## 📂 Category-Wise Detailed Results\n\n")
    for cat in EVAL_CATEGORIES:
        if cat in category_data:
            sections.append(_category_detail_section(cat, category_data[cat]))
        else:
            sections.append(f"### 🔷 {cat}\n\n> No results available for this category.\n\n")

    sections.append("---\n\n")

    # ── Per-model detailed summary ─────────────────────────────────────────────
    sections.append(_answer_quality_summary(overall_data))
    sections.append("---\n\n")

    # ── Footer ─────────────────────────────────────────────────────────────────
    sections.append(f"""## 📝 Notes

- All models ran against the **same 35-question evaluation dataset** (same retrieval context per question).
- **Retrieval** is shared across models (fair comparison — only generation differs).
- **LLM-as-Judge** uses `{models[0] if models else 'qwen2.5-coder:1.5b'}` as the judge model via local Ollama.
- Results generated at: `{ts}`
""")

    report_content = "".join(sections)
    out_path.write_text(report_content, encoding="utf-8")
    print(f"✅ Report written to: {out_path}")
    return out_path


if __name__ == "__main__":
    path = generate_report()
    print(f"Report: {path}")
