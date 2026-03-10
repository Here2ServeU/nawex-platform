"""Time-series storage placeholder."""


def write_point(metric: str, value: float, ts: str) -> dict:
    return {"metric": metric, "value": value, "timestamp": ts}
