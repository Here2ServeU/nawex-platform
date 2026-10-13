# Threat modeling: method

This page describes how the Golden platform builds threat models and keeps them current. The models
themselves are in [`security/threat-models/`](../../security/threat-models/README.md):

- [platform-stride.md](../../security/threat-models/platform-stride.md): API, services, governed actions, audit chain, CI/CD, cloud IAM
- [agentops-stride.md](../../security/threat-models/agentops-stride.md): LLM gateway, agent runner, RAG, tool use, mapped to the OWASP LLM Top 10 and MITRE ATLAS

A threat model is useful only if someone can check it against the code. Every mitigation therefore names
the file that implements it. A control that exists only in a document is recorded as a gap.

## 1. Draw the data-flow diagram (DFD)

Draw the system as a Mermaid `flowchart` in the model file, so it is reviewed in the same pull request as
the code. Use four element types:

| Element | Drawn as | Examples |
|---|---|---|
| External entity | node outside every boundary | user, IdP, model provider |
| Process | rectangle | platform API, action governor, LLM gateway |
| Data store | `[( )]` cylinder | audit log, vector index, checkpoints |
| Data flow | labelled arrow | `HTTPS + x-api-key`, `OIDC federation` |

Keep the diagram at the level where a security decision is made. One "domain services" node is enough
unless the services differ in who can reach them or what they hold.

## 2. Mark the trust boundaries

A trust boundary is any place where the level of trust changes: a network edge, a process that runs with
different privileges, a hand-off between organisations (IdP → cloud, platform → model provider), or the
point where a model's decision becomes an action. Draw each one as a Mermaid `subgraph` and list it in a
table with what crosses it and who sits on the far side. Most threats sit on a data flow that crosses a
boundary, so start the analysis there.

## 3. Apply STRIDE to each element

For each element and each boundary-crossing flow, go through the categories that apply:

| Category | Property violated | Typical question |
|---|---|---|
| **S**poofing | Authentication | Can someone act as another user, service or agent? |
| **T**ampering | Integrity | Can input, code, data or a log entry be changed? |
| **R**epudiation | Non-repudiation | Could someone credibly deny an action because nothing recorded it? |
| **I**nformation disclosure | Confidentiality | Can data reach someone who shouldn't see it? |
| **D**enial of service | Availability | Can someone exhaust capacity, budget or a quota? |
| **E**levation of privilege | Authorisation | Can someone gain rights they weren't granted? |

For AI components, also tag each threat with its OWASP LLM Top 10 (2025) ID and a MITRE ATLAS technique.
STRIDE tells you which property fails. OWASP and ATLAS give you the attack vocabulary that red teams and
auditors use, and they let you check coverage: each of the ten OWASP categories should map to at least one
threat, or have a written reason why it doesn't apply.

## 4. Rate the threats

Rate each threat with a qualitative Likelihood × Impact matrix:

| | Impact L | Impact M | Impact H |
|---|---|---|---|
| **Likelihood H** | Medium | High | High |
| **Likelihood M** | Low | Medium | High |
| **Likelihood L** | Low | Low | Medium |

Each row records two ratings:

- **Inherent**: the risk with no mitigation, shown in brackets.
- **Residual**: the risk after the mitigations that the cited files actually implement.

Whenever the residual rating is above Low, the row explains what remains. For example, "limiter state is per
process", or "ingest does not run the input guard". Each High residual, and each Medium residual that has a
known fix, gets a row under **Open actions** with a priority:

- P1: next sprint
- P2: this quarter
- P3: backlog

We chose a qualitative scale on purpose. The rating ranks the work, and agreeing on L/M/H is faster and
more consistent than arguing over CVSS-style decimals for design-level threats.

## 5. Record mitigations with evidence

Each mitigation cell names a file path in this repository: the module, policy, Terraform resource, workflow
or test that implements the control. Reviewers check three things:

1. The file exists. Paths are in backticks so a script can extract and check them.
2. The file does what the cell says.
3. Where possible, a test shows the control working. Examples: `tests/test_security.py` for the action
   governor, `golden agent verify` for the agent-ops cost controls, and `tests/test_identity_multicloud.py`
   for the cloud persona rules.

## 6. Review cadence

| Trigger | What to do |
|---|---|
| A PR adds a trust boundary, external integration, data store or autonomous action | Update the affected model in the same PR |
| Model, system-prompt or tool-allowlist change | Re-read `agentops-stride.md`. The red-team gate runs automatically. |
| Security incident or a new class of finding (Wiz, pen test, red team) | Add the threat and check whether its residual rating was wrong |
| Quarterly | Walk both models end to end, re-rate residual risk, close or re-prioritise open actions |

The quarterly review is owned by platform security, with the service owners of each element in the room.
The outcome is the updated model files, merged like any other change.
