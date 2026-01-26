# 03: Multi-Cloud Infrastructure Topology

## Executive Overview

This document outlines the global footprint of the **Express-Reliability AIOps Platform**. To ensure zero-downtime for clinical operations, the infrastructure utilizes a **Multi-Cloud Active-Active** strategy. The orchestration layer spans Amazon Web Services (AWS), Microsoft Azure, and Oracle Cloud Infrastructure (OCI), managed via a unified [Terraform](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/terraform) and GitOps workflow.

## Global Distribution Map

The platform is architected to survive a complete regional or provider outage by distributing workloads across the following managed Kubernetes clusters:

| Cloud Provider | Managed Service | Primary Region | Role |
| --- | --- | --- | --- |
| **AWS** | [Elastic Kubernetes Service (EKS)](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/terraform) | `us-east-1` | Primary Inference Plane |
| **Azure** | [Azure Kubernetes Service (AKS)](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/terraform) | `eastus` | Disaster Recovery & Data Sync |
| **OCI** | [Oracle Container Engine (OKE)](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/terraform) | `us-ashburn-1` | High-Performance Robotics Edge Aggregator |

## Networking & Interconnectivity

* **Global Traffic Management**: Utilizes an Anycast-based Global Load Balancer (GLB) to route clinical telemetry to the nearest healthy cluster based on latency and health checks.
* **Service Mesh Architecture**: An Istio-based service mesh facilitates secure, cross-cluster communication with mTLS, ensuring sensitive healthcare data is encrypted in transit between clouds.
* **Private Interconnects**: Where available, Equinix Fabric or provider-specific interconnects (e.g., AWS Direct Connect to Azure ExpressRoute) are leveraged to minimize latency for real-time [robotics telemetry](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/robotics).

## Infrastructure as Code (IaC) Standards

All infrastructure is declared using modular [Terraform](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/terraform) code.

* **Module Reusability**: Standardized modules for VPC/VNet, IAM/RBAC, and K8s node groups ensure environmental parity.
* **State Management**: Remote state is stored in encrypted buckets with object locking to prevent race conditions during high-frequency [GitOps](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/gitops) deployments.

---

### Next Steps for Your Portfolio

1. Create the file `docs/architecture/03-infrastructure-topology.md` in your repository.
2. Populate it with the content above to show recruiters you can handle massive scale.
