"""Deep-learning forecasters, GPU acceleration and model integrity (requires the [ml] extra)."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from golden.ai import accel  # noqa: E402
from golden.ai.models import LSTMSLIPredictor, TCNSLIPredictor  # noqa: E402
from golden.ai.prediction import predict_lstm, predict_tcn  # noqa: E402
from golden.ai.training import make_windows, train_and_save  # noqa: E402

pytestmark = pytest.mark.ml


def test_accel_cpu_configuration():
    cfg = accel.configure("cpu")
    assert cfg.device == "cpu" and cfg.amp_dtype is None and not cfg.pin_memory
    with accel.autocast(cfg):
        assert torch.ones(1).dtype == torch.float32
    report = accel.device_report()
    assert report["torch"] == torch.__version__


def test_accel_falls_back_when_device_missing(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert accel.select_device("cuda") == "cpu"


def test_make_windows():
    import numpy as np

    x, y = make_windows(np.arange(10, dtype=float), lookback=3)
    assert x.shape == (7, 3, 1) and y.tolist() == list(range(3, 10))


@pytest.mark.parametrize("cls", [LSTMSLIPredictor, TCNSLIPredictor])
def test_forward_shapes(cls):
    model = cls()
    assert model(torch.zeros(4, 24, 1)).shape == (4,)


def test_train_save_load_and_integrity(tmp_path):
    for kind in ("lstm", "tcn"):
        result = train_and_save(kind, output_dir=tmp_path, epochs=1, n_points=300, device="cpu")
        assert result.device == "cpu" and result.final_loss == result.final_loss  # not NaN
    assert (tmp_path / "manifest.json").exists()

    seq = [150.0 + i for i in range(30)]
    lstm_risk = predict_lstm(seq, model_path=tmp_path / "lstm_model.pt")
    tcn_risk = predict_tcn(seq, model_path=tmp_path / "tcn_model.pt")
    assert 0 <= lstm_risk <= 1 and 0 <= tcn_risk <= 1

    model = LSTMSLIPredictor.load(tmp_path / "lstm_model.pt")
    assert model is not None and model.slo_ms == 200.0
    assert model.predict_risk([500.0] * 24) > model.predict_risk([100.0] * 24)

    # tampering is detected and the model is refused (inference falls back to statistics)
    path = tmp_path / "tcn_model.pt"
    path.write_bytes(path.read_bytes() + b"\x00")
    assert TCNSLIPredictor.load(path) is None
    assert LSTMSLIPredictor.load(tmp_path / "tcn_model.pt") is None  # wrong kind / bad hash


@pytest.mark.gpu
@pytest.mark.skipif(not (torch.cuda.is_available() or torch.backends.mps.is_available()), reason="no GPU")
def test_gpu_training_smoke(tmp_path):
    result = train_and_save("tcn", output_dir=tmp_path, epochs=1, n_points=300)
    assert result.device in {"cuda", "mps"}
