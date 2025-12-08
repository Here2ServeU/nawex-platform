# Service Mesh & Zero Trust Networking

This directory contains the Helm chart for deploying the **Service Mesh** (e.g., Istio or Linkerd) control plane. This component acts as the transparent infrastructure layer that manages service-to-service communication, enforcing security, observability, and traffic rules without requiring changes to application code.

## Directory Structure

* **`Chart.yaml`**: Defines the chart metadata and dependencies.
* **`values.yaml`**: The configuration layer. Defines SRE standards for:
    * **mTLS Mode:** Enforces "Strict" mutual TLS to ensure no unencrypted traffic is allowed within the mesh.
    * **Proxy Resources:** Sets CPU/Memory limits for the sidecar proxies injected into every pod.
    * **Tracing:** Configures the mesh to send distributed trace spans to the OTel Collector.
* **`templates/`**:
    * `control-plane.yaml`: Deploys the mesh controller and identity service.
    * `peer-authentication.yaml`: Defines cluster-wide security policies (Zero Trust).
    * `sidecar-injector.yaml`: Configures the mutating webhook that automatically adds the proxy container to new pods.

## Core Capabilities & SRE Value

### 1. Zero Trust Security (mTLS)
* **Problem:** "Soft Internal Network." Once an attacker is inside the cluster, they can sniff traffic between services (e.g., frontend talking to the database).
* **Solution:** The mesh automatically encrypts all traffic between pods using **Mutual TLS (mTLS)**. It also manages certificate rotation automatically.
* **Impact:** **Compliance & Security.** We satisfy PCI-DSS and HIPAA encryption requirements without developers having to implement HTTPS in every single microservice.

### 2. Progressive Delivery (Canary Deployments)
* **Problem:** "Big Bang" deployments. Releasing a new version to 100% of users immediately carries a high risk of outage.
* **Solution:** The mesh enables **Traffic Splitting**. We can route 1% of traffic to `v2` and 99% to `v1`. If `v2` is healthy, we slowly increase the percentage.
* **Impact:** **Risk Mitigation.** We can test new code in production with real traffic while limiting the blast radius of any bugs.

### 3. Golden Signals without Instrumentation
* **Problem:** Legacy apps or third-party containers that don't emit metrics.
* **Solution:** The sidecar proxy sits in front of the app and measures every request. It generates Request Rate, Error Rate, and Latency metrics automatically.
* **Impact:** **Instant Observability.** We get uniform dashboards for every service in the cluster, even the ones we didn't write.

## Usage Guide

**To Deploy:**
This chart is deployed via ArgoCD.

**To Inject the Mesh:**
Developers simply add an annotation to their Deployment or Namespace:

```yaml
metadata:
  annotations:
    sidecar.istio.io/inject: "true"
````

**To Configure a Canary Split:**
Apply a `VirtualService` or `TrafficSplit` resource:

```yaml
spec:
  hosts:
  - my-service
  http:
  - route:
    - destination:
        host: my-service
        subset: v1
      weight: 90
    - destination:
        host: my-service
        subset: v2
      weight: 10
```

### Interview Talking Point:
> I introduced a **Service Mesh** to solve the 'Encryption at Rest vs. Encryption in Transit' problem. Managing SSL certificates for 50 microservices is a nightmare, so I offloaded it to the mesh. Now, we have **Strict mTLS** everywhere by default. It also gave us 'Red/Black' deployment capabilities for free—we can shift traffic percentages with a few lines of YAML, which is how we maintain 99.99% availability during deployments.
