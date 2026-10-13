"""Decision engine: classify signals, rate risk/severity and route to governed actions."""

from golden.decision.engine import ROUTES, Decision, DecisionEngine
from golden.decision.rules import evaluate_risk, evaluate_severity

__all__ = ["ROUTES", "Decision", "DecisionEngine", "evaluate_risk", "evaluate_severity"]
