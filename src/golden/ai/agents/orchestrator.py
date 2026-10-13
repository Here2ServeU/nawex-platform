"""Observe → Analyze → Plan → Execute control loop."""

from __future__ import annotations

import logging
import time
from importlib import resources
from typing import Any

import yaml

from golden.ai.agents.analyzer import AnalyzerAgent
from golden.ai.agents.executor import ExecutorAgent
from golden.ai.agents.observer import ObserverAgent
from golden.ai.agents.planner import PlannerAgent

logger = logging.getLogger(__name__)


def load_config() -> dict[str, Any]:
    text = resources.files("golden.ai.agents").joinpath("agent_config.yaml").read_text("utf-8")
    return yaml.safe_load(text) or {}


class Orchestrator:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = (config or load_config()).get("agents", {})
        self.observer = ObserverAgent(cfg.get("observer", {}))
        self.analyzer = AnalyzerAgent(cfg.get("analyzer", {}))
        self.planner = PlannerAgent(cfg.get("planner", {}))
        self.executor = ExecutorAgent(cfg.get("executor", {}))
        self.interval = float(
            cfg.get("observer", {}).get("observability", {}).get("collection_interval_seconds", 10)
        )

    def run_cycle(self) -> dict[str, Any]:
        metrics = self.observer.collect_metrics()
        analysis = self.analyzer.analyze(metrics)
        plan = self.planner.plan(analysis)
        report = self.executor.execute(plan)
        logger.info("cycle complete", extra={"status": analysis["status"], "execution": report["status"]})
        return {"metrics": metrics, "analysis": analysis, "plan": plan, "execution": report}

    def run(self, cycles: int | None = None, interval: float | None = None) -> list[dict[str, Any]]:
        """Run ``cycles`` iterations (forever when ``None``)."""
        results: list[dict[str, Any]] = []
        delay = self.interval if interval is None else interval
        n = 0
        try:
            while cycles is None or n < cycles:
                result = self.run_cycle()
                if cycles is not None:
                    results.append(result)
                n += 1
                if cycles is None or n < cycles:
                    time.sleep(delay)
        except KeyboardInterrupt:
            logger.info("orchestrator stopped by operator")
        return results


def run_lifecycle() -> None:
    Orchestrator().run()


if __name__ == "__main__":
    run_lifecycle()
