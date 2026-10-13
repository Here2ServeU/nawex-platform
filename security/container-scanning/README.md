# Container Scanning

This folder contains baseline assets for image vulnerability and container policy scanning.

## Goals
- Fail builds on `HIGH`/`CRITICAL` vulnerabilities.
- Keep scanner behavior consistent across local and CI runs.
- Track suppressions with expiration and rationale.

## Files
- `trivy-ignore.txt`: Controlled vulnerability suppressions.
- `trivy.yaml`: Standard scanner configuration.
- `scan-images.sh`: Batch image scanner for core Golden platform images.

## Local Usage
```bash
bash security/container-scanning/scan-images.sh
```

## CI Usage
Use `.github/workflows/security-scan.yml` for repository-wide scanning and this folder for image-specific standards.
