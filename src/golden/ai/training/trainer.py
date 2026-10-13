"""GPU-aware training for the SLI forecasters.

Uses :mod:`golden.ai.accel` for device selection, mixed precision, pinned memory and optional
``torch.compile``, then writes the checkpoint plus a SHA-256 ``manifest.json`` so inference can verify
model integrity before loading.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from golden.ai.pipelines.data_loader import load_sample_sli_slo

logger = logging.getLogger(__name__)

ModelKind = Literal["lstm", "tcn"]


@dataclass(frozen=True)
class TrainResult:
    kind: str
    path: str
    device: str
    epochs: int
    final_loss: float
    seconds: float


def make_windows(series: np.ndarray, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    """Turn a 1-D series into (N, lookback, 1) inputs and (N,) next-step targets."""
    if len(series) <= lookback:
        raise ValueError(f"series of length {len(series)} is too short for lookback={lookback}")
    x = np.lib.stride_tricks.sliding_window_view(series[:-1], lookback)
    y = series[lookback:]
    return x[..., None].astype(np.float32), y.astype(np.float32)


def train_forecaster(
    kind: ModelKind,
    *,
    epochs: int = 3,
    lookback: int = 24,
    batch_size: int = 64,
    lr: float = 1e-3,
    slo_ms: float = 200.0,
    n_points: int = 2000,
    seed: int = 42,
    device: str | None = None,
):
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    from golden.ai import accel
    from golden.ai.models import LSTMSLIPredictor, TCNSLIPredictor

    torch.manual_seed(seed)
    cfg = accel.configure(device)

    series = load_sample_sli_slo(n_points=n_points, seed=seed)["latency_ms"].to_numpy(dtype=np.float64)
    mean, std = float(series.mean()), float(series.std() or 1.0)
    x, y = make_windows((series - mean) / std, lookback)

    loader = DataLoader(
        TensorDataset(torch.from_numpy(x), torch.from_numpy(y)),
        batch_size=batch_size,
        shuffle=True,
        pin_memory=cfg.pin_memory,
        generator=torch.Generator().manual_seed(seed),
    )

    model: LSTMSLIPredictor | TCNSLIPredictor
    if kind == "lstm":
        model = LSTMSLIPredictor()
    elif kind == "tcn":
        model = TCNSLIPredictor()
    else:
        raise ValueError("kind must be 'lstm' or 'tcn'")
    model.set_normalization(mean, std, slo_ms, lookback)
    model.to(cfg.device)
    runner = accel.maybe_compile(model, cfg)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scaler = accel.grad_scaler(cfg)
    loss_fn = torch.nn.MSELoss()
    non_blocking = cfg.device == "cuda"

    started = time.perf_counter()
    epoch_loss = float("nan")
    model.train()
    for epoch in range(max(epochs, 1)):
        total, count = 0.0, 0
        for xb, yb in loader:
            xb = xb.to(cfg.device, non_blocking=non_blocking)
            yb = yb.to(cfg.device, non_blocking=non_blocking)
            optimizer.zero_grad(set_to_none=True)
            with accel.autocast(cfg):
                loss = loss_fn(runner(xb).float(), yb)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            total += loss.item() * xb.size(0)
            count += xb.size(0)
        epoch_loss = total / max(count, 1)
        logger.info("epoch complete", extra={"model": kind, "epoch": epoch + 1, "loss": round(epoch_loss, 5)})

    model.eval()
    return model, TrainResult(kind, "", cfg.device, max(epochs, 1), epoch_loss, time.perf_counter() - started)


def train_and_save(
    model_type: ModelKind,
    output_dir: str | Path = "models",
    epochs: int = 3,
    **kwargs,
) -> TrainResult:
    """Train ``model_type``, save ``<output_dir>/<type>_model.pt`` and refresh ``manifest.json``."""
    from golden.security.integrity import write_manifest

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    model, result = train_forecaster(model_type, epochs=epochs, **kwargs)
    path = model.save(target_dir / f"{model_type}_model.pt")
    write_manifest(target_dir)
    return TrainResult(
        result.kind, str(path), result.device, result.epochs, result.final_loss, result.seconds
    )
