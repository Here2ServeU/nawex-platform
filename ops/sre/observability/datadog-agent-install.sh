#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
#
# Datadog Agent Deployment Script
# Description: Deploys the Datadog Agent (DaemonSet) and Cluster Agent via Helm.
# Automatically enables APM, Logs, and Process Monitoring.
# Usage: ./datadog-agent-install.sh [-n <namespace>] [-s <site>]
#
# Prerequisite: DD_API_KEY environment variable must be set.
#

set -euo pipefail

# --- Configuration & Colors ---
DEFAULT_NAMESPACE="observability"
DEFAULT_SITE="datadoghq.com"
RELEASE_NAME="datadog-agent"
HELM_REPO_URL="https://helm.datadoghq.com"

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
    echo -e " -n, --namespace <ns> Kubernetes namespace (Default: $DEFAULT_NAMESPACE)"
    echo -e " -s, --site <site> Datadog Site (e.g., datadoghq.eu) (Default: $DEFAULT_SITE)"
    echo -e " -h, --help Show this help message"
    echo -e "\n${BLUE}Example:${NC}"
    echo -e " export DD_API_KEY=your_key_here"
    echo -e " $0 -n monitoring -s datadoghq.com"
    exit 1
}

check_dependencies() {
    local missing=0
    for cmd in kubectl helm; do
        if ! command -v $cmd &> /dev/null; then
            log_error "'$cmd' is not installed."
            missing=1
        fi
    done

    if [[ -z "${DD_API_KEY:-}" ]]; then
        log_error "DD_API_KEY environment variable is not set."
        log_warn "Run: export DD_API_KEY=<your_api_key>"
        missing=1
    fi
    
    if [[ $missing -eq 1 ]]; then
        exit 1
    fi
}

# --- Argument Parsing ---

NAMESPACE="$DEFAULT_NAMESPACE"
DD_SITE="$DEFAULT_SITE"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -n|--namespace) NAMESPACE="$2"; shift ;;
        -s|--site) DD_SITE="$2"; shift ;;
        -h|--help) usage ;;
        *) log_error "Unknown parameter: $1"; usage ;;
    esac
    shift
done

# --- Execution ---

check_dependencies

log_info "Deploying Datadog Agent to namespace: $NAMESPACE"
log_info "Target Site: $DD_SITE"

# 1. Prepare Namespace
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    log_info "Creating namespace '$NAMESPACE'..."
    kubectl create namespace "$NAMESPACE"
fi

# 2. Update Helm Repo
log_info "Updating Datadog Helm repository..."
helm repo add datadog "$HELM_REPO_URL"
helm repo update

# 3. Install / Upgrade
# We enable generic observability features (Logs, APM, Process) to match the platform needs.
log_info "Running Helm upgrade..."

if ! helm upgrade --install "$RELEASE_NAME" datadog/datadog \
    --namespace "$NAMESPACE" \
    --set datadog.apiKey="$DD_API_KEY" \
    --set datadog.site="$DD_SITE" \
    --set datadog.logs.enabled=true \
    --set datadog.logs.containerCollectAll=true \
    --set datadog.apm.portEnabled=true \
    --set datadog.processAgent.enabled=true \
    --set clusterAgent.enabled=true \
    --set clusterAgent.metricsProvider.enabled=true \
    --set kube-state-metrics.enabled=true \
    --wait \
    --timeout 10m; then
    log_error "Helm installation failed."
    exit 1
fi

# 4. Verification
log_info "Verifying rollout status..."

# Check Cluster Agent, then the DaemonSet (Node Agents)
if kubectl rollout status deployment/"$RELEASE_NAME"-cluster-agent -n "$NAMESPACE" --timeout=60s \
    && kubectl rollout status daemonset/"$RELEASE_NAME" -n "$NAMESPACE" --timeout=60s; then
    echo -e "\n${GREEN} Datadog Agent deployed successfully!${NC}"
    echo -e " • Logs: Enabled"
    echo -e " • APM: Enabled"
    echo -e " • Process Agent: Enabled"
else
    echo -e "\n${RED} Verification failed. Check pods with: kubectl get pods -n $NAMESPACE${NC}"
    exit 1
fi
