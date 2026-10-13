# IPv6 / dual-stack on the EKS module (documented change)

This is a **proposed change** to [`deploy/terraform/modules/aws/eks`](../../deploy/terraform/modules/aws/eks/main.tf).
The module has not been changed. The module owner applies the change through the normal review process. The
background is in [README.md §10](./README.md#10-ipv6-and-dual-stack).

## Why

* **Pod IP exhaustion.** The AWS VPC CNI gives every pod a VPC IP. A /21 private subnet holds about 2,000
  pods per AZ, and warm-pool pre-allocation uses them up faster than that. In IPv6 mode each node gets a /80 prefix, so pod
  density is limited by `max-pods`, not by the address space.
* **Overlapping RFC 1918 ranges** after a merger or hybrid connection matter less, because pod-to-pod and pod-to-AWS traffic uses
  globally unique IPv6.
* **No NAT for IPv6 egress.** An egress-only internet gateway has no hourly or per-GB processing charge (standard data transfer still applies). A NAT gateway has both.

## Constraints to know first

1. **The cluster IP family can't be changed after creation.** `cluster_ip_family = "ipv6"` creates a
   new cluster. Migrate with a blue/green cluster: new cluster, move workloads with GitOps, switch DNS or the
   ALB target groups, then retire the old cluster. Plan it like a [cutover](../../ops/runbooks/migration/cutover.md).
2. An EKS IPv6 cluster still needs a **dual-stack VPC**. Nodes keep IPv4. Pods are IPv6-only, and the
   VPC CNI translates their traffic to IPv4 destinations through the node's IPv4 address (egress only).
3. The **Kubernetes service CIDR** is IPv6, chosen by EKS. You can't set it.
4. Every add-on and workload has to listen on `::`. Check the ingress controller, metrics-server, Prometheus, the service mesh
   proxies, and application bind addresses (`0.0.0.0` only binds IPv4).
5. Security groups and NetworkPolicies need IPv6 rules. Treat `::/0` like `0.0.0.0/0`.
   [`network.rego`](../../security/policies/opa/network.rego) denies admin and all-port ingress from both.

## The change

### 1. VPC: dual-stack subnets (`module "vpc"`, terraform-aws-modules/vpc ~> 5.7)

```hcl
module "vpc" {
  # ... existing arguments ...

  enable_ipv6            = var.enable_ipv6
  create_egress_only_igw = var.enable_ipv6

  # /64 index inside the VPC's /56 (or pass the ipv6_netnums emitted by `golden network plan`).
  public_subnet_ipv6_prefixes  = var.enable_ipv6 ? [for i in range(var.az_count) : i] : []
  private_subnet_ipv6_prefixes = var.enable_ipv6 ? [for i in range(var.az_count) : i + 8] : []

  public_subnet_assign_ipv6_address_on_creation  = var.enable_ipv6
  private_subnet_assign_ipv6_address_on_creation = var.enable_ipv6

  # Flow logs: network.rego warns on any aws_vpc without one.
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
}
```

Use the Amazon-provided /56 (the default) or an IPAM pool (`ipv6_ipam_pool_id`) when the
organization plans IPv6 centrally. The planner's `ipv6_pool` stands in for that pool. The flow-log IAM role has to carry
the permission boundary (the enforce-permission-boundary SCP, enforced by `aws-iam.rego`). Set `vpc_flow_log_permissions_boundary` to
`var.permissions_boundary_arn`.

### 2. Cluster: IPv6 family (`module "eks"`, terraform-aws-modules/eks ~> 20.8)

```hcl
module "eks" {
  # ... existing arguments ...

  cluster_ip_family          = var.enable_ipv6 ? "ipv6" : "ipv4"
  create_cni_ipv6_iam_policy = var.enable_ipv6
}
```

`create_cni_ipv6_iam_policy` creates the IAM policy the VPC CNI needs to assign IPv6 prefixes. The `vpc-cni`
add-on already in `cluster_addons` detects the IPv6 cluster family. Prefix delegation is always on in IPv6 mode.

### 3. Variable

```hcl
variable "enable_ipv6" {
  description = "Dual-stack VPC and an IPv6 EKS cluster. Changing this on an existing cluster REPLACES it."
  type        = bool
  default     = false
}
```

### 4. Load balancers and ingress

* ALB (Ingress): annotation `alb.ingress.kubernetes.io/ip-address-type: dualstack`. Target type
  must be `ip` for IPv6 pods.
* NLB (Service): `service.beta.kubernetes.io/aws-load-balancer-ip-address-type: dualstack`.
* Public subnets need IPv6 CIDRs (step 1) before a dual-stack load balancer can be created.

### 5. The rest of the network

* Hub: `enable_ipv6 = true` on [`live/aws/network`](../../deploy/terraform/live/aws/network/main.tf) turns on IPv6 for
  the hub-owned TGW attachments, adds `::/0` inspection routes and makes the resolver endpoints dual-stack. Spoke attachments
  need `ipv6_support = "enable"` on their side. Add the IPv6 summaries to `segment_cidrs` so the
  prod/nonprod blackholes cover IPv6 too.
* Endpoints: `enable_ipv6 = true` on [`vpc-endpoints`](../../deploy/terraform/modules/aws/vpc-endpoints/main.tf)
  creates dual-stack interface endpoints.
* IPv6-only subnets (not part of this change) would also need DNS64 and NAT64 (`64:ff9b::/96` → NAT gateway) to reach
  IPv4-only services.

## Rollout

1. Dual-stack the VPC (step 1). This is non-disruptive: existing IPv4 resources are unaffected.
2. Add IPv6 rules to security groups and NetworkPolicies, then run `opa test` and `golden network verify`.
3. Create the new IPv6 cluster next to the old one (step 2). Deploy the add-ons and check that they listen on `::`.
4. Move workloads with GitOps. Shift traffic with weighted DNS or ALB target groups.
5. Retire the IPv4 cluster.

## Verification

```bash
kubectl get pods -o wide            # pod IPs are IPv6
kubectl run t --rm -it --image=busybox -- wget -qO- http://ipv4.example.com   # IPv4 egress via node
aws ec2 describe-subnets --filters Name=vpc-id,Values=<vpc> \
  --query 'Subnets[].Ipv6CidrBlockAssociationSet[].Ipv6CidrBlock'
```
