# Raw Kubernetes Manifests

This directory contains the **declarative YAML primitives** for deploying the application. While our production pipeline utilizes **Helm** charts (for templating) and **ArgoCD** (for GitOps), these files serve as the reference implementation for the underlying resources.

They demonstrate a clear understanding of core Kubernetes objects without the complexity of abstraction layers.

## Directory Structure

* **`namespace.yaml`**
    * Defines the logical isolation boundary (`apps`) for the workload.
    * **Why:** Prevents resource collisions and enables granular RBAC/Quota management.

* **`deployment.yaml`**
    * The primary workload definition.
    * **Key Features:** Defines the `ReplicaSet`, container image, resource requests/limits, and the `RollingUpdate` strategy to ensure zero-downtime deployments.

* **`service.yaml`**
    * Abstraction layer for pod discovery.
    * **Type:** `ClusterIP` (Internal only).
    * **Why:** Provides a stable virtual IP (VIP) and DNS name for the pods, regardless of their lifecycle.

* **`ingress.yaml`**
    * The external entry point.
    * **Function:** Routes external HTTP/HTTPS traffic to the internal `service`.
    * **Controller:** Configured for the standard Ingress Controller (e.g., Nginx or GCE).

* **`kafka-zookeeper.yaml`**
    * Internal Kafka + Zookeeper backbone.
    * **Function:** Provides a durable event stream for telemetry and async processing.
    * **Scope:** Cluster-internal only (no external listeners).

## Usage Guide (Manual)

These files are typically used for local development (Minikube/Kind) or debugging.

**1. Create the Namespace:**
```bash
kubectl apply -f namespace.yaml
````

**2. Deploy the Stack:**

```bash
kubectl apply -f . -n apps
```

**2a. Deploy Kafka + Zookeeper Only (optional):**

```bash
kubectl apply -f kafka-zookeeper.yaml -n apps
```

**3. Verify:**

```bash
kubectl get all -n apps
```

-----

### SRE Context: "Why Raw YAML?"

While Helm is superior for packaging, raw manifests are critical for **debugging**. When a Helm install fails, I inspect the rendered YAML against these primitives to identify if the issue lies in the template logic or the Kubernetes object definition itself.

```

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
