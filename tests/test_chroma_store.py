import pytest
import shutil
import os
from pathlib import Path
from unittest.mock import patch

from config import CHROMA_DB_DIR
from vectorstore.chroma_store import ChromaStore

@pytest.fixture(autouse=True)
def clean_chroma_dir(tmp_path):
    # Setup: Use a temp directory for Chroma
    temp_db_dir = tmp_path / "chroma_test_db"
    
    with patch("vectorstore.chroma_store.CHROMA_DB_DIR", temp_db_dir):
        ChromaStore._instance = None
        yield
        ChromaStore._instance = None

def test_chroma_store_persistence():
    store = ChromaStore.get_instance()
    store.add_records(
        ids=["doc1"],
        embeddings=[[0.1] * 384],
        metadatas=[{"document_name": "Test Doc"}],
        documents=["Test Content"]
    )
    assert store.get_count() == 1
    
    # Re-initialize
    ChromaStore._instance = None
    store2 = ChromaStore.get_instance()
    assert store2.get_count() == 1

def test_chroma_store_duplicate_prevention_stable_ids():
    store = ChromaStore.get_instance()
    store.add_records(
        ids=["doc1"],
        embeddings=[[0.1] * 384],
        metadatas=[{"document_name": "Test Doc"}],
        documents=["Test Content"]
    )
    
    assert store.get_count() == 1
    
    # Upsert with SAME id should just update/overwrite, not create duplicate
    store.add_records(
        ids=["doc1"],
        embeddings=[[0.2] * 384],
        metadatas=[{"document_name": "Test Doc V2"}],
        documents=["Test Content V2"]
    )
    
    assert store.get_count() == 1
    
    result = store.collection.get(ids=["doc1"])
    assert result["documents"][0] == "Test Content V2"
    assert result["metadatas"][0]["document_name"] == "Test Doc V2"

def test_chroma_store_metadata_preservation():
    store = ChromaStore.get_instance()
    
    complex_metadata = {
        "document_name": "Test Doc",
        "page_start": 1,
        "has_table": True,
        "none_value": None,
        "list_value": ["tag1", "tag2"]
    }
    
    store.add_records(
        ids=["meta1"],
        embeddings=[[0.1] * 384],
        metadatas=[complex_metadata],
        documents=["Metadata content"]
    )
    
    result = store.collection.get(ids=["meta1"])
    retrieved_meta = result["metadatas"][0]
    
    assert retrieved_meta["document_name"] == "Test Doc"
    assert retrieved_meta["page_start"] == 1
    assert retrieved_meta["has_table"] == True
    # None should be filtered out by chroma_store logic
    assert "none_value" not in retrieved_meta
    # Lists should be joined into comma-separated strings
    assert retrieved_meta["list_value"] == "tag1, tag2"
