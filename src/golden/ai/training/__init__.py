"""Model training orchestration (requires the ``[ml]`` extra)."""

from golden.ai.training.trainer import TrainResult, make_windows, train_and_save, train_forecaster

__all__ = ["TrainResult", "make_windows", "train_and_save", "train_forecaster"]
