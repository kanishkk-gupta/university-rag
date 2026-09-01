"""
ingestion/__init__.py — Public API for the ingestion package.
"""

from .pipeline import run_pipeline
from .discovery import discover_documents

__all__ = ["run_pipeline", "discover_documents"]
