"""Shared behaviour for univariate SLI forecasters (LSTM, TCN).

Models are trained on z-normalised latency windows and forecast the next point. The normalisation
statistics and the SLO are stored in the checkpoint so inference is self-contained, and the forecast
is converted to a calibrated ``[0, 1]`` breach risk::

    risk = sigmoid((forecast - slo) / (0.1 * slo))   # 0.5 exactly at the SLO
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

import torch
from torch import nn

from golden.security.guardrails import clamp_score, validate_sequence
from golden.security.integrity import IntegrityError, safe_torch_load

logger = logging.getLogger(__name__)


class SequenceForecaster(nn.Module):
    kind: ClassVar[str] = "base"

    def __init__(self) -> None:
        super().__init__()
        self.norm_mean = 0.0
        self.norm_std = 1.0
        self.slo_ms = 200.0
        self.lookback = 24

    # subclasses implement forward(x: (batch, seq, 1)) -> (batch,)
    def config(self) -> dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError

    def set_normalization(self, mean: float, std: float, slo_ms: float, lookback: int) -> None:
        self.norm_mean = float(mean)
        self.norm_std = float(std) if std > 1e-9 else 1.0
        self.slo_ms = float(slo_ms)
        self.lookback = int(lookback)

    def _to_tensor(self, sequence: Sequence[float]) -> torch.Tensor:
        values = validate_sequence(sequence, min_length=2, low=-1e7, high=1e7)
        window = values[-self.lookback :]
        normed = [(v - self.norm_mean) / self.norm_std for v in window]
        device = next(self.parameters()).device
        return torch.tensor(normed, dtype=torch.float32, device=device).view(1, -1, 1)

    @torch.inference_mode()
    def forecast(self, sequence: Sequence[float]) -> float:
        self.eval()
        out = self.forward(self._to_tensor(sequence)).float().item()
        return out * self.norm_std + self.norm_mean

    def predict_risk(self, sequence: Sequence[float]) -> float:
        forecast = self.forecast(sequence)
        scale = max(0.1 * self.slo_ms, 1e-6)
        z = max(-50.0, min(50.0, (forecast - self.slo_ms) / scale))
        return clamp_score(1.0 / (1.0 + math.exp(-z)))

    # ------------------------------------------------------------------ persistence
    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {k: v.detach().cpu() for k, v in self.state_dict().items()}
        torch.save(
            {
                "kind": self.kind,
                "config": self.config(),
                "state_dict": state,
                "norm_mean": self.norm_mean,
                "norm_std": self.norm_std,
                "slo_ms": self.slo_ms,
                "lookback": self.lookback,
            },
            path,
        )
        return path

    @classmethod
    def build(cls, config: dict[str, Any]) -> SequenceForecaster:  # pragma: no cover - overridden
        raise NotImplementedError

    @classmethod
    def load(
        cls, path: str | Path, *, manifest: str | Path | None = None, require_manifest: bool = False
    ) -> SequenceForecaster | None:
        """Integrity-check and load a checkpoint; returns ``None`` (never raises) when unusable."""
        path = Path(path)
        if not path.exists():
            return None
        try:
            ckpt = safe_torch_load(path, manifest, required=require_manifest)
            if ckpt.get("kind") != cls.kind:
                logger.warning("checkpoint %s is a %s model, expected %s", path, ckpt.get("kind"), cls.kind)
                return None
            model = cls.build(ckpt["config"])
            model.load_state_dict(ckpt["state_dict"])
            model.set_normalization(ckpt["norm_mean"], ckpt["norm_std"], ckpt["slo_ms"], ckpt["lookback"])
            model.eval()
            return model
        except IntegrityError:
            logger.error("refusing to load %s: integrity check failed", path, exc_info=True)
            return None
        except Exception:
            logger.error("failed to load checkpoint %s", path, exc_info=True)
            return None
