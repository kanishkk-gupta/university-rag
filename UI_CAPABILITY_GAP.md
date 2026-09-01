# UI Capability Gap Audit
Generated: 2026-08-31

## Legend
- FULL: Professor can see and interact with it
- PARTIAL: Backend and API exist but UI incomplete or misleading  
- MISSING: Backend exists but NO UI surface

---

## WEEK 3 — CORE RAG CAPABILITIES

| # | Capability | Backend | API | UI | Demonstrable |
|---|---|---|---|---|---|
| 1 | LLM without RAG | YES | POST /api/chat use_rag=false | YES LLMApp.jsx | FULL |
| 2 | LLM with RAG | YES | POST /api/chat use_rag=true | YES LLMApp.jsx | FULL |
| 3 | Document list | YES | GET /api/documents | YES KnowledgeBase.jsx | FULL |
| 4 | OCR/Native indication | YES | in /api/documents | YES per doc | FULL |
| 5 | Table count per doc | YES | in /api/documents | YES | FULL |
| 6 | Chunk count per doc | YES | in /api/documents | YES | FULL |
| 7 | Chunk browsing | YES | GET /api/documents/{name}/chunks | YES chunk grid | FULL |
| 8 | Chunk detail (text, page, type) | YES | implicit | YES detail panel | FULL |
| 9 | Chunking strategy params | YES config.py | NO dedicated endpoint | NO not shown | MISSING |
| 10 | Chunk 384-D embedding | YES | GET /api/chunks/{id}/embedding | YES collapsible | FULL |
| 11 | Embedding model info | YES | GET /api/stats | YES KnowledgeBase | FULL |
| 12 | 2D vector projection | PARTIAL (pseudo-plot, not real PCA) | NO projection endpoint | PARTIAL misleading | PARTIAL |
| 13 | Query embedding 384-D | YES | POST /api/query-embedding | YES RAG.jsx step 02 | FULL |
| 14 | Vector similarity distances | YES | POST /api/retrieve | YES RAG.jsx step 03 | FULL |
| 15 | Top-K retrieval with rank | YES | POST /api/retrieve | YES RAG.jsx step 03 | FULL |
| 16 | Retrieved chunk text | YES | in retrieve response | YES RAG.jsx steps 04/05 | FULL |
| 17 | Exact system prompt sent to LLM | YES | embedded in retrieve | PARTIAL chunks shown, not exact prompt | PARTIAL |
| 18 | RAG pipeline step-by-step | YES | multiple endpoints | YES RAG.jsx 8 steps | FULL |
| 19 | Final answer from Code Llama | YES | POST /api/chat | YES RAG.jsx step 07 | FULL |
| 20 | Source citations doc/page/chunk | YES | /api/chat sources field | YES RAG.jsx step 08 | FULL |
| 21 | Orchestration architecture | YES | static + /api/chat | PARTIAL intermediate steps simulated | PARTIAL |
| 22 | Service request trace real timing | PARTIAL | wall-clock only | PARTIAL setTimeout intermediate | PARTIAL |
| 23 | Docker architecture diagram | YES | static | YES Dockerized.jsx | FULL |
| 24 | System stats model/DB/count | YES | GET /api/stats | YES used in KnowledgeBase | FULL |

---

## WEEK 4 — EVALUATION & CODEBASE

