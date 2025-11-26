from __future__ import annotations
from typing import Dict,Any

class AnalyzerAgent:
    def __init__(self, config:Dict[str,Any]):
        self.config=config
    def analyze(self, metrics:Dict[str,float])->Dict[str,Any]:
        risk={}
        if metrics.get('latency_ms',0)>200:
            risk['latency_risk']='high'
        return {'metrics':metrics,'risk_flags':risk}
