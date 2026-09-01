import chromadb
from chromadb.config import Settings
import logging
from typing import Dict, List, Any

from config import CHROMA_DB_DIR, CHROMA_COLLECTION_NAME

logger = logging.getLogger(__name__)

class ChromaStore:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            # Ensure directory exists
            CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Initializing persistent ChromaDB at {CHROMA_DB_DIR}")
            client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
            
            # Get or create collection
            collection = client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"} # Use cosine similarity for sentence-transformers
            )
            
            cls._instance = cls(client, collection)
        return cls._instance
        
    _codebase_instance = None

    @classmethod
    def get_codebase_instance(cls):
        from config import CODEBASE_CHROMA_COLLECTION_NAME
        if cls._codebase_instance is None:
            CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
            collection = client.get_or_create_collection(
                name=CODEBASE_CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            cls._codebase_instance = cls(client, collection)
        return cls._codebase_instance
        
    def __init__(self, client, collection):
        self.client = client
        self.collection = collection
        
    def add_records(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], documents: List[str]):
        """
        Upsert records into ChromaDB
        """
        # Ensure metadata values are str, int, float, or bool
        cleaned_metadatas = []
        for m in metadatas:
            clean_m = {}
            for k, v in m.items():
                if v is None:
                    continue # Chroma doesn't like None metadata values
                if isinstance(v, (str, int, float, bool)):
                    clean_m[k] = v
                elif isinstance(v, list):
                    clean_m[k] = ", ".join(str(x) for x in v)
                else:
                    clean_m[k] = str(v)
            cleaned_metadatas.append(clean_m)
            
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=cleaned_metadatas,
            documents=documents
        )
        
    def get_count(self) -> int:
        return self.collection.count()
