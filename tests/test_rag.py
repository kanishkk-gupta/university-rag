import pytest
from unittest.mock import patch, MagicMock
import json
import urllib.error

from rag.context_builder import ContextBuilder
from rag.generator import OllamaGenerator
from rag.pipeline import RAGPipeline

def test_context_builder_formatting():
    retrieval_results = [
        {
            "document_name": "Test Doc",
            "page_start": 1,
            "section": "Intro",
            "chunk_id": "chunk_1",
            "content_type": "text",
            "text": "This is a test."
        },
        {
            "document_name": "Table Doc",
            "page_start": 2,
            "content_type": "table",
            "table_id": "tab1",
            "text": "| A | B |\n|---|---|\n| 1 | 2 |"
        }
    ]
    
    context, sources = ContextBuilder.build_context(retrieval_results)
    
    assert "[SOURCE 1]" in context
    assert "Document: Test Doc" in context
    assert "Page: 1" in context
    assert "Section: Intro" in context
    assert "This is a test." in context
    
    assert "[SOURCE 2]" in context
    assert "Document: Table Doc" in context
    assert "Content Type: table" in context
    assert "Table ID: tab1" in context
    assert "| A | B |" in context
    
    assert len(sources) == 2
    assert sources[0]["source_id"] == 1
    assert sources[1]["source_id"] == 2

def test_context_builder_truncation():
    large_text = "A" * 6000
    retrieval_results = [
        {"document_name": "Doc1", "text": large_text},
        {"document_name": "Doc2", "text": large_text}
    ]
    
    with patch("rag.context_builder.MAX_CONTEXT_CHARS", 8000):
        context, sources = ContextBuilder.build_context(retrieval_results)
        
        # Only the first source should fit
        assert "Doc1" in context
        assert "Doc2" not in context
        assert len(sources) == 1

@patch("urllib.request.urlopen")
def test_generator_success(mock_urlopen):
    # Mock successful response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({"response": "This is the generated answer."}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    generator = OllamaGenerator()
    answer = generator.generate("System", "User")
    
    assert answer == "This is the generated answer."

@patch("urllib.request.urlopen")
def test_generator_connection_error(mock_urlopen):
    # Mock connection failure during health check
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
    
    generator = OllamaGenerator()
    with pytest.raises(ConnectionError, match="Ollama is unavailable"):
        generator.generate("System", "User")

@patch("rag.pipeline.Retriever")
@patch("rag.pipeline.OllamaGenerator")
def test_pipeline_insufficient_context(mock_generator_class, mock_retriever_class):
    # Mock empty retrieval
    mock_retriever = mock_retriever_class.get_instance.return_value
    mock_retriever.retrieve.return_value = []
    
    pipeline = RAGPipeline()
    result = pipeline.query("Test query")
    
    assert result["query"] == "Test query"
    assert "I couldn't find enough information" in result["answer"]
    assert len(result["sources"]) == 0

@patch("rag.pipeline.Retriever")
@patch("rag.pipeline.OllamaGenerator")
def test_pipeline_success(mock_generator_class, mock_retriever_class):
    mock_retriever = mock_retriever_class.get_instance.return_value
    mock_retriever.retrieve.return_value = [
        {"document_name": "Doc1", "page_start": 1, "text": "Content"}
    ]
    
    mock_generator = mock_generator_class.return_value
    mock_generator.generate.return_value = "Generated answer"
    
    pipeline = RAGPipeline()
    result = pipeline.query("Test query")
    
    assert result["answer"] == "Generated answer"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["document"] == "Doc1"
