"""A small, correct feature store: feature views, point-in-time joins, online serving, skew checks.

This module teaches the concepts a production feature store (Feast, Tecton, SageMaker/Vertex Feature
Store) implements, with the same vocabulary — see ``ml/feast/`` for the equivalent Feast definitions.

* **Entity**       — the thing features describe, identified by a join key (``account_id``).
* **FeatureView**  — a named group of features for one entity, with a ``ttl`` and a ``source``.
  Every feature row carries the timestamp at which its values became true (``event_timestamp``).
* **Offline store** — the full history of feature rows (here: pandas frames). Training sets are built
  with a **point-in-time correct join**: for each (entity, event timestamp) in the label frame, take the
  latest feature row with ``feature_ts <= event_ts`` and ``event_ts - feature_ts <= ttl``. A row from
  the future is never used (no label leakage), and a row older than the TTL yields nulls rather than a
  silently stale value.
* **Materialization** — copies the latest row per entity in a time window from the offline store into
  the **online store** (here: an in-memory dict; Redis/DynamoDB in production). Incremental: a newer
  row never gets overwritten by an older one.
* **Online serving** — ``get_online_features`` returns the latest values per entity with a freshness
  status: ``PRESENT``, ``EXPIRED`` (older than the TTL at request time) or ``NOT_FOUND``.
* **Training-serving skew** — :meth:`FeatureStore.check_skew` samples entity keys and compares what
  the online store serves with what the offline point-in-time join returns for the same instant. Any
  difference means the two paths compute or deliver features differently.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

TIMESTAMP_COL = "event_timestamp"

PRESENT = "PRESENT"
EXPIRED = "EXPIRED"
NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class Entity:
    name: str
    join_key: str
    description: str = ""


@dataclass(frozen=True)
class FeatureView:
    """A group of features for one entity, valid for ``ttl`` after their timestamp."""

    name: str
    entity: Entity
    features: tuple[str, ...]
    ttl: timedelta
    source: str = ""
    timestamp_field: str = TIMESTAMP_COL
    description: str = ""

    def __post_init__(self) -> None:
        if not self.features:
            raise ValueError(f"feature view {self.name!r} defines no features")
        if self.ttl <= timedelta(0):
            raise ValueError(f"feature view {self.name!r} needs a positive ttl")
        if len(set(self.features)) != len(self.features):
            raise ValueError(f"feature view {self.name!r} has duplicate feature names")

    @property
    def join_key(self) -> str:
        return self.entity.join_key

    @property
    def columns(self) -> list[str]:
        return [self.join_key, self.timestamp_field, *self.features]


# --------------------------------------------------------------------------------------- offline
class OfflineStore:
    """Historical feature rows per view (append-only pandas frames)."""

    def __init__(self) -> None:
        self._frames: dict[str, pd.DataFrame] = {}

    def write(self, view: FeatureView, rows: pd.DataFrame) -> None:
        missing = [c for c in view.columns if c not in rows.columns]
        if missing:
            raise ValueError(f"{view.name}: rows are missing columns {missing}")
        frame = rows[view.columns].copy()
        frame[view.timestamp_field] = pd.to_datetime(frame[view.timestamp_field])
        if frame[view.timestamp_field].isna().any():
            raise ValueError(f"{view.name}: feature rows need a timestamp")
        existing = self._frames.get(view.name)
        if existing is not None:
            frame = pd.concat([existing, frame], ignore_index=True)
        self._frames[view.name] = frame.sort_values(view.timestamp_field, kind="stable").reset_index(
            drop=True
        )

    def read(self, view: FeatureView) -> pd.DataFrame:
        if view.name not in self._frames:
            return pd.DataFrame(columns=view.columns)
        return self._frames[view.name].copy()

    def point_in_time_join(self, entity_df: pd.DataFrame, view: FeatureView) -> pd.DataFrame:
        """As-of join ``entity_df`` (join key + event timestamp) to ``view``; preserves row order.

        ``merge_asof(direction="backward")`` picks, per key, the latest feature row whose timestamp is
        <= the event timestamp; ``tolerance=ttl`` turns rows older than the TTL into nulls.
        """
        key, ts = view.join_key, view.timestamp_field
        for col in (key, ts):
            if col not in entity_df.columns:
                raise ValueError(f"entity_df needs column {col!r}")
        clash = [f for f in view.features if f in entity_df.columns]
        if clash:
            raise ValueError(f"entity_df already has columns {clash}")
        left = entity_df.copy()
        left[ts] = pd.to_datetime(left[ts])
        left["__row"] = np.arange(len(left))
        feats = self.read(view)
        feats = feats.rename(columns={ts: "__feature_ts"})
        if feats.empty:
            out = left.copy()
            for f in view.features:
                out[f] = np.nan
            return out.drop(columns="__row").reset_index(drop=True)
        # Ties on the same timestamp: keep the last-written row, so a correction supersedes.
        feats = feats.drop_duplicates([key, "__feature_ts"], keep="last")
        feats[key] = feats[key].astype(left[key].dtype)
        joined = pd.merge_asof(
            left.sort_values(ts, kind="stable"),
            feats.sort_values("__feature_ts", kind="stable"),
            left_on=ts,
            right_on="__feature_ts",
            by=key,
            direction="backward",
            allow_exact_matches=True,
            tolerance=pd.Timedelta(view.ttl),
        )
        joined = joined.sort_values("__row").drop(columns=["__row", "__feature_ts"])
        return joined.reset_index(drop=True)


# ---------------------------------------------------------------------------------------- online
@dataclass
class OnlineRecord:
    feature_ts: pd.Timestamp
    values: dict[str, Any]


class OnlineStore:
    """Latest feature values per (view, entity key) — the low-latency serving copy."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, Any], OnlineRecord] = {}

    def write(self, view: FeatureView, key: Any, feature_ts: pd.Timestamp, values: dict[str, Any]) -> bool:
        """Upsert unless the stored row is newer; returns whether the write applied."""
        current = self._data.get((view.name, key))
        if current is not None and current.feature_ts > feature_ts:
            return False
        self._data[(view.name, key)] = OnlineRecord(pd.Timestamp(feature_ts), dict(values))
        return True

    def read(self, view: FeatureView, key: Any) -> OnlineRecord | None:
        return self._data.get((view.name, key))

    def __len__(self) -> int:
        return len(self._data)


