# Naweji Reliability Platform - OpenShift Integration Summary

## Quick Reference

OpenShift support for NRP includes production-ready manifests, scripts, and documentation for deploying all platform services on Red Hat OpenShift Container Platform (RHEL-based).

### Files Created

```
openshift/
├── README.md                          ← Start here: Full deployment guide
├── TROUBLESHOOTING.md                 ← Common issues and solutions
├── OPERATIONS.md                      ← Day 2 operations & advanced features
├── manifests/
│   ├── namespace.yaml                 ← 4 namespaces for isolation
│   ├── scc-nrp.yaml                   ← Security Context Constraints
│   ├── service-accounts.yaml           ← RBAC configuration
│   ├── express-app-deployment.yaml     ← Main web application
│   ├── healthcare-deployment.yaml      ← EHR, Clinical Decision, Patient Gateway
│   ├── fintech-deployment.yaml         ← Fraud Detection, Payment Gateway, Transaction Engine
│   ├── kafka-zookeeper.yaml            ← Event backbone
│   ├── network-policies.yaml           ← Network security policies
│   ├── config-maps.yaml                ← Application configuration
│   └── pod-disruption-budgets.yaml     ← High availability guarantees
└── helm-values/
    ├── express-app-values.yaml         ← OpenShift-specific Helm values
    ├── healthcare-values.yaml
    └── fintech-values.yaml
```

### Quick Start Command

```bash
# Deploy everything in one command
bash scripts/deploy-openshift.sh

# Or with Helm
bash scripts/deploy-openshift-helm.sh
```

---

## Pre-Deployment Checklist

- [ ] OpenShift cluster 4.10+ available
- [ ] `oc` CLI installed and configured
- [ ] Logged into OpenShift: `oc login --token=<token> --server=https://<api>`
- [ ] Cluster admin or sufficient RBAC permissions
- [ ] Minimum 3 worker nodes with 4+ cores each
- [ ] Container registry access (quay.io or internal registry)
- [ ] DNS resolution for route hostnames
- [ ] Outbound internet for pulling images

---

## Deployment Steps

### Option 1: Automated Deployment (Recommended)

```bash
# Make scripts executable
chmod +x scripts/deploy-openshift.sh
chmod +x scripts/deploy-openshift-helm.sh

# Deploy all services
./scripts/deploy-openshift.sh

# Monitor progress
oc get pods -A -w

# Verify deployment
oc get routes -A -l platform=openshift
```

**Deployment Time**: 5-15 minutes

### Option 2: Manual Deployment (Step-by-Step)

```bash
# 1. Create namespaces
oc apply -f openshift/manifests/namespace.yaml

# 2. Setup security
oc apply -f openshift/manifests/scc-nrp.yaml
oc apply -f openshift/manifests/service-accounts.yaml

# 3. Link SCCs to service accounts
oc adm policy add-scc-to-user nrp-scc \
  -z nrp-platform-sa -n nrp-platform
# ... repeat for other service accounts and namespaces

# 4. Deploy infrastructure
oc apply -f openshift/manifests/kafka-zookeeper.yaml -n nrp-platform
oc apply -f openshift/manifests/network-policies.yaml
oc apply -f openshift/manifests/config-maps.yaml
oc apply -f openshift/manifests/pod-disruption-budgets.yaml

# 5. Deploy applications
oc apply -f openshift/manifests/express-app-deployment.yaml -n nrp-platform
oc apply -f openshift/manifests/healthcare-deployment.yaml -n nrp-healthcare
oc apply -f openshift/manifests/fintech-deployment.yaml -n nrp-fintech

# 6. Verify
oc get pods -A
oc get routes -A
```

### Option 3: Helm Deployment

```bash
# Prerequisites: helm 3.0+ installed
helm repo add nrp https://charts.here2serveu.com

# Deploy with Helm
helm upgrade --install nrp-platform nrp/express-app \
  -f openshift/helm-values/express-app-values.yaml \
  -n nrp-platform --create-namespace

helm upgrade --install nrp-healthcare nrp/healthcare \
  -f openshift/helm-values/healthcare-values.yaml \
  -n nrp-healthcare --create-namespace

helm upgrade --install nrp-fintech nrp/fintech \
  -f openshift/helm-values/fintech-values.yaml \
  -n nrp-fintech --create-namespace
```

---

## What Gets Deployed

### Platform Services (nrp-platform namespace)
- **Express Web App** (2-10 replicas, auto-scaling)
- **Kafka** (3-node StatefulSet for event backbone)
- **Zookeeper** (3-node for Kafka coordination)

