#!/usr/bin/env bash
set -euo pipefail

# =======================================================
# build_and_push_aiops.sh
# Fixes CrashLoopBackOff: exec format error
# Build AIOps API Image for linux/amd64 and push to ECR
# =======================================================
AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query 'Account' --output text)"
ECR_REPO="aiops-api"
IMAGE_NAME="aiops-api"

# --- NEW LINES ---
# Use first argument as TAG, or generate a timestamp
TAG="${1:-$(date +%Y%m%d%H%M)}"
# --- END NEW LINES ---

PLATFORM="linux/amd64"

echo "===================================================="
echo "[AIOPS] Building AIOps API image for EKS"
echo "Account: $ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Repo: $ECR_REPO"
echo "Platform: $PLATFORM"
echo "Image Tag: $TAG" # Added to confirmation output
echo "===================================================="

# ... (rest of the script remains the same until the NEXT STEPS section) ...

# -------------------------------------------------------
# Step 5 — Push to ECR
# -------------------------------------------------------
echo "----------------------------------------------------"
echo "[STEP 5] Pushing image to ECR..."
echo "----------------------------------------------------"
docker push "$ECR_URI"

echo "===================================================="
echo "[SUCCESS] AIOps API (linux/amd64) image pushed!"
echo "Image URL:"
echo "   $ECR_URI"
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
echo "   helm upgrade --install aiops ./charts/aiops -n aiops --create-namespace"
echo ""
echo "======================================================"
