# evaluation

Evaluation utilities for predictive and anomaly-detection quality.

## Contents

- `metrics.py`: Regression and binary classification metrics without heavy wrappers.

## Example

```python
from evaluation.metrics import regression_metrics, classification_metrics

reg = regression_metrics([100, 110, 120], [102, 108, 123])
clf = classification_metrics([0, 1, 1, 0], [0, 1, 0, 0])
print(reg)
print(clf)
```

## Why This Exists

It gives deterministic, transparent quality checks for demo environments where
you want concise evaluation output without pulling full experiment frameworks.
