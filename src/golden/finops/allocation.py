"""Showback / chargeback: allocate FOCUS ``EffectiveCost`` to owners, spread shared costs, measure tagging.

* **Direct cost** — rows carrying the allocation tag (``Team`` by default) belong to that tag value.
* **Shared cost** — platform services many teams consume (networking, observability) are tagged with a
  shared value (``shared``) or selected by service/category, pooled, and redistributed
  ``proportional`` (to each owner's direct spend), ``even`` or by ``fixed`` weights.
* **Untagged cost** — stays a visible ``untagged`` bucket in *showback* (so it gets fixed); *chargeback*
  must invoice every dollar, so it is spread proportionally instead.

Tag keys are matched case- and separator-insensitively (``CostCenter`` == ``cost_center``), the same rule
``security/policies/opa/tagging.rego`` uses, because GCP labels are lowercase.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import pandas as pd

DEFAULT_REQUIRED_TAGS = ("Project", "Environment", "Team", "CostCenter", "Owner")
UNTAGGED = "untagged"
SHARED_VALUES = frozenset({"shared", "platform-shared"})
Method = Literal["proportional", "even", "fixed"]


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def tag_value(tags: Mapping[str, str] | None, key: str) -> str | None:
    """Value of ``key`` in ``tags`` (case/separator-insensitive); ``None`` when absent or blank."""
    if not tags:
        return None
    wanted = normalize_key(key)
    for k, v in tags.items():
        if normalize_key(str(k)) == wanted and str(v).strip():
            return str(v).strip()
    return None


def with_dimension(
    frame: pd.DataFrame, key: str, column: str | None = None, untagged: str = UNTAGGED
) -> pd.DataFrame:
    """Copy of ``frame`` with a column holding each row's ``key`` tag value (or ``untagged``)."""
    out = frame.copy()
    out[column or key] = [tag_value(t, key) or untagged for t in out["Tags"]]
    return out


def breakdown(
    frame: pd.DataFrame, by: str | Sequence[str], tag_keys: Iterable[str] = ("Team",)
) -> pd.DataFrame:
    """``EffectiveCost`` summed by FOCUS columns and/or tag keys, largest first, with a share column."""
    columns = [by] if isinstance(by, str) else list(by)
    data = frame
    for key in tag_keys:
        if key in columns and key not in frame.columns:
            data = with_dimension(data, key)
    grouped = data.groupby(columns, dropna=False)["EffectiveCost"].sum().reset_index()
    total = float(grouped["EffectiveCost"].sum()) or 1.0
    grouped["share"] = grouped["EffectiveCost"] / total
    return grouped.sort_values("EffectiveCost", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------- tag coverage
@dataclass
class TagCoverage:
    total_cost: float
    compliant_cost: float
    by_tag: dict[str, float]  # tag key -> share of spend carrying it
    untagged_resources: list[dict[str, Any]] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return self.compliant_cost / self.total_cost if self.total_cost else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "coverage": round(self.coverage, 4)}


def tag_coverage(
    frame: pd.DataFrame, required_tags: Sequence[str] = DEFAULT_REQUIRED_TAGS, top: int = 10
) -> TagCoverage:
    """Share of spend carrying each required tag, share carrying all of them, and the costliest offenders."""
    total = float(frame["EffectiveCost"].sum())
    has = {key: frame["Tags"].map(lambda t, k=key: tag_value(t, k) is not None) for key in required_tags}
    all_tags = pd.Series(True, index=frame.index)
    for mask in has.values():
        all_tags &= mask
    by_tag = {
        key: round(float(frame.loc[mask, "EffectiveCost"].sum()) / total, 4) if total else 1.0
        for key, mask in has.items()
    }
    offenders = (
        frame.loc[~all_tags]
        .groupby(["ProviderName", "SubAccountId", "ResourceId"], dropna=False)
        .agg(cost=("EffectiveCost", "sum"), tags=("Tags", "first"))
        .reset_index()
        .sort_values("cost", ascending=False)
        .head(top)
    )
    untagged = [
        {
            "provider": r["ProviderName"],
            "account": r["SubAccountId"],
            "resource": r["ResourceId"],
            "cost": round(float(r["cost"]), 2),
            "missing": [k for k in required_tags if tag_value(r["tags"], k) is None],
        }
        for r in offenders.to_dict(orient="records")
    ]
    return TagCoverage(
        total_cost=round(total, 2),
        compliant_cost=round(float(frame.loc[all_tags, "EffectiveCost"].sum()), 2),
        by_tag=by_tag,
        untagged_resources=untagged,
    )


# ----------------------------------------------------------------------------- allocation
@dataclass
class OwnerCost:
    owner: str
    direct: float
    shared: float
    untagged: float = 0.0

    @property
    def total(self) -> float:
        return self.direct + self.shared + self.untagged

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "direct": round(self.direct, 2),
            "shared": round(self.shared, 2),
            "untagged": round(self.untagged, 2),
            "total": round(self.total, 2),
        }


@dataclass
class Allocation:
    key: str
    mode: str  # showback | chargeback
    method: str
    owners: list[OwnerCost]
    shared_pool: float
    untagged_pool: float
    total_cost: float

    def owner(self, name: str) -> OwnerCost | None:
        return next((o for o in self.owners if o.owner == name), None)

    def totals(self) -> dict[str, float]:
        return {o.owner: round(o.total, 2) for o in self.owners}

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "mode": self.mode,
            "method": self.method,
            "shared_pool": round(self.shared_pool, 2),
            "untagged_pool": round(self.untagged_pool, 2),
            "total_cost": round(self.total_cost, 2),
            "owners": [o.to_dict() for o in self.owners],
        }


