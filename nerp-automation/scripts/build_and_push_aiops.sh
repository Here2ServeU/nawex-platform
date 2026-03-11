#!/usr/bin/env bash
# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
set -euo pipefail

# =======================================================
# build_and_push_aiops.sh
# Build AIOps API image for linux/amd64 and push to ECR.
# Resolves CrashLoopBackOff caused by exec format errors
# on EKS when building from ARM-based machines.
# =======================================================
AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query 'Account' --output text)"
ECR_REPO="aiops-api"
IMAGE_NAME="aiops-api"
TAG="${1:-$(date +%Y%m%d%H%M)}"
PLATFORM="linux/amd64"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${TAG}"

echo "===================================================="
echo "[AIOPS] Building AIOps API image for EKS"
echo "Account:  $ACCOUNT_ID"
echo "Region:   $AWS_REGION"
echo "Repo:     $ECR_REPO"
echo "Platform: $PLATFORM"
echo "Tag:      $TAG"
echo "===================================================="

# -------------------------------------------------------
# Step 1 - Verify prerequisites
# -------------------------------------------------------
echo "----------------------------------------------------"
echo "[STEP 1] Verifying prerequisites..."
echo "----------------------------------------------------"
command -v docker >/dev/null 2>&1 || { echo "[ERROR] Docker is required."; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "[ERROR] AWS CLI is required."; exit 1; }

# -------------------------------------------------------
# Step 2 - Authenticate to ECR
# -------------------------------------------------------
echo "----------------------------------------------------"
echo "[STEP 2] Authenticating to ECR..."
echo "----------------------------------------------------"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin \
    "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# -------------------------------------------------------
# Step 3 - Create ECR repository if it does not exist
# -------------------------------------------------------
echo "----------------------------------------------------"
echo "[STEP 3] Ensuring ECR repository exists..."
echo "----------------------------------------------------"
aws ecr describe-repositories --repository-names "${ECR_REPO}" --region "${AWS_REGION}" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${ECR_REPO}" --region "${AWS_REGION}" --image-scanning-configuration scanOnPush=true

# -------------------------------------------------------
# Step 4 - Build image for linux/amd64
# -------------------------------------------------------
echo "----------------------------------------------------"
echo "[STEP 4] Building image (platform=${PLATFORM})..."
echo "----------------------------------------------------"
docker buildx build \
  --platform "${PLATFORM}" \
  -t "${ECR_URI}" \
  -f ai/Dockerfile \
  --load \
  .

# -------------------------------------------------------
# Step 5 - Push to ECR
# -------------------------------------------------------
echo "----------------------------------------------------"
echo "[STEP 5] Pushing image to ECR..."
echo "----------------------------------------------------"
docker push "$ECR_URI"

echo "===================================================="
echo "[SUCCESS] AIOps API (linux/amd64) image pushed!"
echo "Image URL:"
echo "  $ECR_URI"
echo "===================================================="

echo "[NEXT STEPS]"
echo "1. Update charts/aiops/values.yaml:"
echo ""
echo "image:"
echo "  repository: \"${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}\""
echo "  tag: \"${TAG}\""
echo "  pullPolicy: Always"
echo ""
echo "2. Redeploy AIOps:"
echo "  helm upgrade --install aiops ./charts/aiops -n aiops --create-namespace"
echo ""
echo "======================================================"
