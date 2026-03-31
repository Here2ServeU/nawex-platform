"""Training orchestration for reliability sequence models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..pipelines.train_lstm import train_lstm
from ..pipelines.train_tcn import train_tcn


def train_and_save(
    model_type: Literal["lstm", "tcn"],
    output_dir: str | Path = "models",
    epochs: int = 3,
) -> str:
    """Train one model variant and persist its checkpoint path."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if model_type == "lstm":
        model = train_lstm(epochs=epochs)
        path = target_dir / "lstm_model.pt"
    elif model_type == "tcn":
        model = train_tcn(epochs=epochs)
        path = target_dir / "tcn_model.pt"
    else:
        raise ValueError("model_type must be one of: 'lstm', 'tcn'")

    model.save(str(path))
    return str(path)
