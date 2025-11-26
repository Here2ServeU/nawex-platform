from __future__ import annotations
from typing import Dict,Any
from ...remediation.remediation_engine import execute_action

class ExecutorAgent:
    def __init__(self, config:Dict[str,Any]):
        self.config=config
        self.mode=config.get('mode','dry_run')
    def execute(self, plan:Dict[str,Any])->None:
        for action in plan.get('planned_actions',[]):
            if self.mode=='dry_run':
                print('[Executor] DRY RUN', action)
            else:
                execute_action(action)
