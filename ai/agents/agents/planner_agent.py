# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from ...remediation.remediation_engine import load_rules

# Configure logger for observability
logger = logging.getLogger(__name__)

class PlannerAgent:
    """
    Planner Agent.
    Analyzes risk assessments to generate remediation plans.
    Maps identified risks to specific executable actions based on defined rules or AI logic.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Load remediation rules safely
        try:
            self.rules = load_rules().get('rules', [])
            logger.info(f"PlannerAgent initialized. Loaded {len(self.rules)} remediation rules.")
        except Exception as e:
            logger.error(f"Failed to load remediation rules: {str(e)}")
            self.rules = []

    def plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a remediation plan based on the analysis report.
        Returns a structured plan with actions and reasoning.
        """
        plan_id = datetime.utcnow().strftime('plan-%Y%m%d-%H%M%S')
        logger.info(f"Generating remediation plan {plan_id}...")

        planned_actions = []
        reasoning = []

        try:
            # 1. Validate Input
            if not analysis or analysis.get('status') == 'healthy':
                logger.info("System is healthy. No remediation needed.")
                return {
                    'plan_id': plan_id,
                    'status': 'no_action_needed',
                    'planned_actions': []
                }

            # 2. Analyze Risks & Match Rules
            risks = analysis.get('risk_flags', {})
            for risk_type, risk_level in risks.items():
                logger.info(f"Processing risk: {risk_type} ({risk_level})")
                
                # Logic: Find a matching remediation action
                action = self._match_rule(risk_type, risk_level)
                
                if action:
                    planned_actions.append(action)
                    reasoning.append(f"Selected '{action}' to mitigate '{risk_type}'")
                else:
                    logger.warning(f"No automated rule found for risk: {risk_type}")
                    reasoning.append(f"Manual intervention required for '{risk_type}'")

            # 3. Construct Final Plan
            plan = {
                'plan_id': plan_id,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'actions_planned' if planned_actions else 'manual_review_required',
                'planned_actions': planned_actions,
                'reasoning': reasoning,
                'analysis_reference': analysis.get('timestamp')
            }
            
            logger.info(f"Plan generated with {len(planned_actions)} actions.")
            return plan

        except Exception as e:
            logger.error(f"Planning failed: {str(e)}")
            return {
                'plan_id': plan_id,
                'status': 'planning_failed',
                'error': str(e),
                'planned_actions': []
            }

    def _match_rule(self, risk_type: str, risk_level: str) -> Optional[str]:
        """
        Helper to map risks to actions. 
        """
        # 1. Check loaded rules (dynamic)
        for rule in self.rules:
            if rule.get('trigger') == risk_type and rule.get('level') == risk_level:
                return rule.get('action')

        # 2. Fallback default logic (hardcoded safety net)
        if 'latency' in risk_type and risk_level in ['high', 'critical']:
            return 'scale_up_replicas'
        if 'cpu' in risk_type or 'memory' in risk_type:
            return 'optimize_resources'
        if 'error' in risk_type:
            return 'restart_service'
            
        return None
