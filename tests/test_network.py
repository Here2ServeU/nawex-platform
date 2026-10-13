"""Enterprise networking: IPAM planner, overlap detection, reachability and segmentation, Terraform/OPA artifacts."""

from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import re
from pathlib import Path

import pytest

from golden.network import (
    AllocationError,
    Intent,
    Reservation,
    Route,
    Rule,
    allocate,
    build_hub_route_tables,
    can_reach,
    find_free,
    overlaps,
    plan_addresses,
    reachability_matrix,
    sample_spec,
    sample_topology,
    topology_from_dict,
    verify_segmentation,
)
from golden.network.cli import register
from golden.network.reachability import ASSOCIATE_WITH, PROPAGATE_TO, PROPAGATE_TO_EAST_WEST

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "deploy" / "terraform" / "modules"


# ----------------------------------------------------------------------------- IPAM planner
@pytest.fixture(scope="module")
def plan():
    return plan_addresses(sample_spec())


def test_allocate_skips_taken_blocks():
    assert str(allocate("10.0.0.0/16", 24, ["10.0.0.0/24", "10.0.1.0/25"])) == "10.0.2.0/24"


def test_allocate_raises_when_exhausted():
    with pytest.raises(AllocationError):
        allocate("10.0.0.0/24", 25, ["10.0.0.0/25", "10.0.0.128/25"])


def test_plan_is_deterministic(plan):
    assert plan_addresses(sample_spec()).to_dict() == plan.to_dict()


def test_no_overlaps_and_reserved_ranges_avoided(plan):
    assert overlaps(plan.allocations()) == []
    on_prem = ipaddress.ip_network("10.0.0.0/12")
    for region in plan.regions:
        assert not ipaddress.ip_network(region.cidr).overlaps(on_prem)
    assert plan.regions[0].cidr == "10.16.0.0/12"  # 10.0.0.0/12 is the on-prem reservation


def test_hierarchy_nests(plan):
    for region in plan.regions:
        r = ipaddress.IPv4Network(region.cidr)
        for env in region.environments:
            e = ipaddress.IPv4Network(env.cidr)
            assert e.subnet_of(r)
            for vpc in env.vpcs:
                v = ipaddress.IPv4Network(vpc.cidr)
                assert v.subnet_of(e)
                for s in vpc.subnets:
                    assert ipaddress.IPv4Network(s.cidr).subnet_of(v)


def test_subnet_tiers_per_az(plan):
    vpc = plan.vpcs()[0]
    assert {t: len(vpc.tier(t)) for t in ("public", "private", "data", "tgw")} == {
        "public": 3,
        "private": 3,
        "data": 3,
        "tgw": 3,
    }
    assert all(ipaddress.ip_network(c).prefixlen == 21 for c in vpc.tier("private"))
    assert vpc.tier("private")[0] == "10.16.0.0/21"  # largest tier allocated first


def test_appending_a_vpc_keeps_existing_allocations(plan):
    spec = sample_spec()
    spec["regions"]["us-east-1"]["environments"]["prod"]["vpcs"].append("analytics")
    spec["regions"]["eu-west-1"] = {"environments": {"prod": {"vpcs": ["payments"]}}}
    bigger = {v.key: v.cidr for v in plan_addresses(spec).vpcs()}
    assert all(bigger[v.key] == v.cidr for v in plan.vpcs())
    assert "us-east-1/prod/analytics" in bigger and "eu-west-1/prod/payments" in bigger


def test_ipv6_56_per_vpc_64_per_subnet(plan):
    vpcs = plan.vpcs()
    v6 = [ipaddress.ip_network(v.ipv6_cidr) for v in vpcs]
    assert all(n.prefixlen == 56 for n in v6) and len(set(v6)) == len(v6)
    vpc = vpcs[0]
    assert [s.ipv6_netnum for s in vpc.subnets] == list(range(len(vpc.subnets)))
    for s in vpc.subnets:
        net = ipaddress.IPv6Network(s.ipv6_cidr)
        assert net.prefixlen == 64 and net.subnet_of(ipaddress.IPv6Network(vpc.ipv6_cidr))


