#!/bin/bash
#
# OpenTelemetry Collector Deployment Script
# Description: robustly deploys the OpenTelemetry Collector using Helm (preferred) or raw manifests.
#              Includes dependency checking, namespace validation, and rollout verification.
# Usage: ./opentelemetry-collector-start.sh [-n <namespace>] [-d <chart_dir>]
#

set -o pipefail

# --- Configuration & Colors ---
DEFAULT_NAMESPACE="monitoring"
DEFAULT_CHART_PATH="../../helm/otel-collector"
DEPLOYMENT_NAME="opentelemetry-collector"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Helper Functions ---

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo -e "${BLUE}Usage:${NC} $0 [OPTIONS]"
    echo -e "\nOptions:"
    echo -e "  -n, --namespace <ns>   Kubernetes namespace to deploy into (Default: $DEFAULT_NAMESPACE)"
    echo -e "  -p, --path <path>      Path to Helm chart or Manifest (Default: $DEFAULT_CHART_PATH)"
    echo -e "  -h, --help             Show this help message"
    echo -e "\n${BLUE}Example:${NC}"
    echo -e "  $0 -n observability"
    exit 1
}

check_dependencies() {
    local missing=0
    for cmd in kubectl helm; do
        if ! command -v $cmd &> /dev/null; then
            log_error "'$cmd' is not installed or not in your PATH."
            missing=1
        fi
    done
    
    if [[ $missing -eq 1 ]]; then
        exit 1
    fi
}

check_cluster_connection() {
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
}

# --- Argument Parsing ---

NAMESPACE="$DEFAULT_NAMESPACE"
CHART_PATH="$DEFAULT_CHART_PATH"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -n|--namespace) NAMESPACE="$2"; shift ;;
        -p|--path) CHART_PATH="$2"; shift ;;
        -h|--help) usage ;;
        *) log_error "Unknown parameter: $1"; usage ;;
    esac
    shift
done

# --- Execution ---

check_dependencies
check_cluster_connection

log_info "Target Namespace: $NAMESPACE"
log_info "Source Path: $CHART_PATH"

# Ensure namespace exists
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    log_info "Namespace '$NAMESPACE' not found. Creating it..."
    kubectl create namespace "$NAMESPACE"
fi

# Detect deployment mode: Helm Chart vs Raw Manifest
if [[ -f "$CHART_PATH/Chart.yaml" ]]; then
    # --- HELM DEPLOYMENT (Preferred) ---
    log_info "Detected Helm Chart at $CHART_PATH. Running Helm upgrade/install..."
    
    helm upgrade --install "$DEPLOYMENT_NAME" "$CHART_PATH" \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --wait \
        --timeout 5m
        
    if [[ $? -eq 0 ]]; then
        log_info "Helm release '$DEPLOYMENT_NAME' deployed successfully."
    else
        log_error "Helm deployment failed."
        exit 1
    fi

elif [[ -f "$CHART_PATH" || -f "$CHART_PATH/templates/deployment.yaml" ]]; then
    # --- MANIFEST FALLBACK (Legacy) ---
    # Handle case where user points to a folder or specific file
    TARGET_FILE="$CHART_PATH"
    if [[ -d "$CHART_PATH" ]]; then
        TARGET_FILE="$CHART_PATH/templates/deployment.yaml"
    fi
    
    log_warn "No Chart.yaml found. Falling back to kubectl apply on: $TARGET_FILE"
    
    # Check if the file actually exists
    if [[ ! -f "$TARGET_FILE" ]]; then
        log_error "Manifest file not found at $TARGET_FILE"
        exit 1
    fi

    kubectl apply -f "$TARGET_FILE" -n "$NAMESPACE"
else
    log_error "Invalid path provided. Could not find Chart.yaml or deployment manifest at $CHART_PATH"
    exit 1
fi

# --- Verification ---

log_info "Verifying rollout status..."
# Attempt to find the deployment name dynamically if possible, or use the standard name
kubectl rollout status deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=60s || \
kubectl rollout status deployment/otel-collector -n "$NAMESPACE" --timeout=60s

if [[ $? -eq 0 ]]; then
    echo -e "\n${GREEN}✔ OpenTelemetry Collector is up and running!${NC}"
else
    echo -e "\n${RED}✘ Rollout failed or timed out. Check logs with: kubectl logs -l app=$DEPLOYMENT_NAME -n $NAMESPACE${NC}"
    exit 1
fi
