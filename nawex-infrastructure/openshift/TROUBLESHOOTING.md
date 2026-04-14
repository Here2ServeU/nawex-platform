# OpenShift Troubleshooting Guide for NRP

## Quick Diagnostic Commands

```bash
# Basic cluster health check
oc version
oc cluster-info
oc get nodes

# Check all NRP resources
oc get all -A -l platform=openshift

# View recent events across namespaces
oc get events -A --sort-by='.lastTimestamp'
```

---

## Pod Issues

### 1. Pod Won't Start (CrashLoopBackOff)

**Symptoms**: Pod keeps restarting, never reaches Running state

**Diagnosis**:
```bash
oc describe pod <pod-name> -n <namespace>
oc logs <pod-name> -n <namespace>
oc logs <pod-name> -n <namespace> --previous # If it crashed

# Check for events
oc get events -n <namespace> | grep <pod-name>
```

**Common Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| Image not found | Check registry access: `oc describe pod -n <namespace>`<br> Verify image URL is correct<br> Check credentials |
| Insufficient resources | `oc describe node` to see available resources<br> Adjust CPU/memory requests<br> Scale down other workloads |
| SCC violation | `oc adm policy add-scc-to-user nrp-scc -z <sa> -n <ns>`<br> Check pod security context |
| Liveness probe failure | Check container logs<br> Adjust probe settings (initialDelaySeconds)<br> Verify application startup |
| Configuration error | Verify ConfigMaps/Secrets exist<br> Check environment variables<br> Review log output |

### 2. Pod Running but Not Ready

**Symptoms**: Pod shows Running but Ready=0/1

```bash
# Check readiness probe
oc describe pod <pod-name> -n <namespace> | grep -A 10 "Readiness"

# Test readiness manually
oc rsh <pod-name> -n <namespace> curl http://localhost:PORT/health

# View recent logs
oc logs <pod-name> -n <namespace> --tail=50
```

**Solutions**:
```bash
# Extend initial delay if app is slow to start
oc set probe deployment/<deployment> \
  --readiness --initial-delay-seconds=30 -n <namespace>

# Increase failure threshold
oc set probe deployment/<deployment> \
  --readiness --failure-threshold=5 -n <namespace>
```

### 3. Port/Service Connectivity

**Symptoms**: Cannot connect to service from another pod

```bash
# Verify service exists
oc get svc -n <namespace>

# Check endpoints
oc get endpoints <service-name> -n <namespace>

# Test DNS resolution
oc rsh <some-pod> -n <namespace> \
  nslookup <service-name>.<namespace>.svc.cluster.local

# Test connectivity from pod
oc rsh <pod-name> -n <namespace> \
  curl -v http://<service-name>:80/health
```

**Solutions**:
```bash
# If no endpoints, check pod selectors match service
oc get svc <service-name> -n <namespace> -o yaml | grep -A 5 selector
oc get pods -n <namespace> --show-labels

# Fix labels if needed
oc label pod <pod-name> app=<selector> -n <namespace>
```

---

## Deployment Issues

### 1. Rollout Stuck/Failed

**Diagnosis**:
```bash
oc rollout status deployment/<deployment> -n <namespace>
oc rollout history deployment/<deployment> -n <namespace>
oc describe deployment/<deployment> -n <namespace>
```

**Solutions**:
```bash
# Rollback to previous version
oc rollout undo deployment/<deployment> -n <namespace>

# Check current image
oc get deployment/<deployment> -n <namespace> -o yaml | grep image:

# Force restart pods
oc rollout restart deployment/<deployment> -n <namespace>
```

### 2. Insufficient Replicas

**Diagnosis**:
```bash
oc get deployment <name> -n <namespace>
oc describe deployment <name> -n <namespace> | grep -A 10 "Conditions:"
```

**Solutions**:
```bash
# Scale deployment
oc scale deployment <name> --replicas=3 -n <namespace>

# Check node resources
oc describe nodes

# Check if nodes have proper labels for scheduling
oc get nodes --show-labels
```

---

## Route/Networking Issues

