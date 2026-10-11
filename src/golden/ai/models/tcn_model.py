"""Temporal Convolutional Network forecaster — causal dilated convolutions (Bai, Kolter & Koltun, 2018)."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn

from golden.ai.models.base import SequenceForecaster


class Chomp1d(nn.Module):
    """Trim the right-side padding so convolutions stay causal."""

    def __init__(self, chomp_size: int) -> None:
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, : -self.chomp_size].contiguous() if self.chomp_size else x


class TemporalBlock(nn.Module):
    def __init__(self, n_in: int, n_out: int, kernel_size: int, dilation: int, dropout: float) -> None:
        super().__init__()
        padding = (kernel_size - 1) * dilation
        self.net = nn.Sequential(
            nn.Conv1d(n_in, n_out, kernel_size, padding=padding, dilation=dilation),
            Chomp1d(padding),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Conv1d(n_out, n_out, kernel_size, padding=padding, dilation=dilation),
            Chomp1d(padding),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.downsample = nn.Conv1d(n_in, n_out, 1) if n_in != n_out else None
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(self.net(x) + res)


class TCNSLIPredictor(SequenceForecaster):
    kind = "tcn"

    def __init__(
        self,
        input_size: int = 1,
        num_channels: list[int] | None = None,
        kernel_size: int = 2,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.input_size = input_size
        self.num_channels = list(num_channels or [32, 32, 64])
        self.kernel_size = kernel_size
        self.dropout = dropout
        layers = []
        for i, out_ch in enumerate(self.num_channels):
            in_ch = input_size if i == 0 else self.num_channels[i - 1]
            layers.append(TemporalBlock(in_ch, out_ch, kernel_size, dilation=2**i, dropout=dropout))
        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(self.num_channels[-1], 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.network(x.transpose(1, 2))  # (B, L, C) -> (B, C, L)
        return self.fc(out[:, :, -1]).squeeze(-1)

    def config(self) -> dict[str, Any]:
        return {
            "input_size": self.input_size,
            "num_channels": self.num_channels,
            "kernel_size": self.kernel_size,
            "dropout": self.dropout,
        }

    @classmethod
    def build(cls, config: dict[str, Any]) -> TCNSLIPredictor:
        return cls(**config)
