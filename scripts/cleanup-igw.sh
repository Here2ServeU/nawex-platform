#!/usr/bin/env bash
set -euo pipefail

# --- REQUIRED: set these two ---
REGION="us-east-1"
VPC_ID="vpc-006568642877085d3"
IGW_ID="igw-09fdb9b97dd8dd091"
ENIS=$(aws ec2 describe-network-interfaces --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" \
  --query "NetworkInterfaces[?contains(Description,'ELB') || contains(Description,'Load Balancer')].NetworkInterfaceId" \
  --output text)
# -------------------------------

echo "[Info] Region: $REGION  VPC: $VPC_ID  IGW: $IGW_ID"

# 0) Quick sanity
aws ec2 describe-vpcs --region "$REGION" --vpc-ids "$VPC_ID" >/dev/null
aws ec2 describe-internet-gateways --region "$REGION" --internet-gateway-ids "$IGW_ID" >/dev/null || {
  echo "[Warn] IGW $IGW_ID not found; continuing."
}

# 1) Delete ELBv2 (ALB/NLB) & listeners
echo "[Step 1] Deleting ELBv2 (ALB/NLB) in VPC..."
for i in {1..20}; do
  ARNS=$(aws elbv2 describe-load-balancers --region "$REGION" \
    --query "LoadBalancers[?VpcId=='$VPC_ID'].LoadBalancerArn" --output text || true)
  [[ -z "$ARNS" ]] && { echo "  No ELBv2 found (ok)."; break; }
  for arn in $ARNS; do
    echo "  - deleting listeners for $arn"
    LST=$(aws elbv2 describe-listeners --region "$REGION" --load-balancer-arn "$arn" \
      --query "Listeners[].ListenerArn" --output text 2>/dev/null || true)
    for l in $LST; do aws elbv2 delete-listener --region "$REGION" --listener-arn "$l" || true; done

    echo "  - deleting load balancer $arn"
    aws elbv2 delete-load-balancer --region "$REGION" --load-balancer-arn "$arn" || true
  done
  echo "  Waiting for ELBv2 to disappear..."; sleep 10
done

# 2) Delete Classic ELBs (if any)
echo "[Step 2] Deleting Classic ELBs (if any) in VPC..."
CLBS=$(aws elb describe-load-balancers --region "$REGION" \
  --query "LoadBalancerDescriptions[].LoadBalancerName" --output text 2>/dev/null || true)
if [[ -n "$CLBS" ]]; then
  for name in $CLBS; do
    # Check if this CLB is in our VPC by subnet
    SUBNETS=$(aws elb describe-load-balancers --region "$REGION" --load-balancer-names "$name" \
      --query "LoadBalancerDescriptions[0].Subnets" --output text 2>/dev/null || true)
    IN_VPC=0
    for s in $SUBNETS; do
      SVPC=$(aws ec2 describe-subnets --region "$REGION" --subnet-ids "$s" \
        --query "Subnets[0].VpcId" --output text 2>/dev/null || true)
      [[ "$SVPC" == "$VPC_ID" ]] && IN_VPC=1
    done
    if [[ "$IN_VPC" == "1" ]]; then
      echo "  - deleting Classic ELB $name"
      aws elb delete-load-balancer --region "$REGION" --load-balancer-name "$name" || true
    fi
  done
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

# 4) Delete NAT Gateways & collect their EIPs
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

# Wait until NATs gone
for i in {1..30}; do
  LEFT=$(aws ec2 describe-nat-gateways --region "$REGION" \
    --filter Name=vpc-id,Values="$VPC_ID" Name=state,Values=pending,available,deleting \
    --query "NatGateways[].NatGatewayId" --output text || true)
  [[ -z "$LEFT" ]] && { echo "  NAT Gateways gone."; break; }
  echo "  Waiting for NAT GW deletion..."; sleep 10
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

# 5) Disassociate & release any other EIPs tied to ENIs in this VPC
echo "[Step 5] Releasing any other EIPs associated to ENIs in this VPC..."
ENIS_JSON=$(aws ec2 describe-network-interfaces --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" --output json || echo "[]")
# Disassociate any EIPs attached to ENIs in this VPC
echo "$ENIS_JSON" | jq -r '.NetworkInterfaces[] | select(.Association and .Association.AllocationId) | [.NetworkInterfaceId, .Association.AssociationId, .Association.AllocationId] | @tsv' | \
while IFS=$'\t' read -r eni assoc alloc; do
  echo "  - disassociate EIP ($alloc) from ENI $eni (assoc $assoc)"
  aws ec2 disassociate-address --region "$REGION" --association-id "$assoc" || true
  aws ec2 release-address --region "$REGION" --allocation-id "$alloc" || true
done

# 6) Report any ENIs that still have *ephemeral* public IPs (non-EIP)
# You can't disassociate those; you must stop/terminate the owning resource first.
LEFT_ENIS=$(echo "$ENIS_JSON" | jq -r '.NetworkInterfaces[] | select(.Association and (.Association.PublicIp!=null) and (.Association.AllocationId==null)) | [.NetworkInterfaceId, .Status, .Description, .Attachment.InstanceId] | @tsv' || true)
if [[ -n "$LEFT_ENIS" ]]; then
  echo "[Attention] These ENIs still have ephemeral public IPs (not EIPs)."
  echo "You must stop/terminate the owning instances before the IGW can detach:"
  echo "$LEFT_ENIS" | awk -F'\t' '{printf "  - ENI: %s  Status:%s  Desc:%s  Instance:%s\n",$1,$2,$3,$4}'
fi

# 7) Disable mapPublicIpOnLaunch on public subnets (best-effort)
echo "[Step 7] Disabling mapPublicIpOnLaunch on public subnets..."
PUBS=$(aws ec2 describe-subnets --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC_ID" Name=tag:kubernetes.io/role/elb,Values=1 \
  --query "Subnets[].SubnetId" --output text || true)
for s in $PUBS; do
  aws ec2 modify-subnet-attribute --region "$REGION" --subnet-id "$s" --no-map-public-ip-on-launch || true
done

# 8) Try to detach & delete the IGW
echo "[Step 8] Detaching IGW $IGW_ID from VPC $VPC_ID ..."
aws ec2 detach-internet-gateway --region "$REGION" \
  --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"

echo "[Step 9] Deleting IGW $IGW_ID ..."
aws ec2 delete-internet-gateway --region "$REGION" --internet-gateway-id "$IGW_ID"

echo "[Done] IGW detached & deleted."
