# Week 4: Category-Wise Model Comparison Report

**Generated**: 2026-09-17 03:31:59  
**Models Evaluated**: `starcoder2:3b`, `qwen2.5-coder:1.5b`  
**Evaluation Dataset**: 35 questions across 7 categories (5 per category)  
**Scoring**: LLM-as-Judge + Sentence-Transformer Semantic Similarity + Token-F1 (legacy)  

---

## 🔬 Methodology

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

---

## 📊 Overall Model Rankings
> Ranked by **LLM-Judge normalized score** (semantic quality).
| Rank | Model | LLM Judge ↑ | Semantic Sim ↑ | Token-F1 ↑ | Recall@K ↑ | Hallucination ↓ | Avg Latency |
|------|-------|------------|----------------|-----------|-----------|-----------------|-------------|
| 🥇 1 | **starcoder2:3b** | 0.6700 | 0.4678 | 0.1714 | 0.7548 | 0.0286 | 16.72s |
| 🥈 2 | **qwen2.5-coder:1.5b** | 0.6129 | 0.5706 | 0.7429 | 0.7548 | 0.0286 | 16.31s |

---

## 📈 Old (Token-F1) vs. New (LLM-Judge + Semantic) Comparison

> This table directly shows why the old approach was inadequate.

| Model | Old Token-F1 ↑ | New Semantic Sim ↑ | New LLM Judge ↑ | Difference |
|-------|---------------|-------------------|----------------|------------|
| **starcoder2:3b** | 0.1714 | 0.4678 | 0.6700 | +0.4986 ↑ |
| **qwen2.5-coder:1.5b** | 0.7429 | 0.5706 | 0.6129 | -0.1300 ↓ |

> **Interpretation**: A large difference between Token-F1 and LLM-Judge scores reveals cases where models are semantically correct but lexically different from the reference, which Token-F1 would incorrectly penalize.

---

## 🏅 Category Winner Matrix
> For each category, the metric determines which model is **best suited** for that task type.

| Category | **starcoder2:3b** (Judge↑) | **qwen2.5-coder:1.5b** (Judge↑) | 🏆 Winner |
|---|---|---|---|
| Explanation | 0.800 | 0.680 | **starcoder2:3b** |
| Code Retrieval | 0.800 | 0.520 | **starcoder2:3b** |
| Dependency Understanding | 0.720 | 0.800 | **qwen2.5-coder:1.5b** |
| Bug Analysis | 0.640 | 0.600 | **starcoder2:3b** |
| Code Generation | 0.440 | 0.360 | **starcoder2:3b** |
| Refactoring | 0.400 | 0.480 | **qwen2.5-coder:1.5b** |
| RAG based Question | 0.600 | 0.640 | **qwen2.5-coder:1.5b** |

---

## 📂 Category-Wise Detailed Results

### 🔷 Explanation

| Metric | **starcoder2:3b** | **qwen2.5-coder:1.5b** | Winner |
|--------|--------|--------|--------|
| LLM Accuracy (judge≥3/5) | 1.0000 🏆 | 0.8000 | **starcoder2:3b** |
| Avg Correctness (0→1) | 0.8000 🏆 | 0.6800 | **starcoder2:3b** |
| Avg Relevance (0→1) | 1.0000 🏆 | 0.8800 | **starcoder2:3b** |
| Avg Groundedness (0→1) | 0.8000 🏆 | 0.7600 | **starcoder2:3b** |
| Avg Completeness (0→1) | 0.6400 🏆 | 0.5200 | **starcoder2:3b** |
| Hallucination Rate (lower=better) | 0.0000 🏆 | 0.0000 | **starcoder2:3b** |
| Avg Semantic Similarity (0→1) | 0.5283 | 0.7080 🏆 | **qwen2.5-coder:1.5b** |
| Retrieval Recall@K (0→1) | 1.0000 🏆 | 1.0000 | **starcoder2:3b** |
| Avg Latency (s) | 15.24s 🏆 | 16.38s | **starcoder2:3b** |
| Avg Token Usage | 253 🏆 | 1195 | **starcoder2:3b** |

**Visual Comparison (LLM Correctness | Semantic Similarity | Latency)**

```
LLM Correctness:
  starcoder2:3b                ████████████████░░░░ 0.800
  qwen2.5-coder:1.5b           █████████████░░░░░░░ 0.680

Semantic Similarity:
  starcoder2:3b                ██████████░░░░░░░░░░ 0.528
  qwen2.5-coder:1.5b           ██████████████░░░░░░ 0.708

Avg Latency (s):
  starcoder2:3b                ██████████████████░░ 15.245
  qwen2.5-coder:1.5b           ████████████████████ 16.381

```

