# features

Feature assembly and validation for reliability forecasting pipelines.

## Contents

- `feature_store.py`: Required-column validation and canonical feature builders.
- `store.py`: Feature store — `Entity` / `FeatureView` (TTL, source), offline store with
  point-in-time correct (as-of) joins, materialization to an online store, `get_online_features`
  with freshness status, training–serving skew checks, and the fintech account features
  (`txn_count_1h`, `amount_sum_24h`, `distinct_countries_24h`). Feast equivalent: `ml/feast/`.
  Guide: `docs/ai-engine/ml-platform.md`.

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

### Feature store

```python
from golden.ai.features.store import ACCOUNT_TXN_VIEW, fintech_feature_store

store = fintech_feature_store()  # simulator history ingested offline
train = store.get_historical_features(labels_df, [ACCOUNT_TXN_VIEW.name])  # no leakage
store.materialize_incremental(ACCOUNT_TXN_VIEW.name, end=now)
store.get_online_features(ACCOUNT_TXN_VIEW.name, ["ACC-123456"], now=now)
store.check_skew(ACCOUNT_TXN_VIEW.name, as_of=now).ok
```
