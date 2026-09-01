import pytest
import shutil
from unittest.mock import patch

from config import CHROMA_DB_DIR
from vectorstore.chroma_store import ChromaStore
from retrieval.retriever import Retriever

@pytest.fixture(autouse=True)
def clean_chroma_dir(tmp_path):
    temp_db_dir = tmp_path / "chroma_test_db"
    
    with patch("vectorstore.chroma_store.CHROMA_DB_DIR", temp_db_dir):
        ChromaStore._instance = None
        Retriever._instance = None
        
        store = ChromaStore.get_instance()
        store.add_records(
            ids=["chunk_1", "chunk_2", "chunk_table"],
            embeddings=[
                [1.0] + [0.0] * 383,  # Vector 1
                [-1.0] + [0.0] * 383, # Vector 2 (opposite)
                [0.0, 1.0] + [0.0] * 382 # Vector 3 (orthogonal)
            ],
            metadatas=[
                {"document_name": "Doc A", "has_table": False},
                {"document_name": "Doc A", "has_table": False},
                {"document_name": "Doc B", "has_table": True, "table_id": "table_1"}
            ],
            documents=[
                "This is about admission process.",
                "This is about disciplinary actions.",
                "| Fee | Amount |\n|---|---|\n| Tuition | 1000 |"
            ]
        )
        
        yield
        
        ChromaStore._instance = None
        Retriever._instance = None

@patch("retrieval.retriever.generate_embeddings")
def test_retrieve_basic(mock_generate_embeddings):
    # Mock the embedding generator to return Vector 1
    mock_generate_embeddings.return_value = [[1.0] + [0.0] * 383]
    
    retriever = Retriever.get_instance()
    results = retriever.retrieve("admission", top_k=2)
    
    assert len(results) == 2
    # Vector 1 should be closest to Vector 1
    assert results[0]["chunk_id"] == "chunk_1"
    assert results[0]["text"] == "This is about admission process."
    assert results[0]["document_name"] == "Doc A"

@patch("retrieval.retriever.generate_embeddings")
def test_retrieve_with_filters(mock_generate_embeddings):
    # Mock the embedding generator to return Vector 1
    mock_generate_embeddings.return_value = [[1.0] + [0.0] * 383]
    
    retriever = Retriever.get_instance()
    
    # Filter for has_table=True
    results = retriever.retrieve("query", top_k=5, filters={"has_table": True})
    
    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk_table"
    assert results[0]["has_table"] is True
    assert "Tuition | 1000" in results[0]["text"]

@patch("retrieval.retriever.generate_embeddings")
def test_retrieve_metadata_preserved(mock_generate_embeddings):
    # Mock the embedding generator to return Vector 3
    mock_generate_embeddings.return_value = [[0.0, 1.0] + [0.0] * 382]
    
    retriever = Retriever.get_instance()
    results = retriever.retrieve("query", top_k=1)
    
    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk_table"
    assert results[0]["document_name"] == "Doc B"
    assert results[0]["table_id"] == "table_1"