### Healthcare Services (nrp-healthcare namespace) - HIPAA Compliant
- **EHR Ingestion Service** (FHIR R4)
- **Clinical Decision Support** (ML-based vital monitoring)
- **Patient Data Gateway** (HL7/FHIR interoperability)

### Fintech Services (nrp-fintech namespace) - PCI-DSS Compliant
- **Fraud Detection Service** (ML models, <50ms latency)
- **Payment Gateway Service** (multi-provider failover)
- **Transaction Engine** (settlement processing)

### Infrastructure
- **Routes**: TLS-terminated for all services via OpenShift router
- **Services**: ClusterIP type for internal communication
- **SCCs**: Custom restricted and privileged policies
- **RBAC**: Service accounts with minimal required permissions
- **Network Policies**: Default deny with explicit allowlists
- **HPA**: Auto-scaling based on CPU/memory metrics

---

## Service Access URLs

After deployment, services are accessible via OpenShift routes:

```bash
# Get all routes
oc get routes -A

# Example output:
# Express App: https://nerp-dashboard-nrp-platform.apps.<cluster>
# EHR Service: https://ehr-ingestion-nrp-healthcare.apps.<cluster>
# Fraud Detection: https://fraud-detection-nrp-fintech.apps.<cluster>
```

---

## Key OpenShift Features Used

| Feature | Benefit |
|---------|---------|
| **Routes** | TLS-terminated, public-facing endpoints (replaces Ingress) |
| **SCCs** | Fine-grained security enforcement for pod privileges |
| **Service Accounts** | Workload identity and RBAC |
| **Network Policies** | Microsegmentation and network security |
| **StatefulSets** | Ordered, durable Kafka deployment |
| **HPA** | Automatic scaling on metrics (CPU, memory) |
| **Pod Disruption Budgets** | High availability during node maintenance |
| **ConfigMaps** | Non-sensitive application configuration |
| **OpenShift Operator Lifecycle Manager** | App delivery and lifecycle management |

---

## Configuration & Customization

### Environment Variables

Edit manifests or Helm values to customize:

**Healthcare (HIPAA)**:
```yaml
env:
  - name: FHIR_VERSION
    value: "R4"
  - name: HIPAA_AUDIT_LOG_ENABLED
    value: "true"
  - name: HIPAA_ENCRYPTION_ENABLED
    value: "true"
```

**Fintech (PCI-DSS)**:
```yaml
env:
  - name: PCI_DSS_ENABLED
    value: "true"
  - name: FRAUD_DETECTION_THRESHOLD
    value: "0.75"
```

### Resource Allocation

Adjust CPU/memory per service:

```bash
oc set resources deployment/<name> \
  --requests=cpu=500m,memory=512Mi \
  --limits=cpu=2000m,memory=2Gi \
  -n <namespace>
```

### Scaling

```bash
# Manual scaling
oc scale deployment/<name> --replicas=5 -n <namespace>

# HPA auto-scaling (already configured)
oc get hpa -n <namespace>
```

---

## Security Best Practices

✅ **Applied by Default**:
- Non-root container security contexts
- ReadOnlyRootFilesystem where possible
- Capability dropping (CAP_DROP=ALL)
- Network policies with default-deny
- RBAC with least-privilege service accounts
- Pod disruption budgets for high availability
- Resource requests and limits

⚠️ **Additional Hardening**:
```bash
# Encrypt secrets at rest
oc patch apiserver cluster -p \
  '{"spec":{"encryption":{"type":"aescbc"}}}' --type merge

# Use sealed-secrets for GitOps-safe config
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml

# Enable audit logging
oc patch audit cluster --type merge -p '{"spec":{"profile":"Default"}}'
```

---

## Monitoring & Observability

Metrics are exposed on standard ports:
- **Express App**: Port 3000 (Prometheus format)
- **Healthcare/Fintech**: Port 8080
- **Kafka**: JMX on port 9092

Integration points:
- **Prometheus**: ServiceMonitor labels for automatic scraping
- **Grafana**: Pre-built dashboards available
- **OpenShift Console**: Built-in metrics visualization
- **Datadog/Splunk**: Forward logs via forwarders

