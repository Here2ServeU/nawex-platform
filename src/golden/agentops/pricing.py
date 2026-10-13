"""Token → dollar conversion. Prices live in ``pricing.yaml`` (or ``GOLDEN_PRICING_FILE``), never in code.

``cost = (input·p_in + cache_write·p_in·m_w + cache_read·p_in·m_r + output·p_out) / 1e6``

Input and output are priced separately and never averaged: output tokens cost ~5x input, and agents
that loop are dominated by re-sent input context.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            self.cache_read_input_tokens + other.cache_read_input_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any]:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path
        else resources.files("golden.agentops").joinpath("pricing.yaml").read_text("utf-8")
    )
    return yaml.safe_load(text)


def price_table() -> dict[str, Any]:
    return _load(os.getenv("GOLDEN_PRICING_FILE", ""))


def prices(model: str) -> tuple[float, float]:
    models = price_table()["models"]
    if model not in models:
        raise KeyError(f"no price for model {model!r}; add it to the pricing file")
    return float(models[model]["input"]), float(models[model]["output"])


def cost_usd(model: str, usage: Usage) -> float:
    table = price_table()
    p_in, p_out = prices(model)
    return (
        usage.input_tokens * p_in
        + usage.cache_creation_input_tokens * p_in * float(table.get("cache_write_multiplier", 1.25))
        + usage.cache_read_input_tokens * p_in * float(table.get("cache_read_multiplier", 0.1))
        + usage.output_tokens * p_out
    ) / 1_000_000
