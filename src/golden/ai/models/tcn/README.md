# tcn

Folder for persisted TCN checkpoints and metadata.

## Expected Artifacts

- `tcn_model.pt`: Serialized `TCNSLIPredictor` checkpoint.
- `tcn_metrics.json`: Optional training/evaluation metrics snapshot.

## Convention

Use timestamped names when storing multiple runs, for example:
`tcn_model_20260331T153000Z.pt`.
