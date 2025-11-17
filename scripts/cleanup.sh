#!/usr/bin/env bash
set -euo pipefail

#
# cleanup_super.sh
# Interactive cleanup for:
#  - EKS clusters (if they exist)
#  - VPCs (with full dependency cleanup)
#
# Requirements: aws, jq
#

# -------- Global arrays (must be defined before any use) --------
CLUSTERS_TO_DELETE=()
VPCS_TO_DELETE=()

# -------- Helpers --------
need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' required"; exit 1; }; }
need aws
need jq

line() { printf '%s\n' "=================================================="; }

# -------- Select region --------
echo "Enter AWS region (default: us-east-1): "
read -r AWS_REGION
AWS_REGION="${AWS_REGION:-us-east-1}"

echo
echo "Using AWS region: $AWS_REGION"
echo

# -------- Detect EKS clusters --------
echo "Detecting EKS clusters in region $AWS_REGION..."
CLUSTERS_JSON="$(aws eks list-clusters --region "$AWS_REGION" --query 'clusters' --output json 2>/dev/null || echo '[]')"
CLUSTERS_LIST="$(echo "$CLUSTERS_JSON" | jq -r '.[]?')"

if [[ -z "${CLUSTERS_LIST}" ]]; then
  echo "No EKS clusters found."
else
  echo "Found EKS clusters:"
  echo "$CLUSTERS_LIST" | sed 's/^/ - /'
fi

echo
echo "Delete ALL detected EKS clusters? (yes/no)"
read -r DELETE_ALL_CLUSTERS

if [[ "$DELETE_ALL_CLUSTERS" == "yes" && -n "${CLUSTERS_LIST}" ]]; then
  for c in $CLUSTERS_LIST; do
    CLUSTERS_TO_DELETE+=("$c")
  done
else
  echo "Enter EKS cluster names to delete (space-separated), or press ENTER to skip:"
  read -r CUSTOM_CLUSTERS
  for c in $CUSTOM_CLUSTERS; do
    CLUSTERS_TO_DELETE+=("$c")
  done
fi

# -------- Detect VPCs --------
echo
echo "Detecting VPCs in region $AWS_REGION..."
VPCS_RAW="$(aws ec2 describe-vpcs --region "$AWS_REGION" --query 'Vpcs[].VpcId' --output text 2>/dev/null || true)"

if [[ -z "${VPCS_RAW:-}" ]]; then
  echo "No VPCs found."
else
  echo "Found VPCs:"
  echo "$VPCS_RAW" | sed 's/^/ - /'
fi

echo
echo "Delete ALL VPCs? (yes/no)"
read -r DELETE_ALL_VPCS

if [[ "$DELETE_ALL_VPCS" == "yes" && -n "${VPCS_RAW:-}" ]]; then
  for v in $VPCS_RAW; do
    VPCS_TO_DELETE+=("$v")
  done
else
  echo "Enter VPC IDs to delete (space-separated), or press ENTER to skip:"
  read -r CUSTOM_VPCS
  for v in $CUSTOM_VPCS; do
    VPCS_TO_DELETE+=("$v")
  done
fi

# -------- Summary --------
echo
line
echo " SUMMARY — RESOURCES MARKED FOR DELETION"
line

