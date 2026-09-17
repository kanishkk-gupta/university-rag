import json
from pathlib import Path
from config import MODEL_CONFIGS

DATASET_PATH = Path(__file__).parent / "dataset.json"


def get_dataset():
    """Load the canonical evaluation dataset from dataset.json."""
    with open(DATASET_PATH, "r") as f:
        return json.load(f)


def get_available_models():
    """
    Returns models that are both present in MODEL_CONFIGS and flagged as OOM-safe.
    Add new models to config.py with oom_safe=True to include them automatically —
    no changes needed here.
    """
    return [m for m, cfg in MODEL_CONFIGS.items() if cfg.get("oom_safe", False)]
