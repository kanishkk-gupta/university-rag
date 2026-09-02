import json
from pathlib import Path
from config import MODEL_CONFIGS

DATASET_PATH = Path(__file__).parent / "dataset.json"

# OOM-safe model list for evaluation.
# codellama:7b-instruct is excluded because it requires 4-6GB RAM
# and gets OOM-killed by the kernel on systems with limited RAM.
OOM_SAFE_MODELS = ["qwen2.5-coder:1.5b", "starcoder2:3b"]

def get_dataset():
    with open(DATASET_PATH, "r") as f:
        return json.load(f)

def get_available_models():
    # Only return models that are both configured AND OOM-safe
    configured = list(MODEL_CONFIGS.keys())
    return [m for m in OOM_SAFE_MODELS if m in configured]
