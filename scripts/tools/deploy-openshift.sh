#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/here2serveu/golden-platform
# ===========================================================================
# OpenShift Deployment Script for Golden Platform
# This script automates the deployment of NRP to OpenShift clusters
# Requirements: oc CLI installed and logged into OpenShift cluster

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_DOMAIN="${CLUSTER_DOMAIN:-apps.cluster.example.com}"
REGISTRY="${REGISTRY:-quay.io}"
REGISTRY_USER="${REGISTRY_USER:-here2serveu}"
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/deploy"
MANIFESTS_DIR="${DEPLOY_DIR}/openshift/manifests"
# shellcheck disable=SC2034 # used by the Helm-based variant
HELM_VALUES_DIR="${DEPLOY_DIR}/openshift/helm-values"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_oc_cli() {
    if ! command -v oc &> /dev/null; then
        log_error "oc CLI not found. Please install OpenShift CLI (oc) first."
        exit 1
    fi
    log_success "oc CLI found: $(oc version --client)"
}

check_cluster_connection() {
    if ! oc cluster-info &> /dev/null; then
        log_error "Not connected to OpenShift cluster. Please login first: oc login <cluster-url>"
        exit 1
    fi
    CLUSTER_INFO=$(oc cluster-info | head -1)
    log_success "Connected to cluster: $CLUSTER_INFO"
}

create_namespaces() {
    log_info "Creating OpenShift namespaces..."
    
    oc apply -f "${MANIFESTS_DIR}/namespace.yaml" || {
        log_error "Failed to create namespaces"
        return 1
    }
    
    log_success "Namespaces created successfully"
}

setup_security_contexts() {
    log_info "Setting up Security Context Constraints (SCCs)..."
    
    oc apply -f "${MANIFESTS_DIR}/scc-golden.yaml" || {
        log_error "Failed to create SCCs"
        return 1
    }
    
    log_success "SCCs created successfully"
}

setup_service_accounts() {
    log_info "Setting up Service Accounts and RBAC..."
    
    oc apply -f "${MANIFESTS_DIR}/service-accounts.yaml" || {
        log_error "Failed to create service accounts"
        return 1
    }
    
    # Link SCC to service accounts
    local scc="golden-scc"
    for sa in golden-platform-sa golden-healthcare-sa golden-fintech-sa golden-robotics-sa; do
        oc adm policy add-scc-to-user "$scc" -z "$sa" -n "$(oc get sa "$sa" -o jsonpath='{.metadata.namespace}' 2>/dev/null || echo 'golden-platform')" 2>/dev/null || true
    done
    
    log_success "Service accounts and RBAC configured"
}

deploy_kafka_zookeeper() {
    log_info "Deploying Kafka and Zookeeper..."
    
    oc apply -f "${MANIFESTS_DIR}/kafka-zookeeper.yaml" || {
        log_error "Failed to deploy Kafka/Zookeeper"
        return 1
    }
    
    log_info "Waiting for Kafka and Zookeeper to be ready..."
    oc wait --for=condition=ready pod -l app=kafka -n golden-platform --timeout=300s || true
    oc wait --for=condition=ready pod -l app=zookeeper -n golden-platform --timeout=300s || true
    
    log_success "Kafka and Zookeeper deployed"
}

deploy_express_app() {
    log_info "Deploying Express Web Application..."
    
    oc apply -f "${MANIFESTS_DIR}/express-app-deployment.yaml" || {
        log_error "Failed to deploy Express app"
        return 1
    }
    
    log_info "Waiting for Express app to be ready..."
    oc wait --for=condition=ready pod -l app=express-web-app -n golden-platform --timeout=300s || true
    
    EXPRESS_ROUTE=$(oc get route express-web-app -n golden-platform -o jsonpath='{.spec.host}' 2>/dev/null || echo "pending")
    log_success "Express app deployed. Access at: https://$EXPRESS_ROUTE"
}

deploy_healthcare() {
    log_info "Deploying Healthcare Services..."
    
    oc apply -f "${MANIFESTS_DIR}/healthcare-deployment.yaml" || {
        log_error "Failed to deploy Healthcare services"
        return 1
    }
    
    log_info "Waiting for Healthcare services to be ready..."
    oc wait --for=condition=ready pod -l app=ehr-ingestion-service -n golden-healthcare --timeout=300s || true
    
    log_success "Healthcare services deployed"
    
    # Display routes
    log_info "Healthcare service routes:"
    oc get routes -n golden-healthcare --no-headers 2>/dev/null | awk '{print " - https://" $2}' || true
}

deploy_fintech() {
    log_info "Deploying Fintech Services..."
    
    oc apply -f "${MANIFESTS_DIR}/fintech-deployment.yaml" || {
        log_error "Failed to deploy Fintech services"
        return 1
    }
    
    log_info "Waiting for Fintech services to be ready..."
    oc wait --for=condition=ready pod -l app=fraud-detection-service -n golden-fintech --timeout=300s || true
    
    log_success "Fintech services deployed"
    
    # Display routes
    log_info "Fintech service routes:"
    oc get routes -n golden-fintech --no-headers 2>/dev/null | awk '{print " - https://" $2}' || true
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    for ns in golden-platform golden-healthcare golden-fintech; do
        log_info "Checking namespace: $ns"
        oc get pods -n "$ns" -o wide
    done
    
    log_success "Deployment verification complete"
}

show_summary() {
    log_info "Deployment Summary:"
    echo ""
    echo " Golden Platform deployed to OpenShift"
    echo ""
    echo "Namespaces created:"
    oc get ns -l app=naweji-reliability-platform -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | sed 's/^/ - /'
    echo ""
    echo "Platform Routes:"
    oc get routes -A -l platform=openshift 2>/dev/null | tail -n +2 | awk '{print " - https://" $3}' || echo " No routes yet (they are being created)"
    echo ""
    echo "Pod Status:"
    for ns in golden-platform golden-healthcare golden-fintech; do
        count=$(oc get pods -n "$ns" 2>/dev/null | tail -n +2 | grep -c "Running" || echo "0")
        echo " $ns: $count pods running"
    done
    echo ""
    echo "Next steps:"
    echo " 1. Monitor deployment: oc get pods -A -w"
    echo " 2. View logs: oc logs -f pod/<pod-name> -n <namespace>"
    echo " 3. Access services via the routes listed above"
}

main() {
    log_info "Starting NRP deployment to OpenShift..."
    
    check_oc_cli
    check_cluster_connection
    
    create_namespaces
    setup_security_contexts
    setup_service_accounts
    
    log_info "Deploying core services..."
    deploy_kafka_zookeeper
    deploy_express_app
    
    log_info "Deploying domain-specific services..."
    deploy_healthcare
    deploy_fintech
    
    verify_deployment
    show_summary
    
    log_success "Deployment complete! "
}

# Handle errors
trap 'log_error "An error occurred during deployment"; exit 1' ERR

# Run main function
main "$@"
