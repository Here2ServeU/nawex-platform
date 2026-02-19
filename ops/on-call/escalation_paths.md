# Escalation Paths for NRP Platform

## Severity Levels
*P1 – Critical*
- Full outage of **NRP microservices** or **Backstage IDP**; major **PostgreSQL** data corruption/loss; confirmed security breach.
- Escalation:
1. Primary on-call
2. Secondary on-call
3. SRE / Platform Lead
4. Incident Manager / Duty Exec

*P2 – High*
- Partial outage of core services; **SLO breach** (e.g., high latency, Backstage Catalog ingestion lagging); **PostgreSQL** performance degradation.
- Escalation:
1. Primary on-call
2. Secondary on-call
3. Service Owner / Relevant Engineering Team Lead

*P3 – Medium*
- Degraded non-critical service (e.g., non-core Backstage plugin); non-urgent bug or failure in a secondary system.
- Escalation:
1. Primary on-call (during business hours)
2. Product / Engineering team

*P4 – Low*
- Cosmetic issues, low-priority tickets, or minor documentation discrepancies.

## Communication Channels
- PagerDuty / OpsGenie / custom webhook from Prometheus/Grafana (for automated alerts).
- Slack / Teams incident channel (e.g., #inc-<date>-<short-desc> ).
- Email summary to stakeholders for P2 and higher post-mortem.
