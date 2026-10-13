"""ML platform: feature store (point-in-time, TTL, online/offline skew), OIP model serving, GPU partitioning."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from golden.ai.datasets.fintech_simulator import make_fraud_scenario_stream
from golden.ai.features.store import (
    ACCOUNT_FEATURES,
    ACCOUNT_TXN_VIEW,
    EXPIRED,
    NOT_FOUND,
    PRESENT,
    Entity,
    FeatureStore,
    FeatureView,
    compute_account_features,
    fintech_feature_store,
)
from golden.ai.lifecycle.fraud_model import FEATURES, featurize, train
from golden.ai.lifecycle.registry import ModelRegistry
from golden.ai.serving import FraudModelServer, InferenceError, InferRequest, InferTensor
from golden.gpu.partitioning import (
    GPU_MODELS,
    MIG,
    MPS,
    TIME_SLICING,
    TIME_SLICING_REPLICAS,
    WHOLE_GPU,
    Workload,
    gpu_model,
    mig_lower_bound,
    pack_mig,
    plan_partitioning,
    recommend_strategy,
    smallest_profile,
    valid_layout,
)

T0 = pd.Timestamp("2026-01-01 00:00:00")
USER = Entity("user", "user_id")


def _view(ttl_hours: float = 2) -> FeatureView:
    return FeatureView("user_stats", USER, ("score",), ttl=timedelta(hours=ttl_hours), source="test")


def _store(rows: list[tuple[str, int, float]], ttl_hours: float = 2) -> FeatureStore:
    """rows: (user_id, minutes after T0, score)."""
    store = FeatureStore()
    view = _view(ttl_hours)
    store.apply(view)
    store.ingest(
        view.name,
        pd.DataFrame(
            {
                "user_id": [r[0] for r in rows],
                "event_timestamp": [T0 + pd.Timedelta(minutes=r[1]) for r in rows],
                "score": [r[2] for r in rows],
            }
        ),
    )
    return store


def _entities(pairs: list[tuple[str, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "user_id": [p[0] for p in pairs],
            "event_timestamp": [T0 + pd.Timedelta(minutes=p[1]) for p in pairs],
            "label": range(len(pairs)),
        }
    )


# ------------------------------------------------------------------------- point-in-time joins
def test_point_in_time_join_never_uses_future_rows():
    store = _store([("u1", 0, 1.0), ("u1", 30, 2.0), ("u1", 60, 3.0)])
    out = store.get_historical_features(_entities([("u1", 45), ("u1", 29), ("u1", 61)]), ["user_stats"])
    # at 45 the 60-minute row exists in the table but is in the future: must not be used
    assert out["score"].tolist() == [2.0, 1.0, 3.0]
    assert out["label"].tolist() == [0, 1, 2]  # original order preserved


def test_point_in_time_join_includes_exact_timestamp_and_isolates_entities():
    store = _store([("u1", 10, 1.0), ("u2", 5, 9.0), ("u2", 20, 8.0)])
    out = store.get_historical_features(_entities([("u1", 10), ("u2", 10), ("u3", 10)]), ["user_stats"])
    assert out["score"].iloc[0] == 1.0
    assert out["score"].iloc[1] == 9.0
    assert np.isnan(out["score"].iloc[2])  # unknown entity -> null, not another entity's value


def test_point_in_time_join_before_first_row_is_null():
    store = _store([("u1", 60, 1.0)])
    out = store.get_historical_features(_entities([("u1", 59)]), ["user_stats"])
    assert np.isnan(out["score"].iloc[0])


def test_ttl_nulls_stale_feature_rows():
    store = _store([("u1", 0, 1.0)], ttl_hours=1)
    out = store.get_historical_features(_entities([("u1", 59), ("u1", 60), ("u1", 61)]), ["user_stats"])
    assert out["score"].iloc[0] == 1.0
    assert out["score"].iloc[1] == 1.0  # exactly at the TTL boundary is still valid
    assert np.isnan(out["score"].iloc[2])


def test_no_leakage_against_brute_force_on_simulator():
    txns = make_fraud_scenario_stream(400, seed=7)
    feats = compute_account_features(txns)
    store = fintech_feature_store(txns)
    rng = np.random.default_rng(1)
    sample = txns.sample(60, random_state=3)
    offsets = pd.to_timedelta(rng.integers(-1800, 1800, size=len(sample)), unit="s")
    entity_df = pd.DataFrame(
        {
            "account_id": sample["account_id"].to_numpy(),
            "event_timestamp": sample["timestamp"].to_numpy() + offsets,
        }
    )
    out = store.get_historical_features(entity_df, [ACCOUNT_TXN_VIEW.name])
    ttl = pd.Timedelta(ACCOUNT_TXN_VIEW.ttl)
    for i, row in out.iterrows():
        hist = feats[
            (feats.account_id == row.account_id)
            & (feats.event_timestamp <= row.event_timestamp)
            & (feats.event_timestamp >= row.event_timestamp - ttl)
        ]
        if hist.empty:
            assert np.isnan(row.txn_count_1h), i
        else:
            assert row.txn_count_1h == hist.iloc[-1].txn_count_1h
            assert row.amount_sum_24h == pytest.approx(hist.iloc[-1].amount_sum_24h)


def test_account_feature_windows_are_trailing():
    txns = pd.DataFrame(
        {
            "account_id": ["a"] * 4,
            "timestamp": [
                T0,
                T0 + pd.Timedelta(minutes=30),
                T0 + pd.Timedelta(minutes=61),
                T0 + pd.Timedelta(hours=26),
            ],
            "amount": [10.0, 20.0, 30.0, 40.0],
            "country_code": ["US", "GB", "US", "FR"],
        }
    )
    f = compute_account_features(txns)
    assert f["txn_count_1h"].tolist() == [1, 2, 2, 1]
    assert f["amount_sum_24h"].tolist() == [10.0, 30.0, 60.0, 40.0]
    assert f["distinct_countries_24h"].tolist() == [1, 2, 2, 1]
    assert set(ACCOUNT_FEATURES) <= set(f.columns)


# ---------------------------------------------------------------------------- online serving
def test_materialize_and_online_freshness():
    store = _store([("u1", 0, 1.0), ("u1", 30, 2.0), ("u2", 10, 5.0)], ttl_hours=1)
    assert store.materialize("user_stats", T0, T0 + pd.Timedelta(minutes=45)) == 2
    now = T0 + pd.Timedelta(minutes=80)
    got = store.get_online_features("user_stats", ["u1", "u2", "u9"], now=now)
    assert got.status == {"u1": PRESENT, "u2": EXPIRED, "u9": NOT_FOUND}
    assert got.values["u1"]["score"] == 2.0
    assert got.values["u2"]["score"] is None  # stale value is never served


def test_materialize_never_overwrites_newer_with_older():
    store = _store([("u1", 0, 1.0), ("u1", 30, 2.0)])
    store.materialize("user_stats", T0, T0 + pd.Timedelta(minutes=40))
    assert store.materialize("user_stats", T0, T0 + pd.Timedelta(minutes=5)) == 0
    got = store.get_online_features("user_stats", ["u1"], now=T0 + pd.Timedelta(minutes=40))
    assert got.values["u1"]["score"] == 2.0


def test_incremental_materialization_picks_up_new_rows():
    store = _store([("u1", 0, 1.0)])
    store.materialize_incremental("user_stats", T0 + pd.Timedelta(minutes=10))
    store.ingest(
        "user_stats",
        pd.DataFrame({"user_id": ["u1"], "event_timestamp": [T0 + pd.Timedelta(minutes=20)], "score": [7.0]}),
    )
    store.materialize_incremental("user_stats", T0 + pd.Timedelta(minutes=30))
    got = store.get_online_features("user_stats", ["u1"], now=T0 + pd.Timedelta(minutes=30))
    assert got.values["u1"]["score"] == 7.0


def test_no_skew_after_materialization_on_simulator():
    store = fintech_feature_store(make_fraud_scenario_stream(600, seed=11))
    end = store.offline.read(ACCOUNT_TXN_VIEW)["event_timestamp"].max()
    store.materialize_incremental(ACCOUNT_TXN_VIEW.name, end)
    report = store.check_skew(ACCOUNT_TXN_VIEW.name, as_of=end, sample=50)
    assert report.keys_checked > 0 and report.ok and report.mismatch_rate == 0.0


def test_skew_detected_when_online_store_is_stale_or_corrupted():
    store = _store([("u1", 0, 1.0), ("u2", 0, 4.0)])
    store.materialize("user_stats", T0, T0 + pd.Timedelta(minutes=1))
    # new offline data that was never materialized + a bad online write
    store.ingest(
        "user_stats",
        pd.DataFrame({"user_id": ["u1"], "event_timestamp": [T0 + pd.Timedelta(minutes=30)], "score": [2.0]}),
    )
    store.online.write(store.view("user_stats"), "u2", T0 + pd.Timedelta(minutes=1), {"score": 40.0})
    report = store.check_skew("user_stats", as_of=T0 + pd.Timedelta(minutes=40), keys=["u1", "u2"])
    assert not report.ok
    assert {m["key"] for m in report.mismatches} == {"u1", "u2"}
    assert report.per_feature["score"] == 2


def test_feature_view_validation():
    with pytest.raises(ValueError):
        FeatureView("bad", USER, (), ttl=timedelta(hours=1))
    with pytest.raises(ValueError):
        FeatureView("bad", USER, ("a",), ttl=timedelta(0))
    store = _store([("u1", 0, 1.0)])
    with pytest.raises(ValueError):
        store.ingest("user_stats", pd.DataFrame({"user_id": ["u1"], "score": [1.0]}))


# ---------------------------------------------------------------------------- model serving
@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    root = tmp_path_factory.mktemp("serving")
    df = make_fraud_scenario_stream(1500, seed=5)
    m1, met1 = train(df, seed=0)
    m2, met2 = train(df, seed=1, epochs=50)
    m2.threshold = 0.99  # visibly different behaviour for the swap test
    p1, p2 = m1.save(root / "m1.json"), m2.save(root / "m2.json")
    return df, (p1, met1), (p2, met2)


@pytest.fixture
def server(trained, tmp_path):
    _, (p1, met1), _ = trained
    reg = ModelRegistry(tmp_path / "registry")
    reg.register("fraud-detector", p1, met1, alias="champion")
    srv = FraudModelServer(reg)
    srv.load()
    return srv


def _req(x: np.ndarray, rid: str = "r1") -> dict:
    return {
        "id": rid,
        "inputs": [
            {"name": "features", "shape": list(x.shape), "datatype": "FP32", "data": x.ravel().tolist()}
        ],
    }


def test_oip_infer_matches_model_and_carries_version(server, trained):
    df = trained[0]
    x = featurize(df.head(5))
    resp = server.infer(_req(x))
    body = resp.to_dict()
    assert body["model_name"] == "fraud-detector" and body["model_version"] == "1" and body["id"] == "r1"
    probs = resp.output("probability").data
    assert resp.output("probability").shape == [5]
    np.testing.assert_allclose(probs, server._current().model.predict_proba(x), atol=1e-6)
    assert server.response_headers(resp) == {"x-model-name": "fraud-detector", "x-model-version": "1"}


def test_oip_columnar_inputs_equal_matrix_inputs(server, trained):
    x = featurize(trained[0].head(3))
    cols = {
        "inputs": [
            {"name": f, "shape": [3], "datatype": "FP64", "data": x[:, i].tolist()}
            for i, f in enumerate(FEATURES)
        ]
    }
    a = server.infer(cols).output("probability").data
    b = server.infer(_req(x)).output("probability").data
    assert a == b


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"inputs": []},
        {"inputs": [{"name": "features", "shape": [1, 7], "datatype": "FP32", "data": [0.0] * 6}]},
        {"inputs": [{"name": "features", "shape": [1, 6], "datatype": "FP32", "data": [0.0] * 6}]},
        {"inputs": [{"name": "features", "shape": [1, 7], "datatype": "COMPLEX", "data": [0.0] * 7}]},
        {"inputs": [{"name": "features", "shape": [1, 7], "datatype": "FP32", "data": ["x"] * 7}]},
        {
            "inputs": [
                {"name": "features", "shape": [1, 7], "datatype": "FP32", "data": [1.0, 0.5, 0, 0, 0, 0, 0]}
            ]
        },
        {
            "inputs": [
                {
                    "name": "features",
                    "shape": [1, 7],
                    "datatype": "FP32",
                    "data": [float("nan"), 1, 0, 0, 0, 0, 0],
                }
            ]
        },
        {"inputs": [{"name": "amount", "shape": [1], "datatype": "FP32", "data": [1.0]}]},
    ],
)
def test_oip_validation_rejects_bad_requests(server, body):
    with pytest.raises(InferenceError) as e:
        server.infer(body)
    assert e.value.status == 400


def test_oip_batch_limit_and_server_side_batching(server, trained):
    x = featurize(trained[0].head(6))
    server.max_batch_size = 5
    with pytest.raises(InferenceError) as e:
        server.infer(_req(x))
    assert e.value.status == 413
    server.max_batch_size = 100
    reqs = [InferRequest.from_dict(_req(x[:2], "a")), InferRequest.from_dict(_req(x[2:], "b"))]
    batched = server.infer_batch(reqs)
    assert [r.id for r in batched] == ["a", "b"]
    assert (
        batched[0].output("probability").data + batched[1].output("probability").data
        == server.infer(_req(x)).output("probability").data
    )


def test_champion_swap_and_rollback_hot_reload(server, trained):
    _, _, (p2, met2) = trained
    x = featurize(trained[0].head(20))
    assert server.reload() is False  # nothing changed
    v2 = server.registry.register("fraud-detector", p2, met2)
    server.registry.set_alias("fraud-detector", "champion", v2.version)
    assert server.reload() is True
    resp = server.infer(_req(x))
    assert resp.model_version == "2" and resp.parameters["threshold"] == 0.99
    server.registry.set_alias("fraud-detector", "champion", 1)
    assert server.reload() is True and server.version == "1"


def test_server_loads_from_relocated_registry(server, tmp_path):
    import shutil

    moved = tmp_path / "mnt" / "models"
    shutil.copytree(server.registry.root, moved)
    shutil.rmtree(server.registry.root)  # the registered artifact path no longer exists
    srv = FraudModelServer(ModelRegistry(moved))
    assert srv.load() == 1 and srv.ready


def test_server_not_ready_without_champion(tmp_path):
    srv = FraudModelServer(ModelRegistry(tmp_path))
    assert not srv.ready and srv.reload() is False
    with pytest.raises(InferenceError) as e:
        srv.infer(_req(np.zeros((1, len(FEATURES)))))
    assert e.value.status == 503


def test_oip_tensor_roundtrip_and_nested_data():
    t = InferTensor.from_dict({"name": "x", "shape": [2, 2], "datatype": "FP32", "data": [[1, 2], [3, 4]]})
    assert t.data == [1, 2, 3, 4]
    req = InferRequest.from_dict({"id": "q", "inputs": [t.to_dict()], "outputs": [{"name": "probability"}]})
    assert InferRequest.from_dict(req.to_dict()) == req


def test_model_server_http_app(server, trained):
    from fastapi.testclient import TestClient

    from golden.ai.serving.app import make_app

    client = TestClient(make_app(server))
    assert client.get("/v2/health/ready").json() == {"ready": True}
    assert client.get("/v2/models/fraud-detector").json()["inputs"][0]["shape"] == [-1, len(FEATURES)]
    x = featurize(trained[0].head(2))
    r = client.post("/v2/models/fraud-detector/infer", json=_req(x))
    assert r.status_code == 200 and r.headers["x-model-version"] == "1"
    assert client.post("/v2/models/other/infer", json=_req(x)).status_code == 404
    bad = client.post("/v2/models/fraud-detector/infer", json={"inputs": []})
    assert bad.status_code == 400 and "error" in bad.json()


# --------------------------------------------------------------------------- GPU partitioning
def test_mig_profile_tables_are_consistent():
    for gpu in GPU_MODELS.values():
        names = [p.name for p in gpu.profiles]
        assert names[0].startswith("1g.") and names[-1].startswith("7g.")
        for p in gpu.profiles:
            assert p.memory_gb == pytest.approx(gpu.memory_gb * p.memory_slices / 8)
            assert valid_layout(gpu, [p] * p.max_instances) is not None
            assert valid_layout(gpu, [p] * (p.max_instances + 1)) is None
    a100 = gpu_model("A100-40GB")
    assert a100.profile("1g.5gb").max_instances == 7 and a100.profile("3g.20gb").max_instances == 2
    assert gpu_model("H100-80GB").profile("7g.80gb").compute_slices == 7


def test_mig_placement_rules():
    g = gpu_model("A100-80GB")
    assert valid_layout(g, ["4g.40gb", "3g.40gb"]) == [("4g.40gb", 0), ("3g.40gb", 4)]
    assert valid_layout(g, ["3g.40gb", "2g.20gb", "1g.10gb", "1g.10gb"]) is not None
    assert valid_layout(g, ["3g.40gb", "3g.40gb", "1g.10gb"]) is None  # 9 memory slices
    assert valid_layout(g, ["4g.40gb", "4g.40gb"]) is None  # 4g only starts at slice 0
    assert valid_layout(g, ["7g.80gb", "1g.10gb"]) is None


def test_mig_packing_is_optimal_on_simple_cases():
    g = gpu_model("A100-40GB")
    cases = [
        ["1g.5gb"] * 7,
        ["1g.5gb"] * 14,
        ["3g.20gb", "4g.20gb", "3g.20gb", "4g.20gb"],
        ["2g.10gb", "2g.10gb", "3g.20gb", "1g.5gb"] * 3,
        ["3g.20gb", "3g.20gb", "1g.5gb"],
    ]
    for profiles in cases:
        bins = pack_mig(g, [(f"w{i}", g.profile(p)) for i, p in enumerate(profiles)])
        assert all(valid_layout(g, [p for _, p in b]) for b in bins)
        assert sum(len(b) for b in bins) == len(profiles)
        assert len(bins) == mig_lower_bound(g, profiles), profiles


def test_gpu_operator_mig_layouts_are_valid():
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1] / "deploy/k8s/gpu-operator"
    cm = yaml.safe_load((root / "mig-config.yaml").read_text())
    configs = yaml.safe_load(cm["data"]["config.yaml"])["mig-configs"]
    g = gpu_model("A100-80GB")
    for name, groups in configs.items():
        for group in groups:
            devices = group.get("mig-devices") or {}
            layout = [p for p, n in devices.items() for _ in range(n)]
            assert not layout or valid_layout(g, layout) is not None, name
    ts = yaml.safe_load((root / "time-slicing-config.yaml").read_text())
    replicas = yaml.safe_load(ts["data"]["any"])["sharing"]["timeSlicing"]["resources"][0]["replicas"]
    assert replicas == TIME_SLICING_REPLICAS


def test_smallest_profile_respects_memory_and_compute():
    g = gpu_model("A100-80GB")
    assert smallest_profile(g, Workload("a", 8, 0.1)).name == "1g.10gb"
    assert smallest_profile(g, Workload("b", 15, 0.1)).name == "1g.20gb"
    assert smallest_profile(g, Workload("c", 8, 0.25)).name == "2g.20gb"
    assert smallest_profile(g, Workload("d", 90, 0.1)) is None


def test_strategy_recommendations():
    rec = recommend_strategy
    assert rec(Workload("train", 70, 1.0, kind="training")).strategy == WHOLE_GPU
    assert rec(Workload("big-infer", 75, 0.3)).strategy == WHOLE_GPU  # only the 7g profile fits
    iso = rec(Workload("pii-infer", 9, 0.1, isolation_required=True))
    assert iso.strategy == MIG and iso.mig_profile == "1g.10gb"
    assert rec(Workload("batch", 10, 0.3, throughput_oriented=True, kind="batch")).strategy == MPS
    assert rec(Workload("chatbot", 6, 0.2, bursty=True)).strategy == TIME_SLICING
    assert rec(Workload("nb", 6, 0.1, kind="notebook")).strategy == TIME_SLICING
    assert rec(Workload("steady", 6, 0.1)).strategy == MIG
    with pytest.raises(ValueError):
        Workload("bad", 1, 1.5)


def test_plan_partitioning_saves_gpus_and_money():
    workloads = [Workload(f"iso-{i}", 9, 0.12, isolation_required=True, tenant=f"t{i}") for i in range(7)]
    workloads += [Workload(f"burst-{i}", 10, 0.2, bursty=True) for i in range(4)]
    workloads += [Workload("train", 70, 1.0, kind="training")]
    plan = plan_partitioning(workloads, "A100-80GB", price_per_gpu_hour=4.0)
    assert plan.baseline_gpus == 12
    strategies = sorted(g.strategy for g in plan.gpus)
    assert strategies == [MIG, TIME_SLICING, WHOLE_GPU]
    assert plan.gpus_saved == 9
    assert plan.monthly_savings_usd == pytest.approx(9 * 4.0 * 730)
    assert plan.to_dict()["annual_savings_usd"] == pytest.approx(plan.monthly_savings_usd * 12)


def test_shared_gpus_never_mix_tenants_and_respect_memory():
    workloads = [Workload(f"a{i}", 30, 0.4, throughput_oriented=True, tenant="a") for i in range(3)]
    workloads += [Workload("b0", 10, 0.1, throughput_oriented=True, tenant="b")]
    plan = plan_partitioning(workloads, "A100-80GB")
    for g in plan.gpus:
        assert g.strategy == MPS
        assert g.memory_gb_used <= 80 and g.compute_used <= 1.0 + 1e-9
        assert len({w[0] for w in g.workloads}) == 1  # tenant prefix
    assert plan.gpus_needed == 3


def test_plan_override_and_duplicate_names():
    w = [Workload("x", 5, 0.1, bursty=True)]
    assert plan_partitioning(w, strategies={"x": MIG}).gpus[0].strategy == MIG
    with pytest.raises(ValueError):
        plan_partitioning([Workload("x", 5, 0.1), Workload("x", 5, 0.1)])
