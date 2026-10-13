"""Analyzer agent — deterministic thresholds plus optional LSTM/TCN forecast risk."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

import numpy as np

from golden.ai.prediction import predict_lstm, predict_tcn
from golden.security.guardrails import GuardrailViolation

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    def __init__(self, config: dict[str, Any]) -> None:
        thresholds = config.get("thresholds", {})
        features = config.get("features", {})
        self.latency_threshold = float(thresholds.get("latency_ms", 200))
        self.error_rate_threshold = float(thresholds.get("error_rate_percent", 1.0))
        self.cpu_threshold = float(thresholds.get("cpu_usage_percent", 80.0))
        self.memory_threshold = float(thresholds.get("memory_usage_percent", 85.0))
        self.enable_ml = bool(features.get("enable_ml_analysis", False))
        self.window = int(features.get("ml_sequence_window", 24))
        self.history: deque[float] = deque(maxlen=self.window)
        # Trend + spike detection on saturation metrics: catches a slow climb before it crosses a threshold.
        self.trend_slope = float(thresholds.get("trend_slope_per_reading", 1.5))
        self.trend_min_points = int(features.get("trend_min_points", 6))
        self.spike_z = float(thresholds.get("spike_zscore", 2.0))
        self.saturation: dict[str, deque[float]] = {
            m: deque(maxlen=self.window) for m in ("cpu_usage_percent", "memory_usage_percent")
        }

    def analyze(self, metrics: dict[str, Any]) -> dict[str, Any]:
        if metrics.get("status") == "collection_failed":
            return {
                "timestamp": metrics.get("timestamp"),
                "metrics": metrics,
                "risk_flags": {"telemetry_risk": "high"},
                "status": "risk_detected",
            }

        flags: dict[str, Any] = {}
        latency = float(metrics.get("latency_ms", 0) or 0)
        error_rate = float(metrics.get("error_rate_percent", 0) or 0)
        self.history.append(latency)

        if latency > self.latency_threshold:
            flags["latency_risk"] = "critical" if latency > 2 * self.latency_threshold else "high"
        if error_rate > self.error_rate_threshold:
            flags["error_risk"] = "critical" if error_rate > 5 * self.error_rate_threshold else "high"
        if float(metrics.get("cpu_usage_percent", 0) or 0) > self.cpu_threshold:
            flags["cpu_risk"] = "high"
        if float(metrics.get("memory_usage_percent", 0) or 0) > self.memory_threshold:
            flags["memory_risk"] = "critical"

        trend = self._trend(metrics)
        if trend:
            flags["capacity_trend_risk"] = "high"
            flags["trend"] = trend

        if self.enable_ml and len(self.history) >= 4:
            try:
                series = list(self.history)
                lstm, tcn = predict_lstm(series), predict_tcn(series)
                ensemble = (lstm + tcn) / 2
                if ensemble > 0.85:
                    flags["forecast_risk"] = "critical"
                elif ensemble > 0.70:
                    flags["forecast_risk"] = "high"
                flags["ml_scores"] = {
                    "lstm": round(lstm, 4),
                    "tcn": round(tcn, 4),
                    "ensemble": round(ensemble, 4),
                }
            except GuardrailViolation as exc:
                flags["input_rejected"] = exc.reason

        risky = {k for k in flags if k.endswith("_risk")}
        return {
            "timestamp": metrics.get("timestamp"),
            "metrics": metrics,
            "risk_flags": flags,
            "status": "risk_detected" if risky else "healthy",
        }

    def _trend(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Linear-regression slope (units per reading) and z-score spike per saturation metric."""
        out: dict[str, Any] = {}
        for name, series in self.saturation.items():
            value = metrics.get(name)
            if value is None:
                continue
            series.append(float(value))
            if len(series) < self.trend_min_points:
                continue
            values = np.asarray(series)
            slope = float(np.polyfit(np.arange(values.size), values, 1)[0])
            prior = values[:-1]
            z = float((values[-1] - prior.mean()) / prior.std()) if prior.std() > 0 else 0.0
            if slope > self.trend_slope or z > self.spike_z:
                out[name] = {"slope_per_reading": round(slope, 3), "zscore": round(z, 2)}
        return out
