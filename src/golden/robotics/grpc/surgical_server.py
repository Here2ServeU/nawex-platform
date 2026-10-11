"""Bi-directional gRPC telemetry server: each packet is checked by the SafetyInterceptor."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from concurrent import futures

import grpc

from golden.robotics.agents.safety_interceptor import SafetyInterceptor
from golden.robotics.grpc.generated import surgical_telemetry_pb2 as pb2
from golden.robotics.grpc.generated import surgical_telemetry_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)
_ACTIONS = {
    "NOMINAL": pb2.SafetyCommand.NOMINAL,
    "ENABLE_LOCAL_PERSISTENCE": pb2.SafetyCommand.REROUTE_TO_EDGE,
    "REROUTE_TO_EDGE": pb2.SafetyCommand.REROUTE_TO_EDGE,
    "SAFE_STATE_TRANSITION": pb2.SafetyCommand.SAFE_STATE_TRANSITION,
    "EMERGENCY_STOP": pb2.SafetyCommand.EMERGENCY_STOP,
}


class SurgicalTelemetryServicer(pb2_grpc.SurgicalTelemetryServicer):
    def __init__(self, interceptor: SafetyInterceptor | None = None) -> None:
        self.interceptor = interceptor or SafetyInterceptor()

    def StreamTelemetry(
        self, request_iterator: Iterator[pb2.TelemetryPacket], context
    ) -> Iterator[pb2.SafetyCommand]:
        for packet in request_iterator:
            verdict = self.interceptor.analyze_telemetry(
                {
                    "device_id": packet.device_id,
                    "telemetry": {
                        "network": {
                            "cloud_rtt_ms": packet.network.cloud_rtt_ms,
                            "packet_loss": packet.network.packet_loss_pct,
                        },
                        "kinematics": {
                            "joint_vibration_index": packet.kinematics.joint_vibration_index,
                            "motor_temp_celsius": packet.kinematics.motor_temp_celsius,
                        },
                    },
                }
            )
            yield pb2.SafetyCommand(
                recommended_action=_ACTIONS.get(verdict.action, pb2.SafetyCommand.NOMINAL),
                reason="; ".join(verdict.reasons) or "operational baseline maintained",
                command_id=f"CMD-{time.time_ns()}",
            )


def build_server(port: int = 50051, max_workers: int = 10) -> tuple[grpc.Server, int]:
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[("grpc.max_receive_message_length", 64 * 1024)],
    )
    pb2_grpc.add_SurgicalTelemetryServicer_to_server(SurgicalTelemetryServicer(), server)
    bound = server.add_insecure_port(f"[::]:{port}")  # terminate TLS at the mesh/sidecar in production
    return server, bound


def serve() -> None:
    server, port = build_server(int(os.getenv("PORT", "50051")))
    server.start()
    logger.info("robotics telemetry server listening", extra={"port": port})
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
