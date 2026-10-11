"""Simple explainability helpers for reliability risk outputs."""

from __future__ import annotations

from collections.abc import Iterable


def normalize_contributions(contributions: dict[str, float]) -> dict[str, float]:
    """Normalize absolute contributions so they sum to 1.0."""
    abs_sum = sum(abs(v) for v in contributions.values())
    if abs_sum == 0:
        return {k: 0.0 for k in contributions}
    return {k: abs(v) / abs_sum for k, v in contributions.items()}


def top_features(contributions: dict[str, float], top_k: int = 5) -> Iterable[tuple[str, float]]:
    """Return top-k features by absolute contribution."""
    norm = normalize_contributions(contributions)
    return sorted(norm.items(), key=lambda kv: kv[1], reverse=True)[:top_k]


def build_text_report(contributions: dict[str, float], top_k: int = 5) -> str:
    """Produce a human-readable explanation report for incident tickets."""
    items = list(top_features(contributions, top_k=top_k))
    if not items:
        return "No explainability signal available."

    lines = ["Top model contributors:"]
    for name, score in items:
        lines.append(f"- {name}: {score:.2%}")
    return "\n".join(lines)
