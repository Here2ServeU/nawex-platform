"""Network reachability analysis: "can A reach B on port P?" with the hop path, or the rule that blocks it.

A small, offline model of what AWS Reachability Analyzer does, over the objects that decide it:

* **security groups** (stateful): source egress and destination ingress, by CIDR or SG membership
* **VPC route tables**: longest-prefix match; ``local``, ``tgw``, ``igw``/``nat``, ``blackhole``
* **Transit Gateway route tables**: attachments are *associated* with one table (where lookups happen)
  and *propagate* their CIDRs into others; static routes beat propagated ones at equal length;
  blackholes drop
* **inspection** attachments: a firewall in the path, evaluated in order (first match wins), after
  which the packet re-enters the TGW from the inspection attachment
* **the return path**: routing must also work from B back to A, and a flow that crossed a stateful
  firewall must come back through the same firewall (asymmetric routing is the classic inspection bug)

``build_hub_route_tables`` derives the TGW tables from attachment segments with *the same rules* as
``deploy/terraform/modules/aws/network-hub`` (``PROPAGATE_TO`` / ``ASSOCIATE_WITH`` mirror its locals),
and ``verify_segmentation`` checks the intent: prod <-> nonprod denied, both -> shared allowed.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

MAX_TGW_HOPS = 8

# Mirrors locals.propagate_to / locals.associate_with in modules/aws/network-hub/main.tf.
PROPAGATE_TO: dict[str, list[str]] = {
    "prod": ["shared", "inspection"],
    "nonprod": ["shared", "inspection"],
    "shared": ["prod", "nonprod", "shared", "inspection"],
    "hybrid": ["prod", "nonprod", "shared", "inspection"],
    "inspection": [],
}
PROPAGATE_TO_EAST_WEST: dict[str, list[str]] = {
    "prod": ["inspection"],
    "nonprod": ["inspection"],
    "shared": ["shared", "inspection"],
    "hybrid": ["inspection"],
    "inspection": [],
}
ASSOCIATE_WITH: dict[str, str] = {
    "prod": "prod",
    "nonprod": "nonprod",
    "shared": "shared",
    "hybrid": "shared",
    "inspection": "inspection",
}
HUB_TABLES = ("prod", "nonprod", "shared", "inspection")


def _ip(x: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    return ipaddress.ip_address(x)


def _in(ip: str, cidr: str) -> bool:
    addr, net = _ip(ip), ipaddress.ip_network(cidr, strict=False)
    return addr.version == net.version and addr in net


# ----------------------------------------------------------------------------- model
@dataclass(frozen=True)
class Rule:
    """A security-group rule. For ingress, ``cidrs``/``groups`` are sources; for egress, destinations."""

    protocol: str = "tcp"  # tcp | udp | icmp | -1 (all)
    from_port: int = 0
    to_port: int = 65535
    cidrs: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()
    description: str = ""

    def matches(self, ip: str, port: int, protocol: str, peer_groups: Iterable[str]) -> bool:
        if self.protocol not in ("-1", protocol):
            return False
        if (
            self.protocol != "-1"
            and protocol in ("tcp", "udp")
            and not self.from_port <= port <= self.to_port
        ):
            return False
        return any(_in(ip, c) for c in self.cidrs) or bool(set(self.groups) & set(peer_groups))

    def label(self) -> str:
        ports = "all" if self.protocol == "-1" else f"{self.protocol}/{self.from_port}-{self.to_port}"
        peers = ",".join([*self.cidrs, *(f"sg:{g}" for g in self.groups)])
        return f"{ports} {peers}" + (f" ({self.description})" if self.description else "")


@dataclass
class SecurityGroup:
    name: str
    ingress: list[Rule] = field(default_factory=list)
    egress: list[Rule] = field(default_factory=list)


@dataclass(frozen=True)
class Route:
    destination: str
    target: str  # local | tgw | igw | nat | blackhole | attachment:<name>
    origin: str = "static"  # static | propagated

    @property
    def prefixlen(self) -> int:
        return ipaddress.ip_network(self.destination, strict=False).prefixlen


@dataclass
class RouteTable:
    name: str
    routes: list[Route] = field(default_factory=list)

    def lookup(self, ip: str) -> Route | None:
        """Longest-prefix match; at equal length a static route beats a propagated one (TGW rule)."""
        hits = [r for r in self.routes if _in(ip, r.destination)]
        if not hits:
            return None
        return max(hits, key=lambda r: (r.prefixlen, r.origin == "static"))


@dataclass
class Subnet:
    name: str
    cidr: str
    route_table: str


@dataclass
class Network:
    """A VPC, an on-prem site (behind DX/VPN) or an inspection VPC."""

    name: str
    cidrs: list[str]
    segment: str
    subnets: list[Subnet] = field(default_factory=list)
    attachment: str | None = None
    kind: str = "vpc"  # vpc | onprem | inspection
    internet_egress: bool = False  # inspection VPC with NAT/IGW behind the firewall

    def contains(self, ip: str) -> bool:
        return any(_in(ip, c) for c in self.cidrs)

    def subnet_for(self, ip: str) -> Subnet | None:
        return next((s for s in self.subnets if _in(ip, s.cidr)), None)


@dataclass(frozen=True)
class FirewallRule:
    action: str  # allow | deny
    source: str
    destination: str
    protocol: str = "-1"
    from_port: int = 0
    to_port: int = 65535
    name: str = ""

    def matches(self, src: str, dst: str, port: int, protocol: str) -> bool:
        if self.protocol not in ("-1", protocol):
            return False
        if self.protocol != "-1" and not self.from_port <= port <= self.to_port:
            return False
        return _in(src, self.source) and _in(dst, self.destination)


@dataclass
class Firewall:
    name: str
    rules: list[FirewallRule] = field(default_factory=list)
    default_action: str = "deny"

    def evaluate(self, src: str, dst: str, port: int, protocol: str) -> tuple[str, str]:
        for r in self.rules:
            if r.matches(src, dst, port, protocol):
                return r.action, r.name or f"{r.action} {r.source} -> {r.destination}"
        return self.default_action, "default action"


@dataclass
class Attachment:
    name: str
    network: str
    route_table: str  # associated TGW route table
    segment: str
    appliance_mode: bool = False
    firewall: str | None = None


@dataclass
class Endpoint:
    name: str
    ip: str
    network: str
    security_groups: list[str] = field(default_factory=list)


@dataclass
class Topology:
    networks: dict[str, Network] = field(default_factory=dict)
    route_tables: dict[str, RouteTable] = field(default_factory=dict)  # VPC tables
    tgw_route_tables: dict[str, RouteTable] = field(default_factory=dict)
    attachments: dict[str, Attachment] = field(default_factory=dict)
    security_groups: dict[str, SecurityGroup] = field(default_factory=dict)
    firewalls: dict[str, Firewall] = field(default_factory=dict)
    endpoints: dict[str, Endpoint] = field(default_factory=dict)

    def network_of(self, ip: str) -> Network | None:
        return next((n for n in self.networks.values() if n.contains(ip)), None)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Verdict:
    source: str
    destination: str
    port: int
    protocol: str
    reachable: bool
    path: list[str]
    blocked_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _Blocked(Exception):
    """Internal control flow: carries the rule that blocked the flow."""

    def __init__(self, rule: str) -> None:
        super().__init__(rule)
        self.rule = rule


# ----------------------------------------------------------------------------- analysis
def _route(
    topo: Topology, start: Network, src_ip: str, dst_ip: str, port: int, protocol: str, *, stateful: bool
) -> tuple[list[str], str, list[str]]:
    """Follow routing from ``start`` toward ``dst_ip``. Returns (hops, arrived-at, firewalls crossed)."""
    hops: list[str] = []
    firewalls: list[str] = []
    subnet = start.subnet_for(src_ip)
    if subnet is None:
        raise _Blocked(f"{src_ip} is in no subnet of {start.name}")
    rt = topo.route_tables[subnet.route_table]
    route = rt.lookup(dst_ip)
    if route is None:
        raise _Blocked(f"route table {rt.name}: no route to {dst_ip}")
    hops.append(f"rt {rt.name}: {route.destination} -> {route.target}")
    dst_net = topo.network_of(dst_ip)
    if route.target == "blackhole":
        raise _Blocked(f"route table {rt.name}: blackhole {route.destination}")
    if route.target == "local":
        if not start.contains(dst_ip):
            raise _Blocked(f"route table {rt.name}: local route but {dst_ip} is outside {start.name}")
        return hops, start.name, firewalls
    if route.target in ("igw", "nat"):
        if dst_net is not None:
            raise _Blocked(f"route table {rt.name}: private destination {dst_ip} routed to {route.target}")
        return hops, "internet", firewalls
    if route.target != "tgw" or start.attachment is None:
        raise _Blocked(f"route table {rt.name}: target {route.target} is not usable from {start.name}")

    ingress = topo.attachments[start.attachment]
    for _ in range(MAX_TGW_HOPS):
        tgw_rt = topo.tgw_route_tables[ingress.route_table]
        tr = tgw_rt.lookup(dst_ip)
        if tr is None:
            inspection_net = topo.networks[ingress.network]
            if ingress.firewall and inspection_net.internet_egress and dst_net is None:
                hops.append(f"{inspection_net.name}: egress to internet after inspection")
                return hops, "internet", firewalls
            raise _Blocked(f"tgw route table {tgw_rt.name}: no route to {dst_ip}")
        if tr.target == "blackhole":
            raise _Blocked(f"tgw route table {tgw_rt.name}: blackhole {tr.destination}")
        nxt = topo.attachments[tr.target.removeprefix("attachment:")]
        hops.append(f"tgw-rt {tgw_rt.name}: {tr.destination} -> {nxt.name} ({tr.origin})")
        if nxt.firewall:
            fw = topo.firewalls[nxt.firewall]
            firewalls.append(fw.name)
            if not stateful:
                action, why = fw.evaluate(src_ip, dst_ip, port, protocol)
                if action != "allow":
                    raise _Blocked(f"firewall {fw.name}: {why}")
                hops.append(f"firewall {fw.name}: allow ({why})")
            else:
                hops.append(f"firewall {fw.name}: return traffic of an allowed flow")
            ingress = nxt
            continue
        net = topo.networks[nxt.network]
        if not net.contains(dst_ip):
            raise _Blocked(f"tgw route to {nxt.name} but {dst_ip} is not in {net.name}")
        return hops, net.name, firewalls
    raise _Blocked("routing loop in the transit gateway")


def _sg_allows(
    topo: Topology,
    groups: list[str],
    direction: str,
    peer_ip: str,
    port: int,
    protocol: str,
    peer_groups: list[str],
) -> str | None:
    for g in groups:
        sg = topo.security_groups[g]
        for rule in sg.egress if direction == "egress" else sg.ingress:
            if rule.matches(peer_ip, port, protocol, peer_groups):
                return f"sg {g} {direction}: {rule.label()}"
    return None


def can_reach(topo: Topology, source: str, destination: str, port: int, protocol: str = "tcp") -> Verdict:
    """Can endpoint ``source`` open a ``protocol``/``port`` flow to ``destination`` (endpoint name or IP)?"""
    src = topo.endpoints[source]
    dst = topo.endpoints.get(destination)
    dst_ip = dst.ip if dst else destination
    dst_groups = dst.security_groups if dst else []
    path: list[str] = [f"{src.name} ({src.ip}, {src.network})"]
    verdict = Verdict(source, destination, port, protocol, False, path)
    try:
        if src.security_groups:
            hit = _sg_allows(topo, src.security_groups, "egress", dst_ip, port, protocol, dst_groups)
            if hit is None:
                raise _Blocked(
                    f"no egress rule in {src.security_groups} allows {protocol}/{port} to {dst_ip}"
                )
            path.append(hit)
        start = topo.networks[src.network]
        hops, arrived, crossed = _route(topo, start, src.ip, dst_ip, port, protocol, stateful=False)
        path += hops
        if arrived == "internet":
            path.append(f"internet ({dst_ip})")
            verdict.reachable = True
            return verdict
        dst_net = topo.networks[arrived]
        back, back_at, back_crossed = _route(topo, dst_net, dst_ip, src.ip, port, protocol, stateful=True)
        if back_at != start.name:
            raise _Blocked(f"return path from {dst_net.name} reaches {back_at}, not {start.name}")
        missing = [f for f in crossed if f not in back_crossed]
        if missing:
            raise _Blocked(
                f"asymmetric routing: return path bypasses firewall {missing[0]} (stateful inspection drops it)"
            )
        path.append("return: " + " | ".join(back))
        if dst is not None and dst.security_groups:
            hit = _sg_allows(
                topo, dst.security_groups, "ingress", src.ip, port, protocol, src.security_groups
            )
            if hit is None:
                raise _Blocked(
                    f"no ingress rule in {dst.security_groups} allows {protocol}/{port} from {src.ip}"
                )
            path.append(hit)
        path.append(f"{destination} ({dst_ip}, {dst_net.name})")
        verdict.reachable = True
    except _Blocked as b:
        verdict.blocked_by = b.rule
    return verdict


# ----------------------------------------------------------------------------- hub design + intent
def build_hub_route_tables(
    topo: Topology,
    segment_cidrs: Mapping[str, list[str]] | None = None,
    *,
    inspection: str | None = None,
    east_west: bool = False,
) -> None:
    """Fill ``topo.tgw_route_tables`` from attachment segments, exactly as the network-hub module does."""
    matrix = PROPAGATE_TO_EAST_WEST if inspection and east_west else PROPAGATE_TO
    tables = {name: RouteTable(name) for name in HUB_TABLES}
    for att in topo.attachments.values():
        att.route_table = ASSOCIATE_WITH[att.segment]
        for rt in matrix[att.segment]:
            for cidr in topo.networks[att.network].cidrs:
                tables[rt].routes.append(Route(cidr, f"attachment:{att.name}", "propagated"))
    if inspection:
        for rt in ("prod", "nonprod", "shared") if east_west else ("prod", "nonprod"):
            tables[rt].routes.append(Route("0.0.0.0/0", f"attachment:{inspection}"))
    cidrs = segment_cidrs or {}
    for here, other in (("prod", "nonprod"), ("nonprod", "prod")):
        tables[here].routes += [Route(c, "blackhole") for c in cidrs.get(other, [])]
    topo.tgw_route_tables = tables


def _vpc(name: str, cidr: str, segment: str, *, onprem: bool = False) -> tuple[Network, RouteTable]:
    rt_name = f"{name}-private"
    if onprem:
        routes = [Route(cidr, "local"), Route("0.0.0.0/0", "tgw")]
    else:
        routes = [Route(cidr, "local"), Route("10.0.0.0/8", "tgw"), Route("172.16.0.0/12", "tgw")]
        routes.append(Route("0.0.0.0/0", "tgw"))
    net = Network(name, [cidr], segment, [Subnet(f"{name}-private", cidr, rt_name)], attachment=name)
    if onprem:
        net.kind = "onprem"
    return net, RouteTable(rt_name, routes)


def sample_topology(*, inspection: bool = False, east_west: bool = False) -> Topology:
    """The us-east-1 hub from ``sample_spec`` / live/aws/network: prod, nonprod, shared, on-prem (DX)."""
    topo = Topology()
    layout = [
        ("prod-payments", "10.16.0.0/18", "prod", False),
        ("nonprod-payments", "10.20.0.0/18", "nonprod", False),
        ("shared-services", "10.24.0.0/18", "shared", False),
        ("onprem", "172.16.0.0/12", "hybrid", True),
    ]
    for name, cidr, segment, onprem in layout:
        net, rt = _vpc(name, cidr, segment, onprem=onprem)
        topo.networks[name] = net
        topo.route_tables[rt.name] = rt
        topo.attachments[name] = Attachment(name, name, segment, segment)
    if inspection:
        net = Network(
            "inspection", ["10.24.64.0/18"], "inspection", attachment="inspection", kind="inspection"
        )
        net.internet_egress = True
        topo.networks["inspection"] = net
        topo.attachments["inspection"] = Attachment(
            "inspection",
            "inspection",
            "inspection",
            "inspection",
            appliance_mode=True,
            firewall="network-firewall",
        )
        topo.firewalls["network-firewall"] = Firewall(
            "network-firewall",
            rules=[
                FirewallRule("deny", "10.16.0.0/14", "10.20.0.0/14", name="prod-to-nonprod"),
                FirewallRule("deny", "10.20.0.0/14", "10.16.0.0/14", name="nonprod-to-prod"),
                FirewallRule("allow", "10.0.0.0/8", "0.0.0.0/0", name="org-egress"),
                FirewallRule("allow", "172.16.0.0/12", "10.0.0.0/8", name="onprem-to-aws"),
            ],
        )
    build_hub_route_tables(
        topo,
        {"prod": ["10.16.0.0/14"], "nonprod": ["10.20.0.0/14"]},
        inspection="inspection" if inspection else None,
        east_west=east_west,
    )
    org = ("10.0.0.0/8", "172.16.0.0/12")
    app = SecurityGroup(
        "app",
        ingress=[Rule("tcp", 443, 443, org, description="HTTPS from the org and on-prem")],
        egress=[Rule("-1", cidrs=("0.0.0.0/0",))],
    )
    tools = SecurityGroup(
        "shared-tools",
        ingress=[Rule("tcp", 443, 443, org), Rule("udp", 53, 53, org), Rule("tcp", 53, 53, org)],
        egress=[Rule("-1", cidrs=("0.0.0.0/0",))],
    )
    topo.security_groups = {"app": app, "shared-tools": tools}
    topo.endpoints = {
        "prod-app": Endpoint("prod-app", "10.16.0.10", "prod-payments", ["app"]),
        "nonprod-app": Endpoint("nonprod-app", "10.20.0.10", "nonprod-payments", ["app"]),
        "shared-tools": Endpoint("shared-tools", "10.24.0.10", "shared-services", ["shared-tools"]),
        "onprem-host": Endpoint("onprem-host", "172.16.0.10", "onprem"),
    }
    return topo


@dataclass(frozen=True)
class Intent:
    source: str
    destination: str
    port: int
    expected: bool
    protocol: str = "tcp"
    why: str = ""


DEFAULT_INTENTS: tuple[Intent, ...] = (
    Intent("prod-app", "nonprod-app", 443, False, why="prod must not reach nonprod"),
    Intent("nonprod-app", "prod-app", 443, False, why="nonprod must not reach prod"),
    Intent("prod-app", "shared-tools", 443, True, why="prod uses shared services"),
    Intent("nonprod-app", "shared-tools", 443, True, why="nonprod uses shared services"),
    Intent("prod-app", "shared-tools", 53, True, protocol="udp", why="DNS via shared resolver"),
    Intent("onprem-host", "prod-app", 443, True, why="on-prem reaches prod over Direct Connect"),
)


def verify_segmentation(topo: Topology, intents: Iterable[Intent] = DEFAULT_INTENTS) -> dict[str, Any]:
    """Check every intent; ``passed`` is True only if every expected allow/deny holds."""
    results = []
    for intent in intents:
        v = can_reach(topo, intent.source, intent.destination, intent.port, intent.protocol)
        results.append(
            {
                "flow": f"{intent.source} -> {intent.destination} {intent.protocol}/{intent.port}",
                "expected": "allow" if intent.expected else "deny",
                "actual": "allow" if v.reachable else "deny",
                "ok": v.reachable == intent.expected,
                "why": intent.why,
                "blocked_by": v.blocked_by,
            }
        )
    return {"passed": all(r["ok"] for r in results), "results": results}


def reachability_matrix(topo: Topology, port: int, protocol: str = "tcp") -> dict[str, dict[str, bool]]:
    """Endpoint x endpoint reachability on one port (the segmentation picture at a glance)."""
    names = list(topo.endpoints)
    return {a: {b: can_reach(topo, a, b, port, protocol).reachable for b in names if b != a} for a in names}


def topology_from_dict(data: Mapping[str, Any]) -> Topology:
    """Inverse of ``Topology.to_dict`` (load a topology exported to JSON/YAML)."""

    def rules(raw: Iterable[Mapping[str, Any]]) -> list[Rule]:
        return [
            Rule(**{**r, "cidrs": tuple(r.get("cidrs", ())), "groups": tuple(r.get("groups", ()))})
            for r in raw
        ]

    def tables(raw: Mapping[str, Any]) -> dict[str, RouteTable]:
        return {k: RouteTable(v["name"], [Route(**r) for r in v.get("routes", [])]) for k, v in raw.items()}

    return Topology(
        networks={
            k: Network(**{**v, "subnets": [Subnet(**s) for s in v.get("subnets", [])]})
            for k, v in data.get("networks", {}).items()
        },
        route_tables=tables(data.get("route_tables", {})),
        tgw_route_tables=tables(data.get("tgw_route_tables", {})),
        attachments={k: Attachment(**v) for k, v in data.get("attachments", {}).items()},
        security_groups={
            k: SecurityGroup(v["name"], rules(v.get("ingress", [])), rules(v.get("egress", [])))
            for k, v in data.get("security_groups", {}).items()
        },
        firewalls={
            k: Firewall(
                v["name"], [FirewallRule(**r) for r in v.get("rules", [])], v.get("default_action", "deny")
            )
            for k, v in data.get("firewalls", {}).items()
        },
        endpoints={k: Endpoint(**v) for k, v in data.get("endpoints", {}).items()},
    )