def test_tfvars_output_feeds_network_hub(plan):
    tfvars = plan.to_tfvars()
    assert tfvars["segment_cidrs"]["prod"] == ["10.16.0.0/14", "10.32.0.0/14"]
    assert set(tfvars["segment_cidrs"]) == {"prod", "nonprod", "shared"}
    vpc = tfvars["vpcs"]["us-east-1-prod-payments"]
    assert vpc["account"] == "555555555555" and len(vpc["subnets"]["private"]) == 3
    json.dumps(tfvars)  # must be serializable for *.tfvars.json


def test_utilization_report(plan):
    rows = {r["scope"]: r for r in plan.utilization()}
    top = rows["supernet"]
    assert top["capacity"] == 2**24 and top["allocated"] + top["free"] == top["capacity"]
    assert rows["region:us-east-1"]["utilization_pct"] == 75.0  # 3 of 4 environment /14s
    assert 0 < rows["vpc:us-east-1/prod/payments"]["utilization_pct"] < 100


def test_invalid_prefix_nesting_rejected():
    spec = sample_spec() | {"region_prefix": 16, "environment_prefix": 14}
    with pytest.raises(ValueError, match="nest"):
        plan_addresses(spec)


# ----------------------------------------------------------------------------- overlap detection (M&A / hybrid)
def test_overlap_detection_classifies_pairs():
    found = overlaps(
        [
            {"cidr": "10.0.0.0/16", "owner": "us"},
            {"cidr": "10.0.42.0/24", "owner": "acquired-co"},
            {"cidr": "10.0.0.0/16", "owner": "partner"},
            {"cidr": "192.168.0.0/16", "owner": "branch"},
            {"cidr": "2001:db8::/48", "owner": "v6-a"},
            {"cidr": "2001:db8:0:1::/64", "owner": "v6-b"},
        ]
    )
    pairs = {(o.a.owner, o.b.owner, o.kind) for o in found}
    assert pairs == {
        ("us", "partner", "duplicate"),
        ("us", "acquired-co", "contains"),
        ("partner", "acquired-co", "contains"),
        ("v6-a", "v6-b", "contains"),
    }


def test_disjoint_inventory_has_no_overlaps():
    assert overlaps([Reservation("10.0.0.0/24", "a"), Reservation("10.0.1.0/24", "b")]) == []


def test_find_free_suggests_non_colliding_blocks():
    taken = ["10.0.0.0/16", "10.1.0.0/16"]
    free = find_free("10.0.0.0/8", 16, taken, count=2)
    assert free == ["10.2.0.0/16", "10.3.0.0/16"]


# ----------------------------------------------------------------------------- reachability
@pytest.fixture
def topo():
    return sample_topology()


def test_prod_reaches_shared_with_full_path(topo):
    v = can_reach(topo, "prod-app", "shared-tools", 443)
    assert v.reachable and v.blocked_by is None
    assert any(h.startswith("tgw-rt prod: 10.24.0.0/18 -> shared-services") for h in v.path)
    assert any(h.startswith("return:") for h in v.path)


def test_prod_to_nonprod_blocked_by_blackhole(topo):
    v = can_reach(topo, "prod-app", "nonprod-app", 443)
    assert not v.reachable and v.blocked_by == "tgw route table prod: blackhole 10.20.0.0/14"


def test_without_blackholes_still_no_route(topo):
    build_hub_route_tables(topo, segment_cidrs=None)
    v = can_reach(topo, "prod-app", "nonprod-app", 443)
    assert not v.reachable and "no route" in (v.blocked_by or "")


def test_security_group_blocks_port(topo):
    v = can_reach(topo, "prod-app", "shared-tools", 22)
    assert not v.reachable and "no ingress rule" in (v.blocked_by or "")


def test_egress_rule_blocks(topo):
    topo.security_groups["app"].egress = [Rule("tcp", 443, 443, ("10.24.0.0/18",))]
    assert can_reach(topo, "prod-app", "shared-tools", 443).reachable
    assert "no egress rule" in (can_reach(topo, "prod-app", "onprem-host", 443).blocked_by or "")


