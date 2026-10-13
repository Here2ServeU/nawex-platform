# Enterprise networking: fundamentals to landing zone

This guide goes from IP addressing basics to a multi-account, multi-cloud enterprise network. Each
concept points to the file in this repo that implements it, so you can read the idea and then the code.

| Layer | Implementation |
|---|---|
| Address plan (IPAM) | [`src/golden/network/cidr.py`](../../src/golden/network/cidr.py): `golden network plan`, `golden network overlaps` |
| AWS hub: Transit Gateway, segments, hybrid DNS, Direct Connect | [`modules/aws/network-hub`](../../deploy/terraform/modules/aws/network-hub/main.tf) · root [`live/aws/network`](../../deploy/terraform/live/aws/network/main.tf) |
| AWS PrivateLink + data perimeter | [`modules/aws/vpc-endpoints`](../../deploy/terraform/modules/aws/vpc-endpoints/main.tf) |
| Azure hub-spoke + Azure Firewall | [`modules/azure/hub-spoke`](../../deploy/terraform/modules/azure/hub-spoke/main.tf) |
| GCP Shared VPC + Cloud NAT + PSC | [`modules/gcp/shared-vpc`](../../deploy/terraform/modules/gcp/shared-vpc/main.tf) |
| Reachability / segmentation proof | [`src/golden/network/reachability.py`](../../src/golden/network/reachability.py): `golden network reach`, `golden network verify` |
| Plan-time guardrails | [`security/policies/opa/network.rego`](../../security/policies/opa/network.rego) (+ [`_test`](../../security/policies/opa/network_test.rego)) |
| Kubernetes network policy and mesh | [`deploy/helm/golden/templates/networkpolicy.yaml`](../../deploy/helm/golden/templates/networkpolicy.yaml) · [`deploy/helm/service-mesh`](../../deploy/helm/service-mesh) |
| IPv6 on EKS (documented change) | [`ipv6-and-eks.md`](./ipv6-and-eks.md) |

Tests: [`tests/test_network.py`](../../tests/test_network.py). They cover the planner, overlap detection,
reachability, the segmentation intent in every hub mode, and a check that the Python model's
propagation matrix matches the Terraform module's matrix.

---

## 1. IP addresses, CIDR and subnets

An IPv4 address is 32 bits. **CIDR** notation `10.16.0.0/14` means "the first 14 bits are the
network, the remaining 18 bits are hosts": 2^18 = 262,144 addresses. A larger prefix length gives a smaller block:

| Prefix | Addresses | Typical use |
|---|---|---|
| /8 | 16.7M | whole-company private supernet (`10.0.0.0/8`) |
| /12 | 1M | one region |
| /14 | 262k | one environment in a region (a routing **segment** summary) |
| /18 | 16k | one VPC / VNet |
| /21 | 2,048 | private (workload / Kubernetes pod) subnet per AZ |
| /24 | 256 | public or data subnet per AZ |
| /28 | 16 | Transit Gateway attachment subnet per AZ |

Some rules you can't get around:

* **RFC 1918** private ranges are `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16`. Every company uses
  them, so after a merger, or once a partner VPN is up, two networks often turn out to use the same ranges. Use
  `100.64.0.0/10` (CGNAT) only deliberately. EKS custom networking uses it for pods.
* Clouds **reserve addresses** in every subnet (AWS reserves 5: network, router, DNS, future, broadcast).
  A /28 has 11 usable addresses, not 16.
* Blocks **nest or are disjoint**. Two CIDRs can't partially overlap, so overlap detection is a
  containment check.
* **Summarization** only works if the hierarchy is clean. When every prod VPC in a region sits inside one
  /14, a single route (or a single blackhole) covers all of them.

### The IPAM planner

`golden network plan` allocates supernet → region → environment → VPC → tier × AZ, taking the first
free aligned block each time ([`cidr.py`](../../src/golden/network/cidr.py)):

