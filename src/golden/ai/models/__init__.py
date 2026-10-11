"""Deep-learning SLI forecasters. Requires the ``[ml]`` extra (torch)."""

from golden.ai.models.lstm_model import LSTMSLIPredictor
from golden.ai.models.tcn_model import TCNSLIPredictor

__all__ = ["LSTMSLIPredictor", "TCNSLIPredictor"]
