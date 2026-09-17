# Release v2.0.0: Enterprise Guardrails & LLM-as-a-Judge Evaluation

We are incredibly excited to announce the release of **v2.0.0** of the BMU University RAG platform. 

This release transforms the system from an educational prototype into a highly reliable, controlled, and observable AI architecture. We have fundamentally changed how we handle LLM inputs/outputs and how we evaluate model performance.

## 🛡️ Complete Guardrail Pipeline Added
To ensure the AI operates reliably and safely in a university context, we've introduced a robust Guardrail system that intercepts queries before they hit the LLM, and validates responses before they reach the user.
- **Input Guardrails**:
  - `ScopeGuard`: Restricts interactions strictly to university topics.
  - `PIIGuard`: Prevents the leakage/logging of personal identifiable information (Aadhaar, Phone numbers).
  - `ContentGuard`: Filters offensive/inappropriate language.
  - `InputLengthGuard`: Protects against prompt injection and context window overflow.
- **Output Guardrails**:
  - `ContextGroundingGuard`: Enforces semantic grounding to eliminate hallucinated answers.
  - `RefusalConsistencyGuard`: Guarantees the LLM gracefully refuses to answer when information is unavailable.
  - `SourceCitationGuard`: Ensures every answer explicitly links to the source document chunk.

## 📊 Multi-Model Category Evaluation (LLM-as-a-Judge)
We've completely overhauled our evaluation methodology, moving away from brittle, hardcoded heuristics.
- Integrated a powerful **LLM-as-a-judge** module alongside Sentence-Transformer **Semantic Similarity** to objectively grade answers on Accuracy, Completeness, and Relevance.
- Deployed a **Highly Optimized Parallel Runner** that dynamically tests models (`starcoder2:3b`, `qwen2.5-coder:1.5b`) across 7 unique categories (Explanation, Refactoring, RAG, etc.).
- Auto-generates detailed markdown reports declaring category winners.

## 💻 Frontend UI Upgrades
- **New Guardrails Dashboard:** Visual interface demonstrating active guards, a Live output tester, and programmatic execution of the 20+ Guardrail tests directly in the browser.
- **Live Output Validation:** The main RAG pipeline UI now features real-time visual "Step 00" (Input Checking) and "Step 09" (Output Validation) widgets.
- **Evaluation Dashboard:** Rewritten to render dynamic category-by-category performance breakdowns based on the LLM judge.

## 🧪 Comprehensive Pytest Suite
- Added a 24-case `pytest` suite simulating Edge cases to rigorously validate the RAG pipeline's resistance to hallucination and refusal mechanics.

**Full Changelog**: https://github.com/yourusername/university-rag/compare/v1.0.0...v2.0.0
