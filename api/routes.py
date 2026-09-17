from fastapi import APIRouter, HTTPException, BackgroundTasks
import logging

from api.schemas import ChatRequest, ChatResponse, RetrieveRequest, RetrieveResponse, CodebaseRequest
from rag.pipeline import RAGPipeline
from retrieval.retriever import Retriever
from pydantic import BaseModel
import config

# Guardrails
try:
    from guardrails.guardrail import GuardrailPipeline, build_blocked_response
    _guardrail = GuardrailPipeline()
    GUARDRAILS_ENABLED = True
except Exception as _ge:
    GUARDRAILS_ENABLED = False
    _guardrail = None
    logging.getLogger(__name__).warning(f"Guardrails not loaded: {_ge}")

logger = logging.getLogger(__name__)
router = APIRouter()

rag_pipeline = RAGPipeline()
retriever = Retriever.get_instance()

class QueryEmbeddingRequest(BaseModel):
    query: str

@router.get("/health")
def health_check():
    return {"status": "ok", "rag_ready": rag_pipeline.check_readiness()}

@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    top_k = request.top_k or config.RAG_TOP_K

    # ── Input Guardrail ───────────────────────────────────────────────────────
    if GUARDRAILS_ENABLED and _guardrail:
        input_check = _guardrail.check_input(request.query)
        if not input_check.passed:
            logger.info(f"Query BLOCKED by {input_check.blocked_by}: {request.query[:60]}")
            return ChatResponse(
                query=request.query,
                answer=input_check.reason,
                sources=[],
                retrieval_results=[],
                guardrail=input_check.to_dict(),
            )

    try:
        result = rag_pipeline.query(request.query, top_k=top_k, use_rag=request.use_rag, model_name=request.model_name)

        # ── Output Guardrail ──────────────────────────────────────────────────
        guardrail_info = {"passed": True, "blocked_by": None, "reason": "Guardrails disabled", "warnings": []}
        if GUARDRAILS_ENABLED and _guardrail:
            context_str = " ".join([
                r.get("text", "") for r in result.get("retrieval_results", [])
            ])
            context_available = bool(context_str.strip())
            output_check = _guardrail.check_output(
                result["answer"], context_str, context_available
            )
            guardrail_info = output_check.to_dict()
            if output_check.warnings:
                logger.info(f"Output warnings for query '{request.query[:40]}': "
                            f"{[w['guard'] for w in guardrail_info['warnings']]}")

        return ChatResponse(
            query=result["query"],
            answer=result["answer"],
            sources=result["sources"],
            retrieval_results=result["retrieval_results"],
            guardrail=guardrail_info,
        )
    except Exception as e:
        logger.error(f"Error during chat generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/retrieve", response_model=RetrieveResponse)
