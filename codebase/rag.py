import logging
from typing import Dict, Any, List
from vectorstore.chroma_store import ChromaStore
from embeddings.embedder import generate_embeddings
from rag.generator import OllamaGenerator
from config import RAG_TOP_K

logger = logging.getLogger(__name__)

CODEBASE_SYSTEM_PROMPT = """You are an expert software engineer assistant. You help the user understand a software repository.
Use the provided codebase snippets to answer the user's question accurately.
Always cite the file path and line numbers when referencing code.
If the answer is not in the provided code snippets, say "I cannot determine this from the provided codebase."

Codebase Snippets:
{context}
"""

class CodebaseRAGPipeline:
    def __init__(self):
        self.store = ChromaStore.get_codebase_instance()
        self.generator = OllamaGenerator()

    def query(self, user_query: str, top_k: int = RAG_TOP_K, model_name: str = None) -> Dict[str, Any]:
        logger.info(f"Starting Codebase RAG pipeline for query: '{user_query}'")
        
        # 1. Embed & Retrieve
        query_emb = generate_embeddings([user_query])[0]
        results = self.store.collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        retrieved_chunks = []
        if results and results["documents"] and len(results["documents"]) > 0:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0]
            for doc, meta, dist in zip(docs, metas, dists):
                retrieved_chunks.append({
                    "text": doc,
                    "metadata": meta,
                    "distance": dist
                })
                
        # 2. Build Context
        context_parts = []
        sources = []
        for c in retrieved_chunks:
            context_parts.append(c["text"])
            m = c["metadata"]
            sources.append({
                "file_path": m.get("file_path"),
                "start_line": m.get("start_line"),
                "end_line": m.get("end_line"),
                "chunk_id": m.get("chunk_id", "")
            })
            
        context_str = "\n\n---\n\n".join(context_parts)
        
        if not context_str:
            return {
                "query": user_query,
                "answer": "No relevant codebase context found.",
                "sources": [],
                "retrieved_chunks": []
            }
            
        # 3. Generate Answer
        system_prompt = CODEBASE_SYSTEM_PROMPT.replace("{context}", context_str)
        try:
            answer = self.generator.generate(system_prompt, user_query, model_name=model_name)
        except ConnectionError as e:
            logger.error(f"Generation failed: {e}")
            answer = f"Error: {e}"
            
        return {
            "query": user_query,
            "answer": answer.strip(),
            "sources": sources,
            "retrieved_chunks": retrieved_chunks
        }