| # | Capability | Backend | API | UI | Demonstrable |
|---|---|---|---|---|---|
| 25 | Three-model support | YES config.py MODEL_CONFIGS | YES model_name in /api/chat | NO no model selector | MISSING |
| 26 | 25-question dataset | YES evaluation/dataset.json | YES GET /api/evaluation/dataset | NO not shown | MISSING |
| 27 | Evaluation results JSONL | YES evaluation/reports/ | YES GET /api/evaluation/results | NO not loaded | MISSING |
| 28 | Summary metrics per model | YES summary_latest.json | YES GET /api/evaluation/summary | PARTIAL only Accuracy+Latency | PARTIAL |
| 29 | Accuracy metric | YES metrics.py | via summary | PARTIAL no definition shown | PARTIAL |
| 30 | Relevance metric | YES metrics.py | via results | MISSING | MISSING |
| 31 | Recall@5 metric | YES metrics.py | via results | MISSING | MISSING |
| 32 | Hallucination rate | YES metrics.py (heuristic 0.1 fixed) | via results | MISSING | MISSING |
| 33 | Latency median/p95 | YES recorded per record | via results | PARTIAL only mean | PARTIAL |
| 34 | Token usage prompt/completion/total | YES generator.py return_usage | via results | MISSING | MISSING |
| 35 | CPU/RAM resource measurement | YES psutil in metrics.py | via results | MISSING | MISSING |
| 36 | GPU measurement | NO returns "unavailable" | unavailable | MISSING N/A | N/A |
| 37 | Question-level A vs B vs C comparison | YES in JSONL | via /api/evaluation/results | MISSING no drill-down | MISSING |
| 38 | Controlled generation (same context 3 models) | YES runner.py retrieves ONCE | via results | MISSING not demonstrated | MISSING |
| 39 | RAG failure/success analysis | YES data in JSONL | via results | MISSING no analysis page | MISSING |
| 40 | Metric definitions explained | YES in code | none | MISSING | MISSING |
| 41 | Full model comparison table | YES calculable | via results | PARTIAL only 2 cols | PARTIAL |
| 42 | Codebase index stats | YES ChromaDB bmu_codebase 133 chunks | YES GET /api/codebase/stats | MISSING not shown | MISSING |
| 43 | Codebase retrieval | YES codebase/rag.py | YES POST /api/codebase/query | PARTIAL answer+paths, no code | PARTIAL |
| 44 | Codebase chunk code content | YES in retrieved_chunks | via /api/codebase/query | MISSING Codebase.jsx ignores it | MISSING |
| 45 | Multi-file codebase reasoning | YES top-K all files | via /api/codebase/query | PARTIAL paths only | PARTIAL |
| 46 | File/line citations with code preview | YES start_line/end_line | via /api/codebase/query | PARTIAL lines shown no code | PARTIAL |
| 47 | Codebase files list | NO missing endpoint | MISSING /api/codebase/files | MISSING | MISSING |
| 48 | BMU vs Codebase separation visible | YES separate collections | via /api/codebase/stats | PARTIAL not labelled | PARTIAL |
| 49 | Evaluation run trigger (actual) | YES runner.py | PARTIAL stub returns msg only | PARTIAL button exists does nothing | PARTIAL |

---

## NAVIGATION STATUS

| Page | Route | In Navigation | Works |
|---|---|---|---|
| LLM Application | /llm-app | YES | YES |
| Knowledge Base | /knowledge-base | YES | YES |
| RAG | /rag | YES | YES |
| Orchestration | /orchestration | YES | YES |
| Dockerized | /docker | BROKEN - nav links to /dockerized | NO |
| Evaluation | /evaluation | MISSING FROM NAV | Reachable only by URL |
| Codebase | /codebase | MISSING FROM NAV | Reachable only by URL |

---

## CRITICAL GAPS (Priority Order)

1. CRITICAL: Evaluation and Codebase pages missing from Navigation
2. CRITICAL: Dockerized nav link broken (/dockerized vs /docker)
3. HIGH: Evaluation.jsx shows only 2 of 9 required metrics
4. HIGH: No question-level comparison (same question, 3 models side-by-side)
5. HIGH: Codebase.jsx does not display actual code chunk content
6. HIGH: No codebase stats panel (collection, chunk count, files)
7. MEDIUM: Orchestration intermediate steps simulated via setTimeout
8. MEDIUM: 2D projection is pseudo-random scatter, not real PCA
9. MEDIUM: /api/evaluation/run returns stub - evaluation does not actually run from UI
10. INFO: Token counts are 0 for StarCoder2 and Qwen (Ollama was down during eval run - data issue not code bug)