def test_security_group_reference_as_source(topo):
    topo.security_groups["shared-tools"].ingress = [Rule("tcp", 8443, 8443, groups=("app",))]
    assert can_reach(topo, "prod-app", "shared-tools", 8443).reachable
    assert not can_reach(topo, "onprem-host", "shared-tools", 8443).reachable


def test_missing_return_route_detected(topo):
    rt = topo.route_tables["shared-services-private"]
    rt.routes = [r for r in rt.routes if r.destination == "10.24.0.0/18"]  # only local
    v = can_reach(topo, "prod-app", "shared-tools", 443)
    assert not v.reachable and "no route to 10.16.0.10" in (v.blocked_by or "")


def test_hybrid_onprem_reaches_both_segments(topo):
    assert can_reach(topo, "onprem-host", "prod-app", 443).reachable
    assert can_reach(topo, "onprem-host", "nonprod-app", 443).reachable


def test_no_internet_egress_without_inspection(topo):
    v = can_reach(topo, "prod-app", "8.8.8.8", 443)
    assert not v.reachable and "no route to 8.8.8.8" in (v.blocked_by or "")


def test_internet_egress_through_inspection():
    v = can_reach(sample_topology(inspection=True), "prod-app", "8.8.8.8", 443)
    assert v.reachable
    assert "firewall network-firewall: allow (org-egress)" in v.path


def test_east_west_inspection_symmetric_and_firewall_enforced():
    topo = sample_topology(inspection=True, east_west=True)
    v = can_reach(topo, "prod-app", "shared-tools", 443)
    assert v.reachable and any("firewall" in h for h in v.path)
    # Firewall policy is the second line of defense: drop the blackholes, the firewall still denies.
    build_hub_route_tables(topo, None, inspection="inspection", east_west=True)
    blocked = can_reach(topo, "prod-app", "nonprod-app", 443)
    assert not blocked.reachable and blocked.blocked_by == "firewall network-firewall: prod-to-nonprod"


def test_asymmetric_routing_around_firewall_detected():
    topo = sample_topology(inspection=True, east_west=True)
    # Misconfiguration: prod propagated straight into the shared table, so replies skip the firewall.
    topo.tgw_route_tables["shared"].routes.append(
        Route("10.16.0.0/18", "attachment:prod-payments", "propagated")
    )
    v = can_reach(topo, "prod-app", "shared-tools", 443)
    assert not v.reachable and "asymmetric routing" in (v.blocked_by or "")


def test_static_route_beats_propagated_at_equal_length(topo):
    rt = topo.tgw_route_tables["prod"]
    rt.routes.append(Route("10.24.0.0/18", "blackhole"))
    assert rt.lookup("10.24.0.10") == Route("10.24.0.0/18", "blackhole")


# ----------------------------------------------------------------------------- segmentation intent
@pytest.mark.parametrize(
    "kwargs", [{}, {"inspection": True}, {"inspection": True, "east_west": True}], ids=["plain", "ns", "ew"]
)
def test_segmentation_intent_holds_for_every_hub_mode(kwargs):
    result = verify_segmentation(sample_topology(**kwargs))
    assert result["passed"], [r for r in result["results"] if not r["ok"]]


def test_segmentation_violation_is_reported(topo):
    # Classic mistake: nonprod attachment propagated into the prod table, blackholes forgotten.
    build_hub_route_tables(topo, None)
    topo.tgw_route_tables["prod"].routes.append(
        Route("10.20.0.0/18", "attachment:nonprod-payments", "propagated")
    )
    topo.tgw_route_tables["nonprod"].routes.append(
        Route("10.16.0.0/18", "attachment:prod-payments", "propagated")
    )
    result = verify_segmentation(topo)
    assert not result["passed"]
    bad = [r["flow"] for r in result["results"] if not r["ok"]]
    assert "prod-app -> nonprod-app tcp/443" in bad


