from typing import List, Dict, Any, Optional
import logging

from embeddings.embedder import generate_embeddings
from vectorstore.chroma_store import ChromaStore

logger = logging.getLogger(__name__)

class Retriever:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def __init__(self):
        self.store = ChromaStore.get_instance()
        
    def retrieve(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Retrieves the most semantically similar chunks for a given query.
        """
        logger.info(f"Retrieving top {top_k} chunks for query: '{query}'")
        
        # 1. Embed the query
        query_embedding = generate_embeddings([query], batch_size=1)[0]
        
        # 2. Query ChromaDB
        results = self.store.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters
        )
        
        # 3. Format results
        formatted_results = []
        if results and results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                # distance is returned because we use cosine space
                dist = results['distances'][0][i] if results['distances'] else 0.0
                doc_text = results['documents'][0][i] if results['documents'] else ""
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                chunk_id = results['ids'][0][i]
                
                formatted_results.append({
                    "chunk_id": chunk_id,
                    "text": doc_text,
                    "distance": dist,
                    "document_name": metadata.get("document_name"),
                    "page_start": metadata.get("page_start"),
                    "section": metadata.get("section"),
                    "heading": metadata.get("heading"),
                    "content_type": metadata.get("content_type"),
                    "has_table": metadata.get("has_table", False),
                    "table_id": metadata.get("table_id")
                })
                
        return formatted_results

    def embed_query(self, query: str) -> List[float]:
        """Returns the raw 384-d vector for a query string."""
        return generate_embeddings([query], batch_size=1)[0]
        
    def get_document_chunks(self, document_name: str) -> List[Dict[str, Any]]:
        """Returns all chunks belonging to a specific document."""
        data = self.store.collection.get(
            where={"document_name": document_name},
            include=["metadatas", "documents"]
        )
        chunks = []
        if data and data['ids']:
            for i in range(len(data['ids'])):
                meta = data['metadatas'][i] if data['metadatas'] else {}
                chunks.append({
                    "chunk_id": data['ids'][i],
                    "text": data['documents'][i] if data['documents'] else "",
                    "document_name": meta.get("document_name"),
                    "page_start": meta.get("page_start"),
                    "section": meta.get("section"),
                    "heading": meta.get("heading"),
                    "content_type": meta.get("content_type"),
                    "table_id": meta.get("table_id")
                })
        # Sort chunks logically by chunk_id since they include chunk index
        chunks.sort(key=lambda x: x["chunk_id"])
        return chunks
        
    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Returns metadata and text for a specific chunk."""
        data = self.store.collection.get(
            ids=[chunk_id],
            include=["metadatas", "documents"]
        )
        if data and data['ids'] and len(data['ids']) > 0:
            meta = data['metadatas'][0] if data['metadatas'] else {}
            return {
                "chunk_id": data['ids'][0],
                "text": data['documents'][0] if data['documents'] else "",
                **meta
            }
        return None

    def get_chunk_embedding(self, chunk_id: str) -> Optional[List[float]]:
        """Returns the raw 384-d vector embedding for a specific chunk."""
        data = self.store.collection.get(
            ids=[chunk_id],
            include=["embeddings"]
        )
        if data and data['embeddings'] and len(data['embeddings']) > 0:
            return data['embeddings'][0]
        return None
