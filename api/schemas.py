from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union

class ChatRequest(BaseModel):
    query: str
    top_k: Optional[int] = None
    use_rag: Optional[bool] = True
    model_name: Optional[str] = None

class Source(BaseModel):
    source_id: int
    document: str
    page: Union[str, int]
    section: Optional[str] = None
    chunk_id: str
    content_type: str

class ChatResponse(BaseModel):
    query: str
    answer: str
    sources: List[Source]
    retrieval_results: List[Dict[str, Any]]

class RetrieveRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class CodebaseRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    model_name: Optional[str] = None

class RetrieveResponse(BaseModel):
    query: str
    chunks: List[Dict[str, Any]]
