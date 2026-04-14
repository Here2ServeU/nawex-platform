# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
from ai.models.lstm_model import LSTMSLIPredictor
import torch

model = LSTMSLIPredictor()
model.load_state_dict(torch.load("models/lstm_latency.pt"))
model.eval()

# Hypothetical inference call
x = torch.randn(1, 30, 1)
y = model(x).item()
print("Recommended autoscale target:", max(1, round(y / 40)))
