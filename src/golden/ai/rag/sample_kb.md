# Access control policy
Production access is granted through IAM Identity Center permission sets mapped to Active Directory groups. Standing administrator access is prohibited; the BreakGlassAdmin permission set is limited to one-hour sessions and every use is reviewed by security within one business day.

# Cardholder data (PCI DSS)
Primary account numbers must never be stored after authorization. Card data in transit is encrypted with TLS 1.2 or higher and the cardholder data environment is segmented from all other networks. Access to cardholder data is reviewed quarterly.

# Protected health information (HIPAA)
Protected health information is encrypted at rest with AES-256 and in transit with TLS. Every access to a patient record is written to a tamper-evident audit log retained for six years. The minimum-necessary standard applies to every disclosure.

# AI agent operations
Every AI agent has a registered identity, an owning team, a tool allowlist and per-run and per-day budgets. Agents that loop are stopped automatically by loop detection, and the kill switch halts all autonomous actions within seconds. The failed-run tax is reviewed weekly.

# Incident response
Severity one incidents page the on-call engineer within five minutes. The incident commander posts an update every thirty minutes and a blameless postmortem is published within five business days.
