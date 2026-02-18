# OpenShift Deployment Guide for Naweji Reliability Platform

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Detailed Deployment](#detailed-deployment)
5. [Configuration](#configuration)
6. [Security](#security)
7. [Monitoring & Observability](#monitoring--observability)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)
10. [Scaling](#scaling)

## Overview

This guide covers deploying the **Naweji Reliability Platform (NRP)** on **Red Hat OpenShift Container Platform (RHOCP)** with full support for:

- **Healthcare Services**: HIPAA-compliant EHR ingestion, clinical decision support
- **Fintech Services**: PCI-DSS compliant fraud detection, payment processing
- **Platform Core**: Express web app, Kafka event backbone, monitoring
- **Robotics Services**: Real-time gRPC telemetry processing

### Key Benefits of OpenShift Deployment

✅ **Enterprise Security**: Built-in RBAC, SCCs, network policies, and audit logging  
✅ **Operator Framework**: Automated lifecycle management with Red Hat operators  
✅ **GitOps**: Integrated with OpenShift GitOps (ArgoCD)  
✅ **Developer Experience**: OpenShift Console, Source-to-Image (S2I) builds  
✅ **Compliance**: Native support for compliance monitoring and policy enforcement  
✅ **RHEL-based**: Runs on Red Hat Enterprise Linux with full support  

---

## Prerequisites

### Required Tools
```bash
# OpenShift CLI (oc) - Download from https://console-openshift-console.apps.<cluster>/command-line-tools
oc version

# Helm 3.0+
helm version

# kubectl (usually installed with oc)
kubectl version

# Docker CLI (for image builds, optional)
docker version
```

### OpenShift Cluster Requirements

- **OpenShift 4.10+** (tested on 4.12, 4.13, 4.14)
- **Minimum Nodes**: 3 worker nodes
- **Minimum Resources per Node**:
  - CPU: 4 cores (32 cores recommended for production)
  - Memory: 8GB RAM (64GB recommended for production)
  - Storage: 100GB per node

### Access Requirements

1. Administrative or developer-level access to OpenShift cluster
2. Ability to create namespaces and set SCCs
3. Access to container registry (e.g., quay.io, Red Hat registry)
4. Ability to create routes and services

### Network Requirements

- Outbound internet access for pulling container images
- Internal cluster networking enabled (CNI plugin configured)
- DNS resolution for route hostnames
- Load balancer for external traffic (automatic with OpenShift routes)

---

## Quick Start

### 1. Login to OpenShift Cluster

```bash
# Login with token (get from OpenShift web console)
oc login --token=<your-token> --server=https://<api-server>:6443

# Or use credentials
oc login -u <username> -p <password> https://<api-server>:6443

# Verify connection
oc whoami
oc cluster-info
```

### 2. Deploy Using Automated Script

```bash
# Make scripts executable
chmod +x scripts/deploy-openshift.sh
chmod +x scripts/deploy-openshift-helm.sh

# Deploy with manifests
scripts/deploy-openshift.sh

# Or deploy with Helm
scripts/deploy-openshift-helm.sh
```

### 3. Verify Deployment

```bash
# Check all namespaces
oc get ns -l app=naweji-reliability-platform

# List all pods across namespaces
oc get pods -A -l platform=openshift

# View platform routes
oc get routes -A -l platform=openshift

# Monitor deployment
oc get pods -A -w
```

---

## Detailed Deployment

### Step-by-Step Manual Deployment

#### 1. Create Namespaces

```bash
oc apply -f openshift/manifests/namespace.yaml

# Verify namespaces
oc get ns -l app=naweji-reliability-platform
```

**Namespaces created:**
- `nrp-platform`: Core platform services (Express app, API)
- `nrp-healthcare`: Healthcare services (EHR, Clinical Decision)
- `nrp-fintech`: Fintech services (Fraud Detection, Payment Gateway)
- `nrp-robotics`: Robotics and edge services

#### 2. Apply Security Context Constraints

```bash
oc apply -f openshift/manifests/scc-nrp.yaml

# Verify SCCs
oc get scc nrp-scc nrp-privileged-scc
```

**NRP SCC**: Restricted security model for standard workloads  
**NRP Privileged SCC**: For robotics and edge workloads requiring elevated privileges

#### 3. Setup Service Accounts and RBAC

```bash
oc apply -f openshift/manifests/service-accounts.yaml

# Verify service accounts
oc get sa -A -l app=naweji-reliability-platform

# Link SCCs to service accounts
oc adm policy add-scc-to-user nrp-scc \
  -z nrp-platform-sa -n nrp-platform \
  -z nrp-healthcare-sa -n nrp-healthcare \
  -z nrp-fintech-sa -n nrp-fintech \
  -z nrp-robotics-sa -n nrp-robotics
```

#### 4. Deploy Kafka & Zookeeper (Event Backbone)

```bash
# Apply Kafka and Zookeeper manifests
oc apply -f openshift/manifests/kafka-zookeeper.yaml -n nrp-platform

# Monitor deployment
oc wait --for=condition=ready pod -l app=kafka -n nrp-platform --timeout=600s
oc wait --for=condition=ready pod -l app=zookeeper -n nrp-platform --timeout=600s

# Verify
oc get statefulsets -n nrp-platform
oc logs -f kafka-0 -n nrp-platform
```

#### 5. Deploy Express Web Application

```bash
oc apply -f openshift/manifests/express-app-deployment.yaml -n nrp-platform

# Monitor rollout
oc rollout status deployment/express-web-app -n nrp-platform

# Get route URL
oc get route express-web-app -n nrp-platform
# Access at: https://express-web-app-nrp-platform.apps.<cluster>/
```

#### 6. Deploy Healthcare Services

```bash
oc apply -f openshift/manifests/healthcare-deployment.yaml -n nrp-healthcare

# Monitor deployment
oc rollout status deployment/ehr-ingestion-service -n nrp-healthcare

# Get route URLs
oc get routes -n nrp-healthcare
```

#### 7. Deploy Fintech Services

```bash
oc apply -f openshift/manifests/fintech-deployment.yaml -n nrp-fintech

# Monitor deployment
oc rollout status deployment/fraud-detection-service -n nrp-fintech

# Get route URLs
oc get routes -n nrp-fintech
```

---

## Configuration

### Environment Variables

Edit the manifest files to customize environment variables:

#### Healthcare Services

```yaml
env:
  - name: FHIR_VERSION
    value: "R4"
  - name: HIPAA_AUDIT_LOG_ENABLED
    value: "true"
  - name: HIPAA_ENCRYPTION_ENABLED
    value: "true"
  - name: PHI_MASKING_ENABLED
    value: "true"
  - name: LOG_LEVEL
    value: "info"
```

#### Fintech Services

```yaml
env:
  - name: PCI_DSS_ENABLED
    value: "true"
  - name: ENCRYPTION_AT_REST
    value: "true"
  - name: ENCRYPTION_IN_TRANSIT
    value: "true"
  - name: FRAUD_DETECTION_THRESHOLD
    value: "0.75"
  - name: ML_MODEL_VERSION
    value: "v1"
```

### Helm Values Override

Use OpenShift-specific Helm values for customization:

```bash
# Express App
helm upgrade --install express-app helm/express-app \
  -f openshift/helm-values/express-app-values.yaml \
  -n nrp-platform \
  --create-namespace

# Healthcare Services
helm upgrade --install healthcare helm/healthcare \
  -f openshift/helm-values/healthcare-values.yaml \
  -n nrp-healthcare \
  --create-namespace

# Fintech Services
helm upgrade --install fintech helm/fintech \
  -f openshift/helm-values/fintech-values.yaml \
  -n nrp-fintech \
  --create-namespace
```

### Persistent Storage

Configure persistent volumes for data:

```yaml
# Add persistent storage for Kafka
volumeClaimTemplates:
  - metadata:
      name: kafka-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: "standard"  # or your OpenShift storage class
      resources:
        requests:
          storage: 100Gi
```

---

## Security

### Network Policies

Applied by default in manifests to restrict traffic:

```bash
# View applied network policies
oc get networkpolicies -A -l platform=openshift

# Example: Allow only nrp-platform to access fintech namespace
oc create networkpolicy allow-nrp-platform \
  --deny-all \
  --allow-from-selector app=nrp-platform \
  -n nrp-fintech
```

### Security Context Constraints

```bash
# Verify SCCs are bound to service accounts
oc describe scc nrp-scc

# Add additional SCCs as needed
oc adm policy add-scc-to-user anyuid \
  -z special-sa -n nrp-robotics  # For robotics with special requirements
```

### RBAC and Access Control

```bash
# View roles and bindings
oc get roles,rolebindings -A -l app=naweji-reliability-platform

# Create custom role for additional access
oc create role custom-admin --verb=* --resource=pods,configmaps
oc create rolebinding custom-admin-binding --clusterrole=admin --serviceaccount=nrp-platform:nrp-platform-sa
```

### Secret Management

Store sensitive data using OpenShift secrets:

```bash
# Create secret for database credentials
oc create secret generic db-credentials \
  --from-literal=username=admin \
  --from-literal=password=secure-password \
  -n nrp-healthcare

# Reference in deployment
oc set env deployment/ehr-ingestion-service \
  --from=secret/db-credentials \
  -n nrp-healthcare
```

---

## Monitoring & Observability

### Integration with Prometheus/Grafana

NRP exports Prometheus metrics on port 3000 and 8080:

```bash
# Create ServiceMonitor for Prometheus Operator
oc apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: nrp-platform
  namespace: nrp-platform
spec:
  selector:
    matchLabels:
      app: express-web-app
  endpoints:
  - port: http
    interval: 30s
EOF
```

### Viewing Logs

```bash
# Stream logs from specific pod
oc logs -f pod/express-web-app-xyz -n nrp-platform

# View logs from all pods in deployment
oc logs -f deployment/fraud-detection-service -n nrp-fintech

# View logs by label
oc logs -f -l app=ehr-ingestion-service -n nrp-healthcare

# Get logs with timestamps
oc logs pod/express-web-app-xyz --timestamps=true -n nrp-platform
```

### OpenShift Web Console

Access monitoring dashboards:

```bash
# Get console URL
oc get route console -n openshift-console -o jsonpath='{.spec.host}'

# Or navigate to: https://console-openshift-console.apps.<cluster>
```

---

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting

```bash
# Check pod status and events
oc describe pod <pod-name> -n <namespace>

# Check for image pull errors
oc get events -n <namespace> --sort-by='.lastTimestamp'

# View pod logs
oc logs <pod-name> -n <namespace>
```

#### 2. SCC Violations

```bash
# Check if pod violates SCC
oc get pod <pod-name> -n <namespace> -o yaml | grep -A 5 securityContext

# View SCC requirements
oc describe scc nrp-scc

# Fix: Make sure service account has SCC
oc adm policy add-scc-to-user nrp-scc -z <service-account> -n <namespace>
```

#### 3. Route Not Accessible

```bash
# Check route status
oc get route <route-name> -n <namespace>

# Verify service endpoints
oc get endpoints <service-name> -n <namespace>

# Test connectivity from inside cluster
oc rsh <pod-name> -n <namespace> curl -v http://<service-name>:80/health
```

#### 4. PVC Issues

```bash
# Check PVC status
oc get pvc -n <namespace>

# Describe PVC for details
oc describe pvc <pvc-name> -n <namespace>

# Check available storage classes
oc get storageclass
```

### Debugging

```bash
# Get shell access to a pod
oc rsh pod/<pod-name> -n <namespace>

# Debug pod (creates debugging pod)
oc debug pod/<pod-name> -n <namespace>

# Port forward for local testing
oc port-forward service/express-web-app 3000:80 -n nrp-platform
# Then access: http://localhost:3000
```

---

## Best Practices

### 1. Resource Management
- Set CPU and memory requests/limits for all containers
- Use HPA (Horizontal Pod Autoscaler) for scaling
- Monitor resource usage in OpenShift Console

### 2. High Availability
- Run minimum 2 replicas for critical services
- Use pod disruption budgets to prevent cascading failures
- Configure pod anti-affinity to spread across nodes

### 3. Compliance & Security
- Keep audit logging enabled
- Regularly review RBAC and SCC bindings
- Use network policies to restrict traffic
- Encrypt secrets at rest (configure in OpenShift)

### 4. Observability
- Enable Prometheus scraping for metrics
- Configure distributed tracing (Jaeger) for fintech/healthcare
- Use structured logging (JSON format)
- Set up alerting for critical thresholds

### 5. Disaster Recovery
- Enable automated backups of persistent data
- Test failover procedures regularly
- Document recovery runbooks
- Maintain off-site backup of cluster configuration

### 6. Updates & Maintenance
- Use rolling updates (RollingUpdate strategy)
- Test updates in non-production first
- Plan maintenance windows for infrastructure changes
- Keep OpenShift and container images updated

---

## Scaling

### Horizontal Pod Autoscaling

```bash
# Verify HPA is active
oc get hpa -n nrp-platform
oc describe hpa express-web-app-hpa -n nrp-platform

# Manual scaling
oc scale deployment express-web-app --replicas=5 -n nrp-platform

# Scale fintech services during peak hours
oc scale deployment fraud-detection-service --replicas=10 -n nrp-fintech
```

### Vertical Pod Autoscaling (Optional)

Install VPA operator for automatic resource request/limit optimization:

```bash
# Install VPA operator from OperatorHub
# Then create VPA resource:
oc apply -f - <<EOF
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: express-app-vpa
  namespace: nrp-platform
spec:
  targetRef:
    apiVersion: "apps/v1"
    kind: Deployment
    name: express-web-app
  updatePolicy:
    updateMode: "Auto"
EOF
```

### Cluster Scaling

```bash
# Add worker nodes via OpenShift (depends on infrastructure)
# AWS: Use machine sets in openshift-machine-api
oc get machines -n openshift-machine-api

# View machineset
oc get machineset -n openshift-machine-api

# Scale machinesets
oc scale machineset <machineset-name> --replicas=5 -n openshift-machine-api
```

---

## Next Steps

1. **Set up monitoring**: Install OpenShift Container Platform monitoring and Prometheus for metrics
2. **Configure GitOps**: Integrate with OpenShift GitOps (ArgoCD) for continuous deployment
3. **Enable logging**: Configure ELK, Splunk, or Datadog for centralized logging
4. **Setup CI/CD**: Integrate with OpenShift Pipelines (Tekton) for automation
5. **Advanced networking**: Configure service mesh (Istio/OpenShift ServiceMesh) for traffic management
6. **Compliance auditing**: Enable PCI-DSS/HIPAA compliance monitoring

---

## Support & Documentation

- **OpenShift Documentation**: https://docs.openshift.com/
- **Red Hat Support**: https://access.redhat.com/
- **NRP GitHub**: https://github.com/Here2ServeU/Naweji-Reliability-Platform
- **OpenShift Operators**: https://operatorhub.io/

---

**Last Updated**: February 2026  
**OpenShift Version**: 4.10+  
**Platform Version**: Latest