### 1. Route Not Accessible

**Diagnosis**:
```bash
# Check route status
oc get route <route-name> -n <namespace>
oc describe route <route-name> -n <namespace>

# Verify service is healthy
oc get svc <service-name> -n <namespace>
oc get endpoints <service-name> -n <namespace>

# Check if service selector matches pods
oc get pods -n <namespace> --show-labels
```

**Solutions**:
```bash
# Create route if missing
oc expose svc <service-name> -n <namespace>

# Add TLS
oc create route edge <route-name> \
  --service=<service-name> \
  --insecure-policy=Redirect \
  -n <namespace>

# Check router (ingress controller) status
oc get pods -n openshift-ingress
```

### 2. Network Policy Blocking Traffic

**Diagnosis**:
```bash
# List network policies
oc get networkpolicies -n <namespace>

# Check specific policy
oc describe networkpolicy <policy-name> -n <namespace>
```

**Solutions**:
```bash
# Temporarily disable network policy for debugging
oc delete networkpolicy <policy-name> -n <namespace>

# Create more permissive policy
oc apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-all
  namespace: <namespace>
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - {}
  egress:
  - {}
EOF
```

---

## Storage Issues

### 1. PVC Not Bound

**Diagnosis**:
```bash
oc get pvc -n <namespace>
oc describe pvc <pvc-name> -n <namespace>

# Check available storage classes
oc get storageclass

# Check PV status
oc get pv
```

**Solutions**:
```bash
# Verify storage class exists or change storage class
oc patch pvc <pvc-name> -p '{"spec":{"storageClassName":"standard"}}' \
  -n <namespace>

# Check if nodes have local storage
oc get nodes -L kubernetes.io/hostname

# Remove and recreate PVC
oc delete pvc <pvc-name> -n <namespace>
# Update manifest with correct storageClassName
oc apply -f <manifest> -n <namespace>
```

### 2. Pod Can't Mount PVC

**Diagnosis**:
```bash
oc describe pod <pod-name> -n <namespace> | grep -A 20 "Volumes:"
oc get events -n <namespace> | grep <pod-name>
```

**Solutions**:
```bash
# Check mount permissions
oc rsh <pod-name> ls -la /path/to/mount

# Change PVC access mode if needed
# (Requires recreating PVC)
```

---

## Resource & Performance Issues

### 1. Out of Memory (OOMKilled)

**Diagnosis**:
```bash
oc describe pod <pod-name> -n <namespace> | grep -A 5 "Status: Failed"
oc logs <pod-name> -n <namespace> | tail -20
```

**Solutions**:
```bash
# Increase memory limit
oc set resources deployment <name> \
  --limits=memory=2Gi \
  --requests=memory=1Gi \
  -n <namespace>

# Check what's consuming memory
oc exec <pod-name> -n <namespace> -- free -h
oc exec <pod-name> -n <namespace> -- top
```

### 2. CPU Throttling

**Diagnosis**:
```bash
# Check resource requests vs actual usage
oc top pods -n <namespace>
oc top nodes

# View metrics over time (with metrics-server installed)
```

**Solutions**:
```bash
# Increase CPU allocation
oc set resources deployment <name> \
  --limits=cpu=2000m \
  --requests=cpu=500m \
  -n <namespace>

# Enable more replicas for scaling
oc scale deployment <name> --replicas=4 -n <namespace>
```

---

## Security Context Constraints (SCC)

### 1. SCC Violation ("unable to validate constraints")

**Diagnosis**:
```bash
# Check pod security context
oc get pod <pod-name> -n <namespace> -o yaml | grep -A 10 securityContext

# Check SCCs
oc get scc

# See which SCC applies to pod
oc describe pod <pod-name> -n <namespace> | grep kubernetes.io/scc
```

**Solutions**:
```bash
# Add SCC to service account
oc adm policy add-scc-to-user nrp-scc \
  -z <service-account> \
  -n <namespace>

# Or use the restricted SCC (default)
oc set serviceaccount deployment <name> <new-sa> -n <namespace>

# For debugging, temporarily use restricted-v2 (if available)
oc adm policy remove-scc-from-user <current-scc> \
  -z <sa> -n <namespace>
oc adm policy add-scc-to-user restricted-v2 \
  -z <sa> -n <namespace>
```

