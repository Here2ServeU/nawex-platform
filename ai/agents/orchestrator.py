from __future__ import annotations
from pathlib import Path
import yaml
from .agents.observer_agent import ObserverAgent
from .agents.analyzer_agent import AnalyzerAgent
from .agents.planner_agent import PlannerAgent
from .agents.executor_agent import ExecutorAgent

CONFIG_PATH = Path(__file__).parent/'agent_config.yaml'


def load_config():
    with open(CONFIG_PATH,'r') as f:
        return yaml.safe_load(f)


def run_cycle()->None:
    cfg = load_config().get('agents',{})
    obs=ObserverAgent(cfg.get('observer',{}))
    ana=AnalyzerAgent(cfg.get('analyzer',{}))
    pla=PlannerAgent(cfg.get('planner',{}))
    exe=ExecutorAgent(cfg.get('executor',{}))
    metrics = obs.run_once(); analysis = ana.analyze(metrics); plan = pla.plan(analysis); exe.execute(plan)

if __name__=='__main__':
    run_cycle()
