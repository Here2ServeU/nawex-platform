"""Feast definitions for the account features (mirror of golden.ai.features.store.ACCOUNT_TXN_VIEW).

Not imported by the platform or its tests (Feast is not a platform dependency). Use from this
directory with ``pip install 'feast>=0.40' pyarrow`` — see README.md.

    golden FeatureStore concept          Feast object
    ---------------------------          ------------
    Entity("account", "account_id")      Entity(name="account", join_keys=["account_id"])
    FeatureView(ttl, features, source)   FeatureView(ttl, schema=[Field...], source=FileSource)
    get_historical_features              FeatureStore.get_historical_features (point-in-time join)
    materialize / get_online_features    feast materialize-incremental / get_online_features
"""

from datetime import timedelta

from feast import Entity, FeatureService, FeatureView, Field, FileSource, ValueType
from feast.types import Float64, Int64

account = Entity(
    name="account",
    join_keys=["account_id"],
    value_type=ValueType.STRING,
    description="A customer account in the fintech simulator.",
)

# Written by export_data.py from golden.ai.features.store.compute_account_features.
account_txn_source = FileSource(
    name="account_txn_features_source",
    path="data/account_txn_features.parquet",
    timestamp_field="event_timestamp",
)

account_txn_features = FeatureView(
    name="account_txn_features",
    entities=[account],
    # Same TTL as the golden view: a txn_count_1h value older than one hour is no longer true.
    ttl=timedelta(hours=1),
    schema=[
        Field(name="txn_count_1h", dtype=Int64),
        Field(name="amount_sum_24h", dtype=Float64),
        Field(name="distinct_countries_24h", dtype=Int64),
    ],
    online=True,
    source=account_txn_source,
    tags={"team": "fraud", "owner": "ml-platform"},
)

fraud_model_v1 = FeatureService(
    name="fraud_model_v1",
    features=[account_txn_features],
    description="Features the fraud model reads at training and serving time.",
)
