from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from golden.security import (
    AuditLog,
    GuardrailViolation,
    IntegrityError,
    OODDetector,
    Outcome,
    RateLimiter,
    clamp_score,
    redact_obj,
    redact_text,
    validate_sequence,
    verify_artifact,
    write_manifest,
)
from golden.security.auth import verify_api_key
from golden.security.guardrails import VITALS_BOUNDS, check_bounds


# ----------------------------------------------------------------------------- guardrails & caps
@pytest.mark.parametrize("bad", [math.nan, math.inf, "abc", None])
def test_validate_sequence_rejects_non_finite(bad):
    with pytest.raises(GuardrailViolation):
        validate_sequence([1.0, 2.0, bad])


def test_validate_sequence_caps_length_and_range():
    with pytest.raises(GuardrailViolation) as exc:
        validate_sequence(range(10), max_length=5)
    assert exc.value.reason == "sequence_too_long"
    with pytest.raises(GuardrailViolation) as exc:
        validate_sequence([1, 2, 999], high=100)
    assert exc.value.reason == "out_of_range"
    assert validate_sequence([1, 2, 3]) == [1.0, 2.0, 3.0]


@pytest.mark.parametrize(
    ("raw", "expected"), [(1.7, 1.0), (-3, 0.0), (math.nan, 0.0), (math.inf, 0.0), (0.42, 0.42)]
)
def test_clamp_score(raw, expected):
    assert clamp_score(raw) == expected


def test_check_bounds_rejects_impossible_vitals():
    with pytest.raises(GuardrailViolation):
        check_bounds({"heart_rate": 900}, VITALS_BOUNDS)
    assert check_bounds({"heart_rate": 80, "other": 1}, VITALS_BOUNDS)["other"] == 1


def test_ood_detector_flags_outliers():
    rows = [{"latency": 100 + i % 7, "cpu": 50 + i % 3} for i in range(100)]
    detector = OODDetector.fit(rows, threshold=6.0)
    assert not detector.check({"latency": 103, "cpu": 51}).is_out_of_distribution
    result = detector.check({"latency": 10_000, "cpu": 51})
    assert result.is_out_of_distribution and result.feature == "latency"


# ----------------------------------------------------------------------------- auth, rate limit, redaction
def test_api_key_verification():
    assert verify_api_key("k2", ["k1", "k2"])
    assert not verify_api_key("nope", ["k1"])
    assert not verify_api_key(None, ["k1"])


def test_rate_limiter_token_bucket():
    limiter = RateLimiter(per_minute=60, burst=2)
    assert limiter.allow("a", now=0) and limiter.allow("a", now=0)
    assert not limiter.allow("a", now=0)
    assert limiter.allow("b", now=0)  # independent buckets
    assert limiter.allow("a", now=1.0)  # refills at 1 token/second


def test_redaction():
    text = "patient_id=12345 ssn 123-45-6789 card 4111 1111 1111 1111 mail a@b.com"
    out = redact_text(text)
    for secret in ("12345", "123-45-6789", "4111", "a@b.com"):
        assert secret not in out
    assert redact_obj({"patient_id": "x", "nested": [{"api_key": "y"}], "ok": 1}) == {
        "patient_id": "[REDACTED]",
        "nested": [{"api_key": "[REDACTED]"}],
        "ok": 1,
    }


