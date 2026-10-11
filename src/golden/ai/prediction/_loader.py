"""Cached, integrity-checked model loading shared by the predictors."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from golden.config import get_settings

logger = logging.getLogger(__name__)
_cache: dict[tuple[str, str, float], Any] = {}
_lock = threading.Lock()


def default_model_path(kind: str) -> Path:
    return Path(get_settings().model_dir) / f"{kind}_model.pt"


def load_cached(kind: str, model_path: str | Path | None) -> Any | None:
    """Return a loaded forecaster, or ``None`` when torch/checkpoint is unavailable."""
    path = Path(model_path) if model_path else default_model_path(kind)
    if not path.exists():
        return None
    try:
        from golden.ai.models import LSTMSLIPredictor, TCNSLIPredictor
    except ImportError:
        return None
    key = (kind, str(path.resolve()), path.stat().st_mtime)
    with _lock:
        if key not in _cache:
            settings = get_settings()
            cls = LSTMSLIPredictor if kind == "lstm" else TCNSLIPredictor
            _cache[key] = cls.load(
                path,
                manifest=settings.model_manifest or None,
                require_manifest=bool(settings.model_manifest),
            )
        return _cache[key]
