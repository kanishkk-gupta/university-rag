import os
import ast
import logging
from pathlib import Path
from typing import List, Dict, Any

from config import BASE_DIR, INDEXING_BATCH_SIZE, CODEBASE_CHUNK_LINES, CODEBASE_CHUNK_OVERLAP_LINES
from vectorstore.chroma_store import ChromaStore
from embeddings.embedder import generate_embeddings

logger = logging.getLogger(__name__)

class CodebaseIndexer:
    def __init__(self):
        self.store = ChromaStore.get_codebase_instance()
        self.included_dirs = ['api', 'rag', 'retrieval', 'embeddings', 'vectorstore', 'ingestion', 'frontend/src']
        self.excluded_dirs = ['node_modules', 'venv', '.git', '__pycache__', 'dist', 'build']
        
    def _is_valid_file(self, file_path: Path) -> bool:
        if file_path.suffix not in ['.py', '.js', '.jsx']:
            return False
        for ex in self.excluded_dirs:
            if ex in file_path.parts:
                return False
        return True

    def index_repository(self):
        logger.info("Starting codebase indexing...")
        all_chunks = []
        
        for d in self.included_dirs:
            target_dir = BASE_DIR / d
            if not target_dir.exists():
                continue
            for file_path in target_dir.rglob("*"):
                if file_path.is_file() and self._is_valid_file(file_path):
                    chunks = self._chunk_file(file_path)
                    all_chunks.extend(chunks)
                    
        # Upsert chunks in batches
        logger.info(f"Found {len(all_chunks)} codebase chunks. Indexing...")
        for i in range(0, len(all_chunks), INDEXING_BATCH_SIZE):
            batch = all_chunks[i:i + INDEXING_BATCH_SIZE]
            texts = [c['text'] for c in batch]
            ids = [c['chunk_id'] for c in batch]
            metadatas = [c['metadata'] for c in batch]
            
            embeddings = generate_embeddings(texts)
            self.store.add_records(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
            logger.info(f"Indexed batch {i // INDEXING_BATCH_SIZE + 1} / {(len(all_chunks) + INDEXING_BATCH_SIZE - 1) // INDEXING_BATCH_SIZE}")

        logger.info(f"Finished indexing {len(all_chunks)} chunks into codebase collection.")

    def _chunk_file(self, file_path: Path) -> List[Dict[str, Any]]:
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return []

        rel_path = str(file_path.relative_to(BASE_DIR))
        lines = content.split('\n')
        chunks = []
        
        chunk_size = CODEBASE_CHUNK_LINES
        overlap = CODEBASE_CHUNK_OVERLAP_LINES
        
        i = 0
        chunk_idx = 0
        while i < len(lines):
            end = min(i + chunk_size, len(lines))
            chunk_lines = lines[i:end]
            chunk_text = "\n".join(chunk_lines)
            
            if chunk_text.strip():
                metadata = {
                    "file_path": rel_path,
                    "language": file_path.suffix[1:],
                    "start_line": i + 1,
                    "end_line": end,
                    "chunk_index": chunk_idx
                }
                
                chunks.append({
                    "chunk_id": f"{rel_path}_{chunk_idx}",
                    "text": f"File: {rel_path} (Lines {i+1}-{end})\n```\n{chunk_text}\n```",
                    "metadata": metadata
                })
                chunk_idx += 1
            i += chunk_size - overlap
            
        return chunks

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    indexer = CodebaseIndexer()
    indexer.index_repository()