def retrieve(request: RetrieveRequest):
    try:
        results = retriever.retrieve(request.query, top_k=request.top_k)
        return RetrieveResponse(query=request.query, chunks=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/documents")
def get_documents():
    try:
        data = retriever.store.collection.get(include=["metadatas"])
        doc_stats = {}
        for meta in data.get("metadatas", []):
            if not meta or "document_name" not in meta:
                continue
            name = meta["document_name"]
            if name not in doc_stats:
                doc_stats[name] = {
                    "filename": name,
                    "type": "PDF",
                    "pages": set(),
                    "tables": 0,
                    "chunks": 0,
                    "extraction": set()
                }
            if "page_start" in meta:
                doc_stats[name]["pages"].add(meta["page_start"])
            doc_stats[name]["chunks"] += 1
            if meta.get("content_type") == "table":
                doc_stats[name]["tables"] += 1
            if "extraction_method" in meta:
                doc_stats[name]["extraction"].add(meta["extraction_method"])
                
        results = []
        for name, stats in doc_stats.items():
            results.append({
                "filename": name,
                "type": stats["type"],
                "page_count": len(stats["pages"]),
                "table_count": stats["tables"],
                "chunk_count": stats["chunks"],
                "extraction_method": ", ".join(list(stats["extraction"])) or "native"
            })
            
        return {"documents": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/documents/{document_name}/chunks")
def get_document_chunks(document_name: str):
    try:
        chunks = retriever.get_document_chunks(document_name)
        return {"document_name": document_name, "chunks": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    try:
        chunk = retriever.get_chunk(chunk_id)
        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk not found")
        return chunk
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/chunks/{chunk_id}/embedding")
def get_chunk_embedding(chunk_id: str):
    try:
        embedding = retriever.get_chunk_embedding(chunk_id)
        if not embedding:
            raise HTTPException(status_code=404, detail="Embedding not found")
        return {"chunk_id": chunk_id, "embedding": embedding}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/query-embedding")
def embed_query(request: QueryEmbeddingRequest):
    try:
        embedding = retriever.embed_query(request.query)
        # convert numpy float32 to float
        embedding = [float(x) for x in embedding]
        return {"query": request.query, "embedding": embedding}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/stats")
def get_stats():
    try:
        count = retriever.store.collection.count()
        is_ready = rag_pipeline.check_readiness()
        return {
            "embedding_model": config.EMBEDDING_MODEL_NAME,
            "embedding_dimension": config.EMBEDDING_DIMENSION,
            "llm_model": config.LLM_MODEL,
            "vector_database": "ChromaDB",
            "indexed_records": count,
            "rag_status": "ready" if is_ready else "offline",
            "ollama_status": "ready" if is_ready else "offline"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/api/codebase/query")
def codebase_query(request: CodebaseRequest):
    from codebase.rag import CodebaseRAGPipeline
    cb_rag = CodebaseRAGPipeline()
    try:
        result = cb_rag.query(request.query, top_k=request.top_k, model_name=request.model_name)
        return result
    except Exception as e:
        logger.exception("Codebase query failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/codebase/stats")
def codebase_stats():
    from vectorstore.chroma_store import ChromaStore
    try:
        store = ChromaStore.get_codebase_instance()
        return {"indexed_chunks": store.collection.count()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/api/evaluation/dataset")
def get_eval_dataset():
    from evaluation.models import get_dataset
    try:
        return {"dataset": get_dataset()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/evaluation/run")
def run_eval(background_tasks: BackgroundTasks):
    from evaluation.runner import run_evaluation
    try:
        background_tasks.add_task(run_evaluation)
        return {"status": "started", "message": "Evaluation started in background. Refresh /api/evaluation/results to check progress."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/evaluation/results")
def get_eval_results():
    import json
    from evaluation.runner import RESULTS_DIR
    try:
        if not RESULTS_DIR.exists():
            return {"results": []}
        # Find latest jsonl
        jsonl_files = list(RESULTS_DIR.glob("*.jsonl"))
        if not jsonl_files:
            return {"results": []}
        latest = max(jsonl_files, key=lambda p: p.stat().st_mtime)
        results = []
        with open(latest, "r") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/evaluation/summary")
def get_eval_summary():
    import json
    from evaluation.runner import RESULTS_DIR
    try:
        summary_file = RESULTS_DIR / "summary_latest.json"
        if not summary_file.exists():
            return {"summary": {}}
        with open(summary_file, "r") as f:
            return {"summary": json.load(f)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tests/output-quality")
def run_output_quality_tests():
    """Run the AI Output Quality pytest suite and return structured results."""
    import subprocess, json as _json, re as _re
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/test_output_quality.py",
             "-v", "--tb=short", "--no-header", "-q"],
            capture_output=True, text=True,
            cwd="/home/student/university-rag", timeout=120
        )
        output = result.stdout + result.stderr
        lines = output.strip().splitlines()

        tests = []
        # Parse verbose pytest output lines like: tests/...::Class::method PASSED/FAILED
        for line in lines:
            m = _re.match(r"tests/test_output_quality\.py::(\w+)::(\w+)\s+(PASSED|FAILED)", line)
            if m:
                criterion, test_name, status = m.groups()
                # Extract failure reason from next lines if FAILED
                tests.append({
                    "criterion": criterion.replace("Test", ""),
                    "test": test_name.replace("test_", "").replace("_", " "),
                    "passed": status == "PASSED",
                    "status": status,
                })

        # Parse summary line "X passed, Y failed"
        summary_match = _re.search(r"(\d+) passed", output)
        failed_match = _re.search(r"(\d+) failed", output)
        total_pass = int(summary_match.group(1)) if summary_match else 0
        total_fail = int(failed_match.group(1)) if failed_match else 0
        total = total_pass + total_fail

        # Group by criterion
        by_criterion = {}
        for t in tests:
            c = t["criterion"]
            if c not in by_criterion:
                by_criterion[c] = {"criterion": c, "tests": [], "passed": 0, "total": 0}
            by_criterion[c]["tests"].append(t)
            by_criterion[c]["total"] += 1
            if t["passed"]:
                by_criterion[c]["passed"] += 1

        return {
            "total": total,
            "passed": total_pass,
            "failed": total_fail,
            "pass_rate": round(total_pass / total, 4) if total else 0,
            "exit_code": result.returncode,
            "criteria": list(by_criterion.values()),
            "raw_tests": tests,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Tests timed out after 120s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tests/guardrails")
def run_guardrail_tests_structured():
    """Run guardrail test suite and return full structured results."""
    try:
        from guardrails.test_guardrails import INPUT_TEST_CASES, OUTPUT_TEST_CASES
        from guardrails.guardrail import GuardrailPipeline
        from guardrails.output_guards import RefusalConsistencyGuard, MinimumLengthGuard

        pipeline = GuardrailPipeline()
        input_results, output_results = [], []

        for tid, query, expect_pass, desc in INPUT_TEST_CASES:
            r = pipeline.check_input(query)
            ok = (r.passed == expect_pass)
            cat = tid[:3]  # OUT, LEN, CON, PII, VAL
            input_results.append({
                "id": tid, "category": cat, "description": desc,
                "query_preview": query[:90] + ("..." if len(query) > 90 else ""),
                "expected": "PASS" if expect_pass else "BLOCK",
                "actual": "PASS" if r.passed else "BLOCK",
                "passed_test": ok, "blocked_by": r.blocked_by, "reason": r.reason,
            })

        for tid, answer, context, ctx_avail, exp_refusal, exp_length, desc in OUTPUT_TEST_CASES:
            r_ref = RefusalConsistencyGuard().check(answer, ctx_avail)
            r_len = MinimumLengthGuard().check(answer)
            ok = (r_ref.passed == exp_refusal) and (r_len.passed == exp_length)
            output_results.append({
                "id": tid, "description": desc,
                "answer_preview": answer[:80] + ("..." if len(answer) > 80 else ""),
                "passed_test": ok,
                "refusal_ok": r_ref.passed == exp_refusal,
                "length_ok": r_len.passed == exp_length,
            })

        all_results = input_results + output_results
        total_pass = sum(1 for r in all_results if r["passed_test"])
        total = len(all_results)

        return {
            "total": total, "passed": total_pass, "failed": total - total_pass,
            "pass_rate": round(total_pass / total, 4) if total else 0,
            "input_tests": input_results,
            "output_tests": output_results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/evaluation/category-summary")
def get_category_summary():
    import json
    from evaluation.runner import RESULTS_DIR
    try:
        cat_file = RESULTS_DIR / "category_summary_latest.json"
        if not cat_file.exists():
            return {"category_summary": {}}
        with open(cat_file, "r") as f:
            raw_data = json.load(f)

        # Transform raw data into the structure expected by the frontend
        overall = {}
        categories = {}
        winners = {}
        
        # Collect models dynamically
        models = set()
        for cat, results in raw_data.items():
            models.update(results.keys())
        
        # Initialize overall accumulators
        for m in models:
            overall[m] = {"judge_score": 0, "semantic_similarity": 0, "avg_latency": 0, "count": 0}

        for cat, results in raw_data.items():
            categories[cat] = {}
            best_model = None
            best_score = -1
            
            for m, metrics in results.items():
                j_score = metrics.get("llm_accuracy", 0)
                sem = metrics.get("avg_semantic_similarity", 0)
                lat = metrics.get("avg_latency_s", 0)
                
                categories[cat][m] = {"judge_score": j_score}
                
                # Update overall stats
                overall[m]["judge_score"] += j_score
                overall[m]["semantic_similarity"] += sem
                overall[m]["avg_latency"] += lat
                overall[m]["count"] += 1
                
                if j_score > best_score:
                    best_score = j_score
                    best_model = m
                elif j_score == best_score and best_score > 0:
                    best_model = "Tie"
                    
            winners[cat] = best_model

        # Average the overall stats
        for m in models:
            c = overall[m]["count"]
            if c > 0:
                overall[m]["judge_score"] /= c
                overall[m]["semantic_similarity"] /= c
                overall[m]["avg_latency"] /= c

        return {
            "overall": overall,
            "categories": categories,
            "winners": winners
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/guardrails/check")
def check_guardrail(request: ChatRequest):
    """Test a query against the input guardrail pipeline without running RAG."""
    if not GUARDRAILS_ENABLED:
        return {"enabled": False, "passed": True, "message": "Guardrails not loaded"}
    result = _guardrail.check_input(request.query)
    return {
        "enabled":    True,
        "query":      request.query,
        "passed":     result.passed,
        "blocked_by": result.blocked_by,
        "reason":     result.reason,
        "severity":   result.severity,
        "warnings":   [{"guard": w.guard_name, "reason": w.reason} for w in result.warnings],
    }


@router.get("/api/guardrails/test")
def run_guardrail_tests():
    """Run the full guardrail test suite and return pass/fail results."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from guardrails.test_guardrails import INPUT_TEST_CASES, OUTPUT_TEST_CASES
        from guardrails.guardrail import GuardrailPipeline
        from guardrails.output_guards import RefusalConsistencyGuard, MinimumLengthGuard
        pipeline = GuardrailPipeline()
        results  = []
        for tid, query, expect_pass, desc in INPUT_TEST_CASES:
            r   = pipeline.check_input(query)
            ok  = (r.passed == expect_pass)
            results.append({
                "id": tid, "type": "input", "description": desc,
                "query_preview": query[:80], "expected": "PASS" if expect_pass else "BLOCK",
                "actual": "PASS" if r.passed else "BLOCK",
                "passed_test": ok, "blocked_by": r.blocked_by, "reason": r.reason,
            })
        total_pass = sum(1 for r in results if r["passed_test"])
        return {
            "total": len(results), "passed": total_pass,
            "failed": len(results) - total_pass,
            "pass_rate": round(total_pass / len(results), 4) if results else 0,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