### 🔷 Code Retrieval

| Metric | **starcoder2:3b** | **qwen2.5-coder:1.5b** | Winner |
|--------|--------|--------|--------|
| LLM Accuracy (judge≥3/5) | 1.0000 🏆 | 0.6000 | **starcoder2:3b** |
| Avg Correctness (0→1) | 0.8000 🏆 | 0.5200 | **starcoder2:3b** |
| Avg Relevance (0→1) | 1.0000 🏆 | 0.6000 | **starcoder2:3b** |
| Avg Groundedness (0→1) | 0.8000 🏆 | 0.5200 | **starcoder2:3b** |
| Avg Completeness (0→1) | 0.6000 🏆 | 0.4400 | **starcoder2:3b** |
| Hallucination Rate (lower=better) | 0.0000 🏆 | 0.0000 | **starcoder2:3b** |
| Avg Semantic Similarity (0→1) | 0.5730 🏆 | 0.5156 | **starcoder2:3b** |
| Retrieval Recall@K (0→1) | 0.6000 🏆 | 0.6000 | **starcoder2:3b** |
| Avg Latency (s) | 15.90s | 12.66s 🏆 | **qwen2.5-coder:1.5b** |
| Avg Token Usage | 291 🏆 | 1001 | **starcoder2:3b** |

**Visual Comparison (LLM Correctness | Semantic Similarity | Latency)**

```
LLM Correctness:
  starcoder2:3b                ████████████████░░░░ 0.800
  qwen2.5-coder:1.5b           ██████████░░░░░░░░░░ 0.520

Semantic Similarity:
  starcoder2:3b                ███████████░░░░░░░░░ 0.573
  qwen2.5-coder:1.5b           ██████████░░░░░░░░░░ 0.516

Avg Latency (s):
  starcoder2:3b                ████████████████████ 15.898
  qwen2.5-coder:1.5b           ███████████████░░░░░ 12.664

```

### 🔷 Dependency Understanding

| Metric | **starcoder2:3b** | **qwen2.5-coder:1.5b** | Winner |
|--------|--------|--------|--------|
| LLM Accuracy (judge≥3/5) | 1.0000 🏆 | 1.0000 | **starcoder2:3b** |
| Avg Correctness (0→1) | 0.7200 | 0.8000 🏆 | **qwen2.5-coder:1.5b** |
| Avg Relevance (0→1) | 0.8800 | 1.0000 🏆 | **qwen2.5-coder:1.5b** |
| Avg Groundedness (0→1) | 0.7600 | 0.8000 🏆 | **qwen2.5-coder:1.5b** |
| Avg Completeness (0→1) | 0.6000 | 0.6400 🏆 | **qwen2.5-coder:1.5b** |
| Hallucination Rate (lower=better) | 0.0000 🏆 | 0.0000 | **starcoder2:3b** |
| Avg Semantic Similarity (0→1) | 0.6159 | 0.7845 🏆 | **qwen2.5-coder:1.5b** |
| Retrieval Recall@K (0→1) | 0.7000 🏆 | 0.7000 | **starcoder2:3b** |
| Avg Latency (s) | 16.62s 🏆 | 21.76s | **starcoder2:3b** |
| Avg Token Usage | 292 🏆 | 1472 | **starcoder2:3b** |

**Visual Comparison (LLM Correctness | Semantic Similarity | Latency)**

```
LLM Correctness:
  starcoder2:3b                ██████████████░░░░░░ 0.720
  qwen2.5-coder:1.5b           ████████████████░░░░ 0.800

Semantic Similarity:
  starcoder2:3b                ████████████░░░░░░░░ 0.616
  qwen2.5-coder:1.5b           ███████████████░░░░░ 0.784

Avg Latency (s):
  starcoder2:3b                ███████████████░░░░░ 16.617
  qwen2.5-coder:1.5b           ████████████████████ 21.765

```

### 🔷 Bug Analysis

