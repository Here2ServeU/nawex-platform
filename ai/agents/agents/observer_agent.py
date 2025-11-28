from __future__ import annotations
from typing import Dict, Any
import logging
import random
import time
from datetime import datetime

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
        self.source = self.config.get('observability', {}).get('source', 'simulated')
        logger.info(f"ObserverAgent initialized. Source: {self.source}")

    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collects current system metrics.
        Returns a structured dictionary with timestamps and values.
        """
        logger.info("Collecting system telemetry...")
        
        try:
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