@dataclass
class OnlineFeatures:
    """Online lookup result: one entry per requested entity key."""

    values: dict[Any, dict[str, Any]]
    status: dict[Any, str]
    feature_ts: dict[Any, pd.Timestamp | None]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame.from_dict(self.values, orient="index")


@dataclass
class SkewReport:
    view: str
    as_of: pd.Timestamp
    keys_checked: int
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    per_feature: dict[str, int] = field(default_factory=dict)

    @property
    def mismatch_rate(self) -> float:
        cells = self.keys_checked * max(1, len(self.per_feature))
        return len(self.mismatches) / cells if cells else 0.0

    @property
    def ok(self) -> bool:
        return not self.mismatches


def _same(a: Any, b: Any, tol: float) -> bool:
    a_missing = a is None or (isinstance(a, float) and math.isnan(a))
    b_missing = b is None or (isinstance(b, float) and math.isnan(b))
    if a_missing or b_missing:
        return a_missing and b_missing
    if isinstance(a, int | float | np.number) and isinstance(b, int | float | np.number):
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))
    return bool(a == b)


def _py(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    return value


# ------------------------------------------------------------------------------------ the store
class FeatureStore:
    def __init__(self) -> None:
        self.offline = OfflineStore()
        self.online = OnlineStore()
        self._views: dict[str, FeatureView] = {}
        self._materialized_to: dict[str, pd.Timestamp] = {}

    # registry ---------------------------------------------------------------------------------
    def apply(self, *views: FeatureView) -> None:
        for v in views:
            self._views[v.name] = v

    def view(self, name: str) -> FeatureView:
        try:
            return self._views[name]
        except KeyError:
            raise KeyError(f"unknown feature view {name!r}") from None

    @property
    def views(self) -> list[FeatureView]:
        return list(self._views.values())

    def ingest(self, view_name: str, rows: pd.DataFrame) -> None:
        self.offline.write(self.view(view_name), rows)

    # offline ----------------------------------------------------------------------------------
    def get_historical_features(self, entity_df: pd.DataFrame, view_names: Sequence[str]) -> pd.DataFrame:
        """Point-in-time correct training frame: ``entity_df`` plus every feature of every view."""
        out = entity_df
        for name in view_names:
            out = self.offline.point_in_time_join(out, self.view(name))
        return out

    # materialization --------------------------------------------------------------------------
    def materialize(
        self, view_name: str, start: datetime | pd.Timestamp, end: datetime | pd.Timestamp
    ) -> int:
        """Load the latest row per entity with ``start <= ts <= end`` into the online store."""
        view = self.view(view_name)
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        if end_ts < start_ts:
            raise ValueError("materialize: end is before start")
        rows = self.offline.read(view)
        ts = view.timestamp_field
        window = rows[(rows[ts] >= start_ts) & (rows[ts] <= end_ts)]
        latest = window.sort_values(ts, kind="stable").groupby(view.join_key, sort=False).tail(1)
        written = 0
        for rec in latest.to_dict("records"):
            values = {f: _py(rec[f]) for f in view.features}
            written += self.online.write(view, rec[view.join_key], pd.Timestamp(rec[ts]), values)
        prev = self._materialized_to.get(view_name)
        self._materialized_to[view_name] = end_ts if prev is None else max(prev, end_ts)
        return written

    def materialize_incremental(self, view_name: str, end: datetime | pd.Timestamp) -> int:
        """Materialize from the last materialized point (or the beginning of history) up to ``end``."""
        view = self.view(view_name)
        start = self._materialized_to.get(view_name)
        if start is None:
            rows = self.offline.read(view)
            if rows.empty:
                return 0
            start = rows[view.timestamp_field].min()
        return self.materialize(view_name, start, end)

    # online -----------------------------------------------------------------------------------
    def get_online_features(
        self, view_name: str, keys: Iterable[Any], *, now: datetime | pd.Timestamp | None = None
    ) -> OnlineFeatures:
        """Latest online values; rows older than the view's TTL at ``now`` come back as ``EXPIRED``
        with null values, so a stale feature is never served as if it were current."""
        view = self.view(view_name)
        now_ts = pd.Timestamp(now) if now is not None else pd.Timestamp.now()
        values: dict[Any, dict[str, Any]] = {}
        status: dict[Any, str] = {}
        feature_ts: dict[Any, pd.Timestamp | None] = {}
        empty = dict.fromkeys(view.features)
        for key in keys:
            rec = self.online.read(view, key)
            if rec is None:
                values[key], status[key], feature_ts[key] = dict(empty), NOT_FOUND, None
            elif now_ts - rec.feature_ts > pd.Timedelta(view.ttl):
                values[key], status[key], feature_ts[key] = dict(empty), EXPIRED, rec.feature_ts
            else:
                values[key], status[key], feature_ts[key] = dict(rec.values), PRESENT, rec.feature_ts
        return OnlineFeatures(values, status, feature_ts)

    # skew -------------------------------------------------------------------------------------
    def check_skew(
        self,
        view_name: str,
        *,
        as_of: datetime | pd.Timestamp,
        keys: Sequence[Any] | None = None,
        sample: int = 100,
        seed: int = 0,
        tolerance: float = 1e-9,
    ) -> SkewReport:
        """Compare online values with the offline point-in-time join at ``as_of`` for sampled keys."""
        view = self.view(view_name)
        as_of_ts = pd.Timestamp(as_of)
        if keys is None:
            all_keys = self.offline.read(view)[view.join_key].unique().tolist()
            rng = np.random.default_rng(seed)
            n = min(sample, len(all_keys))
            keys = [all_keys[i] for i in sorted(rng.choice(len(all_keys), size=n, replace=False))]
        keys = list(keys)
        online = self.get_online_features(view_name, keys, now=as_of_ts)
        entity_df = pd.DataFrame({view.join_key: keys, view.timestamp_field: [as_of_ts] * len(keys)})
        offline = self.offline.point_in_time_join(entity_df, view)
        report = SkewReport(view_name, as_of_ts, len(keys), per_feature=dict.fromkeys(view.features, 0))
        for i, key in enumerate(keys):
            for f in view.features:
                off, on = _py(offline.at[i, f]), online.values[key][f]
                if not _same(off, on, tolerance):
                    report.mismatches.append({"key": key, "feature": f, "offline": off, "online": on})
                    report.per_feature[f] += 1
        return report


# --------------------------------------------------------------- fintech account features
ACCOUNT = Entity("account", "account_id", "A customer account in the fintech simulator.")
ACCOUNT_FEATURES = ("txn_count_1h", "amount_sum_24h", "distinct_countries_24h")
ACCOUNT_TXN_VIEW = FeatureView(
    name="account_txn_features",
    entity=ACCOUNT,
    features=ACCOUNT_FEATURES,
    # The TTL matches the shortest window: a txn_count_1h value older than one hour is no longer true.
    ttl=timedelta(hours=1),
    source="golden.ai.datasets.fintech_simulator.make_fraud_scenario_stream",
    description="Per-account velocity, spend and geography features, updated on every transaction.",
)


def compute_account_features(txns: pd.DataFrame) -> pd.DataFrame:
    """One feature row per transaction: the account's windowed aggregates *as of* that transaction.

    Windows are trailing and right-closed — ``(t - window, t]`` — so the row at ``t`` includes the
    transaction at ``t`` and nothing after it. Columns: ``account_id``, ``event_timestamp`` and
    :data:`ACCOUNT_FEATURES`.
    """
    required = {"account_id", "timestamp", "amount", "country_code"}
    missing = required - set(txns.columns)
    if missing:
        raise ValueError(f"transactions are missing columns {sorted(missing)}")
    df = txns[["account_id", "timestamp", "amount", "country_code"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["account_id", "timestamp"], kind="stable").reset_index(drop=True)
    hour, day = np.timedelta64(1, "h"), np.timedelta64(24, "h")
    counts = np.zeros(len(df), dtype=np.int64)
    sums = np.zeros(len(df), dtype=float)
    distinct = np.zeros(len(df), dtype=np.int64)
    for _, idx in df.groupby("account_id", sort=False).indices.items():
        times = df["timestamp"].to_numpy()[idx]
        amounts = df["amount"].to_numpy(dtype=float)[idx]
        countries = df["country_code"].to_numpy()[idx]
        h_start = d_start = 0
        running_sum = 0.0
        seen: Counter[str] = Counter()
        for j in range(len(idx)):
            t = times[j]
            while times[h_start] <= t - hour:
                h_start += 1
            running_sum += amounts[j]
            seen[countries[j]] += 1
            while times[d_start] <= t - day:
                running_sum -= amounts[d_start]
                seen[countries[d_start]] -= 1
                if seen[countries[d_start]] == 0:
                    del seen[countries[d_start]]
                d_start += 1
            counts[idx[j]] = j - h_start + 1
            sums[idx[j]] = round(running_sum, 2)
            distinct[idx[j]] = len(seen)
    return pd.DataFrame(
        {
            "account_id": df["account_id"].to_numpy(),
            TIMESTAMP_COL: df["timestamp"].to_numpy(),
            "txn_count_1h": counts,
            "amount_sum_24h": sums,
            "distinct_countries_24h": distinct,
        }
    ).sort_values(TIMESTAMP_COL, kind="stable", ignore_index=True)


def fintech_feature_store(txns: pd.DataFrame | None = None, *, seed: int = 42) -> FeatureStore:
    """A store with the account view registered and its offline history ingested from ``txns``
    (default: ``make_fraud_scenario_stream(2000, seed=seed)``)."""
    if txns is None:
        from golden.ai.datasets.fintech_simulator import make_fraud_scenario_stream

        txns = make_fraud_scenario_stream(2000, seed=seed)
    store = FeatureStore()
    store.apply(ACCOUNT_TXN_VIEW)
    store.ingest(ACCOUNT_TXN_VIEW.name, compute_account_features(txns))
    return store