| Metric | **starcoder2:3b** | **qwen2.5-coder:1.5b** | Winner |
|--------|--------|--------|--------|
| LLM Accuracy (judge≥3/5) | 1.0000 🏆 | 0.8000 | **starcoder2:3b** |
| Avg Correctness (0→1) | 0.6400 🏆 | 0.6000 | **starcoder2:3b** |
| Avg Relevance (0→1) | 0.7600 | 0.9200 🏆 | **qwen2.5-coder:1.5b** |
| Avg Groundedness (0→1) | 0.7200 | 0.7600 🏆 | **qwen2.5-coder:1.5b** |
| Avg Completeness (0→1) | 0.6000 🏆 | 0.5600 | **starcoder2:3b** |
| Hallucination Rate (lower=better) | 0.0000 🏆 | 0.0000 | **starcoder2:3b** |
| Avg Semantic Similarity (0→1) | 0.3555 | 0.4688 🏆 | **qwen2.5-coder:1.5b** |
| Retrieval Recall@K (0→1) | 0.9000 🏆 | 0.9000 | **starcoder2:3b** |
| Avg Latency (s) | 18.86s 🏆 | 21.32s | **starcoder2:3b** |
| Avg Token Usage | 294 🏆 | 1439 | **starcoder2:3b** |

**Visual Comparison (LLM Correctness | Semantic Similarity | Latency)**

```
LLM Correctness:
  starcoder2:3b                ████████████░░░░░░░░ 0.640
  qwen2.5-coder:1.5b           ████████████░░░░░░░░ 0.600

Semantic Similarity:
  starcoder2:3b                ███████░░░░░░░░░░░░░ 0.355
  qwen2.5-coder:1.5b           █████████░░░░░░░░░░░ 0.469

Avg Latency (s):
  starcoder2:3b                █████████████████░░░ 18.859
  qwen2.5-coder:1.5b           ████████████████████ 21.320

```

### 🔷 Code Generation

| Metric | **starcoder2:3b** | **qwen2.5-coder:1.5b** | Winner |
|--------|--------|--------|--------|
| LLM Accuracy (judge≥3/5) | 0.6000 🏆 | 0.2000 | **starcoder2:3b** |
| Avg Correctness (0→1) | 0.4400 🏆 | 0.3600 | **starcoder2:3b** |
| Avg Relevance (0→1) | 0.6000 🏆 | 0.4400 | **starcoder2:3b** |
| Avg Groundedness (0→1) | 0.6800 🏆 | 0.4400 | **starcoder2:3b** |
| Avg Completeness (0→1) | 0.4000 🏆 | 0.3600 | **starcoder2:3b** |
| Hallucination Rate (lower=better) | 0.0000 🏆 | 0.0000 | **starcoder2:3b** |
| Avg Semantic Similarity (0→1) | 0.5452 🏆 | 0.4500 | **starcoder2:3b** |
| Retrieval Recall@K (0→1) | 0.5333 🏆 | 0.5333 | **starcoder2:3b** |
| Avg Latency (s) | 15.68s | 13.24s 🏆 | **qwen2.5-coder:1.5b** |
| Avg Token Usage | 293 🏆 | 1130 | **starcoder2:3b** |

**Visual Comparison (LLM Correctness | Semantic Similarity | Latency)**

```
LLM Correctness:
  starcoder2:3b                ████████░░░░░░░░░░░░ 0.440
  qwen2.5-coder:1.5b           ███████░░░░░░░░░░░░░ 0.360

Semantic Similarity:
  starcoder2:3b                ██████████░░░░░░░░░░ 0.545
  qwen2.5-coder:1.5b           █████████░░░░░░░░░░░ 0.450

Avg Latency (s):
  starcoder2:3b                ████████████████████ 15.679
  qwen2.5-coder:1.5b           ████████████████░░░░ 13.238

```

### 🔷 Refactoring

| Metric | **starcoder2:3b** | **qwen2.5-coder:1.5b** | Winner |
|--------|--------|--------|--------|
| LLM Accuracy (judge≥3/5) | 0.6000 🏆 | 0.4000 | **starcoder2:3b** |
| Avg Correctness (0→1) | 0.4000 | 0.4800 🏆 | **qwen2.5-coder:1.5b** |
| Avg Relevance (0→1) | 0.5600 🏆 | 0.5200 | **starcoder2:3b** |
| Avg Groundedness (0→1) | 0.6800 🏆 | 0.5200 | **starcoder2:3b** |
| Avg Completeness (0→1) | 0.3600 | 0.4400 🏆 | **qwen2.5-coder:1.5b** |
| Hallucination Rate (lower=better) | 0.0000 🏆 | 0.0000 | **starcoder2:3b** |
| Avg Semantic Similarity (0→1) | 0.3735 | 0.4949 🏆 | **qwen2.5-coder:1.5b** |
| Retrieval Recall@K (0→1) | 1.0000 🏆 | 1.0000 | **starcoder2:3b** |
| Avg Latency (s) | 15.71s | 11.04s 🏆 | **qwen2.5-coder:1.5b** |
| Avg Token Usage | 292 🏆 | 1085 | **starcoder2:3b** |

