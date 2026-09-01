import json
import logging
from typing import List, Dict, Any
from tqdm import tqdm

from config import CHUNKS_OUTPUT_FILE, INDEXING_BATCH_SIZE, MAX_EMBEDDING_CHUNK_CHARS
from embeddings.embedder import generate_embeddings
from vectorstore.chroma_store import ChromaStore

logger = logging.getLogger(__name__)

def load_chunks(filepath: str = CHUNKS_OUTPUT_FILE) -> List[Dict[str, Any]]:
    chunks = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks

def split_oversized_chunk(chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Splits an oversized chunk into smaller chunks while preserving metadata.
    If it's a table, retains the header row for each sub-chunk.
    """
    text = chunk["text"]
    if len(text) <= MAX_EMBEDDING_CHUNK_CHARS:
        return [chunk]
        
    logger.info(f"Splitting oversized chunk {chunk['chunk_id']} ({len(text)} chars)")
    
    sub_chunks = []
    
    if chunk.get("has_table"):
        # Table splitting strategy
        lines = text.split("\n")
        
        # Find headers (usually first 2 lines if Markdown table: headers, then |---|---|)
        header_lines = []
        data_lines = []
        is_header_section = True
        
        for line in lines:
            if is_header_section:
                header_lines.append(line)
                if line.strip().startswith("|-") or line.strip().startswith("|-"):
                    is_header_section = False
            else:
                data_lines.append(line)
                
        # If we didn't find standard markdown headers, just treat first line as header
        if is_header_section:
            header_lines = lines[:1]
            data_lines = lines[1:]
            
        header_text = "\n".join(header_lines) + "\n"
        
        current_subtext = header_text
        part = 1
        
        for line in data_lines:
            if len(current_subtext) + len(line) + 1 > MAX_EMBEDDING_CHUNK_CHARS and current_subtext != header_text:
                # Save current sub-chunk
                new_chunk = chunk.copy()
                new_chunk["text"] = current_subtext.strip()
                new_chunk["chunk_id"] = f"{chunk['chunk_id']}_part{part}"
                sub_chunks.append(new_chunk)
                
                # Start new sub-chunk
                current_subtext = header_text + line + "\n"
                part += 1
            else:
                current_subtext += line + "\n"
                
        if current_subtext != header_text:
            new_chunk = chunk.copy()
            new_chunk["text"] = current_subtext.strip()
            new_chunk["chunk_id"] = f"{chunk['chunk_id']}_part{part}"
            sub_chunks.append(new_chunk)
            
    else:
        # Standard text splitting strategy (by paragraphs \n\n)
        paragraphs = text.split("\n\n")
        current_subtext = ""
        part = 1
        
        for p in paragraphs:
            if len(current_subtext) + len(p) + 2 > MAX_EMBEDDING_CHUNK_CHARS and current_subtext:
                new_chunk = chunk.copy()
                new_chunk["text"] = current_subtext.strip()
                new_chunk["chunk_id"] = f"{chunk['chunk_id']}_part{part}"
                sub_chunks.append(new_chunk)
                
                current_subtext = p + "\n\n"
                part += 1
            else:
                current_subtext += p + "\n\n"
                
        if current_subtext:
            new_chunk = chunk.copy()
            new_chunk["text"] = current_subtext.strip()
            new_chunk["chunk_id"] = f"{chunk['chunk_id']}_part{part}"
            sub_chunks.append(new_chunk)
            
    return sub_chunks

def prepare_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared_chunks = []
    for c in chunks:
        prepared_chunks.extend(split_oversized_chunk(c))
    return prepared_chunks

def run_indexing():
    logger.info("Loading validated chunks...")
    chunks = load_chunks()
    
    logger.info("Preparing oversized chunks...")
    prepared_chunks = prepare_chunks(chunks)
    logger.info(f"Total chunks to index: {len(prepared_chunks)} (up from {len(chunks)} before splitting)")
    
    store = ChromaStore.get_instance()
    
    logger.info("Starting embedding and indexing process...")
    # Process in batches
    for i in tqdm(range(0, len(prepared_chunks), INDEXING_BATCH_SIZE)):
        batch = prepared_chunks[i:i + INDEXING_BATCH_SIZE]
        
        texts = [c["text"] for c in batch]
        ids = [c["chunk_id"] for c in batch]
        
        # metadatas is everything except 'text'
        metadatas = [{k: v for k, v in c.items() if k != "text"} for c in batch]
        
        embeddings = generate_embeddings(texts, batch_size=INDEXING_BATCH_SIZE)
        
        store.add_records(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
        
    logger.info(f"Indexing complete! Vector store now contains {store.get_count()} records.")
