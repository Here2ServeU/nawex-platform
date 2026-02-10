from __future__ import annotations
from typing import Dict, Any
import logging
import random
import time
from datetime import datetime
import requests

# Configure logger for observability
logger = logging.getLogger(__name__)

class ObserverAgent:
    """
    Observer Agent.
    Responsible for collecting real-time system telemetry.
    Currently simulates metrics, but designed to integrate with Prometheus/CloudWatch.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        observability_cfg = self.config.get('observability', {})
        self.source = observability_cfg.get('source', 'simulated')
        self.http_endpoint = observability_cfg.get('http_endpoint', 'http://localhost:8080/metrics')
        self.http_timeout_seconds = observability_cfg.get('http_timeout_seconds', 3)
        logger.info(f"ObserverAgent initialized. Source: {self.source}")

    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collects current system metrics.
        Returns a structured dictionary with timestamps and values.
        """
        logger.info("Collecting system telemetry...")
        
        try:
            # HTTP Metrics Source (real app telemetry)
            if self.source == 'http':
                response = requests.get(self.http_endpoint, timeout=self.http_timeout_seconds)
                response.raise_for_status()
                payload = response.json()
                metrics_payload = payload.get('metrics', payload)

                return {
                    'timestamp': payload.get('timestamp', datetime.utcnow().isoformat()),
                    'source': self.source,
                    'latency_ms': metrics_payload.get('latency_ms', 0),
                    'error_rate': metrics_payload.get('error_rate', 0),
                    'cpu_usage_percent': metrics_payload.get('cpu_usage_percent', 0),
                    'memory_usage_percent': metrics_payload.get('memory_usage_percent', metrics_payload.get('memory_usage_mb'))
                }

            # Simulation Logic (Replace with real API calls like boto3 or prometheus_client)
            # Example: latency = cloudwatch.get_metric_statistics(...)
            
            # Simulating realistic variance to test Analyzer triggers
            # Base latency 190ms +/- 30ms noise
            current_latency = round(190 + random.uniform(-20, 40), 2)
            
            metrics = {
                'timestamp': datetime.utcnow().isoformat(),
                'source': self.source,
                'latency_ms': current_latency,
                'error_rate': round(random.uniform(0, 0.5), 2), # 0.0% to 0.5%
                'cpu_usage_percent': round(random.uniform(40, 75), 1),
                'memory_usage_percent': round(random.uniform(30, 60), 1)
            }
            
            logger.debug(f"Metrics collected: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Failed to collect metrics: {str(e)}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'status': 'collection_failed'
            }
