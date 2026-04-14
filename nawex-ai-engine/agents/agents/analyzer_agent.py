# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
from __future__ import annotations
from typing import Dict, Any, Optional
import logging
from ...prediction import predict_lstm, predict_tcn

# Configure logger for observability
logger = logging.getLogger(__name__)

class AnalyzerAgent:
    """
    AI-Driven Analyzer Agent.
    Evaluates system metrics against static thresholds and ML models 
    to detect anomalies and forecast risks.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = self.config.get('thresholds', {})
        self.latency_threshold = self.thresholds.get('latency_ms', 200)
        self.error_rate_threshold = self.thresholds.get('error_rate_percent', 1.0)
        self.enable_ml = self.config.get('features', {}).get('enable_ml_analysis', False)
        self.sequence_window = int(self.config.get('features', {}).get('ml_sequence_window', 12))
        
        # Placeholder: Load your LSTM/TCN models here
        # self.model = load_model(self.config['model_path'])
        logger.info(f"AnalyzerAgent initialized. Latency Threshold: {self.latency_threshold}ms")

    def analyze(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """
        Analyzes real-time metrics for risk.
        Returns a dictionary containing the original metrics and identified risk flags.
        """
        risk_flags = {}
        
        try:
            # 1. Deterministic Rule Check (Fast Fail)
            current_latency = float(metrics.get('latency_ms', 0.0) or 0.0)
            if current_latency > self.latency_threshold:
                risk_flags['latency_risk'] = 'high'
                risk_flags['reason'] = f"Latency {current_latency}ms exceeds threshold {self.latency_threshold}ms"
                logger.warning(f"High Latency Detected: {current_latency}ms")

            current_error_rate = float(metrics.get('error_rate_percent', 0.0) or 0.0)
            if current_error_rate > self.error_rate_threshold:
                risk_flags['error_risk'] = 'high'
                logger.warning(
                    "High Error Rate Detected: %.3f%% > %.3f%%",
                    current_error_rate,
                    self.error_rate_threshold,
                )

            # 2. Predictive AI Analysis (Future Integration)
            if self.enable_ml:
                history = metrics.get('latency_history')
                if not history:
                    # Use synthetic short history from current telemetry when no series is provided.
                    history = [current_latency] * self.sequence_window

                lstm_score = float(predict_lstm(history))
                tcn_score = float(predict_tcn(history))
                ensemble_score = (lstm_score + tcn_score) / 2.0

                if ensemble_score > 0.85:
                    risk_flags['forecast_risk'] = 'critical'
                elif ensemble_score > 0.70:
                    risk_flags['forecast_risk'] = 'high'

                risk_flags['ml_scores'] = {
                    'lstm': round(lstm_score, 4),
                    'tcn': round(tcn_score, 4),
                    'ensemble': round(ensemble_score, 4),
                }

        except Exception as e:
            logger.error(f"Error during analysis: {str(e)}")
            risk_flags['analyzer_error'] = str(e)

        return {
            'timestamp': metrics.get('timestamp'),
            'metrics': metrics,
            'risk_flags': risk_flags,
            'status': 'risk_detected' if risk_flags else 'healthy'
        }
