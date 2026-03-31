# anomaly-detection

Folder for unsupervised anomaly detector artifacts.

## Expected Artifacts

- `isolation_forest.pkl`: IsolationForest model dump.
- `autoencoder_centroid.json` or `autoencoder.pkl`: Reconstruction model metadata.

## Notes

Persisting these artifacts lets the analyzer run consistent inference between
training and production-like demo sessions.
