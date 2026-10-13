"""GPU acceleration for training and inference.

* Device auto-selection: CUDA → Apple MPS → CPU (override with ``GOLDEN_DEVICE=cuda|mps|cpu``).
* Automatic mixed precision: bf16 when the GPU supports it, else fp16 with ``GradScaler``
  (``GOLDEN_AMP=false`` disables).
* TF32 matmul/cudnn on Ampere+, ``cudnn.benchmark`` for fixed-shape workloads.
* Pinned host memory + non-blocking H2D copies in data loaders.
* Optional ``torch.compile`` (``GOLDEN_COMPILE=true``).

Everything degrades to plain CPU execution, so the same code path runs in CI and on laptops.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from golden.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccelConfig:
    device: str
    amp_dtype: Any | None  # torch.dtype or None when AMP is off
    use_grad_scaler: bool
    pin_memory: bool
    compile: bool

    @property
    def is_gpu(self) -> bool:
        return self.device in {"cuda", "mps"}


def select_device(preference: str | None = None) -> str:
    import torch

    pref = (preference or get_settings().device or "auto").lower()
    if pref in {"cuda", "mps", "cpu"}:
        if pref == "cuda" and not torch.cuda.is_available():
            logger.warning("GOLDEN_DEVICE=cuda requested but CUDA is unavailable; using CPU")
            return "cpu"
        if pref == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
            logger.warning("GOLDEN_DEVICE=mps requested but MPS is unavailable; using CPU")
            return "cpu"
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def configure(
    preference: str | None = None, *, amp: bool | None = None, compile: bool | None = None
) -> AccelConfig:
    """Resolve the accelerator configuration and apply global backend tuning."""
    import torch

    settings = get_settings()
    device = select_device(preference)
    amp_on = settings.amp if amp is None else amp
    amp_dtype = None
    scaler = False

    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.backends.cudnn.benchmark = True
        if amp_on:
            if torch.cuda.is_bf16_supported():
                amp_dtype = torch.bfloat16
            else:
                amp_dtype, scaler = torch.float16, True
    elif device == "mps" and amp_on:
        amp_dtype = torch.float16  # MPS autocast supports fp16; no scaler needed

    cfg = AccelConfig(
        device=device,
        amp_dtype=amp_dtype,
        use_grad_scaler=scaler,
        pin_memory=device == "cuda",
        compile=settings.compile if compile is None else compile,
    )
    logger.info("accelerator configured", extra={"device": cfg.device, "amp": str(cfg.amp_dtype)})
    return cfg


@contextlib.contextmanager
def autocast(cfg: AccelConfig) -> Iterator[None]:
    import torch

    if cfg.amp_dtype is None:
        yield
        return
    with torch.autocast(device_type=cfg.device, dtype=cfg.amp_dtype):
        yield


def grad_scaler(cfg: AccelConfig) -> Any:
    """Return a GradScaler for fp16 CUDA training, or a no-op stand-in."""
    import torch

    if cfg.use_grad_scaler:
        return torch.amp.GradScaler("cuda")
    return _NoScaler()


class _NoScaler:
    def scale(self, loss: Any) -> Any:
        return loss

    def step(self, optimizer: Any) -> None:
        optimizer.step()

    def update(self) -> None:
        return None


def maybe_compile(model: Any, cfg: AccelConfig) -> Any:
    if not cfg.compile:
        return model
    import torch

    try:
        return torch.compile(model)
    except Exception as exc:  # compile is an optimization, never a hard dependency
        logger.warning("torch.compile unavailable (%s); running eager", exc)
        return model


def device_report() -> dict[str, Any]:
    """Describe available accelerators (used by ``golden gpu doctor`` and the GPU service)."""
    try:
        import torch
    except ImportError:
        return {"torch": None, "device": "cpu", "cuda": False, "mps": False, "gpus": []}
    gpus = []
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            gpus.append(
                {
                    "index": i,
                    "name": props.name,
                    "memory_gb": round(props.total_memory / 1e9, 1),
                    "compute_capability": f"{props.major}.{props.minor}",
                    "bf16": torch.cuda.is_bf16_supported(),
                }
            )
    return {
        "torch": torch.__version__,
        "device": select_device(),
        "cuda": torch.cuda.is_available(),
        "mps": bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available()),
        "gpus": gpus,
    }
