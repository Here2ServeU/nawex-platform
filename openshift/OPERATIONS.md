# OpenShift Operations Guide for NRP

## Table of Contents
1. [Day 2 Operations](#day-2-operations)
2. [Monitoring & Alerting](#monitoring--alerting)
3. [Backup & Disaster Recovery](#backup--disaster-recovery)
4. [GitOps Integration](#gitops-integration)
5. [Performance Tuning](#performance-tuning)
6. [Security Hardening](#security-hardening)
7. [Cost Optimization](#cost-optimization)

---

## Day 2 Operations

### Health Monitoring

```bash
# Daily health check
oc get nodes
oc top nodes
oc get pods -A | grep -E "(CrashLoop|Pending|Unknown)"

# Check cluster capacity
oc describe nodes | grep -A 5 "Allocated resources"

# Verify cluster version
oc version
```

### Daily Maintenance

```bash
# Update deployments without downtime
oc set image deployment/nerp-dashboard \
  express=here2serveu/nrp-app:v1.1 \
  -n nrp-platform

# Monitor rollout
oc rollout status deployment/nerp-dashboard -n nrp-platform

# View deployment history
oc rollout history deployment/nerp-dashboard -n nrp-platform

# Rollback if needed
oc rollout undo deployment/nerp-dashboard -n nrp-platform
```

### Certificate Management

```bash
# Check route TLS status
oc describe route nerp-dashboard -n nrp-platform

# Renew certificates (handled automatically by OpenShift/Let's Encrypt)
# Monitor certificate expiration
oc get certificate -A

# For manual cert, create secret
oc create secret tls custom-cert \
  --cert=/path/to/cert.crt \
  --key=/path/to/key.key \
  -n nrp-platform
```

### Scaling Operations

```bash
# Manual scaling
oc scale deployment nerp-dashboard --replicas=5 -n nrp-platform

# Check HPA status
oc get hpa nerp-dashboard-hpa -n nrp-platform
oc describe hpa nerp-dashboard-hpa -n nrp-platform

# Adjust HPA limits
oc patch hpa nerp-dashboard-hpa -p \
  '{"spec":{"minReplicas":3,"maxReplicas":15}}' \
  -n nrp-platform

# View HPA metrics
oc get hpa nerp-dashboard-hpa -n nrp-platform -w
```

---

## Monitoring & Alerting

### Prometheus Metrics

```bash
# Verify metrics are being scraped
oc get servicemonitor -A -l app=naweji-reliability-platform

# Port-forward to Prometheus (if available)
oc port-forward svc/prometheus 9090:9090 -n openshift-monitoring

# Query metrics
oc exec -it <prometheus-pod> -n openshift-monitoring -- \
  /bin/sh -c 'curl localhost:9090/api/v1/query?query=container_cpu_usage_seconds_total'
```

### Custom Metrics

Create Prometheus rules for NRP:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: nrp-rules
  namespace: nrp-platform
spec:
  groups:
    - name: nrp.rules
      interval: 30s
      rules:
        # Express app metrics
        - alert: ExpressAppHighErrorRate
          expr: rate(http_requests_total{job="express-app",status=~"5.."}[5m]) > 0.05
          for: 5m
          annotations:
            summary: "Express app error rate high"

        # Kafka metrics
        - alert: KafkaMissingPartitionLeader
          expr: kafka_controller_kafkacontroller_offline_partitions_count > 0
          for: 5m
          annotations:
            summary: "Kafka partition missing leader"

        # Healthcare metrics
        - alert: EHRIngestionLatencyHigh
          expr: histogram_quantile(0.99, ehr_ingestion_duration_seconds) > 5
          for: 10m
          annotations:
            summary: "EHR ingestion latency high"

        # Fintech metrics
        - alert: FraudDetectionLatencyHigh
          expr: histogram_quantile(0.99, fraud_detection_duration_seconds) > 0.5
          annotations:
            summary: "Fraud detection latency > 500ms"
```

### Logging Integration

```bash
# With ELK Stack
oc create secret generic elasticsearch-credentials \
  --from-literal=username=elastic \
  --from-literal=password=changeme \
  -n nrp-platform

# Configure Fluentd to ship logs
oc apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: nrp-platform
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush 5
        Daemon Off
        Log_Level info

    [INPUT]
        Name tail
        Path /var/log/containers/*.log
        Parser docker
        Tag kube.*
        Refresh_Interval 5

    [OUTPUT]
        Name es
        Match kube.*
        Host elasticsearch.example.com
        Port 9200
        HTTP_User elastic
        HTTP_Passwd ${ELASTICSEARCH_PASSWORD}
EOF
```

---

## Backup & Disaster Recovery

### Persistent Data Backup

```bash
# Backup Kafka data
oc get pvc -n nrp-platform
oc create job backup-kafka-$(date +%s) --from=cronjob/backup-kafka -n nrp-platform

# Backup application configuration
oc get cm,secret -n nrp-platform -o yaml > nrp-config-backup.yaml

# Schedule regular backups with CronJob
oc apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-kafka
  namespace: nrp-platform
spec:
  schedule: "0 2 * * *" # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: nrp-platform-sa
          containers:
          - name: backup
            image: rhel:8
            command:
            - /bin/bash
            - -c
            - |
              oc get pvc -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | \
              while read pvc; do
                echo "Backing up $pvc"
                # Your backup logic here
              done
          restartPolicy: OnFailure
EOF
```

### Cluster Backup (etcd)

```bash
# Manual etcd backup (requires cluster-admin)
oc debug node/<node-name> -t -- chroot /host /usr/local/bin/etcd-snapshot-backup.sh /tmp/etcd-backup

# View backup
oc debug node/<node-name> -t -- chroot /host -- ls -la /tmp/etcd-backup/
```

### Recovery Procedures

```bash
# Restore from backup
# 1. Stop all control plane services
# 2. Restore etcd backup
# 3. Start control plane services

# For application-level recovery:
# Redeploy from manifests/Helm
oc apply -f openshift/manifests/

# Or restore from ConfigMap backup
oc apply -f nrp-config-backup.yaml
```

---

## GitOps Integration

### OpenShift GitOps (ArgoCD)

```bash
# Install OpenShift GitOps operator via OperatorHub

# Create ArgoCD instance
oc apply -f - <<EOF
apiVersion: argoproj.io/v1beta1
kind: ArgoCD
metadata:
  name: openshift-gitops
  namespace: openshift-gitops
spec:
  server:
    route:
      enabled: true
  controller:
    processors:
      resources: 4
EOF

# Create ArgoCD application for NRP
oc apply -f - <<EOF
apiVersion: argoproj.io/v1beta1
kind: Application
metadata:
  name: nrp-platform
  namespace: openshift-gitops
spec:
  project: default
  source:
    repoURL: https://github.com/Here2ServeU/Naweji-Reliability-Platform
    targetRevision: HEAD
    path: openshift/manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: nrp-platform
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF

# Get ArgoCD admin password
oc extract secret/openshift-gitops-cluster -n openshift-gitops --to=-

# Access ArgoCD UI
oc get route openshift-gitops-server -n openshift-gitops -o jsonpath='{.spec.host}'
```

### Flux Integration

```bash
# Install Flux
flux bootstrap github \
  --owner=Here2ServeU \
  --repo=Naweji-Reliability-Platform \
  --path=openshift/manifests \
  --personal

# Create Flux manifest
flux create source git nrp-repo \
  --url=https://github.com/Here2ServeU/Naweji-Reliability-Platform \
  --branch=main \
  --interval=1m

flux create kustomization nrp \
  --source=git/nrp-repo \
  --path=./openshift/manifests \
  --prune=true \
  --interval=10m
```

---

## Performance Tuning

### Pod Resource Optimization

```bash
# Analyze actual vs requested resources
oc top pods -n nrp-platform

# Adjust based on actual usage
oc set resources deployment nerp-dashboard \
  --requests=cpu=300m,memory=256Mi \
  --limits=cpu=700m,memory=512Mi \
  -n nrp-platform

# Use VPA for automatic adjustment
oc apply -f - <<EOF
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: express-app-vpa
  namespace: nrp-platform
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nerp-dashboard
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: express
      minAllowed:
        cpu: 100m
        memory: 128Mi
      maxAllowed:
        cpu: 1000m
        memory: 1Gi
EOF
```

### Network Performance

```bash
# Configure Service QoS
oc apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: network-qos
  namespace: nrp-platform
data:
  config: |
    {
      "classBasedQueueing": {
        "enabled": true,
        "queueLength": 1000,
        "queues": [
          {"priority": 1, "bandwidth": "100Mbps"},
          {"priority": 2, "bandwidth": "50Mbps"}
        ]
      }
    }
EOF

# Monitor network performance
oc exec <pod> -n <namespace> -- iftop
```

### Storage Performance

```bash
# Check storage class performance characteristics
oc get storageclass -o wide

# For high-performance Kafka storage
oc patch storageclass fast -p \
  '{"provisioner":"local.storage.openshift.io","allowVolumeExpansion":true}'
```

---

## Security Hardening

### Enhanced RBAC

```bash
# Create least-privilege service account for operator
oc create role fraud-checker-role \
  --verb=list,get \
  --resource=transactions

oc create rolebinding fraud-checker-binding \
  --role=fraud-checker-role \
  --serviceaccount=nrp-fintech:nrp-fintech-sa
```

### Network Security

```bash
# Implement default-deny network policy
oc apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: nrp-platform
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
EOF

# Then explicitly allow required connections
oc apply -f openshift/manifests/network-policies.yaml
```

### Secret Encryption

```bash
# Enable encryption at rest for etcd
oc patch apiserver cluster -p '{"spec":{"encryption":{"type":"aescbc"}}}' --type merge

# Use sealed-secrets for GitOps
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml

# Encrypt secrets for git
echo -n 'my-secret' | kubectl seal -f - > secret.yaml
```

---

## Cost Optimization

### Resource Right-Sizing

```bash
# Identify over-provisioned pods
oc top pods -A --containers | sort -k4 -rn

# Set accurate requests based on historical usage
oc set resources deployment nerp-dashboard \
  --requests=cpu=150m,memory=200Mi \
  -n nrp-platform
```

### Spot Instances (AWS)

```bash
# Configure node selector for cost optimization
oc apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nerp-dashboard
  namespace: nrp-platform
spec:
  template:
    spec:
      nodeSelector:
        karpenter.sh/capacity-type: spot
      tolerations:
      - key: karpenter.sh/capacity-type
        operator: Equal
        value: spot
        effect: NoSchedule
EOF
```

### Workload Prioritization

```bash
# Create priority classes
oc apply -f - <<EOF
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical-apps
value: 1000
globalDefault: false
description: "For critical production workloads"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: low-priority
value: 100
globalDefault: false
description: "For non-critical workloads"
EOF

# Use priority classes in deployments
spec:
  template:
    spec:
      priorityClassName: critical-apps
```

---

## Useful Commands Reference

```bash
# General cluster info
oc cluster-info
oc version
oc whoami
oc auth can-i create deployments --list

# Resource management
oc get all -A
oc top nodes
oc top pods -A
oc describe node <node>
oc events -A --sort-by='.lastTimestamp'

# Application management
oc get pods -o wide
oc logs <pod>
oc exec -it <pod> -- bash
oc debug pod/<pod>
oc port-forward svc/<service> 8080:80

# Scaling and updates
oc scale deployment/<name> --replicas=3
oc set image deployment/<name> <container>=<image>
oc rollout status deployment/<name>
oc rollout undo deployment/<name>

# Network and routes
oc get svc -A
oc get routes -A
oc expose svc/<name>
oc port-forward pod/<pod> 8080:8080

# Secrets and config
oc create secret generic <name> --from-literal=key=value
oc create configmap <name> --from-literal=key=value
oc get secrets
oc get configmaps
```

---

**Last Updated**: February 2026 
**Platform Version**: Latest

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
