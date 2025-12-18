# AI Worker Isolated Helm Chart

This chart deploys an isolated Celery worker environment as part of the [express-reliability-aiops-platform](https://github.com/Here2ServeU/express-reliability-aiops-platform).

## Features
- **Namespace Isolation**: Deploys into a dedicated `ai-worker-isolated` namespace.
- **Physical Isolation**: Uses Node Affinity to target specific worker nodes.
- **Security**: Includes a Network Policy to restrict cross-package communication.

## Prerequisites
- Kubernetes 1.19+
- Helm 3+
- Redis broker provisioned via [Terraform Redis module](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/terraform/modules/redis).

## Installation
To install the chart with the release name `my-worker`:
```bash
helm install my-worker ./helm/redis
