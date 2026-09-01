import pytest
from embeddings.model import EmbeddingModel
from embeddings.embedder import generate_embeddings

def test_embedding_model_singleton():
    model1 = EmbeddingModel.get_instance()
    model2 = EmbeddingModel.get_instance()
    assert model1 is model2
    assert model1 is not None

def test_generate_embeddings():
    texts = ["Hello world", "This is a test"]
    embeddings = generate_embeddings(texts, batch_size=2)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384  # Default all-MiniLM-L6-v2 dimension
    assert isinstance(embeddings[0][0], float)

def test_generate_embeddings_empty():
    embeddings = generate_embeddings([])
    assert embeddings == []
