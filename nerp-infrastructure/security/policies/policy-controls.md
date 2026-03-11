# Security Policy Controls

## Mandatory Controls
- Containers must run as non-root.
- Privileged containers are prohibited.
- HostPath mounts require explicit approval.
- Images must pass HIGH/CRITICAL vulnerability scanning before deploy.
- Secrets must not be committed to version control.

## Enforcement Levels
- `block`: Prevent merge/deploy when violated.
- `warn`: Flag in CI and create follow-up tasks.
- `observe`: Collect telemetry and tune control.

## Current Baseline
- Container security controls: `block`
- Dependency vulnerabilities: `block` for HIGH/CRITICAL
- IaC misconfiguration: `block` for HIGH/CRITICAL
- Secret leakage detection: `block`
