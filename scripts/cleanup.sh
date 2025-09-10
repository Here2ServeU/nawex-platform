#!/usr/bin/env bash
set -euo pipefail

###############################################
# Force cleanup & delete a VPC and dependencies
###############################################

# -------- Config (edit or pass as envs) -----
REGION="${REGION:-us-east-1}"
VPC_ID="${VPC_ID:-vpc-006568642877085d3}"
IGW_ID="${IGW_ID:-igw-09fdb9b97dd8dd091}"
FORCE_TERMINATE_INSTANCES="${FORCE_TERMINATE_INSTANCES:-false}"  # set true to terminate EC2 in the VPC
MAX_RETRIES="${MAX_RETRIES:-30}"
SLEEP_SECS="${SLEEP_SECS:-10}"
# --------------------------------------------

echo "[Info] Region=$REGION  VPC=$VPC_ID  IGW=$IGW_ID  FORCE_TERMINATE_INSTANCES=$FORCE_TERMINATE_INSTANCES"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' is required"; exit 1; }; }
need aws
need jq

retry() {
  local tries=$1; shift
  local delay=$1; shift
  local i=1
  while true; do
    if "$@"; then return 0; fi
    [[ $i -ge $tries ]] && return 1
    echo "  retry $i/$tries ..."; sleep "$delay"; i=$((i+1))
  done
}

# 0) Sanity
aws ec2 describe-vpcs --region "$REGION" --vpc-ids "$VPC_ID" >/dev/null
if [[ -n "${IGW_ID:-}" ]]; then
  aws ec2 describe-internet-gateways --region "$REGION" --internet-gateway-ids "$IGW_ID" >/dev/null || {
    echo "[Warn] IGW $IGW_ID not found; will discover dynamically."
    IGW_ID=""
  }
fi

# Discover IGW if not provided
if [[ -z "${IGW_ID:-}" ]]; then
  IGW_ID="$(aws ec2 describe-internet-gateways --region "$REGION" \
    --filters Name=attachment.vpc-id,Values="$VPC_ID" \
    --query "InternetGateways[0].InternetGatewayId" --output text 2>/dev/null || true)"
  [[ "$IGW_ID" == "None" ]] && IGW_ID=""
fi

# 1) Delete ALB/NLB (ELBv2) & listeners
echo "[Step 1] Deleting ELBv2 (ALB/NLB) in VPC..."
for _ in $(seq 1 $MAX_RETRIES); do
  ARNS=$(aws elbv2 describe-load-balancers --region "$REGION" \
    --query "LoadBalancers[?VpcId=='$VPC_ID'].LoadBalancerArn" --output text || true)
  if [[ -z "$ARNS" ]]; then echo "  No ELBv2 found (ok)."; break; fi
  for arn in $ARNS; do
    echo "  - deleting listeners for $arn"
    LST=$(aws elbv2 describe-listeners --region "$REGION" --load-balancer-arn "$arn" \
      --query "Listeners[].ListenerArn" --output text 2>/dev/null || true)
    for l in $LST; do aws elbv2 delete-listener --region "$REGION" --listener-arn "$l" || true; done
    echo "  - deleting load balancer $arn"
    aws elbv2 delete-load-balancer --region "$REGION" --load-balancer-arn "$arn" || true
  done
  echo "  Waiting for ELBv2 to disappear..."; sleep "$SLEEP_SECS"
done

# 2) Delete Classic ELBs (if any)
echo "[Step 2] Deleting Classic ELBs (if any) in VPC..."
CLBS=$(aws elb describe-load-balancers --region "$REGION" \
  --query "LoadBalancerDescriptions[].{Name:LoadBalancerName,Subnets:Subnets}" --output json 2>/dev/null | jq -r '.[]?|@base64' || true)
if [[ -n "$CLBS" ]]; then
  while read -r row; do
    d() { echo "$row" | base64 --decode | jq -r "$1"; }
    name=$(d '.Name')
    subnets_json=$(d '.Subnets')
    in_vpc=0
    for s in $(echo "$subnets_json" | jq -r '.[]'); do
      svpc=$(aws ec2 describe-subnets --region "$REGION" --subnet-ids "$s" --query "Subnets[0].VpcId" --output text 2>/dev/null || true)
      [[ "$svpc" == "$VPC_ID" ]] && in_vpc=1
    done
    if [[ "$in_vpc" == "1" ]]; then
      echo "  - deleting Classic ELB $name"
      aws elb delete-load-balancer --region "$REGION" --load-balancer-name "$name" || true
    fi
  done <<< "$CLBS"
else
  echo "  No Classic ELBs found (ok)."
fi

# 3) Delete orphaned Target Groups
echo "[Step 3] Deleting orphaned Target Groups..."
TGS=$(aws elbv2 describe-target-groups --region "$REGION" \
  --query "TargetGroups[?VpcId=='$VPC_ID'].TargetGroupArn" --output text || true)
