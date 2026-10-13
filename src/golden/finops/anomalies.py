"""Daily cost anomaly detection, month-end forecast and budget status over FOCUS data.

Anomalies use a robust z-score: for each day, the median and MAD (median absolute deviation) of the
previous ``window`` days of the same group form the baseline, so a single spike cannot inflate its own
baseline the way a mean/stddev would. Only spikes are flagged, and only when the dollar impact is worth a
human's time (``min_impact``). This mirrors what AWS Cost Anomaly Detection / Azure anomaly alerts do,
but runs on any FOCUS export and on team tags as well as services.

The forecast fits a straight line through month-to-date daily cost and sums it to the end of the month,
the same way a budget's FORECASTED notification reasons about spend.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from golden.finops.allocation import with_dimension

MAD_TO_SIGMA = 1.4826  # MAD * 1.4826 ~ stddev for normal data (robust z = 0.6745 * (x - median) / MAD)


def _group_column(frame: pd.DataFrame, by: str) -> tuple[pd.DataFrame, str]:
    if by in frame.columns:
        return frame, by
    return with_dimension(frame, by, column=f"_tag_{by}"), f"_tag_{by}"


def daily_costs(frame: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """Daily ``EffectiveCost`` (rows = dates, columns = groups; a single ``total`` column when ``by`` is None).

    ``by`` is a FOCUS column (``ServiceName``) or, if no such column exists, a tag key (``Team``).
    Missing days are filled with 0.
    """
    data = frame.assign(_day=frame["ChargePeriodStart"].dt.normalize())
    if by is None:
        table = data.groupby("_day")["EffectiveCost"].sum().to_frame("total")
    else:
        data, column = _group_column(data, by)
        table = data.pivot_table(
            index="_day", columns=column, values="EffectiveCost", aggfunc="sum", fill_value=0.0
        )
    if table.empty:
        return table
    full = pd.date_range(table.index.min(), table.index.max(), freq="D")
    table = table.reindex(full, fill_value=0.0)
    table.index.name = "date"
    table.columns.name = None
    return table.astype(float)


@dataclass
class Anomaly:
    date: str
    group: str
    by: str
    cost: float
    expected: float
    robust_z: float
    severity: str  # medium | high

    @property
    def impact(self) -> float:
        return self.cost - self.expected

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "impact": round(self.impact, 2)}


def robust_z(value: float, history: np.ndarray, floor_ratio: float = 0.05) -> tuple[float, float]:
    """(z, median) of ``value`` against ``history``. The scale is floored at ``floor_ratio`` x median so a
    perfectly flat history does not turn a 1% wobble into an infinite z-score."""
    median = float(np.median(history))
    mad = float(np.median(np.abs(history - median)))
    scale = max(MAD_TO_SIGMA * mad, floor_ratio * abs(median), 1e-9)
    return float((value - median) / scale), median


def detect_anomalies(
    frame: pd.DataFrame,
    by: str = "ServiceName",
    *,
    window: int = 14,
    min_history: int = 7,
    threshold: float = 3.5,
    min_impact: float = 25.0,
    floor_ratio: float = 0.05,
) -> list[Anomaly]:
    """Spikes per ``by`` group (FOCUS column or tag key) whose robust z-score >= ``threshold`` and whose
    cost exceeds the baseline median by at least ``min_impact``. Newest first, then largest impact."""
    table = daily_costs(frame, by)
    found: list[Anomaly] = []
    for group in table.columns:
        values = table[group].to_numpy(dtype=float)
        for i in range(min_history, len(values)):
            history = values[max(0, i - window) : i]
            z, median = robust_z(values[i], history, floor_ratio)
            if z >= threshold and values[i] - median >= min_impact:
                found.append(
                    Anomaly(
                        date=table.index[i].date().isoformat(),
                        group=str(group),
                        by=by,
                        cost=round(float(values[i]), 2),
                        expected=round(median, 2),
                        robust_z=round(float(z), 2),
                        severity="high" if z >= 2 * threshold else "medium",
                    )
                )
    return sorted(found, key=lambda a: (a.date, a.impact), reverse=True)


# ----------------------------------------------------------------------------- forecast
@dataclass
class Forecast:
    month: str
    as_of: str
    days_elapsed: int
    days_in_month: int
    month_to_date: float
    forecast: float
    daily_run_rate: float
    daily_trend: float  # fitted change in daily cost per day

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_of(frame: pd.DataFrame, as_of: date | None) -> date:
    if as_of is not None:
        return as_of
    if frame.empty:
        raise ValueError("cannot infer as_of from empty cost data")
    return pd.Timestamp(frame["ChargePeriodStart"].max()).date()


def forecast_series(daily: pd.Series, as_of: date) -> Forecast:
    """Month-end forecast from a daily cost series (DatetimeIndex) as of ``as_of`` (inclusive)."""
    month_start = pd.Timestamp(as_of.replace(day=1))
    days_in_month = calendar.monthrange(as_of.year, as_of.month)[1]
    elapsed = as_of.day
    span = pd.date_range(month_start, periods=elapsed, freq="D")
    mtd = daily.reindex(span, fill_value=0.0).to_numpy(dtype=float)
    month_to_date = float(mtd.sum())
    remaining_days = np.arange(elapsed + 1, days_in_month + 1, dtype=float)

    if elapsed >= 3:
        slope, intercept = np.polyfit(np.arange(1, elapsed + 1, dtype=float), mtd, 1)
        projected = np.clip(slope * remaining_days + intercept, 0.0, None)
    else:
        slope = 0.0
        projected = np.full(remaining_days.shape, mtd.mean() if elapsed else 0.0)
    return Forecast(
        month=as_of.strftime("%Y-%m"),
        as_of=as_of.isoformat(),
        days_elapsed=elapsed,
        days_in_month=days_in_month,
        month_to_date=round(month_to_date, 2),
        forecast=round(month_to_date + float(projected.sum()), 2),
        daily_run_rate=round(month_to_date / elapsed, 2) if elapsed else 0.0,
        daily_trend=round(float(slope), 4),
    )


def forecast_month_end(frame: pd.DataFrame, as_of: date | None = None) -> Forecast:
    """Linear-trend month-end forecast of total spend; data after ``as_of`` is ignored."""
    day = _as_of(frame, as_of)
    data = frame[frame["ChargePeriodStart"] < pd.Timestamp(day) + pd.Timedelta(days=1)]
    return forecast_series(daily_costs(data)["total"] if not data.empty else pd.Series(dtype=float), day)


# ----------------------------------------------------------------------------- budgets
@dataclass
class BudgetStatus:
    name: str
    budget: float
    month_to_date: float
    forecast: float
    status: str  # ok | warning | at_risk | over

    @property
    def used(self) -> float:
        return self.month_to_date / self.budget if self.budget else 0.0

    @property
    def forecast_used(self) -> float:
        return self.forecast / self.budget if self.budget else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "used": round(self.used, 4), "forecast_used": round(self.forecast_used, 4)}


def budget_status(
    frame: pd.DataFrame,
    budgets: Mapping[str, float],
    key: str = "Team",
    as_of: date | None = None,
    warn_at: float = 0.8,
) -> list[BudgetStatus]:
    """Month-to-date and forecast vs budget for each ``{name: monthly budget}``.

    ``name`` is a value of ``key`` (tag key or FOCUS column); ``"total"`` means all spend. Status is
    ``over`` (actual > budget), ``at_risk`` (forecast > budget), ``warning`` (actual >= warn_at x budget)
    or ``ok`` — the same ladder as the ACTUAL/FORECASTED budget notifications in deploy/terraform.
    """
    day = _as_of(frame, as_of)
    data = frame[frame["ChargePeriodStart"] < pd.Timestamp(day) + pd.Timedelta(days=1)]
    data, column = _group_column(data, key)
    out = []
    for name, amount in budgets.items():
        rows = data if name == "total" else data[data[column] == name]
        series = daily_costs(rows)["total"] if not rows.empty else pd.Series(dtype=float)
        fc = forecast_series(series, day)
        if fc.month_to_date > amount:
            status = "over"
        elif fc.forecast > amount:
            status = "at_risk"
        elif fc.month_to_date >= warn_at * amount:
            status = "warning"
        else:
            status = "ok"
        out.append(
            BudgetStatus(
                name=name,
                budget=float(amount),
                month_to_date=fc.month_to_date,
                forecast=fc.forecast,
                status=status,
            )
        )
    return out
