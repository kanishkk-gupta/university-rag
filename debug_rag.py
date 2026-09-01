import time
import logging
from rag.pipeline import RAGPipeline
from rag.context_builder import ContextBuilder
from rag.prompt import build_user_prompt, RAG_SYSTEM_PROMPT
from retrieval.retriever import Retriever

logging.basicConfig(level=logging.INFO)

query = "What is the deadline for Odd Semester fee payment for existing students?"

print("--- DIAGNOSTIC SCRIPT STARTED ---")
start_time = time.time()

# Initialize components
pipeline = RAGPipeline()
retriever = pipeline.retriever

init_time = time.time()
print(f"Initialization took: {init_time - start_time:.2f}s")

# 1. Retrieval
print("\n--- 1. RETRIEVAL ---")
t0 = time.time()
retrieval_results = retriever.retrieve(query, top_k=3)
t1 = time.time()
print(f"Retrieval took: {t1 - t0:.2f}s")
print(f"Number of chunks retrieved: {len(retrieval_results)}")

for idx, res in enumerate(retrieval_results):
    print(f"  Chunk {idx+1}: {res.get('chunk_id')} | Distance: {res.get('distance', 0):.4f}")

# 2. Context Building
print("\n--- 2. CONTEXT BUILDING ---")
t2 = time.time()
context_str, sources = ContextBuilder.build_context(retrieval_results)
t3 = time.time()
print(f"Context building took: {t3 - t2:.2f}s")
print(f"Context length (chars): {len(context_str)}")

# 3. Prompt Construction
print("\n--- 3. PROMPT CONSTRUCTION ---")
system_prompt = RAG_SYSTEM_PROMPT.format(context=context_str)
user_prompt = build_user_prompt(query)
print(f"System prompt length (chars): {len(system_prompt)}")
print(f"User prompt length (chars): {len(user_prompt)}")
print(f"Total prompt length (chars): {len(system_prompt) + len(user_prompt)}")

# 4. Ollama Small Generation
print("\n--- 4. OLLAMA GENERATION (TINY PROMPT) ---")
generator = pipeline.generator
tiny_sys = "You are a helpful assistant."
tiny_usr = "What is 2+2?"
t4 = time.time()
try:
    ans1 = generator.generate(tiny_sys, tiny_usr)
    t5 = time.time()
    print(f"Tiny generation took: {t5 - t4:.2f}s")
    print(f"Response: {ans1.strip()}")
except Exception as e:
    print(f"Tiny generation failed: {e}")

# 5. Ollama Full Generation (with timeout)
print("\n--- 5. OLLAMA GENERATION (FULL RAG PROMPT) ---")
import socket
socket.setdefaulttimeout(30) # Enforce a 30s socket timeout globally just in case
t6 = time.time()
try:
    ans2 = generator.generate(system_prompt, user_prompt)
    t7 = time.time()
    print(f"Full generation took: {t7 - t6:.2f}s")
    print(f"Response length: {len(ans2)}")
except Exception as e:
    t7 = time.time()
    print(f"Full generation failed after {t7 - t6:.2f}s: {e}")
