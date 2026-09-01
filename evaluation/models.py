import json
from pathlib import Path
from config import MODEL_CONFIGS

DATASET_PATH = Path(__file__).parent / "dataset.json"

def get_dataset():
    with open(DATASET_PATH, "r") as f:
        return json.load(f)

def get_available_models():
    return list(MODEL_CONFIGS.keys())