for tg in $TGS; do
  aws elbv2 delete-target-group --region "$REGION" --target-group-arn "$tg" || true
done

# 4) Delete NAT Gateways & release their EIPs
echo "[Step 4] Deleting NAT Gateways and collecting EIPs..."
NAT_EIPS=()
NGWS=$(aws ec2 describe-nat-gateways --region "$REGION" \
  --filter Name=vpc-id,Values="$VPC_ID" \
  --query "NatGateways[].NatGatewayId" --output text || true)
for ngw in $NGWS; do
  ALLOCS=$(aws ec2 describe-nat-gateways --region "$REGION" --nat-gateway-ids "$ngw" \
    --query "NatGateways[0].NatGatewayAddresses[].AllocationId" --output text || true)
  for a in $ALLOCS; do [[ -n "$a" && "$a" != "None" ]] && NAT_EIPS+=("$a"); done
  echo "  - deleting NAT Gateway $ngw"
  aws ec2 delete-nat-gateway --region "$REGION" --nat-gateway-id "$ngw" || true
done

# Wait for NAT deletion
for _ in $(seq 1 $MAX_RETRIES); do
  LEFT=$(aws ec2 describe-nat-gateways --region "$REGION" \
    --filter Name=vpc-id,Values="$VPC_ID" Name=state,Values=pending,available,deleting \
    --query "NatGateways[].NatGatewayId" --output text || true)
  [[ -z "$LEFT" ]] && { echo "  NAT Gateways gone."; break; }
  echo "  Waiting for NAT GW deletion..."; sleep "$SLEEP_SECS"
done

# Release NAT EIPs
if [[ "${#NAT_EIPS[@]}" -gt 0 ]]; then
  echo "[Step 4b] Releasing EIPs from NATs: ${NAT_EIPS[*]}"
  for alloc in "${NAT_EIPS[@]}"; do
    ASSOC=$(aws ec2 describe-addresses --region "$REGION" --allocation-ids "$alloc" \
      --query "Addresses[0].AssociationId" --output text 2>/dev/null || true)
    [[ "$ASSOC" != "None" && -n "$ASSOC" && "$ASSOC" != "null" ]] && \
      aws ec2 disassociate-address --region "$REGION" --association-id "$ASSOC" || true
    aws ec2 release-address --region "$REGION" --allocation-id "$alloc" || true
  done
fi

