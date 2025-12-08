# Engineering Knowledge Base & Architecture

This directory serves as the **Single Source of Truth** for the platform's architectural design, decision records, and operational guides.

Following the **"Docs-as-Code"** methodology, all documentation is version-controlled alongside the application code. This ensures that the documentation evolves in lockstep with the infrastructure, preventing the common "stale wiki" problem.

## Directory Structure

### 1. Architectural Deep Dives
* **File:** `splunk-observability.md`
* **Focus:** **Observability Strategy.**
* **Content:** Detailed explanation of the logging pipeline architecture. It covers:
    * **Data Flow:** How logs move from Kubernetes Pods -> Splunk Universal Forwarder -> Splunk Indexers.
    * **Design Decisions:** Why we chose the Universal Forwarder for node-level logging vs. the HEC (HTTP Event Collector) for serverless functions.
    * **Index Strategy:** How data is segregated (e.g., `main` vs. `audit`) to meet retention and security compliance policies.

### 2. Diagrammatic Source Code (`diagrams/`)
* **Focus:** **Visual Architecture.**
* **Content:** Contains the *source code* for system diagrams, primarily using **Mermaid.js** (`.mmd`).
    * `splunk-architecture.mmd`: The sequence diagram defining the telemetry ingestion path.
* **Why Code?** Unlike static PNGs, these text-based diagrams can be edited, versioned, and rendered dynamically by GitHub. This allows us to "refactor" our architecture diagrams just like we refactor code.

## Documentation Standards

**1. Context over Config**
We do not duplicate `values.yaml` settings here. Instead, we explain the *intent* behind those settings (e.g., "Why did we set the HEC buffer size to 50MB?").

**2. Living Artifacts**
Every major Pull Request that changes the architecture (e.g., adding a new Service Mesh) must include a corresponding update to these documents.

**3. Incident Readiness**
These docs are written for the "3 AM On-Call Engineer." They prioritize clarity, mental models, and links to relevant runbooks over abstract theory.

## Usage

**To Edit Diagrams:**
We use the Mermaid syntax. You can preview changes directly in the GitHub UI or using a local IDE plugin.

```mermaid
graph TD;
    A[App Pod] -->|Logs| B(Splunk Forwarder);
    B -->|TCP| C{Splunk Cloud};
````

### Interview Talking Point
> I treat documentation as a first-class engineering citizen. In this `docs/` folder, I implement a **'Docs-as-Code'** strategy. For example, my `splunk-architecture.mmd` allows me to version-control my diagrams. If I change the architecture in Terraform, I update the diagram in the same PR. This guarantees that my system documentation never drifts from the actual state of production, which is critical for reducing MTTR during incidents.