```bash
golden network plan                       # sample: 10.0.0.0/8, on-prem 10.0.0.0/12 + partner reserved
golden network plan --format utilization  # capacity / allocated / free at every level
golden network plan --spec net.yaml --format tfvars --tfvars network.auto.tfvars.json
```

Design choices:

* **Deterministic and append-only.** The same spec always gives the same plan. Appending a region, environment or
  VPC never moves an existing one (`test_appending_a_vpc_keeps_existing_allocations`).
* **Reserved ranges are avoided at every level**, not only at the leaves, so a region or environment
  block never contains an on-prem prefix and stays a clean summary route. If it didn't, the nonprod
  blackhole in the prod TGW table would also drop traffic to on-prem. The utilization report shows how much space this uses.
* **Largest tiers are allocated first** inside a VPC to avoid fragmentation.
* The `tfvars` output contains the per-VPC CIDRs and subnet lists, plus `segment_cidrs`. That value is the exact input the
  network hub uses for its prod/nonprod blackholes.

### Mergers and hybrid: overlap detection

```bash
golden network overlaps --input inventory.yaml --supernet 10.0.0.0/8
# inventory: [{cidr: 10.0.0.0/16, owner: us}, {cidr: 10.0.42.0/24, owner: acquired-co}, ...]
```

`overlaps()` sorts the blocks and sweeps them (O(n log n + k)), reporting each colliding pair as a `duplicate` or a
`contains`. With `--supernet` it also suggests a free block of the same size for each conflict. The usual fixes for an
overlap are: re-IP the smaller side (best, but slowest); NAT at the boundary (private NAT gateway, or
NAT on the firewall); or connect only through PrivateLink so the two address spaces never meet. Put
the acquired ranges under `reserved` in the spec so the planner never allocates them.

## 2. Routing

A route table maps destination → next hop, and the **longest prefix match** wins. In a VPC:

* `local`: the VPC CIDR, which is implicit and can't be removed
* `igw` (internet gateway): public subnets. `nat`: private subnets for outbound-only internet
* `tgw`: everything else in the organization and on-prem
* `blackhole`: drop traffic on purpose

A Transit Gateway adds two concepts that cause most TGW incidents:

* **Association**: each attachment is associated with exactly one TGW route table, and the lookup
  for traffic *arriving from* that attachment happens in that table.
* **Propagation**: an attachment can *advertise* its CIDRs into any number of tables.

Routing is checked in both directions. A packet that gets there but has no route back is dropped as surely as one that
can't get there. `reachability.py` follows the return path for that reason (`test_missing_return_route_detected`).
At equal prefix length a TGW **static route beats a propagated one**, which is why the blackholes work.

## 3. NAT and egress

NAT rewrites addresses so that private hosts can make outbound connections, and nothing can initiate a connection in to them.

| Cloud | Egress | Repo |
|---|---|---|
| AWS | NAT gateway per AZ (or one shared), or centralized through the inspection VPC | EKS module VPC; `network-hub` `inspection_enabled` |
| Azure | Azure Firewall with forced tunneling (UDR `0.0.0.0/0 → firewall`) | `hub-spoke` `azurerm_route_table.spoke` |
| GCP | Cloud NAT on a Cloud Router per region | `shared-vpc` `google_compute_router_nat` |

Centralized egress means there is one place to allow-list destinations (`allowed_egress_fqdns` on Azure,
Network Firewall rules on AWS). In the sample hub without an inspection VPC, spokes have **no**
internet path at all (`test_no_internet_egress_without_inspection`). With one, egress goes through the firewall
(`test_internet_egress_through_inspection`).

## 4. DNS

DNS is the part of hybrid networking that most often breaks, so the hub handles it explicitly:

* **AWS Route 53 Resolver** (`network-hub`): the *inbound endpoint* gives on-prem DNS servers IPs to
  forward AWS private zones to (output `resolver_inbound_ips`). The *outbound endpoint* plus **FORWARD
  rules** send `corp.example.com` queries to on-prem. The rules are **shared to the org with RAM**, so each
  spoke account associates them and doesn't need its own endpoints. A security group limits port 53 to
  `dns_client_cidrs`.
