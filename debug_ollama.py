import time
import requests
import sys

from rag.pipeline import RAGPipeline
from rag.context_builder import ContextBuilder
from rag.prompt import build_user_prompt, RAG_SYSTEM_PROMPT

query = "What is the deadline for Odd Semester fee payment for existing students?"

pipeline = RAGPipeline()
retriever = pipeline.retriever

print("Retrieving chunks...", flush=True)
chunks = retriever.retrieve(query, top_k=3)
ctx3, _ = ContextBuilder.build_context(chunks[:3])
sys3 = RAG_SYSTEM_PROMPT.format(context=ctx3)
usr = build_user_prompt(query)

def test_ollama(sys_prompt, usr_prompt, label):
    print(f"\n--- {label} ---", flush=True)
    payload = {
        "model": "codellama:7b-instruct",
        "system": sys_prompt,
        "prompt": usr_prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    t0 = time.time()
    try:
        resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=240)
        t1 = time.time()
        if resp.status_code == 200:
            print(f"Time: {t1-t0:.2f}s | Response length: {len(resp.json().get('response', ''))}", flush=True)
        else:
            print(f"Failed with status: {resp.status_code}", flush=True)
    except Exception as e:
        print(f"Failed: {e}", flush=True)

test_ollama("You are an assistant.", "What is 2+2?", "TEST 1: Tiny prompt")
test_ollama("You are an assistant.", "What is BML Munjal University?", "TEST 2: BMU question without context")
test_ollama(sys3, usr, "TEST 3: EXACT RAG prompt")

print("Done.", flush=True)