**Visual Comparison (LLM Correctness | Semantic Similarity | Latency)**

```
LLM Correctness:
  starcoder2:3b                ████████░░░░░░░░░░░░ 0.400
  qwen2.5-coder:1.5b           █████████░░░░░░░░░░░ 0.480

Semantic Similarity:
  starcoder2:3b                ███████░░░░░░░░░░░░░ 0.373
  qwen2.5-coder:1.5b           █████████░░░░░░░░░░░ 0.495

Avg Latency (s):
  starcoder2:3b                ████████████████████ 15.711
  qwen2.5-coder:1.5b           ██████████████░░░░░░ 11.037

```

### 🔷 RAG based Question

| Metric | **starcoder2:3b** | **qwen2.5-coder:1.5b** | Winner |
|--------|--------|--------|--------|
| LLM Accuracy (judge≥3/5) | 0.8000 🏆 | 0.8000 | **starcoder2:3b** |
| Avg Correctness (0→1) | 0.6000 | 0.6400 🏆 | **qwen2.5-coder:1.5b** |
| Avg Relevance (0→1) | 0.7600 | 0.8000 🏆 | **qwen2.5-coder:1.5b** |
| Avg Groundedness (0→1) | 0.6400 🏆 | 0.6400 | **starcoder2:3b** |
| Avg Completeness (0→1) | 0.5200 🏆 | 0.5200 | **starcoder2:3b** |
| Hallucination Rate (lower=better) | 0.2000 🏆 | 0.2000 | **starcoder2:3b** |
| Avg Semantic Similarity (0→1) | 0.2828 | 0.5725 🏆 | **qwen2.5-coder:1.5b** |
| Retrieval Recall@K (0→1) | 0.5500 🏆 | 0.5500 | **starcoder2:3b** |
| Avg Latency (s) | 19.05s | 17.77s 🏆 | **qwen2.5-coder:1.5b** |
| Avg Token Usage | 293 🏆 | 1601 | **starcoder2:3b** |

**Visual Comparison (LLM Correctness | Semantic Similarity | Latency)**

```
LLM Correctness:
  starcoder2:3b                ████████████░░░░░░░░ 0.600
  qwen2.5-coder:1.5b           ████████████░░░░░░░░ 0.640

Semantic Similarity:
  starcoder2:3b                █████░░░░░░░░░░░░░░░ 0.283
  qwen2.5-coder:1.5b           ███████████░░░░░░░░░ 0.573

Avg Latency (s):
  starcoder2:3b                ████████████████████ 19.048
  qwen2.5-coder:1.5b           ██████████████████░░ 17.771

```

---

## 📋 Per-Model Detailed Summary

### starcoder2:3b
- **Questions evaluated**: 35
- **LLM Judge Score** (normalized 0→1): `0.6700`
- **Semantic Similarity** (0→1): `0.4678`
- **Token-F1 Accuracy** (legacy): `0.1714`
- **Avg Correctness** (LLM): `0.6286`
- **Avg Groundedness** (LLM): `0.7257`
- **Avg Completeness** (LLM): `0.5314`
- **Hallucination Flag Rate**: `0.0286`
- **Retrieval Recall@K**: `0.7548`
- **Avg Generation Latency**: `16.72s`
- **P95 Generation Latency**: `24.92s`

### qwen2.5-coder:1.5b
- **Questions evaluated**: 35
- **LLM Judge Score** (normalized 0→1): `0.6129`
- **Semantic Similarity** (0→1): `0.5706`
- **Token-F1 Accuracy** (legacy): `0.7429`
- **Avg Correctness** (LLM): `0.5829`
- **Avg Groundedness** (LLM): `0.6343`
- **Avg Completeness** (LLM): `0.4971`
- **Hallucination Flag Rate**: `0.0286`
- **Retrieval Recall@K**: `0.7548`
- **Avg Generation Latency**: `16.31s`
- **P95 Generation Latency**: `25.94s`

---

## 📝 Notes

- All models ran against the **same 35-question evaluation dataset** (same retrieval context per question).
- **Retrieval** is shared across models (fair comparison — only generation differs).
- **LLM-as-Judge** uses `starcoder2:3b` as the judge model via local Ollama.
- Results generated at: `2026-09-17 03:31:59`
