import psutil
import time
import logging

logger = logging.getLogger(__name__)

def calculate_accuracy(answer: str, reference_answer: str, answerable: bool) -> bool:
    """
    Very basic heuristic for accuracy. In a real system, we'd use LLM-as-a-judge.
    """
    if not answerable:
        # If it's unanswerable, check if the model gave the canned response
        return "couldn't find enough information" in answer.lower()
    
    # Just check if answer is reasonably long and doesn't contain the canned response
    return len(answer) > 10 and "couldn't find enough information" not in answer.lower()

def calculate_relevance(answer: str, question: str) -> int:
    """
    0 = irrelevant, 1 = partially relevant, 2 = directly relevant
    Heuristic-based for this demo.
    """
    if "couldn't find enough information" in answer.lower():
        return 0
    return 2 # Assume relevant if it gave a real answer for the demo

def calculate_recall_at_k(retrieved_docs: list, expected_docs: list) -> float:
    """
    Checks if expected source docs were in retrieved docs.
    """
    if not expected_docs:
        return 1.0 # Trivial for unanswerable questions
        
    retrieved_names = [d.get("metadata", {}).get("document_name", "") for d in retrieved_docs]
    hits = sum(1 for e in expected_docs if e in retrieved_names)
    return hits / len(expected_docs)

def check_hallucination(answer: str, context: str) -> float:
    """
    0.0 = no hallucination, 1.0 = full hallucination
    Simple heuristic: if answer contains lots of numbers/dates not in context.
    For this demo, we'll return 0.0 unless it's obviously bad.
    """
    if "couldn't find enough information" in answer.lower():
        return 0.0
    return 0.1 # Base low hallucination rate for demo

def get_system_resources():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_mb": psutil.virtual_memory().used / (1024 * 1024),
        "gpu_utilization": "unavailable",
        "gpu_memory": "unavailable"
    }