def _weights(
    owners: Sequence[str], direct: Mapping[str, float], method: Method, fixed: Mapping[str, float] | None
) -> dict[str, float]:
    if not owners:
        return {}
    if method == "even":
        raw = {o: 1.0 for o in owners}
    elif method == "fixed":
        if not fixed:
            raise ValueError("method='fixed' needs weights, e.g. {'payments': 0.5, 'search': 0.5}")
        unknown = set(fixed) - set(owners)
        if unknown:
            raise ValueError(f"fixed weights name owners with no direct spend: {sorted(unknown)}")
        raw = {o: float(fixed.get(o, 0.0)) for o in owners}
    elif method == "proportional":
        raw = {o: max(direct.get(o, 0.0), 0.0) for o in owners}
    else:
        raise ValueError(f"unknown method {method!r}; use proportional, even or fixed")
    total = sum(raw.values())
    if total <= 0:
        return {o: 1.0 / len(owners) for o in owners}
    return {o: w / total for o, w in raw.items()}


def allocate(
    frame: pd.DataFrame,
    key: str = "Team",
    *,
    method: Method = "proportional",
    weights: Mapping[str, float] | None = None,
    shared_values: Iterable[str] = SHARED_VALUES,
    shared_services: Iterable[str] = (),
    mode: Literal["showback", "chargeback"] = "showback",
) -> Allocation:
    """Allocate ``EffectiveCost`` to ``key`` tag values.

    Rows whose tag value is in ``shared_values`` or whose ``ServiceName``/``ServiceCategory`` is in
    ``shared_services`` form the shared pool, redistributed with ``method``. In ``showback`` mode untagged
    cost stays an ``untagged`` owner; in ``chargeback`` mode it is spread proportionally to direct spend so
    the owners' totals equal the bill.
    """
    data = with_dimension(frame, key, column="_owner")
    shared_tags = {s.lower() for s in shared_values}
    services = set(shared_services)
    is_shared = data["_owner"].str.lower().isin(shared_tags) | (
        data["ServiceName"].isin(services) | data["ServiceCategory"].isin(services)
    )
    is_untagged = (data["_owner"] == UNTAGGED) & ~is_shared
    direct_rows = data[~is_shared & ~is_untagged]

    direct = {str(k): float(v) for k, v in direct_rows.groupby("_owner")["EffectiveCost"].sum().items()}
    shared_pool = float(data.loc[is_shared, "EffectiveCost"].sum())
    untagged_pool = float(data.loc[is_untagged, "EffectiveCost"].sum())
    owners = sorted(direct)

    shared_split = _weights(owners, direct, method, weights)
    result = {o: OwnerCost(owner=o, direct=direct[o], shared=shared_pool * shared_split[o]) for o in owners}
    if not owners:
        # Nothing is tagged: everything is unallocatable, whatever the mode.
        if shared_pool or untagged_pool:
            result[UNTAGGED] = OwnerCost(
                owner=UNTAGGED, direct=0.0, shared=shared_pool, untagged=untagged_pool
            )
    elif mode == "chargeback":
        untagged_split = _weights(owners, direct, "proportional", None)
        for o in owners:
            result[o].untagged = untagged_pool * untagged_split[o]
    elif untagged_pool:
        result[UNTAGGED] = OwnerCost(owner=UNTAGGED, direct=0.0, shared=0.0, untagged=untagged_pool)

    ordered = sorted(result.values(), key=lambda o: o.total, reverse=True)
    return Allocation(
        key=key,
        mode=mode,
        method=method,
        owners=ordered,
        shared_pool=shared_pool,
        untagged_pool=untagged_pool,
        total_cost=float(frame["EffectiveCost"].sum()),
    )


def showback(frame: pd.DataFrame, key: str = "Team", **kwargs: Any) -> Allocation:
    """Informational allocation: untagged spend stays visible as its own owner."""
    return allocate(frame, key, mode="showback", **kwargs)


def chargeback(frame: pd.DataFrame, key: str = "Team", **kwargs: Any) -> Allocation:
    """Invoiceable allocation: every dollar (shared and untagged) lands on an owner."""
    return allocate(frame, key, mode="chargeback", **kwargs)


# ----------------------------------------------------------------------------- unit economics
@dataclass
class UnitCost:
    owner: str
    cost: float
    units: float
    unit: str
    per: int

    @property
    def cost_per_unit(self) -> float:
        return self.cost / self.units if self.units else float("inf")

    @property
    def cost_per_n(self) -> float:
        return self.cost_per_unit * self.per

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "cost_per_unit": round(self.cost_per_unit, 6),
            f"cost_per_{self.per}": round(self.cost_per_n, 4),
        }


def unit_economics(
    costs: Allocation | Mapping[str, float],
    usage: Mapping[str, float],
    unit: str = "transactions",
    per: int = 1000,
) -> list[UnitCost]:
    """Cost per business unit (transactions, requests, active users) for each owner with usage.

    ``costs`` is an :class:`Allocation` (fully loaded totals) or a plain ``{owner: cost}`` mapping; use the
    key ``"total"`` in ``usage`` for a platform-wide figure.
    """
    totals = costs.totals() if isinstance(costs, Allocation) else {k: float(v) for k, v in costs.items()}
    grand_total = sum(totals.values())
    out = []
    for owner, units in usage.items():
        cost = grand_total if owner == "total" else totals.get(owner)
        if cost is None:
            continue
        out.append(UnitCost(owner=owner, cost=round(cost, 2), units=float(units), unit=unit, per=per))
    return out
