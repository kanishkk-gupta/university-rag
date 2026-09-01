import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api.main import app

client = TestClient(app)

@patch("api.routes.rag_pipeline")
def test_health_check(mock_rag):
    mock_rag.check_readiness.return_value = True
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "rag_ready": True}

@patch("api.routes.rag_pipeline")
def test_chat(mock_rag):
    mock_rag.query.return_value = {
        "query": "test query",
        "answer": "test answer",
        "sources": [{"source_id": 1, "document": "Doc", "page": "1", "section": "sec", "chunk_id": "c1", "content_type": "text"}],
        "retrieval_results": []
    }
    
    response = client.post("/api/chat", json={"query": "test query"})
    assert response.status_code == 200
    assert response.json()["answer"] == "test answer"
    assert response.json()["sources"][0]["document"] == "Doc"

@patch("api.routes.retriever")
def test_retrieve(mock_retriever):
    mock_retriever.retrieve.return_value = [{"chunk_id": "c1", "text": "chunk text"}]
    
    response = client.post("/api/retrieve", json={"query": "test query"})
    assert response.status_code == 200
    assert response.json()["chunks"][0]["chunk_id"] == "c1"

@patch("api.routes.retriever")
def test_stats(mock_retriever):
    mock_retriever.store.collection.count.return_value = 100
    
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert response.json()["indexed_records"] == 100
