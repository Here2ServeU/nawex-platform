"""``golden network`` subcommands, kept in this package so ``golden/cli.py`` only has to register them.

Wiring (in ``golden.cli.build_parser``)::

    from golden.network.cli import register as register_network
    register_network(sub)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def _load(path: str) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text) if path.endswith(".json") else yaml.safe_load(text)


def cmd_plan(args: argparse.Namespace) -> int:
    from golden.network import plan_addresses, sample_spec

    plan = plan_addresses(_load(args.spec) if args.spec else sample_spec())
    if args.tfvars:
        Path(args.tfvars).write_text(json.dumps(plan.to_tfvars(), indent=2) + "\n", encoding="utf-8")
    if args.format == "tfvars":
        _print(plan.to_tfvars())
    elif args.format == "utilization":
        _print(plan.utilization())
    else:
        _print(plan.to_dict())
    return 0


def cmd_overlaps(args: argparse.Namespace) -> int:
    from golden.network import find_free, overlaps

    entries = _load(args.input)
    found = overlaps(entries)
    result: dict[str, Any] = {"entries": len(entries), "overlaps": [o.to_dict() for o in found]}
    if args.supernet and found:
        taken = [e["cidr"] for e in entries]
        result["suggested_free"] = {
            o.b.cidr: find_free(args.supernet, o.b.network.prefixlen, taken) for o in found
        }
    _print(result)
    return 1 if found else 0


def cmd_reach(args: argparse.Namespace) -> int:
    from golden.network import can_reach, sample_topology, topology_from_dict

    topo = (
        topology_from_dict(_load(args.topology))
        if args.topology
        else sample_topology(inspection=args.inspection, east_west=args.east_west)
    )
    verdict = can_reach(topo, args.src, args.dst, args.port, args.protocol)
    _print(verdict.to_dict())
    return 0 if verdict.reachable else 1


def cmd_verify(args: argparse.Namespace) -> int:
    from golden.network import sample_topology, topology_from_dict, verify_segmentation

    topo = (
        topology_from_dict(_load(args.topology))
        if args.topology
        else sample_topology(inspection=args.inspection, east_west=args.east_west)
    )
    result = verify_segmentation(topo)
    _print(result)
    return 0 if result["passed"] else 1


def register(sub: Any) -> None:
    """Add ``golden network {plan,overlaps,reach,verify}`` to the top-level subparsers."""
    net = sub.add_parser(
        "network", help="enterprise networking (IPAM plan, overlaps, reachability, segmentation)"
    ).add_subparsers(dest="network_cmd", required=True)

    s = net.add_parser("plan", help="allocate region/env/VPC/subnet CIDRs (+ IPv6) from an address spec")
    s.add_argument("--spec", help="address spec YAML/JSON (default: built-in sample)")
    s.add_argument("--format", choices=["plan", "tfvars", "utilization"], default="plan")
    s.add_argument("--tfvars", help="also write the Terraform values to this .tfvars.json file")
    s.set_defaults(func=cmd_plan)

    s = net.add_parser("overlaps", help="find colliding CIDRs in an inventory ([{cidr, owner}], YAML/JSON)")
    s.add_argument("--input", required=True)
    s.add_argument("--supernet", help="suggest free replacement blocks from this supernet")
    s.set_defaults(func=cmd_overlaps)

    for name, func, helptext in (
        ("reach", cmd_reach, "can SRC reach DST on PORT? hop path or blocking rule"),
        ("verify", cmd_verify, "verify segmentation intent (prod<->nonprod denied, both -> shared)"),
    ):
        s = net.add_parser(name, help=helptext)
        s.add_argument("--topology", help="topology YAML/JSON (default: the network-hub sample)")
        s.add_argument("--inspection", action="store_true", help="sample with an inspection VPC")
        s.add_argument("--east-west", action="store_true", help="sample with east-west inspection")
        if name == "reach":
            s.add_argument("--src", required=True)
            s.add_argument("--dst", required=True, help="endpoint name or IP")
            s.add_argument("--port", type=int, required=True)
            s.add_argument("--protocol", default="tcp", choices=["tcp", "udp", "icmp"])
        s.set_defaults(func=func)
