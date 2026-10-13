# Least Privilege Matrix

## Human Roles
| Role | Scope | Typical Permissions | Notes |
| --- | --- | --- | --- |
| Platform Admin | Platform-wide | Cluster admin, CI/CD settings, emergency break-glass | Restricted and audited |
| SRE Operator | Runtime operations | Read logs/metrics, restart workloads, manage incidents | No IAM policy authoring |
| Security Auditor | Compliance review | Read-only access to logs, configs, and reports | No mutation rights |
| Developer | Service namespace | Deploy owned services, read namespace logs | No production-wide rights |

## Workload Roles
| Workload | Required Access | Denied Access |
| --- | --- | --- |
| App/API services | Read secrets for own namespace, publish metrics | Cross-namespace secret access |
| AI workers | Read model/config artifacts, write inference logs | Admin APIs, cluster mutation |
| Fintech services | Payment queue/topic access, scoped KMS decrypt | Unscoped storage and IAM admin |
| Healthcare services | PHI-safe data store read/write in scoped namespace | Broad object store listing |

## Control Requirements
- Enforce short-lived credentials where possible.
- Rotate static credentials and keys on a schedule.
- Keep service permissions namespaced and purpose-specific.
