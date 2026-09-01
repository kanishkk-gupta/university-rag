import pytest
from vectorstore.indexer import split_oversized_chunk

def test_split_oversized_chunk_text():
    # Create a chunk with 2000 'A's and 2000 'B's separated by double newline
    text = ("A" * 1600) + "\n\n" + ("B" * 1600)
    chunk = {
        "chunk_id": "test_text_chunk",
        "text": text,
        "has_table": False,
        "document_name": "Test Doc"
    }
    
    sub_chunks = split_oversized_chunk(chunk)
    assert len(sub_chunks) == 2
    assert sub_chunks[0]["chunk_id"] == "test_text_chunk_part1"
    assert sub_chunks[1]["chunk_id"] == "test_text_chunk_part2"
    assert "A" * 1600 in sub_chunks[0]["text"]
    assert "B" * 1600 in sub_chunks[1]["text"]
    assert sub_chunks[0]["document_name"] == "Test Doc"

def test_split_oversized_chunk_table():
    header = "| Col1 | Col2 |\n|---|---|"
    data1 = "\n| Data1 | Data2 |" * 100 # 1700 chars
    data2 = "\n| Data3 | Data4 |" * 100 # 1700 chars
    
    chunk = {
        "chunk_id": "test_table_chunk",
        "text": header + data1 + data2,
        "has_table": True,
        "document_name": "Test Table Doc"
    }
    
    sub_chunks = split_oversized_chunk(chunk)
    # Should split into at least 2 parts, both preserving the header
    assert len(sub_chunks) >= 2
    assert sub_chunks[0]["text"].startswith(header)
    assert sub_chunks[1]["text"].startswith(header)
    assert sub_chunks[0]["chunk_id"] == "test_table_chunk_part1"
    
def test_no_split_small_chunk():
    chunk = {
        "chunk_id": "small_chunk",
        "text": "This is small",
        "has_table": False
    }
    sub_chunks = split_oversized_chunk(chunk)
    assert len(sub_chunks) == 1
    assert sub_chunks[0]["chunk_id"] == "small_chunk"