---

## Kafka/Zookeeper Issues

### 1. Kafka Broker Not Ready

**Diagnosis**:
```bash
oc get statefulset kafka -n nrp-platform
oc describe statefulset kafka -n nrp-platform
oc logs kafka-0 -n nrp-platform

# Check Zookeeper connectivity
oc exec kafka-0 -n nrp-platform -- \
  kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

**Solutions**:
```bash
# Restart Kafka cluster
oc rollout restart statefulset/kafka -n nrp-platform

# Check Zookeeper health first
oc logs zookeeper-0 -n nrp-platform

# Delete and recreate if needed (data loss!)
oc delete statefulset kafka -n nrp-platform
oc apply -f openshift/manifests/kafka-zookeeper.yaml
```

### 2. Zookeeper Quorum Lost

**Diagnosis**:
```bash
oc logs zookeeper-0 -n nrp-platform | grep "not a leader"
oc exec zookeeper-0 -n nrp-platform -- zkServer.sh status
```

**Solutions**:
```bash
# Ensure 3 zookeeper replicas running
oc get pods -l app=zookeeper -n nrp-platform

# Restore Zookeeper quorum
oc delete pod zookeeper-1 zookeeper-2 -n nrp-platform
# Let StatefulSet recreate them
```

---

## Debugging Tools

### 1. Terminal Access

```bash
# Exec into pod
oc exec -it <pod-name> -n <namespace> /bin/bash

# Or rsh (does not require /bin/bash)
oc rsh <pod-name> -n <namespace>
```

### 2. Port Forwarding

```bash
# Forward local port to service
oc port-forward svc/<service> 3000:80 -n <namespace>
# Access at http://localhost:3000

# Forward to pod
oc port-forward pod/<pod> 3000:3000 -n <namespace>
```

### 3. Log Aggregation

```bash
# Follow logs in real-time
oc logs -f pod/<pod> -n <namespace>

# Get logs from all pods in deployment
oc logs -f deployment/<deployment> -n <namespace>

# Get logs with timestamps
oc logs <pod> --timestamps=true -n <namespace>

# Get recent logs from crashed pod
oc logs <pod> --previous -n <namespace>
```

### 4. Debug Pod

```bash
# Create ephemeral debug container
oc debug pod/<pod> -n <namespace>

# Or create standalone debug pod
oc debug -it --image=rhel:8 -n <namespace>
```

---

## Health Checks

### Service Health Script

```bash
#!/bin/bash
namespace=${1:-nrp-platform}

echo "=== Cluster Health ==="
oc cluster-info
echo ""

echo "=== Nodes ==="
oc get nodes -L kubernetes.io/hostname
echo ""

echo "=== Pods Status ==="
oc get pods -n "$namespace" -o wide
echo ""

echo "=== Services ==="
oc get svc -n "$namespace"
echo ""

echo "=== Routes ==="
oc get routes -n "$namespace"
echo ""

echo "=== Recent Events ==="
oc get events -n "$namespace" --sort-by='.lastTimestamp' | tail -10
```

---

## Escalation

If issues persist:

1. **Collect diagnostic data**:
   ```bash
   oc adm must-gather --dest-dir=/tmp/nrp-diagnostic
   ```

2. **Check OpenShift events**:
   ```bash
   oc get events -A | grep -i error
   ```

3. **Review cluster logs**:
   ```bash
   oc logs -n openshift-apiserver -l app=openshift-apiserver --tail=100
   ```

4. **Contact support**:
   - Red Hat Support: https://access.redhat.com/
   - OpenShift Online Docs: https://docs.openshift.com/
   - NRP Issues: https://github.com/Here2ServeU/Naweji-Reliability-Platform/issues

---

**Last Updated**: February 2026 
**OpenShift Versions**: 4.10+

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
