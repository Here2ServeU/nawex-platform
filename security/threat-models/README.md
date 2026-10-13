# threat-models

STRIDE threat models for the Golden platform. Each threat links a mitigation to the file that implements it
and ends with a residual-risk rating, so the model can be checked against the code. Method, rating scale and
review cadence: [docs/security/threat-modeling.md](../../docs/security/threat-modeling.md).

| Model | Scope | Frameworks |
|---|---|---|
| [platform-stride.md](./platform-stride.md) | Platform API and services, governed actions, audit chain, CI/CD supply chain, cloud IAM (AWS / Azure / GCP) | STRIDE |
| [agentops-stride.md](./agentops-stride.md) | LLM gateway, agent runner, RAG, tool use, Envoy guard | STRIDE · OWASP LLM Top 10 (2025) · MITRE ATLAS |

Add a model when a change introduces a new trust boundary: copy the structure of an existing file (DFD,
trust boundaries, threat table, open actions) and add a row here.
