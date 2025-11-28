# On-Call Policy for Express Web Platform

## Objectives
- Ensure 24/7 coverage for **Express T2S microservices** and the **Backstage IDP**.
- Minimize mean-time-to-detect (MTTD) and mean-time-to-resolve (MTTR) for platform issues.
- Provide a humane, sustainable rotation for engineers.

## Coverage Model
- Primary on-call: 1 engineer (Responsible for first response and mitigation)
- Secondary on-call: 1 engineer (Responsible for complex diagnosis and escalation support)
- Shadow on-call (optional, trainees)

## Expectations
- Acknowledge P1 (Critical) pages within 5 minutes, initiating the defined **P1 Escalation Path**.
- Acknowledge P2 (High) pages within 15 minutes, initiating the defined **P2 Escalation Path**.
- Utilize the official runbooks in `/ops/playbooks` and `/ops/dr` for incident resolution.
- All changes for mitigation must go through **GitOps (ArgoCD/Flux)** where technically feasible, ensuring auditability.
- Avoid direct production changes unless under documented 'break-glass' protocol.

## Handover
- Daily handoff notes recorded in Slack / Teams, summarizing shift status.
- Review all open incidents, ongoing investigations, and high-risk platform areas during the handoff meeting.
- Confirm next on-call engineer has access to all required tooling and documentation.
