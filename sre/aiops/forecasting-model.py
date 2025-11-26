from ai.models.tcn_model import TCNModel
import torch

model = TCNModel()
model.load_state_dict(torch.load("models/tcn_latency.pt"))
model.eval()

x = torch.randn(1, 100)
y = model(x).item()
print("Predicted latency:", y)
