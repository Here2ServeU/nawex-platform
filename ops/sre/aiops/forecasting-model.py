# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
from ai.models.tcn_model import TCNModel
import torch

model = TCNModel()
model.load_state_dict(torch.load("models/tcn_latency.pt"))
model.eval()

x = torch.randn(1, 100)
y = model(x).item()
print("Predicted latency:", y)