* **Private hosted zones / private DNS zones**: names that resolve only inside the network. On Azure
  each `privatelink.*` zone has to be linked to every VNet that resolves it (`hub-spoke` links them to the hub
  and to every spoke). On GCP, a private `googleapis.com` zone points Google APIs at the PSC endpoint.
* **Firewall DNS proxy** (Azure): VNets use the firewall as their DNS server, so FQDN rules see the
  same answers the clients get.

## 5. Topologies: full mesh, hub-and-spoke, transit gateway

| Topology | Connections for n VPCs | Transitive? | When |
|---|---|---|---|
| Full mesh (VPC peering) | n(n-1)/2 | No | a handful of VPCs, lowest latency/cost |
| Hub-and-spoke with peering (Azure) | n | No, so spoke↔spoke goes through the hub firewall | Azure standard |
| Transit Gateway / Cloud WAN (AWS) | n | Yes, controlled by route tables | AWS at scale, multi-account |
| Shared VPC (GCP) | 1 network for many projects | n/a (one VPC) | GCP standard; one host project per environment |

Peering is non-transitive, and on Azure that is the design: when spokes can only reach each other
through the hub, the firewall is the single segmentation point. On AWS the TGW *is* transitive, so
segmentation has to be built with route tables.

## 6. Segmentation (the network-hub design)

[`network-hub`](../../deploy/terraform/modules/aws/network-hub/main.tf) turns off default association
and propagation, so nothing can route until the module places it:

| Segment | Associated with | Propagates into |
|---|---|---|
| prod | prod table | shared, inspection |
| nonprod | nonprod table | shared, inspection |
| shared | shared table | prod, nonprod, shared, inspection |
| hybrid (DX) | shared table | prod, nonprod, shared, inspection |

prod and nonprod never propagate into each other's table, and as **defense in depth** each table also carries
static blackholes for the other's summaries (`segment_cidrs`). That way a stray static route, or the inspection
default route, still can't leak traffic between them.

You can check this without an AWS account:

```bash
golden network verify                          # plain hub
golden network verify --inspection --east-west # centralized east-west inspection
golden network reach --src prod-app --dst nonprod-app --port 443
# -> "blocked_by": "tgw route table prod: blackhole 10.20.0.0/14"
```

`build_hub_route_tables()` uses the same matrix as the Terraform locals, and
`test_python_model_mirrors_terraform_module` fails if the two drift apart.

On **Azure**, segmentation is enforced by the firewall's default deny, since spokes reach each other only through the
UDR to the firewall. On **GCP** the usual pattern is one Shared VPC host project per environment, with VPC
firewall rules and hierarchical firewall policies applied inside it.

## 7. Inspection

`inspection_enabled` attaches an inspection VPC (AWS Network Firewall or Gateway Load Balancer
appliances) in **appliance mode**. Appliance mode keeps both directions of a flow on the same AZ's appliance, and a stateful
firewall needs that: if the reply arrives at a different appliance, it gets dropped.

* **North-south**: prod and nonprod default-route `0.0.0.0/0` to inspection, and egress leaves from the
  inspection VPC.
* **East-west** (`inspect_east_west`): spokes propagate *only* into the inspection table and every
  segment default-routes to it, so prod→shared and the reply both go through the firewall. If one direction
  has a direct route, the routing is asymmetric and the firewall drops the reply. The model detects this
  (`test_asymmetric_routing_around_firewall_detected`).

## 8. Private connectivity to cloud services

| Cloud | Mechanism | Repo |
|---|---|---|
| AWS | **Interface endpoints (PrivateLink)**: ENIs in your subnets with private DNS; **gateway endpoints** for S3/DynamoDB (route table entries, free) | [`vpc-endpoints`](../../deploy/terraform/modules/aws/vpc-endpoints/main.tf) |
| Azure | **Private Endpoints** in `snet-private-endpoints` + `privatelink.*` zones | [`hub-spoke`](../../deploy/terraform/modules/azure/hub-spoke/main.tf) |
| GCP | **Private Service Connect** endpoint for Google APIs (`all-apis` / `vpc-sc`) + Private Google Access on subnets | [`shared-vpc`](../../deploy/terraform/modules/gcp/shared-vpc/main.tf) |

