import json
import time
import logging
from pathlib import Path
from datetime import datetime

from rag.pipeline import RAGPipeline
from evaluation.models import get_dataset, get_available_models
from evaluation.metrics import (
    calculate_accuracy, 
    calculate_relevance,
    calculate_recall_at_k,
    check_hallucination,
    get_system_resources
)

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "reports"

def run_evaluation(mode="end_to_end"):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    dataset = get_dataset()
    models = get_available_models()
    
    rag = RAGPipeline()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"run_{timestamp}.jsonl"
    
    summary = {m: {"correct": 0, "total": 0, "latencies": []} for m in models}
    
    logger.info(f"Starting evaluation run with {len(dataset)} questions and {len(models)} models.")
    
    with open(results_file, "w") as f:
        for q in dataset:
            question = q["question"]
            answerable = q["answerable"]
            expected = q["expected_source"]
            
            # 1. Retrieve once for this question (fair comparison)
            t0 = time.time()
            retrieval_results = rag.retriever.retrieve(question, top_k=5)
            from rag.context_builder import ContextBuilder
            context_str, sources = ContextBuilder.build_context(retrieval_results)
            t_retrieval = time.time() - t0
            
            recall = calculate_recall_at_k(retrieval_results, expected)
            
            # 2. Evaluate each model
            for model_name in models:
                t1 = time.time()
                res = get_system_resources()
                
                # We use the pipeline's generator directly to pass context if mode == controlled
                from rag.prompt import RAG_SYSTEM_PROMPT, build_user_prompt
                system_prompt = RAG_SYSTEM_PROMPT.format(context=context_str)
                user_prompt = build_user_prompt(question)
                
                if not context_str:
                    answer = "I couldn't find enough information in the BMU knowledge base to answer that reliably."
                    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                else:
                    try:
                        answer, tokens = rag.generator.generate(system_prompt, user_prompt, model_name=model_name, return_usage=True)
                    except Exception as e:
                        logger.error(f"Error generating for {model_name}: {e}")
                        answer = f"Error: {e}"
                        tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                
                t2 = time.time()
                
                acc = calculate_accuracy(answer, q["reference_answer"], answerable)
                rel = calculate_relevance(answer, question)
                hal = check_hallucination(answer, context_str)
                
                record = {
                    "question_id": q["id"],
                    "question": question,
                    "model": model_name,
                    "mode": mode,
                    "answer": answer,
                    "retrieval_latency": t_retrieval,
                    "generation_latency": t2 - t1,
                    "total_latency": (t2 - t1) + t_retrieval,
                    "tokens": tokens,
                    "resources": res,
                    "metrics": {
                        "accuracy": 1 if acc else 0,
                        "relevance": rel,
                        "hallucination": hal,
                        "recall_at_5": recall
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
                summary[model_name]["total"] += 1
                if acc:
                    summary[model_name]["correct"] += 1
                summary[model_name]["latencies"].append(t2 - t1)
                
                f.write(json.dumps(record) + "\n")
                f.flush()
                
    logger.info("Evaluation complete.")
    
    # Generate summary
    summary_file = RESULTS_DIR / "summary_latest.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_evaluation()
