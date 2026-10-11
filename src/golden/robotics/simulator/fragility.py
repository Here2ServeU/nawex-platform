"""Surgical-robot telemetry simulator with injectable "latent fragility" (creeping RTT, vibration, heat)."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any


class ClinicalSafetySimulator:
    def __init__(self, device_id: str = "SURG-ROBOT-01", seed: int | None = None) -> None:
        self.device_id = device_id
        self.rng = random.Random(seed)
        self.step = 0

    def generate_telemetry(self, anomaly: bool = False) -> dict[str, Any]:
        self.step += 1
        temp = 37.0 + self.rng.uniform(-0.2, 0.2)
        rtt = 12.0 + self.rng.uniform(-1, 1)
        vibration = self.rng.uniform(0.01, 0.03)
        if anomaly:  # desynced feedback loops: latency drives vibration drives heat
            rtt += self.step * 0.8
            vibration += self.step * 0.015
            temp += self.step * 0.12
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "device_id": self.device_id,
            "telemetry": {
                "kinematics": {
                    "joint_vibration_index": round(vibration, 4),
                    "motor_temp_celsius": round(temp, 2),
                },
                "network": {"cloud_rtt_ms": round(rtt, 2), "packet_loss": 0.015 if anomaly else 0.001},
            },
            "status": "FRAGILE" if anomaly else "OPERATIONAL",
        }
