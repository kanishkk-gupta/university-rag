from typing import List, Dict, Any, Tuple
import logging

from config import MAX_CONTEXT_CHARS

logger = logging.getLogger(__name__)

class ContextBuilder:
    """
    Constructs a grounded context string from retrieved Chroma chunks.
    Ensures that context limits are respected and provenance is clear.
    """
    
    @classmethod
    def build_context(cls, retrieval_results: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Takes the retrieval results and builds a string context.
        Returns the formatted context string and the list of used sources (for citations).
        """
        if not retrieval_results:
            return "", []
            
        context_parts = []
        used_sources = []
        current_chars = 0
        
        for idx, result in enumerate(retrieval_results):
            # Extract metadata
            doc_name = result.get("document_name", "Unknown Document")
            page = result.get("page_start", "Unknown Page")
            section = result.get("section", "")
            heading = result.get("heading", "")
            content_type = result.get("content_type", "text")
            table_id = result.get("table_id", "")
            chunk_id = result.get("chunk_id", f"chunk_{idx}")
            text = result.get("text", "").strip()
            
            if not text:
                continue
                
            # Build the source block
            source_idx = len(used_sources) + 1
            
            lines = [f"[SOURCE {source_idx}]"]
            lines.append(f"Document: {doc_name}")
            if page != "Unknown Page":
                lines.append(f"Page: {page}")
            if section:
                lines.append(f"Section: {section}")
            if heading:
                lines.append(f"Heading: {heading}")
            lines.append(f"Content Type: {content_type}")
            if table_id:
                lines.append(f"Table ID: {table_id}")
            
            lines.append("Content:")
            lines.append(text)
            
            chunk_str = "\n".join(lines) + "\n"
            
            # Check context limits
            if current_chars + len(chunk_str) > MAX_CONTEXT_CHARS:
                logger.warning(f"Truncating context at source {source_idx} to stay under {MAX_CONTEXT_CHARS} chars.")
                break
                
            context_parts.append(chunk_str)
            used_sources.append({
                "source_id": source_idx,
                "document": doc_name,
                "page": page,
                "section": section,
                "chunk_id": chunk_id,
                "content_type": content_type
            })
            
            current_chars += len(chunk_str)
            
        return "\n\n".join(context_parts), used_sources
