# training

Training orchestration for predictive reliability models.

## Contents

- `trainer.py`: Entry point that trains LSTM or TCN and persists checkpoints.

## Example

```python
from training.trainer import train_and_save

lstm_path = train_and_save("lstm", output_dir="models", epochs=5)
tcn_path = train_and_save("tcn", output_dir="models", epochs=5)
print(lstm_path, tcn_path)
```

## Output

- `models/lstm_model.pt`
- `models/tcn_model.pt`

These files are consumed by `prediction/` and `inference/runtime_inference.py`.
