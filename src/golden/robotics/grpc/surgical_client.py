"""Robot-side gRPC client streaming simulated telemetry and obeying safety commands."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator

import grpc

from golden.robotics.grpc.generated import surgical_telemetry_pb2 as pb2
from golden.robotics.grpc.generated import surgical_telemetry_pb2_grpc as pb2_grpc
from golden.robotics.simulator.fragility import ClinicalSafetySimulator

logger = logging.getLogger(__name__)


def telemetry_stream(
    packets: int = 20, fail_after: int = 10, interval: float = 0.5
) -> Iterator[pb2.TelemetryPacket]:
    sim = ClinicalSafetySimulator()
    for i in range(packets):
        data = sim.generate_telemetry(anomaly=i >= fail_after)
        t = data["telemetry"]
        yield pb2.TelemetryPacket(
            device_id=data["device_id"],
            timestamp=data["timestamp"],
            kinematics=pb2.TelemetryPacket.Kinematics(
                joint_vibration_index=t["kinematics"]["joint_vibration_index"],
                motor_temp_celsius=t["kinematics"]["motor_temp_celsius"],
            ),
            network=pb2.TelemetryPacket.Network(
                cloud_rtt_ms=t["network"]["cloud_rtt_ms"], packet_loss_pct=t["network"]["packet_loss"]
            ),
        )
        if interval:
            time.sleep(interval)


def run(target: str | None = None, packets: int = 20, interval: float = 0.5) -> list[pb2.SafetyCommand]:
    target = target or os.getenv("ROBOTICS_SERVER", "localhost:50051")
    commands = []
    with grpc.insecure_channel(target) as channel:
        stub = pb2_grpc.SurgicalTelemetryStub(channel)
        for command in stub.StreamTelemetry(telemetry_stream(packets, interval=interval)):
            commands.append(command)
            logger.info(
                "safety command", extra={"action": command.recommended_action, "reason": command.reason}
            )
            if command.recommended_action == pb2.SafetyCommand.EMERGENCY_STOP:
                break
    return commands


if __name__ == "__main__":
    run()
