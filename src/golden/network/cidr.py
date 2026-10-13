"""IP address management (IPAM) planner: hierarchical, deterministic, non-overlapping CIDR allocation.

The hierarchy mirrors how an enterprise network is governed::

    supernet (10.0.0.0/8)
      region       /12   us-east-1, eu-west-1, ...
        environment /14  prod, nonprod, shared   (each env block is a summary route -> TGW segment)
          vpc       /18  one per account / workload
            tier x AZ    public /24, private /21, data /24, tgw /28

Design choices (and why):

* **Deterministic, append-only.** Children are allocated in declaration order, each taking the first
  free aligned block. The same spec always yields the same plan; appending a region / env / VPC never
  moves an existing one. Re-ordering or inserting in the middle *does* move later siblings - the plan
  diff makes that visible before Terraform does.
* **Reserved ranges are avoided at every level.** On-prem, partner and acquired-company ranges are
  never inside a region or environment block, so every block stays a clean summary route (a TGW
  blackhole for "nonprod" must never swallow an on-prem prefix). The utilization report shows the cost.
* **Largest tiers first inside a VPC** to avoid fragmentation, ties broken by declaration order.
* **IPv6**: one /56 per VPC from an IPv6 pool (AWS's fixed VPC size), one /64 per subnet (the only
  size SLAAC supports), indexed in the same tier/AZ order as IPv4 so dual-stack subnets line up.

``overlaps`` answers the merger/hybrid question - "which of these existing ranges collide?" - and
``find_free`` proposes non-colliding replacements. ``AddressPlan.to_tfvars`` emits the dict Terraform
consumes (VPC CIDRs, subnet lists, and ``segment_cidrs`` for ``modules/aws/network-hub``).
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

IPv4Net = ipaddress.IPv4Network
IPv6Net = ipaddress.IPv6Network
AnyNet = IPv4Net | IPv6Net

DEFAULT_TIERS: dict[str, int] = {"public": 24, "private": 21, "data": 24, "tgw": 28}
DEFAULT_SEGMENTS: dict[str, str] = {"prod": "prod", "shared": "shared"}  # anything else -> nonprod
VPC_IPV6_PREFIX = 56
SUBNET_IPV6_PREFIX = 64


class AllocationError(ValueError):
    """The requested block does not fit in the remaining free space."""


@dataclass(frozen=True)
class Reservation:
    """A range the planner must not use: on-prem, partner, acquired company, existing VPC."""

    cidr: str
    owner: str
    note: str = ""

    @property
    def network(self) -> AnyNet:
        return ipaddress.ip_network(self.cidr, strict=False)


@dataclass
class SubnetAlloc:
    tier: str
    az_index: int
    cidr: str
    ipv6_cidr: str | None = None
    ipv6_netnum: int | None = None


@dataclass
class VpcAlloc:
    region: str
    environment: str
    name: str
    cidr: str
    account: str = ""
    ipv6_cidr: str | None = None
    subnets: list[SubnetAlloc] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.region}/{self.environment}/{self.name}"

    def tier(self, name: str) -> list[str]:
        return [s.cidr for s in self.subnets if s.tier == name]


@dataclass
class EnvAlloc:
    region: str
    name: str
    segment: str
    cidr: str
    vpcs: list[VpcAlloc] = field(default_factory=list)


@dataclass
class RegionAlloc:
    name: str
    cidr: str
    environments: list[EnvAlloc] = field(default_factory=list)


@dataclass
class Overlap:
    a: Reservation
    b: Reservation
    kind: str  # "duplicate" | "contains"

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "a": f"{self.a.cidr} ({self.a.owner})",
            "b": f"{self.b.cidr} ({self.b.owner})",
        }


# ----------------------------------------------------------------------------- primitives
def _net(cidr: str | AnyNet) -> AnyNet:
    return cidr if isinstance(cidr, IPv4Net | IPv6Net) else ipaddress.ip_network(cidr, strict=False)


def _collides(candidate: AnyNet, taken: Iterable[AnyNet]) -> bool:
    return any(candidate.version == t.version and candidate.overlaps(t) for t in taken)


def _within(inner: AnyNet, outer: AnyNet) -> bool:
    return (
        inner.version == outer.version
        and int(outer.network_address) <= int(inner.network_address)
        and int(inner.broadcast_address) <= int(outer.broadcast_address)
    )


def _candidates(parent: AnyNet, prefix: int) -> Iterator[AnyNet]:
    if prefix < parent.prefixlen:
        raise AllocationError(f"/{prefix} does not fit inside {parent}")
    return parent.subnets(new_prefix=prefix)


def allocate(parent: str | AnyNet, prefix: int, taken: Iterable[str | AnyNet] = ()) -> AnyNet:
    """First aligned /prefix inside ``parent`` that overlaps nothing in ``taken``."""
    parent_net = _net(parent)
    taken_nets = [_net(t) for t in taken]
    relevant = [t for t in taken_nets if t.version == parent_net.version and t.overlaps(parent_net)]
    for candidate in _candidates(parent_net, prefix):
        if not _collides(candidate, relevant):
            return candidate
    raise AllocationError(f"no free /{prefix} left in {parent_net}")


def find_free(supernet: str, prefix: int, taken: Iterable[str], count: int = 1) -> list[str]:
    """Up to ``count`` free /prefix blocks in ``supernet`` (e.g. a new home for a colliding acquired VPC)."""
    used = [_net(t) for t in taken]
    found: list[str] = []
    for candidate in _candidates(_net(supernet), prefix):
        if not _collides(candidate, used):
            found.append(str(candidate))
            used.append(candidate)
            if len(found) == count:
                break
    return found


def overlaps(entries: Sequence[Reservation | Mapping[str, str]]) -> list[Overlap]:
    """Every colliding pair in an allocation inventory (CIDR blocks either nest or are disjoint).

    Sweep over blocks sorted by first address: a block can only collide with earlier blocks whose
    range is still open, so this is O(n log n + k) for k collisions instead of O(n^2).
    """
    items = [e if isinstance(e, Reservation) else Reservation(**dict(e)) for e in entries]
    found: list[Overlap] = []
    for version in (4, 6):
        nets = sorted(
            ((r.network, r) for r in items if r.network.version == version),
            key=lambda x: (int(x[0].network_address), x[0].prefixlen),
        )
        open_blocks: list[tuple[AnyNet, Reservation]] = []
        for net, res in nets:
            start = int(net.network_address)
            open_blocks = [(n, r) for n, r in open_blocks if int(n.broadcast_address) >= start]
            for other_net, other in open_blocks:
                kind = "duplicate" if other_net == net else "contains"
                found.append(Overlap(a=other, b=res, kind=kind))
            open_blocks.append((net, res))
    return found


# ----------------------------------------------------------------------------- plan
@dataclass
class AddressPlan:
    supernet: str
    reserved: list[Reservation]
    regions: list[RegionAlloc]
    ipv6_pool: str | None = None

    def vpcs(self) -> list[VpcAlloc]:
        return [v for r in self.regions for e in r.environments for v in e.vpcs]

    def environments(self) -> list[EnvAlloc]:
        return [e for r in self.regions for e in r.environments]

    def allocations(self) -> list[Reservation]:
        """Flat inventory (reserved + every VPC) - feed it to ``overlaps`` or an external IPAM."""
        out = list(self.reserved)
        out += [Reservation(v.cidr, v.key) for v in self.vpcs()]
        out += [Reservation(v.ipv6_cidr, v.key) for v in self.vpcs() if v.ipv6_cidr]
        return out

    def segment_cidrs(self) -> dict[str, list[str]]:
        segments: dict[str, list[str]] = {}
        for env in self.environments():
            segments.setdefault(env.segment, []).append(env.cidr)
        return {
            k: [str(n) for n in ipaddress.collapse_addresses(ipaddress.IPv4Network(c) for c in v)]
            for k, v in segments.items()
        }

    def utilization(self) -> list[dict[str, Any]]:
        """Allocated vs. capacity at every level (reserved space counts as used at the top)."""
        rows: list[dict[str, Any]] = []

        def row(scope: str, cidr: str, children: Iterable[str]) -> None:
            net = _net(cidr)
            used = sum(_net(c).num_addresses for c in children)
            rows.append(
                {
                    "scope": scope,
                    "cidr": cidr,
                    "capacity": net.num_addresses,
                    "allocated": used,
                    "free": net.num_addresses - used,
                    "utilization_pct": round(100 * used / net.num_addresses, 2),
                }
            )

        top = _net(self.supernet)
        reserved_inside = [str(r.network) for r in self.reserved if _within(r.network, top)]
        row("supernet", self.supernet, [r.cidr for r in self.regions] + reserved_inside)
        for region in self.regions:
            row(f"region:{region.name}", region.cidr, [e.cidr for e in region.environments])
            for env in region.environments:
                row(f"env:{region.name}/{env.name}", env.cidr, [v.cidr for v in env.vpcs])
                for vpc in env.vpcs:
                    row(f"vpc:{vpc.key}", vpc.cidr, [s.cidr for s in vpc.subnets])
        return rows

    def to_tfvars(self) -> dict[str, Any]:
        """Terraform-ready values: per-VPC CIDRs and subnet lists + network-hub ``segment_cidrs``."""
        vpcs: dict[str, Any] = {}
        for v in self.vpcs():
            tiers = sorted({s.tier for s in v.subnets})
            entry: dict[str, Any] = {
                "region": v.region,
                "environment": v.environment,
                "account": v.account,
                "cidr": v.cidr,
                "subnets": {t: v.tier(t) for t in tiers},
            }
            if v.ipv6_cidr:
                entry["ipv6_cidr"] = v.ipv6_cidr
                entry["ipv6_subnets"] = {t: [s.ipv6_cidr for s in v.subnets if s.tier == t] for t in tiers}
                entry["ipv6_netnums"] = {t: [s.ipv6_netnum for s in v.subnets if s.tier == t] for t in tiers}
            vpcs[v.key.replace("/", "-")] = entry
        return {"vpcs": vpcs, "segment_cidrs": self.segment_cidrs()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "supernet": self.supernet,
            "ipv6_pool": self.ipv6_pool,
            "reserved": [{"cidr": r.cidr, "owner": r.owner, "note": r.note} for r in self.reserved],
            "regions": [
                {
                    "name": r.name,
                    "cidr": r.cidr,
                    "environments": [
                        {
                            "name": e.name,
                            "segment": e.segment,
                            "cidr": e.cidr,
                            "vpcs": [
                                {
                                    "name": v.name,
                                    "account": v.account,
                                    "cidr": v.cidr,
                                    "ipv6_cidr": v.ipv6_cidr,
                                    "subnets": [s.__dict__ for s in v.subnets],
                                }
                                for v in e.vpcs
                            ],
                        }
                        for e in r.environments
                    ],
                }
                for r in self.regions
            ],
        }


def _vpc_specs(raw: Any) -> list[dict[str, Any]]:
    """``vpcs`` may be a list of names, a list of dicts, or a name -> options mapping."""
    if isinstance(raw, Mapping):
        return [{"name": k, **(dict(v) if v else {})} for k, v in raw.items()]
    return [{"name": v} if isinstance(v, str) else dict(v) for v in raw or []]


def plan_addresses(spec: Mapping[str, Any]) -> AddressPlan:
    """Allocate the whole hierarchy described by ``spec`` (see ``sample_spec`` for the shape)."""
    supernet = _net(spec["supernet"])
    if not isinstance(supernet, IPv4Net):
        raise ValueError("supernet must be IPv4; IPv6 comes from ipv6_pool")
    region_prefix = int(spec.get("region_prefix", 12))
    env_prefix = int(spec.get("environment_prefix", 14))
    default_vpc_prefix = int(spec.get("vpc_prefix", 18))
    if not supernet.prefixlen <= region_prefix <= env_prefix <= default_vpc_prefix:
        raise ValueError("prefixes must nest: supernet <= region <= environment <= vpc")
    default_tiers: dict[str, int] = dict(spec.get("tiers", DEFAULT_TIERS))
    default_azs = int(spec.get("az_count", 3))
    segments = {**DEFAULT_SEGMENTS, **dict(spec.get("segments", {}))}
    reserved = [r if isinstance(r, Reservation) else Reservation(**dict(r)) for r in spec.get("reserved", [])]
    reserved_nets = [r.network for r in reserved]

    ipv6_pool = spec.get("ipv6_pool")
    v6_parent = _net(ipv6_pool) if ipv6_pool else None
    if v6_parent is not None and (
        not isinstance(v6_parent, IPv6Net) or v6_parent.prefixlen > VPC_IPV6_PREFIX
    ):
        raise ValueError(f"ipv6_pool must be an IPv6 block of /{VPC_IPV6_PREFIX} or larger")
    v6_taken: list[AnyNet] = list(reserved_nets)

    regions: list[RegionAlloc] = []
    region_taken: list[AnyNet] = list(reserved_nets)
    for region_name, region_spec in dict(spec["regions"]).items():
        region_net = allocate(supernet, region_prefix, region_taken)
        region_taken.append(region_net)
        region = RegionAlloc(region_name, str(region_net))
        env_taken: list[AnyNet] = list(reserved_nets)
        for env_name, env_spec in dict(region_spec.get("environments", {})).items():
            env_spec = env_spec or {}
            env_net = allocate(region_net, int(env_spec.get("prefix", env_prefix)), env_taken)
            env_taken.append(env_net)
            env = EnvAlloc(region_name, env_name, segments.get(env_name, "nonprod"), str(env_net))
            vpc_taken: list[AnyNet] = list(reserved_nets)
            for vs in _vpc_specs(env_spec.get("vpcs", [])):
                vpc_net = allocate(env_net, int(vs.get("prefix", default_vpc_prefix)), vpc_taken)
                vpc_taken.append(vpc_net)
                vpc = VpcAlloc(region_name, env_name, vs["name"], str(vpc_net), str(vs.get("account", "")))
                if v6_parent is not None:
                    v6 = allocate(v6_parent, VPC_IPV6_PREFIX, v6_taken)
                    v6_taken.append(v6)
                    vpc.ipv6_cidr = str(v6)
                _plan_subnets(
                    vpc, vpc_net, dict(vs.get("tiers", default_tiers)), int(vs.get("az_count", default_azs))
                )
                env.vpcs.append(vpc)
            region.environments.append(env)
        regions.append(region)
    return AddressPlan(str(supernet), reserved, regions, str(v6_parent) if v6_parent else None)


def _plan_subnets(vpc: VpcAlloc, vpc_net: AnyNet, tiers: dict[str, int], az_count: int) -> None:
    order = sorted(enumerate(tiers.items()), key=lambda t: (t[1][1], t[0]))  # biggest first, then declared
    taken: list[AnyNet] = []
    allocated: dict[tuple[str, int], str] = {}
    for _, (tier, prefix) in order:
        for az in range(az_count):
            net = allocate(vpc_net, prefix, taken)
            taken.append(net)
            allocated[(tier, az)] = str(net)
    v6_net = _net(vpc.ipv6_cidr) if vpc.ipv6_cidr else None
    netnum = 0
    for tier in tiers:  # declared order for the IPv6 index: public=0..2, private=3..5, ...
        for az in range(az_count):
            sub = SubnetAlloc(tier, az, allocated[(tier, az)])
            if v6_net is not None:
                sub.ipv6_netnum = netnum
                step = 1 << (128 - SUBNET_IPV6_PREFIX)
                base = int(v6_net.network_address) + netnum * step
                sub.ipv6_cidr = str(ipaddress.IPv6Network((base, SUBNET_IPV6_PREFIX)))
                netnum += 1
            vpc.subnets.append(sub)


def sample_spec() -> dict[str, Any]:
    """A two-region estate with on-prem and partner ranges carved out of 10.0.0.0/8."""
    return {
        "supernet": "10.0.0.0/8",
        "region_prefix": 12,
        "environment_prefix": 14,
        "vpc_prefix": 18,
        "az_count": 3,
        "tiers": dict(DEFAULT_TIERS),
        "ipv6_pool": "2600:1f18:4000::/48",
        "reserved": [
            {"cidr": "10.0.0.0/12", "owner": "on-prem", "note": "data centers (legacy flat range)"},
            {"cidr": "10.250.0.0/16", "owner": "partner", "note": "payments processor VPN"},
        ],
        "regions": {
            "us-east-1": {
                "environments": {
                    "prod": {"vpcs": [{"name": "payments", "account": "555555555555"}, "platform"]},
                    "nonprod": {"vpcs": ["payments", "platform"]},
                    "shared": {"vpcs": ["shared-services", "inspection"]},
                }
            },
            "us-west-2": {
                "environments": {
                    "prod": {"vpcs": ["payments"]},
                    "nonprod": {"vpcs": ["payments"]},
                    "shared": {"vpcs": ["shared-services"]},
                }
            },
        },
    }
