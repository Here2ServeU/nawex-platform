"""ML lifecycle: experiment tracking, model registry, trained fraud model, drift-triggered retraining,
progressive delivery (flag / shadow / canary / blue-green)."""

from golden.ai.lifecycle.fraud_model import FraudModel, featurize, train
from golden.ai.lifecycle.registry import ModelRegistry, ModelVersion, PromotionRejected
from golden.ai.lifecycle.retrain import DEFAULT_GATES, MODEL_NAME, check_drift, retrain_if_drifted
from golden.ai.lifecycle.rollout import ModelRouter
from golden.ai.lifecycle.tracking import ExperimentTracker

__all__ = [
    "DEFAULT_GATES",
    "MODEL_NAME",
    "ExperimentTracker",
    "FraudModel",
    "ModelRegistry",
    "ModelRouter",
    "ModelVersion",
    "PromotionRejected",
    "check_drift",
    "featurize",
    "retrain_if_drifted",
    "train",
]
