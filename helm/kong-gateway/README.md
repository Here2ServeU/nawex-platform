# Kong API Gateway & Ingress Controller

This directory contains the Helm chart for deploying **Kong**, the cloud-native API Gateway. Kong serves as the **Unified Ingress Layer** for the platform, managing all external traffic entering the Kubernetes cluster.

Unlike a simple load balancer, Kong is configured here to act as an **API Governance Enforcement Point**, offloading critical logic (authentication, rate limiting, logging) from the microservices themselves.

## Directory Structure

* **`Chart.yaml`**: Defines the chart version and declares the dependency on the official Kong chart.
* **`values.yaml`**: The configuration layer. Defines SRE standards for:
    * **Proxy Settings:** Configures the LoadBalancer service to accept HTTP/HTTPS traffic.
    * **Ingress Controller:** Enables the controller to watch for standard Kubernetes `Ingress` resources.
    * **Plugins:** Globally enables plugins like `prometheus` (for metrics) and `correlation-id` (for tracing).
* **`templates/`**: Custom Custom Resource Definitions (CRDs) and configs.
    * `kong-plugin-ratelimit.yaml`: Defines global rate-limiting policies (e.g., 100 req/min per IP).
    * `kong-consumer.yaml`: Manages credentials for specific API consumers (services or external partners).
    * `ingress-class.yaml`: Registers Kong as the default ingress class for the cluster.

## Core Capabilities & SRE Value

### 1. Centralized API Security (Zero Trust)
* **Problem:** "Spaghetti Auth." Every microservice implementing its own authentication logic leads to bugs and security holes.
* **Solution:** We offload authentication to the Gateway. Kong validates JWTs (JSON Web Tokens) or handles OAuth2 flows *before* the request ever reaches the backend service.
* **Impact:** **Hardened Security Posture.** If a request reaches the backend, we know it is already authenticated. The backend developers focus on business logic, not auth code.

### 2. Traffic Control & DDoS Protection
* **Problem:** A single abusive client or a buggy script taking down the entire platform by flooding APIs.
* **Solution:** We apply **Rate Limiting** policies as Code via `KongPlugin` resources.
* **Impact:** **System Stability.** We can cap traffic at the edge, ensuring that Tier-1 services remain available even during traffic spikes.

### 3. Observability at the Edge
* **Problem:** Losing visibility into request latency before it hits the application pod.
* **Solution:** The Kong Prometheus plugin emits "Golden Signals" (Latency, Traffic, Errors, Saturation) for every single route.
* **Impact:** **Full-Stack Visibility.** We can detect network issues or 504 Gateway Timeouts immediately, often before the application even registers an error.

## Usage Guide

**To Expose a Service via Kong:**
Developers do not need to edit this chart. They simply add an annotation to their service's Ingress resource:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-service
  annotations:
    kubernetes.io/ingress.class: kong
    [konghq.com/plugins](https://konghq.com/plugins): global-rate-limit, request-transformer
spec:
  rules:
    - host: api.myplatform.com
      http:
        paths:
          - path: /my-service
            pathType: ImplementationSpecific
            backend:
              service:
                name: my-service
                port:
                  number: 80
```
