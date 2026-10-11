"""Explainability utilities for producing model contribution summaries."""

from .model_report import build_text_report, normalize_contributions, top_features

__all__ = ["normalize_contributions", "top_features", "build_text_report"]
