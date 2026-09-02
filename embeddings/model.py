from sentence_transformers import SentenceTransformer
import torch
import logging

from config import EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)

class EmbeddingModel:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            try:
                # Use cached model — avoids slow HuggingFace HEAD requests on every startup
                cls._instance = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device, local_files_only=True)
            except Exception:
                # Fall back to downloading if not cached
                logger.warning("Local cache miss — downloading model from HuggingFace...")
                cls._instance = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
            logger.info(f"Model loaded successfully on {device}.")
        return cls._instance
