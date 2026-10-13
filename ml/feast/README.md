# Feast repository — fintech account features

The production-shaped equivalent of `src/golden/ai/features/store.py`: the same entity
(`account` / `account_id`), the same feature view (`account_txn_features`: `txn_count_1h`,
`amount_sum_24h`, `distinct_countries_24h`, TTL 1 h) and the same feature logic (the parquet is written
by `golden.ai.features.store.compute_account_features`), defined with Feast so the offline store,
online store and registry can be swapped for BigQuery/Snowflake + Redis/DynamoDB without changing
feature definitions.

Feast is **not** a platform dependency: nothing under `src/` or `tests/` imports this directory, and
it sits outside the `ruff`/`mypy` scopes (`src`, `tests`, package `golden`).

| File | Purpose |
|---|---|
| `feature_store.yaml` | Project config: local provider, file offline store, SQLite online store |
| `features.py` | `Entity`, `FileSource`, `FeatureView`, `FeatureService` |
| `export_data.py` | Writes `data/account_txn_features.parquet` and `data/labels.parquet` |

## Run it

```bash
python -m venv .venv-feast && . .venv-feast/bin/activate
pip install 'feast>=0.40' pyarrow -e .            # run from the repo root; platform package for export_data.py
cd ml/feast
python export_data.py --transactions 5000
feast apply                                        # register entity / view / service
feast materialize-incremental "$(date -u +%Y-%m-%dT%H:%M:%S)"   # offline -> online (SQLite)
```

Point-in-time correct training set (same semantics as `FeatureStore.get_historical_features`):

```python
import pandas as pd
from feast import FeatureStore

store = FeatureStore(repo_path=".")
labels = pd.read_parquet("data/labels.parquet")  # account_id, event_timestamp, is_fraud
training = store.get_historical_features(
    entity_df=labels, features=store.get_feature_service("fraud_model_v1")
).to_df()
```

Online lookup at serving time:

```python
store.get_online_features(
    features=["account_txn_features:txn_count_1h", "account_txn_features:amount_sum_24h"],
    entity_rows=[{"account_id": "ACC-591912"}],
).to_dict()
```

`data/` is generated; do not commit it.
