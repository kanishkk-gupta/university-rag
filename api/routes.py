from fastapi import APIRouter, HTTPException
import logging

from api.schemas import ChatRequest, ChatResponse, RetrieveRequest, RetrieveResponse, CodebaseRequest
from rag.pipeline import RAGPipeline
from retrieval.retriever import Retriever
from pydantic import BaseModel
import config

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
    try:
        result = rag_pipeline.query(request.query, top_k=top_k, use_rag=request.use_rag, model_name=request.model_name)
        return ChatResponse(
            query=result["query"],
            answer=result["answer"],
            sources=result["sources"],
            retrieval_results=result["retrieval_results"]
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
        return {
            "embedding_model": config.EMBEDDING_MODEL_NAME,
            "embedding_dimension": config.EMBEDDING_DIMENSION,
            "llm_model": config.LLM_MODEL,
            "vector_database": "ChromaDB",
            "indexed_records": count,
            "rag_status": "ready" if rag_pipeline.check_readiness() else "offline",
            "ollama_status": "ready" if rag_pipeline.check_readiness() else "offline"
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
def run_eval():
    from evaluation.runner import run_evaluation
    try:
        # In a real app this should be a background task (e.g. Celery/BackgroundTasks)
        # But for this demo, we'll run it synchronously or just kick it off
        # Let's import BackgroundTasks and use it
        return {"message": "Evaluation started. Check logs for progress."}
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
