# lstm

Folder for persisted LSTM checkpoints and metadata.

## Expected Artifacts

- `lstm_model.pt`: Serialized `LSTMSLIPredictor` checkpoint.
- `lstm_metrics.json`: Optional training/evaluation metrics snapshot.

## Convention

Use timestamped names when storing multiple runs, for example:
`lstm_model_20260331T153000Z.pt`.
