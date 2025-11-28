from __future__ import annotations
import torch
import torch.nn as nn
import logging
import os
from typing import List, Optional, Dict

# Configure logger
logger = logging.getLogger(__name__)

class Chomp1d(nn.Module):
    """
    Removes the padding added by the convolution to ensure causality.
    """
    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, :-self.chomp_size].contiguous()

class TemporalBlock(nn.Module):
    """
    Standard TCN Residual Block with Dilated Convolutions.
    """
    def __init__(self, n_inputs, n_outputs, kernel_size, stride, dilation, padding, dropout=0.2):
        super().__init__()
        
        # First dilated convolution
        self.conv1 = nn.Conv1d(n_inputs, n_outputs, kernel_size,
                               stride=stride, padding=padding, dilation=dilation)
        self.chomp1 = Chomp1d(padding)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)

        # Second dilated convolution
        self.conv2 = nn.Conv1d(n_outputs, n_outputs, kernel_size,
                               stride=stride, padding=padding, dilation=dilation)
        self.chomp2 = Chomp1d(padding)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)

        # Sequence of operations
        self.net = nn.Sequential(self.conv1, self.chomp1, self.relu1, self.dropout1,
                                 self.conv2, self.chomp2, self.relu2, self.dropout2)
        
        # Downsample for residual connection if channels mismatch
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        self.relu = nn.ReLU()
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out + res)

class TCNSLIPredictor(nn.Module):
    """
    TCN-based Service Level Indicator (SLI) Predictor.
    Uses dilated convolutions to capture long-range dependencies in telemetry data.
    """
    def __init__(self, input_size: int, num_channels: List[int], kernel_size: int = 2, dropout: float = 0.2):
        super().__init__()
        self.input_size = input_size
        self.num_channels = num_channels
        self.kernel_size = kernel_size
        self.dropout = dropout

        layers = []
        num_levels = len(num_channels)
        
        # Build the TCN stack
        for i in range(num_levels):
            dilation_size = 2 ** i
            in_channels = input_size if i == 0 else num_channels[i-1]
            out_channels = num_channels[i]
            
            layers.append(TemporalBlock(
                in_channels, out_channels, kernel_size, stride=1, dilation=dilation_size,
                padding=(kernel_size-1) * dilation_size, dropout=dropout
            ))

        self.network = nn.Sequential(*layers)
        
        # Regression head (Forecasting a single risk score)
        self.fc = nn.Linear(num_channels[-1], 1)
        
        logger.info(f"TCNSLIPredictor initialized. Channels: {num_channels}, Kernel: {kernel_size}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        Input: (Batch, Seq_Len, Channels) -> Adjusted to (Batch, Channels, Seq_Len) for Conv1d
        """
        # Transpose for Conv1d: (B, L, C) -> (B, C, L)
        x = x.transpose(1, 2)
        
        out = self.network(x)
        
        # Take the last time step
        out = out[:, :, -1]
        return self.fc(out).squeeze(-1)

    def predict_risk(self, sequence: List[float]) -> float:
        """
        Inference helper. Handles tensor shaping for the AnalyzerAgent.
        """
        self.eval()
        try:
            with torch.no_grad():
                # Reshape: (Batch=1, Seq_Len=N, Input=1)
                tensor_in = torch.tensor(sequence, dtype=torch.float32).view(1, -1, self.input_size)
                
                prediction = self.forward(tensor_in)
                risk_score = prediction.item()
                
                logger.debug(f"TCN Prediction: Input Len {len(sequence)} -> Risk Score {risk_score:.4f}")
                return risk_score

        except Exception as e:
            logger.error(f"TCN Inference failed: {str(e)}")
            return 0.0

    @classmethod
    def load(cls, path: str, input_size: int = 1) -> Optional[TCNSLIPredictor]:
        """
        Safe loader that handles config reconstruction from checkpoint.
        """
        if not os.path.exists(path):
            logger.warning(f"TCN Checkpoint not found at {path}")
            return None
        
        try:
            checkpoint = torch.load(path, map_location='cpu')
            
            # Extract config to rebuild model architecture
            num_channels = checkpoint.get('num_channels', [25, 25])
            kernel_size = checkpoint.get('kernel_size', 2)
            dropout = checkpoint.get('dropout', 0.2)
            
            model = cls(input_size, num_channels, kernel_size, dropout)
            model.load_state_dict(checkpoint['state_dict'])
            
            model.eval()
            logger.info(f"TCN Model loaded from {path}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load TCN model: {str(e)}")
            return None

    def save(self, path: str):
        """
        Saves model weights and architecture config.
        """
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            checkpoint = {
                'state_dict': self.state_dict(),
                'num_channels': self.num_channels,
                'kernel_size': self.kernel_size,
                'dropout': self.dropout
            }
            torch.save(checkpoint, path)
            logger.info(f"TCN Model saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save TCN model: {str(e)}")
