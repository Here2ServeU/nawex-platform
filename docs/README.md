# Engineering Knowledge Base & Architecture

This directory serves as the **Single Source of Truth** for the platform's architectural design, decision records, and operational guides.

Following the **"Docs-as-Code"** methodology, all documentation is version-controlled alongside the application code. This ensures that the documentation evolves in lockstep with the infrastructure, preventing the common "stale wiki" problem.

## Directory Structure

### Architectural Deep Dives
These documents detail the implementation strategies for our observability backends.

* **File:** [`splunk-observability.md`](./splunk-observability.md)
    * **Focus:** **Log Aggregation Strategy.**
    * **Key Decisions:** Universal Forwarder vs. HEC, Index Segmentation (`main` vs. `audit`), and Data Retention policies.

* **File:** [`prometheus-grafana.md`](./prometheus-grafana.md)
    * **Focus:** **Open Source Metrics & Alerting.**
    * **Key Decisions:** "Pull" model architecture, `ServiceMonitor` CRD usage, and "Dashboards-as-Code" lifecycle management.

* **File:** [`datadog-observability.md`](./datadog-observability.md)
    * **Focus:** **Unified SaaS Monitoring.**
    * **Key Decisions:** Agent-based collection (DaemonSet), APM trace sampling rates, and Cost Management (custom metrics filtering).

* **File:** [`dynatrace-intelligence.md`](./dynatrace-intelligence.md)
    * **Focus:** **AI-Driven Root Cause Analysis.**
    * **Key Decisions:** OneAgent Operator deployment, Davis AI integration for automated problem detection, and "PurePath" distributed tracing.

### Diagrammatic Source Code (`diagrams/`)
* **Focus:** **Visual Architecture.**
* **Content:** Contains the *source code* for system diagrams, primarily using **Mermaid.js** (`.mmd`).
* **Why Code?** Unlike static PNGs, these text-based diagrams can be edited, versioned, and rendered dynamically.

## Documentation Standards
1. **Context over Config:** We explain the *why*, not just the *what*.
2. **Living Artifacts:** Every PR that changes the stack must update these docs.
3. **Incident Readiness:** Written for the "3 AM On-Call Engineer."