**Data perimeter.** The AWS endpoint policies allow only `aws:PrincipalOrgID = <org>`. That makes them the
*network* side of the perimeter, alongside the identity side (SCPs) and the resource side, which is the
[`data-perimeter` RCP](../../deploy/terraform/modules/aws/org-guardrails/policies/rcp/data-perimeter.json.tftpl).
With all three in place, credentials stolen from a foreign account can't be used through our network path, and our
identities can't write to someone else's bucket through our endpoints. One exception is documented in the S3
policy: ECR image layers are fetched from an AWS-owned bucket.

## 9. Hybrid connectivity and BGP

| | AWS | Azure | GCP |
|---|---|---|---|
| IPsec VPN over the internet | Site-to-Site VPN on the TGW | VPN Gateway in `GatewaySubnet` | HA VPN + Cloud Router |
| Dedicated private circuit | **Direct Connect** → DX gateway → TGW (`direct_connect_enabled`) | **ExpressRoute** gateway in `GatewaySubnet` (`hub_gateway_transit`, spoke `use_remote_gateways`) | **Dedicated/Partner Interconnect** VLAN attachments on the Cloud Router (`router_names` output) |

**BGP basics:**

* Each side has an ASN: TGW `amazon_side_asn`, DX gateway `direct_connect_amazon_side_asn`, Cloud Router
  `router_asn`. Use private ASNs (64512–65534), unique per device.
* Each side advertises prefixes and learns the other side's.
* Advertise **summaries**, not every VPC. On Direct Connect, `direct_connect_allowed_prefixes` is the list
  sent to on-prem, and summaries are the reason the address plan has to be hierarchical.
* Use two circuits in two locations with BGP failover (and BFD) for resilience. Path preference uses AS-path prepending, and the
  more specific prefix always wins.

On Azure, the spoke route tables set BGP route propagation to off, so on-prem routes learned by the gateway can't
skip the firewall.

## 10. IPv6 and dual-stack

IPv6 addresses are 128 bits, with no NAT and no shortage. AWS gives each VPC a **/56**. Each subnet takes a **/64**, the only size
SLAAC supports, which leaves 256 subnets per VPC. The planner allocates a /56 per VPC from `ipv6_pool` (an
IPAM/BYOIP pool) and numbers the /64s in the same tier/AZ order as IPv4. Its `ipv6_netnums` output is what
the VPC module's `*_subnet_ipv6_prefixes` expect. The hub modules accept `enable_ipv6` (TGW
attachments, `::/0` routes, dual-stack resolver and endpoints) and the GCP module builds `IPV4_IPV6` subnets.

Security: with IPv6 every address is globally routable, so the security group is the only boundary. For
outbound-only access use an **egress-only internet gateway**, and treat `::/0` the same as `0.0.0.0/0`.
`network.rego` checks both. For EKS, see [ipv6-and-eks.md](./ipv6-and-eks.md).

## 11. Kubernetes networking

