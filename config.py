"""
config.py — Central configuration for the BMU University RAG ingestion pipeline.
All paths, thresholds, and tunable parameters live here.
"""

import os
from pathlib import Path

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DOCUMENTS_DIR = BASE_DIR / "documents"
DATA_DIR = BASE_DIR / "data"
EXTRACTED_DIR = DATA_DIR / "extracted"
CHUNKS_DIR = DATA_DIR / "chunks"
CHROMA_DB_DIR = DATA_DIR / "chroma"

# ─── Embedding & Vector Store Settings ────────────────────────────────────────
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
CHROMA_COLLECTION_NAME = "bmu_documents"
CODEBASE_CHROMA_COLLECTION_NAME = "bmu_codebase"
INDEXING_BATCH_SIZE = 64
MAX_EMBEDDING_CHUNK_CHARS = 1500    # If chunk is larger, we apply secondary split
EMBEDDING_BATCH_SIZE = 32           # SentenceTransformer encode batch size (keep ≤64 to avoid OOM)

# ─── Codebase Indexer Settings ────────────────────────────────────────────────
CODEBASE_CHUNK_LINES = 50           # Lines per code chunk
CODEBASE_CHUNK_OVERLAP_LINES = 10   # Overlap between consecutive code chunks

# ─── RAG Generation & LLM Settings ────────────────────────────────────────────
MODEL_CONFIGS = {
    # oom_safe=False: requires 4-6 GB RAM; will OOM-kill on low-memory systems
    "codellama:7b-instruct": {
        "display_name": "Code Llama 7B",
        "description": "Llama 2 based coding model",
        "oom_safe": False,
    },
    # oom_safe=True: ~1.9 GB RAM, safe on most systems
    "starcoder2:3b": {
        "display_name": "StarCoder2 3B",
        "description": "3B parameter base model from BigCode",
        "oom_safe": True,
    },
    # oom_safe=True: ~1 GB RAM, fastest on CPU, preferred default
    "qwen2.5-coder:1.5b": {
        "display_name": "Qwen 2.5 Coder 1.5B",
        "description": "Highly capable 1.5B coder from Qwen",
        "oom_safe": True,
    },
}
# DEFAULT: qwen2.5-coder:1.5b — only ~1GB RAM, fast on CPU, no OOM risk
# codellama:7b-instruct requires 4-6GB RAM and will OOM-kill on low-memory systems
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:1.5b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))  # 120s is enough for 1.5B model
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

# ─── LLM-as-Judge Settings ────────────────────────────────────────────────────
# Judge model: uses qwen2.5-coder:1.5b (same as lightest eval model) — lightweight
# and already installed. For a stricter separation use a different judge model.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen2.5-coder:1.5b")
JUDGE_TIMEOUT = int(os.getenv("JUDGE_TIMEOUT", "90"))  # Judge calls are shorter
MAX_CONTEXT_CHARS = 10000           # Rough context limit before truncation


# ─── Supported file types ─────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf"}

# ─── Native PDF Detection ─────────────────────────────────────────────────────
# A page with more than this many extracted characters is considered native text
NATIVE_TEXT_CHARS_THRESHOLD = 50
# Fraction of pages that must exceed the threshold to classify doc as native
NATIVE_TEXT_PAGE_FRACTION = 0.3

# ─── OCR Settings ─────────────────────────────────────────────────────────────
OCR_DPI = 300                       # Render resolution for scanned pages
OCR_ENGINE = "tesseract"
# Tesseract PSM modes:
#   3  = fully automatic page segmentation (default for policy text)
#   6  = assume uniform block of text (good for dense forms/tables)
#   11 = sparse text (some irregular layouts)
OCR_PSM_DEFAULT = 3                 # Used for standard policy/text pages
OCR_PSM_TABLE = 6                   # Used for pages expected to contain tables
OCR_LANG = "eng"
OCR_TIMEOUT = 120                   # seconds per page

# ─── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_SIZE_CHARS = 1800             # ~450 tokens at ~4 chars/token
CHUNK_OVERLAP_CHARS = 350           # ~87 tokens overlap
CHUNK_MIN_CHARS = 80                # Chunks smaller than this are flagged
CHUNK_MAX_CHARS = 8000              # Chunks larger than this are flagged

# ─── Table Detection ──────────────────────────────────────────────────────────
# Documents where table preservation is critical (matched by filename substring)
TABLE_CRITICAL_DOCS = [
    "Fee Payment Calendar",
    "Holiday List",
    "University Calendar",
    "DAC Policy",
]
# Minimum rows/columns for a detected structure to count as a real table
TABLE_MIN_ROWS = 2
TABLE_MIN_COLS = 2

# ─── Cleaning ─────────────────────────────────────────────────────────────────
CLEAN_HEADER_FOOTER_LINES = 3       # Lines at top/bottom to check for repetition
REPEATED_LINE_MIN_DOCS = 2          # Min pages a line must appear to be considered repeated
CLEAN_MIN_LINE_LENGTH = 3           # Lines shorter than this are stripped

# ─── Logging / Output ─────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
CHUNKS_OUTPUT_FILE = CHUNKS_DIR / "all_chunks.jsonl"
EXTRACTED_PAGES_SUFFIX = "_pages.jsonl"
