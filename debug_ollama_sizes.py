import time
import requests

from rag.pipeline import RAGPipeline
from rag.context_builder import ContextBuilder
from rag.prompt import build_user_prompt, RAG_SYSTEM_PROMPT

query = "What is the deadline for Odd Semester fee payment for existing students?"

pipeline = RAGPipeline()
retriever = pipeline.retriever

print("Retrieving chunks...")
chunks = retriever.retrieve(query, top_k=3)

def generate_with_timeout(sys_prompt, usr_prompt, label):
    print(f"\n--- Testing: {label} ---")
    payload = {
        "model": "codellama:7b-instruct",
        "system": sys_prompt,
        "prompt": usr_prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    t0 = time.time()
    try:
        resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
        t1 = time.time()
        if resp.status_code == 200:
            print(f"Time: {t1-t0:.2f}s | Response length: {len(resp.json().get('response', ''))}")
            print(f"Sample: {resp.json().get('response', '')[:100]}")
        else:
            print(f"Failed with status: {resp.status_code}")
    except Exception as e:
        print(f"Failed: {e}")

# Test A: Tiny
generate_with_timeout("You are an assistant.", "What is 2+2?", "Test A: Tiny Prompt")

# Test B: Question Only
usr = build_user_prompt(query)
sys_no_context = RAG_SYSTEM_PROMPT.format(context="")
generate_with_timeout(sys_no_context, usr, "Test B: Question Only")

# Test C: Question + 1 Chunk
ctx1, _ = ContextBuilder.build_context(chunks[:1])
sys1 = RAG_SYSTEM_PROMPT.format(context=ctx1)
generate_with_timeout(sys1, usr, "Test C: Question + 1 Chunk")

# Test D: Question + 3 Chunks
ctx3, _ = ContextBuilder.build_context(chunks[:3])
sys3 = RAG_SYSTEM_PROMPT.format(context=ctx3)
generate_with_timeout(sys3, usr, "Test D: Question + 3 Chunks")

print("Done testing sizes.")
