from __future__ import annotations
import time
import logging
from pathlib import Path
import yaml

# Import Enterprise Agents
from .agents.observer_agent import ObserverAgent
from .agents.analyzer_agent import AnalyzerAgent
from .agents.planner_agent import PlannerAgent
from .agents.executor_agent import ExecutorAgent

# Configure Global Logging
# This ensures logs from all agents appear with timestamps and severity levels
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("Orchestrator")

CONFIG_PATH = Path(__file__).parent / 'agent_config.yaml'

def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.critical(f"Failed to load configuration: {str(e)}")
        return {}

def run_lifecycle():
    """
    Main Orchestration Loop.
    Runs the 'Observe -> Analyze -> Plan -> Execute' cycle continuously.
    """
    logger.info("Starting Express Platform Orchestrator...")
    
    # 1. Load Configuration
    config = load_config()
    if not config:
        return

    agents_cfg = config.get('agents', {})
    
    # 2. Initialize Agents
    try:
        # Pass specific config sections to each agent
        observer = ObserverAgent(agents_cfg.get('observer', {}))
        analyzer = AnalyzerAgent(agents_cfg.get('analyzer', {}))
        planner = PlannerAgent(agents_cfg.get('planner', {}))
        executor = ExecutorAgent(agents_cfg.get('executor', {}))
        
        logger.info("All agents initialized successfully. System is ACTIVE.")
    except Exception as e:
        logger.critical(f"Failed to initialize agents: {str(e)}")
        return

    # 3. Start Continuous Loop
    # Get interval from config, default to 10 seconds if missing
    interval = agents_cfg.get('observer', {}).get('observability', {}).get('collection_interval_seconds', 10)
    
    while True:
        cycle_id = int(time.time())
        logger.info(f"--- Starting Cycle {cycle_id} ---")
        
        try:
            # Step 1: Observe (The Eyes) - Collect Telemetry
            metrics = observer.collect_metrics()
            
            # Step 2: Analyze (The Brain) - Detect Risks
            analysis = analyzer.analyze(metrics)
            
            # Step 3: Plan (The Logic) - Create Remediation Strategy
            plan = planner.plan(analysis)
            
            # Step 4: Execute (The Hands) - Apply Fixes
            report = executor.execute(plan)
            
            # Log Cycle Summary
            status = report.get('status', 'unknown')
            logger.info(f"Cycle {cycle_id} completed. Final Status: {status}")

        except KeyboardInterrupt:
            logger.info("Orchestrator stopped by user.")
            break
        except Exception as e:
            logger.error(f"Cycle {cycle_id} failed unexpectedly: {str(e)}")
        
        # Wait for next cycle
        logger.debug(f"Sleeping for {interval} seconds...")
        time.sleep(interval)

if __name__ == '__main__':
    run_lifecycle()
