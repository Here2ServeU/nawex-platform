# RBAC Templates

This folder contains production-oriented RBAC examples for Kubernetes.

Principles:
- Least privilege by default.
- Separate roles for:
  - SRE / Platform
  - App Developers
  - Read-only Observers
- No direct cluster-admin for day-to-day work.
