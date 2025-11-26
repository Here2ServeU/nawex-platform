from __future__ import annotations
from typing import Dict,Any

def execute_action(action:Dict[str,Any])->None:
    print('[Remediation] would execute', action)

def load_rules()->Dict[str,Any]:
    return {'rules': []}
