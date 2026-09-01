import logging
from typing import List, Dict, Any

from retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

# BMU specific evaluation dataset
EVALUATION_QUERIES = [
    {
        "query": "When is the deadline for Odd Semester fee payment for existing students?",
        "expected_document": "Fee Payment Calendar-Academic Year-2026-27"
    },
    {
        "query": "What are the penalties for ragging?",
        "expected_document": "Anti Ragging Policy V 1.0"
    },
    {
        "query": "When is Mahavir Jayanti in 2026?",
        "expected_document": "Holiday List 2026 (1) (1)"
    },
    {
        "query": "Who is the SPOC for the DAC Policy?",
        "expected_document": "DAC Policy- Version 02 (1)"
    },
    {
        "query": "What is the attendance requirement?",
        "expected_document": "Student Handbook 2026-27_V3"
    },
    {
        "query": "What happens if a student is caught with drugs on campus?",
        "expected_document": "Drug Abuse Policy March 2024"
    },
    {
        "query": "What is the date for the Mid-Semester Examination for SoLS Batch 2026?",
        "expected_document": "University Calendar (Academic Year 2026-27) (2)"
    },
    {
        "query": "What are the rules regarding dress code and personal appearance?",
        "expected_document": "Code of Ethical & Professional Conduct- Student - Copy"
    },
    {
        "query": "How much is the Late Fee fine after the due date for existing students?",
        "expected_document": "Fee Payment Calendar-Academic Year-2026-27"
    },
    {
        "query": "What is the procedure for appealing a disciplinary action?",
        "expected_document": "DAC Policy- Version 02 (1)"
    },
    {
        "query": "When is the hostel reporting date for PG students?",
        "expected_document": "University Calendar (Academic Year 2026-27) (2)"
    },
    {
        "query": "What is the definition of ragging according to the policy?",
        "expected_document": "Anti Ragging Policy V 1.0"
    },
    {
        "query": "Are students allowed to consume alcohol in their hostel rooms?",
        "expected_document": "Drug Abuse Policy March 2024"
    },
    {
        "query": "What is the holiday date for Diwali?",
        "expected_document": "Holiday List 2026 (1) (1)"
    },
    {
        "query": "What constitutes academic misconduct or plagiarism?",
        "expected_document": "Code of Ethical & Professional Conduct- Student - Copy"
    },
    {
        "query": "Can I pay my fees using a Demand Draft?",
        "expected_document": "Fee Payment Calendar-Academic Year-2026-27"
    },
    {
        "query": "What is the composition of the Disciplinary Action Committee?",
        "expected_document": "DAC Policy- Version 02 (1)"
    },
    {
        "query": "When do classes start for the Even Semester?",
        "expected_document": "University Calendar (Academic Year 2026-27) (2)"
    },
    {
        "query": "What are the library rules and timing?",
        "expected_document": "Student Handbook 2026-27_V3"
    },
    {
        "query": "Who should a student contact in case of a medical emergency?",
        "expected_document": "Student Handbook 2026-27_V3"
    }
]

def run_evaluation():
    retriever = Retriever.get_instance()
    
    total_queries = len(EVALUATION_QUERIES)
    recall_at_1 = 0
    recall_at_3 = 0
    recall_at_5 = 0
    mrr_sum = 0.0
    
    failures = []
    
    print("\n" + "="*50)
    print("RETRIEVAL EVALUATION SESSIONS")
    print("="*50)
    
    for idx, eval_data in enumerate(EVALUATION_QUERIES):
        query = eval_data["query"]
        expected_doc = eval_data["expected_document"]
        
        results = retriever.retrieve(query, top_k=5)
        
        # Check ranks
        rank = -1
        for i, res in enumerate(results):
            if expected_doc in res["document_name"]:
                rank = i + 1
                break
                
        # Metrics
        if rank == 1:
            recall_at_1 += 1
        if 1 <= rank <= 3:
            recall_at_3 += 1
        if 1 <= rank <= 5:
            recall_at_5 += 1
            
        if rank > 0:
            mrr_sum += 1.0 / rank
        else:
            failures.append({
                "query": query,
                "expected": expected_doc,
                "top_1_doc": results[0]["document_name"] if results else "None",
                "top_1_text": results[0]["text"][:150] if results else "None"
            })
            
        # Logging
        is_correct = "YES" if rank > 0 else "NO"
        print(f"\nQUERY:\n{query}")
        print(f"\nEXPECTED:\n{expected_doc}")
        print("\nTOP 5:")
        for i, res in enumerate(results):
            doc = res.get('document_name', 'Unknown')
            page = res.get('page_start', '?')
            score = res.get('distance', 0)
            print(f"{i+1}. {doc} / page {page} / {score:.4f}")
        print(f"\nCORRECT SOURCE:\n{is_correct}")
            
    print("\n" + "="*50)
    print("EVALUATION METRICS")
    print("="*50)
    print(f"Total Queries: {total_queries}")
    print(f"Recall@1: {recall_at_1 / total_queries:.2%}")
    print(f"Recall@3: {recall_at_3 / total_queries:.2%}")
    print(f"Recall@5: {recall_at_5 / total_queries:.2%}")
    print(f"MRR:      {mrr_sum / total_queries:.4f}")
    
    if failures:
        print("\n" + "="*50)
        print("QUALITATIVE FAILURES")
        print("="*50)
        for f in failures:
            print(f"\nQuery: {f['query']}")
            print(f"Expected: {f['expected']}")
            print(f"Got (Top 1): {f['top_1_doc']}")
            print(f"Snippet: {f['top_1_text']}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_evaluation()
