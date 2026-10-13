# GPU Acceleration Guide

How the platform trains and serves its models (LSTM / TCN reliability predictors, fraud and
clinical models) on GPUs. Everything lives in `src/golden/ai/accel.py` and is used by
`golden train`, `golden demo engine` and the inference runtime.

## Install

The core package is CPU-only and torch-free. Install the `ml` extra for training:

```bash
# CUDA 12.x wheels (Linux / Windows with an NVIDIA driver)
pip install -e ".[dev,ml]" --extra-index-url https://download.pytorch.org/whl/cu124

# Apple Silicon (MPS) or CPU-only
pip install -e ".[dev,ml]"

golden train --model lstm --epochs 3
python -c "from golden.ai.accel import device_report; print(device_report())"
```

## What happens automatically

| Feature | Behaviour |
|---|---|
| **Device auto-select** | `cuda` → `mps` (Apple Silicon) → `cpu`. A requested but unavailable device logs a warning and falls back to CPU. |
| **Mixed precision (AMP)** | CUDA: `bfloat16` when `torch.cuda.is_bf16_supported()` (Ampere+), otherwise `float16` with a `torch.amp.GradScaler` to prevent gradient underflow. MPS: `float16` autocast, no scaler. CPU: full precision. |
| **TF32** | `torch.backends.cuda.matmul.allow_tf32` and `cudnn.allow_tf32` on Ampere+ — ~free speed-up for fp32 matmuls/convs. |
| **cudnn.benchmark** | Enabled on CUDA so cuDNN picks the fastest kernels for the fixed sequence shapes used by the LSTM/TCN models. |
| **Pinned memory + non_blocking** | DataLoaders use `pin_memory=True` on CUDA and tensors move with `.to(device, non_blocking=True)`, overlapping host→device copies with compute. |
| **torch.compile** (optional) | `GOLDEN_COMPILE=true` wraps the model in `torch.compile`; if compilation is unavailable it logs a warning and runs eagerly. |
| **inference_mode** | Inference runs under `torch.inference_mode()` (no autograd tracking) plus autocast. |

Training loop shape (simplified):

```python
from golden.ai import accel

cfg = accel.configure()                       # device, AMP dtype, scaler, pin_memory, compile
model = accel.maybe_compile(model.to(cfg.device), cfg)
scaler = accel.grad_scaler(cfg)               # real GradScaler only for fp16 on CUDA

for x, y in loader:                           # loader built with pin_memory=cfg.pin_memory
    x = x.to(cfg.device, non_blocking=True)
    y = y.to(cfg.device, non_blocking=True)
    optimizer.zero_grad(set_to_none=True)
    with accel.autocast(cfg):
        loss = criterion(model(x), y)
    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()
```

## Environment variables

| Variable | Default | Values |
|---|---|---|
| `GOLDEN_DEVICE` | `auto` | `auto` \| `cuda` \| `mps` \| `cpu` |
| `GOLDEN_AMP` | `true` | `false` disables mixed precision (debugging numerical issues) |
| `GOLDEN_COMPILE` | `false` | `true` enables `torch.compile` |
| `GOLDEN_MODEL_MANIFEST` | `<model_dir>/manifest.json` | Checkpoints are SHA-256 verified before loading — see [AI safety](../security/ai-safety.md) |

## Containers & Kubernetes

- Use a CUDA-enabled build of the image (base `nvidia/cuda` runtime + cu124 torch wheels) for GPU nodes.
- Request GPUs with `resources.limits: {nvidia.com/gpu: 1}` (or a MIG profile such as
  `nvidia.com/mig-1g.10gb: 1`); the NVIDIA GPU Operator provides drivers, device plugin and DCGM exporter.
- In docker compose: `deploy.resources.reservations.devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `device_report()` shows `cpu` on a GPU host | Driver / CUDA wheel mismatch — reinstall torch from the matching `--extra-index-url` |
| NaN loss with fp16 | Ensure the GradScaler is used (automatic on CUDA fp16) or set `GOLDEN_AMP=false` |
| First epoch slow, later fast | Expected: `cudnn.benchmark` autotuning and `torch.compile` warm-up |
| OOM | Reduce batch size; bf16 halves activation memory vs fp32 |

Fleet-level GPU efficiency (utilization, thermals, savings) is covered by the
[GPU / AI-infrastructure domain](../verticals/gpu.md).
