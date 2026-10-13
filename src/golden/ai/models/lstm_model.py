"""LSTM SLI forecaster — captures long-range sequential dependencies (Hochreiter & Schmidhuber, 1997)."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn

from golden.ai.models.base import SequenceForecaster


class LSTMSLIPredictor(SequenceForecaster):
    kind = "lstm"

    def __init__(self, input_size: int = 1, hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :]).squeeze(-1)

    def config(self) -> dict[str, Any]:
        return {
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
        }

    @classmethod
    def build(cls, config: dict[str, Any]) -> LSTMSLIPredictor:
        return cls(**config)