See [OPERATIONS.md](OPERATIONS.md#monitoring--alerting) for detailed setup.

---

## Common Tasks

### Check Deployment Status

```bash
oc get pods -A -l platform=openshift
oc get deployments -A -l platform=openshift
oc rollout status deployment/<name> -n <namespace>
```

### View Logs

```bash
# Stream logs
oc logs -f deployment/<name> -n <namespace>

# Get logs from specific pod
oc logs <pod-name> -n <namespace>
```

### Access Shell

```bash
# Execute command in pod
oc exec -it <pod> -n <namespace> -- bash

# Interactive shell (no bash required)
oc rsh <pod> -n <namespace>
```

### Port Forward

```bash
# Access service locally
oc port-forward svc/<service> 8080:80 -n <namespace>
# Then: http://localhost:8080
```

### Update Image

```bash
oc set image deployment/<name> \
  <container>=<image>:<tag> \
  -n <namespace>
```

### Rollback

```bash
oc rollout undo deployment/<name> -n <namespace>
```

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for:
- Pod won't start (CrashLoopBackOff)
- Image pull errors
- SCC violations
- Route not accessible
- Storage issues
- Resource constraints
- And many more...

### Quick Diagnostics

```bash
# Check pod status and events
oc describe pod <pod-name> -n <namespace>

# View logs
oc logs <pod-name> -n <namespace>

# Check recent cluster events
oc get events -A --sort-by='.lastTimestamp'

# Verify cluster connectivity
oc cluster-info
```

---

## Day 2 Operations

### Backup Strategy

```bash
# Backup configuration
oc get cm,secret -n nrp-platform -o yaml > backup.yaml

# Regular snapshots with CronJob
# See OPERATIONS.md#backup--disaster-recovery
```

### GitOps Integration

Automate deployments with:
- **OpenShift GitOps** (ArgoCD) - Recommended
- **Flux** - Alternative
- **Jenkins/Tekton** - For CI/CD

See [OPERATIONS.md#gitops-integration](OPERATIONS.md#gitops-integration)

### Scaling & Performance

- Monitor with `oc top` commands
- Adjust HPA targets based on load
- Right-size resources using VPA recommendations
- Use Spot instances for cost savings

See [OPERATIONS.md#performance-tuning](OPERATIONS.md#performance-tuning)

---

## Support & Documentation

### Documentation Files
1. [README.md](README.md) - Full deployment guide
2. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Issue resolution
3. [OPERATIONS.md](OPERATIONS.md) - Day 2 operations

### External Resources
- [OpenShift Documentation](https://docs.openshift.com/)
- [OpenShift Community](https://www.openshift.com/community/)
- [Red Hat Support Portal](https://access.redhat.com/)
- [NRP GitHub Repository](https://github.com/Here2ServeU/Naweji-Reliability-Platform)

### Getting Help

```bash
# Collect diagnostic data
oc adm must-gather --dest-dir=/tmp/nrp-diagnostic

# Check operator logs
oc logs -n openshift-operators deployment/openshift-gitops-operator

# View cluster events
oc get events -A | grep -i error
```

---

## Compliance & Security

### HIPAA (Healthcare)
- ✅ Audit logging enabled
- ✅ Encryption at rest & in transit
- ✅ PHI masking
- ✅ FHIR R4 compliance
- ✅ Access control via RBAC

### PCI-DSS (Fintech)
- ✅ Network segmentation (network policies)
- ✅ Encryption (TLS routes + pod security)
- ✅ Access control (SCCs + RBAC)
- ✅ Logging & monitoring
- ✅ Vulnerability scanning

### SOC 2 Type II
- ✅ Audit trails
- ✅ Change tracking (GitOps)
- ✅ Availability monitoring
- ✅ Incident response

---

## Next Steps

1. **Deploy**: Run `./scripts/deploy-openshift.sh`
2. **Verify**: Check all pods running with `oc get pods -A`
3. **Configure**: Customize environment variables in ConfigMaps
4. **Monitor**: Set up Prometheus/Grafana for metrics
5. **GitOps**: Integrate with ArgoCD for continuous deployment
6. **Backup**: Enable automated backup strategy
7. **Harden**: Apply additional security measures from [OPERATIONS.md](OPERATIONS.md#security-hardening)

---

## Version Information

- **Platform Version**: Latest
- **OpenShift Versions**: 4.10 - 4.14+ (current)
- **Kubernetes**: 1.21+
- **Helm**: 3.0+
- **Last Updated**: February 2026

---

## Quick Reference Commands

```bash
# Deployment
./scripts/deploy-openshift.sh

# Status checks
oc get pods -A
oc get routes -A
oc top nodes
oc top pods -A

# Debugging
oc describe pod <pod> -n <ns>
oc logs <pod> -n <ns>
oc exec -it <pod> -n <ns> -- bash

# Scaling
oc scale deployment <name> --replicas=3 -n <ns>
oc patch hpa <name> -p '{"spec":{"maxReplicas":20}}'

# Updates
oc set image deployment/<name> <container>=<image> -n <ns>
oc rollout status deployment/<name> -n <ns>
oc rollout undo deployment/<name> -n <ns>
```

---

**Welcome to NRP on OpenShift! 🚀**

Start with [README.md](README.md) for the full deployment guide.