| Concept | What it is | Repo |
|---|---|---|
| **CNI** | Gives pods IPs. AWS VPC CNI gives pods real VPC IPs (size the private /21s for pods). GKE VPC-native uses the `pods`/`services` **secondary ranges** (`shared-vpc` `secondary_ranges`). AKS uses Azure CNI / overlay | EKS module `vpc-cni` addon; [`gke`](../../deploy/terraform/modules/gcp/gke/main.tf) |
| **Services** | Stable virtual IP / DNS name in front of pods (ClusterIP, NodePort, LoadBalancer) | chart `service.yaml` templates |
| **Ingress** | L7 entry point. On AWS, the Load Balancer Controller creates ALBs (IRSA role in the EKS module). Internet-facing ALBs must have WAF (`network.rego` warns) | [`golden` ingress](../../deploy/helm/golden/templates/ingress.yaml) · [Kong gateway chart](../../deploy/helm/kong-gateway) |
| **NetworkPolicy** | L3/L4 allow-lists between pods. Default-deny plus allow by label | [`golden` networkpolicy](../../deploy/helm/golden/templates/networkpolicy.yaml) · [payment-gateway](../../deploy/helm/payment-gateway/templates/networkpolicy.yaml) · [OpenShift policies](../../deploy/openshift/manifests/network-policies.yaml) |
| **Service mesh** | mTLS identity between workloads, L7 traffic policy, retries, canaries | [`deploy/helm/service-mesh`](../../deploy/helm/service-mesh) ([Istio gateway](../../deploy/helm/service-mesh/templates/istio-gateway.yaml), [VirtualService](../../deploy/helm/service-mesh/templates/istio-virtualservice.yaml), [Linkerd ServiceProfile](../../deploy/helm/service-mesh/templates/linkerd-serviceprofile.yaml)) |

Cloud segmentation (TGW tables, SGs, firewall) controls traffic *between* networks. NetworkPolicy and the
mesh control traffic *inside* a cluster. You need both: a flat cluster network inside a perfectly segmented VPC still lets
a compromised pod reach everything else in the cluster.

## 12. Zero trust

Zero trust means the network location of a request grants no access by itself. Every request is
authenticated and authorized. In this repo:

* **Identity per workload**: IRSA / Pod Identity roles (EKS module), mesh mTLS identities.
* **Least-privilege paths**: segment route tables, security groups that reference security groups, NetworkPolicy
  default-deny.
* **No admin ports on the internet**: SSM Session Manager (endpoints `ssm`, `ssmmessages`,
  `ec2messages`), Azure Bastion (`bastion_enabled`), GCP IAP (`35.235.240.0/20` → 22 only). `network.rego`
  denies 22 and 3389 from `0.0.0.0/0` or `::/0` on all three clouds.
* **Private service access**: PrivateLink / Private Endpoints / PSC, with org-scoped endpoint policies.
* **Visibility**: TGW flow logs, VPC/subnet flow logs (GCP `log_config`, warn in `network.rego`), firewall
  and NAT logs, and the logged explicit deny-all on GCP.

The network is one control among several. The identity controls are in
[aws-iam-modernization.md](../modernization/aws-iam-modernization.md).

## 13. Plan-time guardrails (`network.rego`)

```bash
terraform plan -out tf.plan && terraform show -json tf.plan > plan.json
opa eval -d security/policies/opa -i plan.json 'data.golden.network.deny'
opa eval -d security/policies/opa -i plan.json 'data.golden.network.warn'
```

| Rule | Level | Resources |
|---|---|---|
| Ingress from `0.0.0.0/0` / `::/0` / `*` / `Internet` on 22, 3389 or all ports | deny | `aws_security_group`, `aws_security_group_rule`, `aws_vpc_security_group_ingress_rule`, `azurerm_network_security_rule`/`_group`, `google_compute_firewall` |
| Public IP auto-assign on a data-tier subnet (`Tier`/`golden:tier` tag or `-data-`/`-db-` in Name) | deny | `aws_subnet` |
| Public databases | deny | `aws_db_instance`, `aws_rds_cluster_instance`, `google_sql_database_instance` (0.0.0.0/0 authorized network), `azurerm_mssql_server` |
| S3 public access block not fully on | deny | `aws_s3_bucket_public_access_block`, `aws_s3_account_public_access_block` |
| VPC without flow logs / GCP subnet without `log_config` | warn | `aws_vpc`, `google_compute_subnetwork` |
| Internet-facing ALB without a WAF association | warn | `aws_lb` / `aws_alb` |

The flow-log and WAF checks resolve references through the plan's `configuration` section, because IDs created
in the same plan aren't known until apply. They also accept a flow log in the same module whose `vpc_id` is unknown,
which is the pattern `terraform-aws-modules/vpc` uses.
