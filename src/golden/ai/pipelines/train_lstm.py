"""Train the LSTM SLI forecaster (``python -m golden.ai.pipelines.train_lstm``)."""

from __future__ import annotations

from golden.ai.training.trainer import train_forecaster


def train_lstm(epochs: int = 3, **kwargs):
    model, _ = train_forecaster("lstm", epochs=epochs, **kwargs)
    return model


if __name__ == "__main__":
    train_lstm()
