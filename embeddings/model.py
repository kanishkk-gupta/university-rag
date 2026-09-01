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
            # Use CPU by default to keep it locally runnable on any machine
            device = "cuda" if torch.cuda.is_available() else "cpu"
            cls._instance = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
            logger.info(f"Model loaded successfully on {device}.")
        return cls._instance
