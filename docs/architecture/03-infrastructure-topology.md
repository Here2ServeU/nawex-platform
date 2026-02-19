# 03: Multi-Cloud Infrastructure Topology

## Executive Overview

This document outlines the global footprint of the **Naweji Reliability Platform (NRP)**. To ensure zero-downtime for clinical operations, the infrastructure utilizes a **Multi-Cloud Active-Active** strategy. The orchestration layer spans Amazon Web Services (AWS), Microsoft Azure, **Google Cloud Platform (GCP)**, and Oracle Cloud Infrastructure (OCI), managed via a unified [Terraform](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/terraform) and GitOps workflow.

## Global Distribution Map

The platform is architected to survive a complete regional or provider outage by distributing workloads across the following managed Kubernetes clusters:

| Cloud Provider | Managed Service | Primary Region | Role |
| --- | --- | --- | --- |
| **AWS** | [Elastic Kubernetes Service (EKS)](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/terraform) | `us-east-1` | Primary Inference Plane |
| **Azure** | [Azure Kubernetes Service (AKS)](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/terraform) | `eastus` | Disaster Recovery & Data Sync |
| **GCP** | [Google Kubernetes Engine (GKE)](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/terraform) | `us-central1` | **AI/ML Model Training & Big Data Analytics** |
| **OCI** | [Oracle Container Engine (OKE)](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/terraform) | `us-ashburn-1` | High-Performance Robotics Edge Aggregator |

## Networking & Interconnectivity

* **Global Traffic Management**: Utilizes an Anycast-based Global Load Balancer (GLB) to route clinical telemetry to the nearest healthy cluster based on latency and health checks.
* **Service Mesh Architecture**: An Istio-based service mesh facilitates secure, cross-cluster communication with mTLS, ensuring sensitive healthcare data is encrypted in transit between clouds.
* **GCP Cloud Interconnect**: Leverages Google’s dedicated backbone for high-speed synchronization of [robotics telemetry](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/robotics) datasets used in training the [LSTM/TCN models](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/ai).
* **Private Interconnects**: Where available, Equinix Fabric or provider-specific interconnects (e.g., AWS Direct Connect to Azure ExpressRoute) are leveraged to minimize latency.

## Infrastructure as Code (IaC) Standards

All infrastructure is declared using modular [Terraform](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/terraform) code.

* **Module Reusability**: Standardized modules for VPC/VNet/VPC (GCP), IAM/RBAC, and K8s node groups ensure environmental parity.
* **State Management**: Remote state is stored in encrypted buckets with object locking to prevent race conditions during high-frequency [GitOps](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/gitops) deployments.

---

### Key Portfolio Enhancement

By adding **GCP (GKE)** specifically for **Model Training**, you demonstrate a sophisticated understanding of cloud specialization: using AWS/Azure for reliable web/inference and GCP for its superior data-processing capabilities.