def test_custom_intents_and_matrix(topo):
    result = verify_segmentation(topo, [Intent("shared-tools", "prod-app", 443, True)])
    assert result["passed"]
    matrix = reachability_matrix(topo, 443)
    assert matrix["prod-app"]["nonprod-app"] is False and matrix["prod-app"]["shared-tools"] is True


def test_topology_round_trips_through_json(topo):
    clone = topology_from_dict(json.loads(json.dumps(topo.to_dict())))
    assert verify_segmentation(clone) == verify_segmentation(topo)


def test_python_model_mirrors_terraform_module():
    main = (MODULES / "aws" / "network-hub" / "main.tf").read_text(encoding="utf-8")

    def tf_map(east_west: bool) -> dict[str, list[str]]:
        out = {}
        for seg, a, b in re.findall(
            r"^\s+(\w+)\s+= local\.east_west \? (\[[^\]]*\]) : (\[[^\]]*\])", main, re.M
        ):
            out[seg] = json.loads(a if east_west else b)
        out["inspection"] = []
        return out

    assert tf_map(False) == PROPAGATE_TO
    assert tf_map(True) == PROPAGATE_TO_EAST_WEST
    block = main.split("associate_with = {", 1)[1].split("}", 1)[0]
    assert dict(re.findall(r'(\w+)\s+= "(\w+)"', block)) == ASSOCIATE_WITH


# ----------------------------------------------------------------------------- CLI + artifacts
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="golden")
    register(p.add_subparsers(dest="command", required=True))
    return p


def test_cli_verify_reach_and_plan(tmp_path, capsys):
    args = _parser().parse_args(["network", "verify", "--inspection"])
    assert args.func(args) == 0
    args = _parser().parse_args(
        ["network", "reach", "--src", "prod-app", "--dst", "nonprod-app", "--port", "443"]
    )
    assert args.func(args) == 1
    out = tmp_path / "net.tfvars.json"
    args = _parser().parse_args(["network", "plan", "--format", "utilization", "--tfvars", str(out)])
    assert args.func(args) == 0
    assert "segment_cidrs" in json.loads(out.read_text())
    capsys.readouterr()


def test_cli_overlaps_suggests_free_blocks(tmp_path, capsys):
    inv = tmp_path / "inv.json"
    inv.write_text(
        json.dumps([{"cidr": "10.0.0.0/16", "owner": "us"}, {"cidr": "10.0.0.0/16", "owner": "acq"}])
    )
    args = _parser().parse_args(["network", "overlaps", "--input", str(inv), "--supernet", "10.0.0.0/8"])
    assert args.func(args) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["suggested_free"] == {"10.0.0.0/16": ["10.1.0.0/16"]}


@pytest.mark.parametrize(
    "module",
    ["aws/network-hub", "aws/vpc-endpoints", "azure/hub-spoke", "gcp/shared-vpc"],
)
def test_terraform_modules_are_documented(module):
    d = MODULES / module
    for f in ("main.tf", "variables.tf", "outputs.tf", "versions.tf"):
        assert (d / f).is_file(), f
    text = (d / "variables.tf").read_text() + (d / "outputs.tf").read_text()
    blocks = re.findall(r'^(?:variable|output) "[^"]+" \{', text, re.M)
    assert len(blocks) == len(re.findall(r"^\s+description\s+=", text, re.M))
    assert (d / "main.tf").read_text().startswith("# ---")


def test_vpc_endpoint_policy_is_org_scoped():
    main = (MODULES / "aws" / "vpc-endpoints" / "main.tf").read_text()
    assert '"aws:PrincipalOrgID" = var.organization_id' in main
    defaults = (MODULES / "aws" / "vpc-endpoints" / "variables.tf").read_text()
    for svc in (
        "ecr.api",
        "ecr.dkr",
        "sts",
        "logs",
        "ssm",
        "ssmmessages",
        "ec2messages",
        "secretsmanager",
        "kms",
    ):
        assert f'"{svc}"' in defaults


def test_sample_spec_is_not_shared_state():
    a = sample_spec()
    b = copy.deepcopy(a)
    a["regions"]["us-east-1"]["environments"]["prod"]["vpcs"].append("x")
    assert sample_spec() == b
