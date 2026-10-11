from __future__ import annotations

import pytest

from golden.robotics.agents.audit_governance_logger import AuditGovernanceLogger
from golden.robotics.agents.emergency_stop_handler import EmergencyStopHandler
from golden.robotics.agents.safety_interceptor import SafetyInterceptor
from golden.robotics.edge.local_persistence_service import LocalPersistenceService
from golden.robotics.simulator.fragility import ClinicalSafetySimulator


def test_nominal_telemetry_needs_no_intervention():
    packet = ClinicalSafetySimulator(seed=1).generate_telemetry(anomaly=False)
    assert SafetyInterceptor().analyze_telemetry(packet).action == "NOMINAL"


def test_latent_fragility_triggers_strongest_intervention(tmp_path):
    interceptor = SafetyInterceptor(incident_dir=tmp_path)
    packet = {
        "device_id": "SURG-ROBOT-TEST",
        "telemetry": {
            "network": {"cloud_rtt_ms": 48.5, "packet_loss": 0.0},
            "kinematics": {"joint_vibration_index": 0.095, "motor_temp_celsius": 37},
        },
    }
    verdict = interceptor.analyze_telemetry(packet)
    assert verdict.action == "SAFE_STATE_TRANSITION"  # outranks REROUTE_TO_EDGE
    assert len(verdict.reasons) == 2 and interceptor.failover_active
    assert list(tmp_path.glob("INC-*.json"))


def test_estop_latches_until_supervisor_reset():
    estop = EmergencyStopHandler()
    assert estop.trigger_estop("JOINT_04", "desync") is True
    assert estop.trigger_estop("JOINT_04", "desync") is False
    with pytest.raises(PermissionError):
        estop.reset("")
    assert estop.reset("supervisor-key") and not estop.estop_active


def test_governance_trail_and_edge_buffer(tmp_path):
    gov = AuditGovernanceLogger()
    gov.log_incident({"incident_id": "INC-1", "patient_id": "secret"})
    assert gov.verify() and gov.audit.entries()[0].data["patient_id"] == "[REDACTED]"
    edge = LocalPersistenceService(tmp_path, max_files=2)
    assert edge.save_telemetry_locally({"n": 1}) and edge.save_telemetry_locally({"n": 2})
    assert edge.save_telemetry_locally({"n": 3}) is None  # bounded
    assert [p["n"] for p in edge.drain()] == [1, 2]


def test_grpc_stream_roundtrip():
    pytest.importorskip("grpc")
    from golden.robotics.grpc.generated import surgical_telemetry_pb2 as pb2
    from golden.robotics.grpc.surgical_client import run
    from golden.robotics.grpc.surgical_server import build_server

    server, port = build_server(port=0)
    server.start()
    try:
        commands = run(f"localhost:{port}", packets=14, interval=0)
    finally:
        server.stop(grace=None)
    actions = [c.recommended_action for c in commands]
    assert actions[0] == pb2.SafetyCommand.NOMINAL
    assert pb2.SafetyCommand.SAFE_STATE_TRANSITION in actions or pb2.SafetyCommand.REROUTE_TO_EDGE in actions
