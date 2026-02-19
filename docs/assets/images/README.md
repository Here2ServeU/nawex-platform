# Visual Architecture & Design Assets

This directory contains the high-level diagrams and visual artifacts that document the **Naweji Reliability Platform (NRP)**. These images are referenced throughout the repository documentation to illustrate complex workflows, from the GitOps pipeline to the AIOps self-healing loops.

## Asset Catalog

### 1. System Architecture
* **File:** `architecture-diagram.png`
* **Description:** A high-level overview of the entire platform ecosystem. It visualizes the relationship between the Multi-Cloud Infrastructure (Terraform), the Kubernetes Control Plane (GKE), the Observability Stack (Splunk/Prometheus), and the Application Layer (Express.js).
* **Key Concept:** Demonstrates the **"Hub-and-Spoke"** design where the AIOps Engine sits at the center of the observability pipeline.

### 2. The AIOps Loop
* **File:** `aiops-selfhealing-pipeline.png`
* **Description:** Illustrates the closed-loop automation process:
    1.  **Detect:** Telemetry data flows into the AIOps engine.
    2.  **Predict:** The LSTM model forecasts an anomaly.
    3.  **Act:** The system triggers an auto-scaling event or circuit breaker.
* **Key Concept:** Visual proof of the transition from **Reactive** to **Predictive** reliability.

### 3. GitOps Workflow
* **File:** `gitops-workflow.png`
* **Description:** Detailed flow of the Continuous Delivery pipeline. Shows how code moves from a GitHub Pull Request -> CI Checks -> Container Registry -> Flux/ArgoCD Synchronization -> Production Cluster.
* **Key Concept:** Enforces the **"Code is Law"** philosophy, where no manual changes are allowed in production.

### 4. Observability & Tracing
* **File:** `opentelemetry-trace.png`
* **Description:** A sample visualization of a distributed trace captured by the OpenTelemetry Collector. It highlights how a single user request is tracked across multiple microservices, exposing latency bottlenecks and error roots.
* **Key Concept:** Demonstrates **Deep Observability** beyond simple metrics.

---

## Usage
These images are embedded in the root `README.md` and module-specific documentation using standard Markdown syntax:

```markdown
![System Architecture](./assets/images/architecture-diagram.png)
````

### Talking Point
> I keep a dedicated `assets` folder because I believe **Visual Communication** is a core SRE skill. When I'm explaining a complex incident to leadership or onboarding a new engineer, having a clear `architecture-diagram.png` or `gitops-workflow.png` is often more valuable than the code itself. It proves I understand the *system design*, not just the syntax.