# 5) VPC Endpoints (Interface & Gateway)
echo "[Step 5] Deleting VPC Endpoints..."
VPCE_IDS=$(aws ec2 describe-vpc-endpoints --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" \
  --query "VpcEndpoints[].VpcEndpointId" --output text || true)
for id in $VPCE_IDS; do
  echo "  - deleting VPC endpoint $id"
  aws ec2 delete-vpc-endpoints --region "$REGION" --vpc-endpoint-ids "$id" || true
done

# 6) Optionally terminate EC2 instances in this VPC
if [[ "$FORCE_TERMINATE_INSTANCES" == "true" ]]; then
  echo "[Step 6] Terminating EC2 instances in VPC (FORCE_TERMINATE_INSTANCES=true)"
  INSTANCE_IDS=$(aws ec2 describe-instances --region "$REGION" \
    --filters Name=vpc-id,Values="$VPC_ID" Name=instance-state-name,Values=pending,running,stopping,stopped \
    --query "Reservations[].Instances[].InstanceId" --output text || true)
  if [[ -n "$INSTANCE_IDS" ]]; then
    aws ec2 terminate-instances --region "$REGION" --instance-ids $INSTANCE_IDS || true
    echo "  Waiting for instances to terminate..."
    aws ec2 wait instance-terminated --region "$REGION" --instance-ids $INSTANCE_IDS || true
  fi
else
  echo "[Step 6] Skipping EC2 termination (set FORCE_TERMINATE_INSTANCES=true to enable)"
fi

# 7) ENIs (delete what we can)
echo "[Step 7] Deleting Network Interfaces (best-effort)..."
ENIS=$(aws ec2 describe-network-interfaces --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" \
  --query "NetworkInterfaces[].NetworkInterfaceId" --output text || true)
for eni in $ENIS; do
  STATUS=$(aws ec2 describe-network-interfaces --region "$REGION" \
    --network-interface-ids "$eni" --query "NetworkInterfaces[0].Status" --output text || true)
  if [[ "$STATUS" == "available" ]]; then
    echo "  - deleting ENI $eni"
    aws ec2 delete-network-interface --region "$REGION" --network-interface-id "$eni" || true
  else
    echo "  - ENI $eni is '$STATUS' (attached); will likely clear after LB/instances are gone"
  fi
done

# 8) Disable mapPublicIpOnLaunch on public subnets (best-effort)
echo "[Step 8] Disabling mapPublicIpOnLaunch on public subnets..."
PUBS=$(aws ec2 describe-subnets --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" Name=tag:kubernetes.io/role/elb,Values=1 \
  --query "Subnets[].SubnetId" --output text || true)
for s in $PUBS; do
  aws ec2 modify-subnet-attribute --region "$REGION" --subnet-id "$s" --no-map-public-ip-on-launch || true
done

# 9) Detach & delete IGW
if [[ -n "${IGW_ID:-}" ]]; then
  echo "[Step 9] Detaching & deleting IGW $IGW_ID ..."
  aws ec2 detach-internet-gateway --region "$REGION" --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID" || true
  aws ec2 delete-internet-gateway  --region "$REGION" --internet-gateway-id "$IGW_ID" || true
else
  echo "[Step 9] No IGW attached (ok)."
fi

# 10) Delete route table associations & non-main route tables
echo "[Step 10] Deleting non-main Route Tables..."
RTBS=$(aws ec2 describe-route-tables --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" \
  --query "RouteTables[].{Id:RouteTableId,Assoc:Associations}" --output json)
echo "$RTBS" | jq -c '.[]' | while read -r item; do
  RT_ID=$(echo "$item" | jq -r '.Id')
  MAIN=$(echo "$item" | jq -r '.Assoc[]? | select(.Main==true) | .Main' || echo "")
  if [[ "$MAIN" == "true" ]]; then
    echo "  - skipping main RTB $RT_ID"
    continue
  fi
  # Disassociate any explicit associations
  ASSOC_IDS=$(echo "$item" | jq -r '.Assoc[]? | select(.Main!=true) | .RouteTableAssociationId')
  for a in $ASSOC_IDS; do
    echo "  - disassociate $a"
    aws ec2 disassociate-route-table --region "$REGION" --association-id "$a" || true
  done
  echo "  - delete RTB $RT_ID"
  aws ec2 delete-route-table --region "$REGION" --route-table-id "$RT_ID" || true
done

# 11) Delete NACLs (non-default)
echo "[Step 11] Deleting non-default Network ACLs..."
NACLS=$(aws ec2 describe-network-acls --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" \
  --query "NetworkAcls[?IsDefault==`false`].NetworkAclId" --output text || true)
for n in $NACLS; do
  echo "  - delete NACL $n"
  aws ec2 delete-network-acl --region "$REGION" --network-acl-id "$n" || true
done

# 12) Delete Security Groups (non-default)
echo "[Step 12] Deleting non-default Security Groups..."
SGS=$(aws ec2 describe-security-groups --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" \
  --query "SecurityGroups[?GroupName!='default'].GroupId" --output text || true)
for sg in $SGS; do
  echo "  - delete SG $sg"
  aws ec2 delete-security-group --region "$REGION" --group-id "$sg" || true
done

# 13) Delete Subnets (any remaining)
echo "[Step 13] Deleting Subnets..."
SUBNETS=$(aws ec2 describe-subnets --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" \
  --query "Subnets[].SubnetId" --output text || true)
for subnet in $SUBNETS; do
  echo "  - delete Subnet $subnet"
  aws ec2 delete-subnet --region "$REGION" --subnet-id "$subnet" || true
done

# 14) Reset & delete custom DHCP options
echo "[Step 14] Reset & delete custom DHCP options (best-effort)..."
DOPT_ID=$(aws ec2 describe-vpcs --region "$REGION" --vpc-ids "$VPC_ID" \
  --query "Vpcs[0].DhcpOptionsId" --output text 2>/dev/null || echo "None")

if [[ -n "$DOPT_ID" && "$DOPT_ID" != "default" && "$DOPT_ID" != "None" ]]; then
  echo "  VPC had DHCP options: $DOPT_ID"
  echo "  Re-associating any VPCs using $DOPT_ID back to 'default'..."
  for V in $(aws ec2 describe-vpcs --region "$REGION" \
      --filters Name=dhcp-options-id,Values="$DOPT_ID" \
      --query 'Vpcs[].VpcId' --output text); do
    aws ec2 associate-dhcp-options --region "$REGION" --vpc-id "$V" --dhcp-options-id default || true
  done

  # Wait until no VPCs reference it, then delete
  for _ in $(seq 1 12); do
    USING=$(aws ec2 describe-vpcs --region "$REGION" \
      --filters Name=dhcp-options-id,Values="$DOPT_ID" \
      --query 'length(Vpcs)')
    if [[ "$USING" == "0" ]]; then
      echo "  Deleting DHCP options $DOPT_ID"
      aws ec2 delete-dhcp-options --region "$REGION" --dhcp-options-id "$DOPT_ID" || true
      break
    fi
    echo "  DHCP options still associated to $USING VPC(s); sleeping 10s..."; sleep 10
  done
else
  echo "  No custom DHCP options to clean (ok)."
fi

# 15) Delete VPC
echo "[Step 15] Deleting VPC $VPC_ID ..."
aws ec2 delete-vpc --region "$REGION" --vpc-id "$VPC_ID" || true

echo "[Done] VPC $VPC_ID and dependencies removed."