# ----------------------------------------------------------------------------- audit chain
def test_audit_chain_detects_tampering(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(5):
        log.record("event", {"i": i, "patient_id": "secret"})
    assert log.verify()
    entries = log.entries()
    assert entries[0].data["patient_id"] == "[REDACTED]"
    assert len((tmp_path / "audit.jsonl").read_text().splitlines()) == 5
    tampered = list(entries)
    tampered[2] = replace(tampered[2], data={"i": 99})
    assert not AuditLog.verify_entries(tampered)
    assert not AuditLog.verify_entries(entries[:2] + entries[3:])  # deletion breaks the chain


# ----------------------------------------------------------------------------- model integrity
def test_manifest_verification(tmp_path):
    artifact = tmp_path / "lstm_model.pt"
    artifact.write_bytes(b"weights")
    assert verify_artifact(artifact) is False  # no manifest, not required
    with pytest.raises(IntegrityError):
        verify_artifact(artifact, required=True)
    write_manifest(tmp_path)
    assert json.loads((tmp_path / "manifest.json").read_text())["files"]["lstm_model.pt"]
    assert verify_artifact(artifact)
    artifact.write_bytes(b"tampered")
    with pytest.raises(IntegrityError, match="checksum mismatch"):
        verify_artifact(artifact)


# ----------------------------------------------------------------------------- action governor
def test_dry_run_is_default_and_simulates(governor):
    verdict = governor.evaluate("scale_up_replicas")
    assert verdict.outcome is Outcome.SIMULATE
    assert governor.audit.verify() and governor.audit.entries()[-1].event == "action.verdict"


def test_unknown_actions_are_denied(governor, monkeypatch):
    monkeypatch.setenv("GOLDEN_AUTONOMY_MODE", "autonomous")
    verdict = governor.evaluate("rm_rf_everything")
    assert verdict.outcome is Outcome.BLOCKED and verdict.reason == "not_allowlisted"


def test_kill_switch_blocks_everything(governor, monkeypatch, tmp_path):
    monkeypatch.setenv("GOLDEN_AUTONOMY_MODE", "autonomous")
    monkeypatch.setenv("GOLDEN_KILL_SWITCH", "true")
    assert governor.evaluate("scale_up_replicas").reason == "kill_switch"
    monkeypatch.setenv("GOLDEN_KILL_SWITCH", "false")
    flag = tmp_path / "STOP"
    monkeypatch.setenv("GOLDEN_KILL_SWITCH_FILE", str(flag))
    assert governor.evaluate("scale_up_replicas").outcome is Outcome.EXECUTE
    flag.touch()
    assert governor.evaluate("scale_up_replicas").reason == "kill_switch"


def test_blast_radius_and_rate_caps(governor, monkeypatch):
    monkeypatch.setenv("GOLDEN_AUTONOMY_MODE", "autonomous")
    assert governor.evaluate("reclaim_idle_gpus", {"targets": list("abcd")}).reason == "blast_radius"
    outcomes = [governor.evaluate("scale_up_replicas").outcome for _ in range(4)]
    assert outcomes[:3] == [Outcome.EXECUTE] * 3
    assert governor.evaluate("scale_up_replicas").reason == "action_rate_cap"
    for action in ["optimize_resources"] * 3 + ["set_gpu_power_cap"] * 3:
        governor.evaluate(action)
    assert governor.evaluate("throttle_api_clients").may_execute  # 10th action: at the cap
    assert governor.evaluate("throttle_api_clients").reason == "global_rate_cap"


def test_rate_cap_window_slides(monkeypatch):
    from golden.security import ActionGovernor

    monkeypatch.setenv("GOLDEN_AUTONOMY_MODE", "autonomous")
    now = [0.0]
    gov = ActionGovernor(audit=AuditLog(), max_actions_per_hour=1, clock=lambda: now[0])
    assert gov.evaluate("scale_up_replicas").may_execute
    assert not gov.evaluate("scale_up_replicas").may_execute
    now[0] = 3601
    assert gov.evaluate("scale_up_replicas").may_execute


def test_approval_tiers(governor, monkeypatch):
    monkeypatch.setenv("GOLDEN_AUTONOMY_MODE", "supervised")
    assert governor.evaluate("scale_up_replicas").outcome is Outcome.EXECUTE  # low risk
    high = governor.evaluate("restart_service")
    assert high.outcome is Outcome.PENDING_APPROVAL
    monkeypatch.setenv("GOLDEN_AUTONOMY_MODE", "autonomous")
    assert governor.evaluate("restart_service").outcome is Outcome.EXECUTE
    critical = governor.evaluate("vm_cutover")
    assert critical.outcome is Outcome.PENDING_APPROVAL  # critical always needs a human

    with pytest.raises(PermissionError):
        governor.approve(critical.request_id, "system")
    approved = governor.approve(critical.request_id, "jane.doe")
    assert approved.outcome is Outcome.EXECUTE and approved.reason == "approved_by:jane.doe"
    with pytest.raises(KeyError):
        governor.approve(critical.request_id, "jane.doe")  # one-shot
    governor.reject(high.request_id, "jane.doe")
    assert governor.pending() == []
    assert governor.audit.verify()


def test_invalid_autonomy_mode_fails_safe(governor, monkeypatch):
    monkeypatch.setenv("GOLDEN_AUTONOMY_MODE", "yolo")
    assert governor.evaluate("scale_up_replicas").outcome is Outcome.SIMULATE
