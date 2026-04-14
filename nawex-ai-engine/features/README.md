# features

Feature assembly and validation for reliability forecasting pipelines.

## Contents

- `feature_store.py`: Required-column validation and canonical feature builders.

## Canonical Feature Set

- `latency_ms`
- `error_rate_percent`
- `cpu_usage_percent`
- `latency_x_error`
- `cpu_pressure`
- `latency_delta`
- `error_delta`

## Example

```python
from features.feature_store import build_reliability_feature_frame, canonical_feature_columns

frame = build_reliability_feature_frame(df)
X = frame[canonical_feature_columns()]
```
