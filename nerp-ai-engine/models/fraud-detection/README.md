# fraud-detection

Folder for fraud-specific model artifacts and threshold configs.

## Expected Artifacts

- `fraud_detector.pkl`: Model trained on transaction behavior features.
- `fraud_thresholds.yaml`: Environment-specific operating thresholds.

## Operational Guidance

Store thresholds separately from model binaries to tune sensitivity per
environment without retraining.
