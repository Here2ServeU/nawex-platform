"""GPU telemetry model and collectors (``nvidia-smi`` locally; DCGM exporter in clusters)."""

from __future__ import annotations

import csv
import io
import logging
import shutil
import socket
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

NVIDIA_SMI_FIELDS = (
    "index,uuid,name,utilization.gpu,memory.used,memory.total,temperature.gpu,"
    "power.draw,power.limit,ecc.errors.uncorrected.volatile.total"
)


@dataclass
class GPUSample:
    node: str
    index: int
    model: str = "unknown"
    uuid: str = ""
    utilization_pct: float = 0.0
    memory_used_pct: float = 0.0
    memory_total_gb: float = 0.0
    temperature_c: float = 0.0
    power_w: float = 0.0
    power_limit_w: float = 0.0
    ecc_errors: int = 0
    xid_errors: int = 0
    idle_minutes: float = 0.0
    workload: str | None = None
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def gpu_id(self) -> str:
        return f"{self.node}/gpu{self.index}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["gpu_id"] = self.gpu_id
        return data


def _num(value: str, default: float = 0.0) -> float:
    value = (value or "").strip()
    if not value or value.startswith("[") or value.upper() in {"N/A", "[N/A]"}:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_nvidia_smi_csv(text: str, node: str | None = None) -> list[GPUSample]:
    """Parse ``nvidia-smi --query-gpu=<NVIDIA_SMI_FIELDS> --format=csv,noheader,nounits`` output."""
    node = node or socket.gethostname()
    samples = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 10:
            continue
        cells = [c.strip() for c in row]
        mem_used, mem_total = _num(cells[4]), _num(cells[5])
        samples.append(
            GPUSample(
                node=node,
                index=int(_num(cells[0])),
                uuid=cells[1],
                model=cells[2],
                utilization_pct=_num(cells[3]),
                memory_used_pct=round(100 * mem_used / mem_total, 2) if mem_total else 0.0,
                memory_total_gb=round(mem_total / 1024, 1),
                temperature_c=_num(cells[6]),
                power_w=_num(cells[7]),
                power_limit_w=_num(cells[8]),
                ecc_errors=int(_num(cells[9])),
            )
        )
    return samples


def collect_local(timeout: float = 5.0) -> list[GPUSample]:
    """Query local NVIDIA GPUs; returns ``[]`` when ``nvidia-smi`` is unavailable."""
    binary = shutil.which("nvidia-smi")
    if not binary:
        return []
    try:
        out = subprocess.run(  # noqa: S603 - fixed binary path and arguments, no shell
            [binary, f"--query-gpu={NVIDIA_SMI_FIELDS}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("nvidia-smi failed: %s", exc)
        return []
    return parse_nvidia_smi_csv(out)
