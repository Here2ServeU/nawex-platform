from __future__ import annotations
from typing import Dict,Any
from ...remediation.remediation_engine import load_rules

class PlannerAgent:
    def __init__(self, config:Dict[str,Any]):
        self.config=config
        self.rules = load_rules().get('rules',[])
    def plan(self, analysis:Dict[str,Any])->Dict[str,Any]:
        return {'planned_actions': []}
