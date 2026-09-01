import logging
from typing import Dict, Any

from config import RAG_TOP_K
from retrieval.retriever import Retriever
from rag.context_builder import ContextBuilder
from rag.prompt import RAG_SYSTEM_PROMPT, build_user_prompt
from rag.generator import OllamaGenerator

logger = logging.getLogger(__name__)

class RAGPipeline:
    """
    Orchestrates the entire RAG pipeline from retrieval to generation.
    """
    
    def __init__(self):
        self.retriever = Retriever.get_instance()
        self.generator = OllamaGenerator()
        
    def check_readiness(self) -> bool:
        return self.generator.check_health()
        
    def query(self, user_query: str, top_k: int = RAG_TOP_K, use_rag: bool = True, model_name: str = None) -> Dict[str, Any]:
        """
        Executes the RAG flow (or base LLM flow) and returns a structured response.
        """
        logger.info(f"Starting RAG pipeline for query: '{user_query}'")
        
        if use_rag:
            # 1. Retrieve
            retrieval_results = self.retriever.retrieve(user_query, top_k=top_k)
            
            # 2. Build Context
            context_str, sources = ContextBuilder.build_context(retrieval_results)
            
            if not context_str:
                return {
                    "query": user_query,
                    "answer": "I couldn't find enough information in the BMU knowledge base to answer that reliably.",
                    "sources": [],
                    "retrieval_results": retrieval_results
                }
                
            # 3. Build Prompts
            system_prompt = RAG_SYSTEM_PROMPT.format(context=context_str)
            user_prompt = build_user_prompt(user_query)
        else:
            # Bypass RAG entirely
            retrieval_results = []
            sources = []
            system_prompt = "You are a helpful assistant. Answer the user's question directly."
            user_prompt = build_user_prompt(user_query)

        
        # 4. Generate Answer
        try:
            answer = self.generator.generate(system_prompt, user_prompt, model_name=model_name)
        except ConnectionError as e:
            logger.error(f"Generation failed: {e}")
            answer = f"Error: {e}"
            
        # 5. Return Structured Response
        return {
            "query": user_query,
            "answer": answer.strip(),
            "sources": sources,
            "retrieval_results": retrieval_results
        }
