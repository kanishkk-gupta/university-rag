# Five-Exercise Demo Report

## A. Application/use case
A transparent, educational university knowledge assistant that answers questions about BML Munjal University while visually exposing the mechanics of LLMs and RAG.

## B. Problem addressed
Demonstrating *how* AI systems retrieve and ground knowledge. Base LLMs hallucinate private institutional knowledge; this app proves the RAG solution visually.

## C. Knowledge source
Official BMU PDF documents parsed via structure-aware chunking (preserving tables and heading hierarchies).

## D. RAG approach
ChromaDB vector similarity search using cosine distance on 384-dimensional embeddings, formulated into a strict context prompt.

## E. LLM role
Code Llama 7B running locally via Ollama is strictly confined to answering from the injected context, acting as a language synthesizer rather than a knowledge base.

## F. Exercise 1 implementation
The **LLM Application** view fires simultaneous API calls. One bypasses the retriever entirely (`use_rag=False`), proving the base model's inadequacy. The other uses the full pipeline, proving RAG's efficacy.

## G. Exercise 2 implementation
The **Knowledge Base** view queries ChromaDB directly via new FastAPI endpoints to list documents, chunks, and exact 384-d float arrays. It uses a scatterplot to conceptualize the vector space.

## H. Exercise 3 implementation
The **RAG Pipeline** view intercepts the standard flow to break it into 7 discrete visual steps, calculating the exact query vector on the fly and exposing the raw chunks and similarity distances returned by ChromaDB.

## I. Exercise 4 implementation
The **Orchestration** view diagrams the service layout and features a real-time request trace logger that tracks the `POST /api/chat` flow from the frontend's perspective.

## J. Exercise 5 implementation
The **Dockerized** view provides a container map. A `Dockerfile` and `docker-compose.yml` have been provided to package the React frontend and FastAPI backend into clean containers.

## K. Architecture diagram
(Refer to the Orchestration and Dockerized views in the application UI).

## L. UI demonstration flow
1. Prove the problem (LLM App).
2. Show the data (Knowledge Base).
3. Trace the logic (RAG Pipeline).
4. Map the services (Orchestration).
5. Deploy the stack (Dockerized).

## M. Testing
Backend endpoints are fully tested via Pytest using FastAPI's `TestClient` and `unittest.mock`, ensuring robust fallback behavior if Ollama disconnects.

## N. Known limitations
- The 2D visualization in Exercise 2 is a simulated conceptual mapping of the 384-d vector, as real-time PCA calculation in browser JS was excluded to preserve minimalism.
- Local LLM inference speed depends entirely on host GPU capacity.
