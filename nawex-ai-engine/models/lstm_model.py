# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
from __future__ import annotations
import torch
import torch.nn as nn
import logging
import os
from typing import Optional, List, Dict

# Configure logger for AI observability
logger = logging.getLogger(__name__)

class LSTMSLIPredictor(nn.Module):
    """
    LSTM-based Service Level Indicator (SLI) Predictor.
    Forecasts critical metric values (latency, error rate) based on historical time-series data.
    """
    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # Define LSTM Architecture
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        
        # Regression Head
        self.fc = nn.Linear(hidden_size, 1)
        
        logger.info(f"LSTMSLIPredictor initialized. Input: {input_size}, Hidden: {hidden_size}, Layers: {num_layers}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass. 
        Shape: (batch, seq_len, input_size) -> (batch)
        """
        out, _ = self.lstm(x)
        # Take the last time step's output for forecasting
        last_time_step = out[:, -1, :]
        return self.fc(last_time_step).squeeze(-1)

    def predict_risk(self, sequence: List[float]) -> float:
        """
        Inference helper for the AnalyzerAgent.
        Takes a raw list of floats (history), handles tensor conversion, and returns a risk score.
        """
        self.eval() # Ensure evaluation mode
        try:
            with torch.no_grad():
                # Reshape: (Batch=1, Seq_Len=N, Input=1)
                # Note: Assuming univariate for simplicity (latency only). 
                # For multivariate, the input list would be a list of lists.
                tensor_in = torch.tensor(sequence, dtype=torch.float32).view(1, -1, self.input_size)
                
                prediction = self.forward(tensor_in)
                risk_score = prediction.item()
                
                logger.debug(f"AI Prediction: Input Len {len(sequence)} -> Risk Score {risk_score:.4f}")
                return risk_score

        except Exception as e:
            logger.error(f"Inference failed: {str(e)}")
            # Fail safe: Return 0 risk on model failure so we don't trigger false positives
            return 0.0

    @classmethod
    def load(cls, path: str, input_size: int = 1) -> Optional[LSTMSLIPredictor]:
        """
        Safe loader that handles file existence and device mapping.
        """
        if not os.path.exists(path):
            logger.warning(f"Model checkpoint not found at {path}. AI features will be disabled.")
            return None
        
        try:
            # Load to CPU to ensure compatibility across environments
            checkpoint = torch.load(path, map_location='cpu')
            
            # Extract hyperparameters if available, else default
            hidden_size = checkpoint.get('hidden_size', 64)
            num_layers = checkpoint.get('num_layers', 2)
            
            model = cls(input_size, hidden_size, num_layers)
            
            # Handle both full checkpoint dicts and direct state_dicts
            state_dict = checkpoint.get('state_dict', checkpoint)
            model.load_state_dict(state_dict)
            
            model.eval()
            logger.info(f"Model successfully loaded from {path}")
            return model

        except Exception as e:
            logger.error(f"Failed to load model weights: {str(e)}")
            return None

    def save(self, path: str):
        """
        Saves model weights and config for reproducibility.
        """
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            checkpoint = {
                'state_dict': self.state_dict(),
                'hidden_size': self.hidden_size,
                'num_layers': self.num_layers,
                'input_size': self.input_size
            }
            torch.save(checkpoint, path)
            logger.info(f"Model saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save model: {str(e)}")
