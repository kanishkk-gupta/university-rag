from typing import List
from embeddings.model import EmbeddingModel
import logging

logger = logging.getLogger(__name__)

def generate_embeddings(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Generate embeddings for a list of strings in batches.
    """
    if not texts:
        return []
        
    model = EmbeddingModel.get_instance()
    
    logger.info(f"Generating embeddings for {len(texts)} texts in batches of {batch_size}...")
    # encode() automatically batches under the hood, but we can pass batch_size explicitly
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True)
    
    return embeddings.tolist()
