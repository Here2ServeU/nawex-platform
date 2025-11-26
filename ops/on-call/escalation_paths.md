# Escalation Paths

## Severity Levels

- **P1 – Critical**
  - Full outage, major data loss, or security breach.
  - Escalation:
    1. Primary on-call
    2. Secondary on-call
    3. SRE / Platform Lead
    4. Incident Manager / Duty Exec

- **P2 – High**
  - Partial outage, SLO at risk, incident requiring fast response.
  - Escalation:
    1. Primary on-call
    2. Secondary on-call
    3. Service Owner

- **P3 – Medium**
  - Degraded non-critical service, non-urgent bug.
  - Escalation:
    1. Primary on-call (during business hours)
    2. Product / Engineering team

- **P4 – Low**
  - Cosmetic issues, low-priority tickets.

## Communication Channels
- PagerDuty / OpsGenie / custom webhook from Prometheus/Grafana.
- Slack / Teams incident channel (e.g., `#inc-<date>-<short-desc>`).