echo "Clusters:"
if [[ ${#CLUSTERS_TO_DELETE[@]} -eq 0 ]]; then
  echo " - none"
else
  printf ' - %s\n' "${CLUSTERS_TO_DELETE[@]}"
fi

echo
echo "VPCs:"
if [[ ${#VPCS_TO_DELETE[@]} -eq 0 ]]; then
  echo " - none"
else
  printf ' - %s\n' "${VPCS_TO_DELETE[@]}"
fi

line
echo "Proceed? Type YES to continue:"
read -r CONFIRM
if [[ "$CONFIRM" != "YES" ]]; then
  echo "Cancelled."
  exit 0
fi

# =====================================================================
# FUNCTION: delete_cluster
# - If cluster does not exist: skip immediately and DO NOT loop
# - If it exists: delete nodegroups, Fargate, cluster
# - Register its VPC for later VPC cleanup
# =====================================================================
delete_cluster() {
  local CLUSTER_NAME="$1"

  echo
  line
  echo " Deleting EKS cluster: $CLUSTER_NAME"
  line

  # Does the cluster still exist?
  local STATUS
  STATUS="$(aws eks describe-cluster \
    --region "$AWS_REGION" \
    --name "$CLUSTER_NAME" \
    --query 'cluster.status' \
    --output text 2>/dev/null || echo "NOT_FOUND")"

  if [[ "$STATUS" == "NOT_FOUND" ]]; then
    echo "Cluster $CLUSTER_NAME not found. Skipping."
    return
  fi

  # Get its VPC and add to deletion list
  local VPC_ID
  VPC_ID="$(aws eks describe-cluster \
    --region "$AWS_REGION" \
    --name "$CLUSTER_NAME" \
    --query 'cluster.resourcesVpcConfig.vpcId' \
    --output text 2>/dev/null || echo "")"

  if [[ -n "$VPC_ID" && "$VPC_ID" != "None" ]]; then
    echo "Cluster uses VPC: $VPC_ID (will be scheduled for cleanup)."
    VPCS_TO_DELETE+=("$VPC_ID")
  else
    echo "Cluster VPC not found or already removed."
  fi

  # Delete nodegroups
  local NGS
  NGS="$(aws eks list-nodegroups \
    --region "$AWS_REGION" \
    --cluster-name "$CLUSTER_NAME" \
    --query 'nodegroups' \
    --output json 2>/dev/null | jq -r '.[]?' || true)"

  if [[ -n "$NGS" ]]; then
    echo "Deleting nodegroups for $CLUSTER_NAME..."
    for ng in $NGS; do
      echo " - Deleting nodegroup: $ng"
      aws eks delete-nodegroup \
        --region "$AWS_REGION" \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$ng" >/dev/null 2>&1 || true
    done
  fi

  # Delete Fargate profiles
  local FPS
  FPS="$(aws eks list-fargate-profiles \
    --region "$AWS_REGION" \
    --cluster-name "$CLUSTER_NAME" \
    --query 'fargateProfileNames' \
    --output json 2>/dev/null | jq -r '.[]?' || true)"

  if [[ -n "$FPS" ]]; then
    echo "Deleting Fargate profiles for $CLUSTER_NAME..."
    for fp in $FPS; do
      echo " - Deleting Fargate profile: $fp"
      aws eks delete-fargate-profile \
        --region "$AWS_REGION" \
        --cluster-name "$CLUSTER_NAME" \
        --fargate-profile-name "$fp" >/dev/null 2>&1 || true
    done
  fi

  # Small wait and delete cluster
  echo "Requesting EKS cluster deletion..."
  aws eks delete-cluster \
    --region "$AWS_REGION" \
    --name "$CLUSTER_NAME" >/dev/null 2>&1 || true

  # Poll a few times only (avoid noisy loops)
  for i in {1..6}; do
    STATUS="$(aws eks describe-cluster \
      --region "$AWS_REGION" \
      --name "$CLUSTER_NAME" \
      --query 'cluster.status' \
      --output text 2>/dev/null || echo "NOT_FOUND")"
    if [[ "$STATUS" == "NOT_FOUND" ]]; then
      echo "Cluster $CLUSTER_NAME deleted."
      return
    fi
    echo "Cluster $CLUSTER_NAME deletion in progress (status=$STATUS). Checking again in 10 seconds..."
    sleep 10
  done

  echo "Cluster $CLUSTER_NAME deletion is still in progress. Continuing with VPC cleanup."
}

# =====================================================================
# FUNCTION: delete_vpc
# - If VPC does not exist: skip
# - If VPC still has EC2 instances: warn and skip (safety)
# - Cleans ELBv2, Classic ELB, TGs, NATs/EIPs, endpoints, RTs, NACLs, SGs, IGWs, subnets, ENIs
# - Finally deletes VPC
# =====================================================================
delete_vpc() {
  local VPC_ID="$1"

  echo
  line
  echo " Cleaning and deleting VPC: $VPC_ID"
  line

  # Does the VPC still exist?
  local EXISTS
  EXISTS="$(aws ec2 describe-vpcs \
    --region "$AWS_REGION" \
    --vpc-ids "$VPC_ID" \
    --query 'Vpcs[0].VpcId' \
    --output text 2>/dev/null || echo "NOT_FOUND")"

  if [[ "$EXISTS" == "NOT_FOUND" || -z "$EXISTS" ]]; then
    echo "VPC $VPC_ID does not exist. Skipping."
    return
  fi

  # Check for instances inside VPC
  local INSTANCES
  INSTANCES="$(aws ec2 describe-instances --region "$AWS_REGION" \
    --filters Name=vpc-id,Values="$VPC_ID" \
              Name=instance-state-name,Values=pending,running,stopping,stopped \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text 2>/dev/null || true)"

  if [[ -n "$INSTANCES" ]]; then
    echo "VPC $VPC_ID has EC2 instances:"
    echo "$INSTANCES" | sed 's/^/ - /'
    echo "For safety, this script will NOT terminate EC2 instances automatically."
    echo "Skipping VPC $VPC_ID. Terminate instances first, then re-run."
    return
  fi

  # 1) Delete ELBv2
  echo "[1] Deleting ELBv2 load balancers in VPC $VPC_ID..."
  local ARNS
  ARNS="$(aws elbv2 describe-load-balancers --region "$AWS_REGION" \
    --query "LoadBalancers[?VpcId=='$VPC_ID'].LoadBalancerArn" \
    --output text 2>/dev/null || true)"
  for arn in $ARNS; do
    echo " - Deleting ELBv2: $arn"
    aws elbv2 delete-load-balancer --region "$AWS_REGION" --load-balancer-arn "$arn" >/dev/null 2>&1 || true
  done

  # 2) Delete Classic ELBs
  echo "[2] Deleting Classic ELBs associated with VPC (best-effort)..."
  local CLB_JSON
  CLB_JSON="$(aws elb describe-load-balancers --region "$AWS_REGION" \
    --query 'LoadBalancerDescriptions' --output json 2>/dev/null || echo '[]')"

  echo "$CLB_JSON" | jq -c '.[]?' | while read -r row; do
    local name
    name="$(echo "$row" | jq -r '.LoadBalancerName')"
    local subnets
    subnets="$(echo "$row" | jq -r '.Subnets[]?')"
    local match=0
    for s in $subnets; do
      local svpc
      svpc="$(aws ec2 describe-subnets --region "$AWS_REGION" \
        --subnet-ids "$s" \
        --query 'Subnets[0].VpcId' \
        --output text 2>/dev/null || echo "")"
      [[ "$svpc" == "$VPC_ID" ]] && match=1
    done
    if [[ $match -eq 1 ]]; then
      echo " - Deleting Classic ELB: $name"
      aws elb delete-load-balancer --region "$AWS_REGION" --load-balancer-name "$name" >/dev/null 2>&1 || true
    fi
  done

  # 3) Delete Target Groups
  echo "[3] Deleting target groups in VPC $VPC_ID..."
  local TGS
  TGS="$(aws elbv2 describe-target-groups --region "$AWS_REGION" \
    --query "TargetGroups[?VpcId=='$VPC_ID'].TargetGroupArn" \
    --output text 2>/dev/null || true)"
  for tg in $TGS; do
    echo " - Deleting target group: $tg"
    aws elbv2 delete-target-group --region "$AWS_REGION" --target-group-arn "$tg" >/dev/null 2>&1 || true
  done

  # 4) NAT + EIPs
  echo "[4] Deleting NAT Gateways and releasing EIPs..."
  local NGWS
  NGWS="$(aws ec2 describe-nat-gateways --region "$AWS_REGION" \
    --filter Name=vpc-id,Values="$VPC_ID" \
    --query 'NatGateways[].NatGatewayId' \
    --output text 2>/dev/null || true)"
  local NAT_EIPS=()

  for ngw in $NGWS; do
    local ALLOCS
    ALLOCS="$(aws ec2 describe-nat-gateways --region "$AWS_REGION" \
      --nat-gateway-ids "$ngw" \
      --query 'NatGateways[0].NatGatewayAddresses[].AllocationId' \
      --output text 2>/dev/null || true)"
    for a in $ALLOCS; do
      [[ -n "$a" && "$a" != "None" ]] && NAT_EIPS+=("$a")
    done
    echo " - Deleting NAT Gateway: $ngw"
    aws ec2 delete-nat-gateway --region "$AWS_REGION" --nat-gateway-id "$ngw" >/dev/null 2>&1 || true
  done

  if [[ "${#NAT_EIPS[@]}" -gt 0 ]]; then
    echo "Releasing NAT EIPs..."
    for alloc in "${NAT_EIPS[@]}"; do
      echo " - Releasing EIP allocation: $alloc"
      aws ec2 release-address --region "$AWS_REGION" --allocation-id "$alloc" >/dev/null 2>&1 || true
    done
  fi

  # 5) VPC Endpoints
  echo "[5] Deleting VPC endpoints..."
  local VPCE_IDS
  VPCE_IDS="$(aws ec2 describe-vpc-endpoints --region "$AWS_REGION" \
    --filters Name=vpc-id,Values="$VPC_ID" \
    --query 'VpcEndpoints[].VpcEndpointId' \
    --output text 2>/dev/null || true)"
  if [[ -n "$VPCE_IDS" ]]; then
    aws ec2 delete-vpc-endpoints --region "$AWS_REGION" --vpc-endpoint-ids $VPCE_IDS >/dev/null 2>&1 || true
  fi

  # 6) Route tables (non-main)
  echo "[6] Deleting non-main route tables..."
  local RTBS_JSON
  RTBS_JSON="$(aws ec2 describe-route-tables --region "$AWS_REGION" \
    --filters Name=vpc-id,Values="$VPC_ID" \
    --output json 2>/dev/null || echo '{}')"

  echo "$RTBS_JSON" | jq -c '.RouteTables[]?' | while read -r rt; do
    local RT_ID
    RT_ID="$(echo "$rt" | jq -r '.RouteTableId')"
    local IS_MAIN
    IS_MAIN="$(echo "$rt" | jq -r '.Associations[]? | select(.Main==true) | .Main' || echo '')"

    if [[ "$IS_MAIN" == "true" ]]; then
      echo " - Skipping main route table: $RT_ID"
      continue
    fi

    # Disassociate first
    echo "$rt" | jq -r '.Associations[]? | select(.Main!=true) | .RouteTableAssociationId' | while read -r a; do
      [[ -n "$a" ]] && aws ec2 disassociate-route-table --region "$AWS_REGION" --association-id "$a" >/dev/null 2>&1 || true
    done

    echo " - Deleting RTB: $RT_ID"
    aws ec2 delete-route-table --region "$AWS_REGION" --route-table-id "$RT_ID" >/dev/null 2>&1 || true
  done

  # 7) NACLs
  echo "[7] Deleting non-default NACLs..."
  local NACLS
  NACLS="$(aws ec2 describe-network-acls --region "$AWS_REGION" \
    --filters Name=vpc-id,Values="$VPC_ID" Name=isDefault,Values=false \
    --query 'NetworkAcls[].NetworkAclId' \
    --output text 2>/dev/null || true)"
  for n in $NACLS; do
    echo " - Deleting NACL: $n"
    aws ec2 delete-network-acl --region "$AWS_REGION" --network-acl-id "$n" >/dev/null 2>&1 || true
  done

  # 8) Security groups
  echo "[8] Deleting non-default security groups..."
  local ALL_SGS
  ALL_SGS="$(aws ec2 describe-security-groups --region "$AWS_REGION" \
    --filters Name=vpc-id,Values="$VPC_ID" \
    --query 'SecurityGroups[?GroupName!=`default`].GroupId' \
    --output text 2>/dev/null || true)"

  for SG in $ALL_SGS; do
    echo " - Clearing rules and deleting SG: $SG"
    local IN_JSON
    IN_JSON="$(aws ec2 describe-security-groups --region "$AWS_REGION" --group-ids "$SG" \
      --query 'SecurityGroups[0].IpPermissions' \
      --output json 2>/dev/null || echo '[]')"
    if [[ "$(echo "$IN_JSON" | jq 'length')" -gt 0 ]]; then
      aws ec2 revoke-security-group-ingress --region "$AWS_REGION" --group-id "$SG" \
        --ip-permissions "$IN_JSON" >/dev/null 2>&1 || true
    fi
    local OUT_JSON
    OUT_JSON="$(aws ec2 describe-security-groups --region "$AWS_REGION" --group-ids "$SG" \
      --query 'SecurityGroups[0].IpPermissionsEgress' \
      --output json 2>/dev/null || echo '[]')"
    if [[ "$(echo "$OUT_JSON" | jq 'length')" -gt 0 ]]; then
      aws ec2 revoke-security-group-egress --region "$AWS_REGION" --group-id "$SG" \
        --ip-permissions "$OUT_JSON" >/dev/null 2>&1 || true
    fi
    aws ec2 delete-security-group --region "$AWS_REGION" --group-id "$SG" >/dev/null 2>&1 || true
  done

  # 9) Internet Gateway
  echo "[9] Detaching and deleting Internet Gateway..."
  local IGW_ID
  IGW_ID="$(aws ec2 describe-internet-gateways --region "$AWS_REGION" \
    --filters Name=attachment.vpc-id,Values="$VPC_ID" \
    --query 'InternetGateways[0].InternetGatewayId' \
    --output text 2>/dev/null || echo 'None')"
  if [[ "$IGW_ID" != "None" && -n "$IGW_ID" ]]; then
    echo " - Detaching IGW: $IGW_ID"
    aws ec2 detach-internet-gateway --region "$AWS_REGION" --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID" >/dev/null 2>&1 || true
    echo " - Deleting IGW: $IGW_ID"
    aws ec2 delete-internet-gateway --region "$AWS_REGION" --internet-gateway-id "$IGW_ID" >/dev/null 2>&1 || true
  fi

  # 10) Subnets
  echo "[10] Deleting subnets..."
  local SUBNETS
  SUBNETS="$(aws ec2 describe-subnets --region "$AWS_REGION" \
    --filters Name=vpc-id,Values="$VPC_ID" \
    --query 'Subnets[].SubnetId' \
    --output text 2>/dev/null || true)"
  for s in $SUBNETS; do
    echo " - Deleting subnet: $s"
    aws ec2 delete-subnet --region "$AWS_REGION" --subnet-id "$s" >/dev/null 2>&1 || true
  done

  # 11) ENIs (available only)
  echo "[11] Deleting 'available' ENIs..."
  local ENI_JSON
  ENI_JSON="$(aws ec2 describe-network-interfaces --region "$AWS_REGION" \
    --filters Name=vpc-id,Values="$VPC_ID" \
    --query 'NetworkInterfaces[].{Id:NetworkInterfaceId,Status:Status}' \
    --output json 2>/dev/null || echo '[]')"
  echo "$ENI_JSON" | jq -c '.[]?' | while read -r eni; do
    local EID EST
    EID="$(echo "$eni" | jq -r '.Id')"
    EST="$(echo "$eni" | jq -r '.Status')"
    if [[ "$EST" == "available" ]]; then
      echo " - Deleting ENI: $EID"
      aws ec2 delete-network-interface --region "$AWS_REGION" --network-interface-id "$EID" >/dev/null 2>&1 || true
    fi
  done

  # 12) Final: delete VPC
  echo "[FINAL] Deleting VPC $VPC_ID..."
  aws ec2 delete-vpc --region "$AWS_REGION" --vpc-id "$VPC_ID" >/dev/null 2>&1 || true
  echo "VPC $VPC_ID deletion attempted. If it still exists, check for remaining dependencies."
}

# =====================================================================
# EXECUTION
# =====================================================================

# 1) Delete clusters (if any)
if [[ ${#CLUSTERS_TO_DELETE[@]} -gt 0 ]]; then
  for C in "${CLUSTERS_TO_DELETE[@]}"; do
    delete_cluster "$C"
  done
fi

# 2) Deduplicate VPC list (clusters may have added their VPCs)
# POSIX safe dedupe (no mapfile)
if [[ ${#VPCS_TO_DELETE[@]} -gt 0 ]]; then
  UNIQUE_VPCS=""
  for v in "${VPCS_TO_DELETE[@]}"; do
    case " $UNIQUE_VPCS " in
      *" $v "*) ;; # skip duplicates
      *) UNIQUE_VPCS="$UNIQUE_VPCS $v" ;;
    esac
  done

  VPCS_TO_DELETE=()
  for v in $UNIQUE_VPCS; do
    VPCS_TO_DELETE+=("$v")
  done
fi

# 3) Delete VPCs
if [[ ${#VPCS_TO_DELETE[@]} -gt 0 ]]; then
  for V in "${VPCS_TO_DELETE[@]}"; do
    delete_vpc "$V"
  done
fi

echo
line
echo " CLEANUP COMPLETE"
line