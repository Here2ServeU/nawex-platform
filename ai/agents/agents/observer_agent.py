from __future__ import annotations
from typing import Dict,Any

class ObserverAgent:
    def __init__(self, config:Dict[str,Any]):
        self.config = config
    def run_once(self)->Dict[str,float]:
        return {'latency_ms':210.0,'error_rate':0.8}
