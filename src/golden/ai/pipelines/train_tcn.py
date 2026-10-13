"""Train the TCN SLI forecaster (``python -m golden.ai.pipelines.train_tcn``)."""

from __future__ import annotations

from golden.ai.training.trainer import train_forecaster


def train_tcn(epochs: int = 3, **kwargs):
    model, _ = train_forecaster("tcn", epochs=epochs, **kwargs)
    return model


if __name__ == "__main__":
    train_tcn()
