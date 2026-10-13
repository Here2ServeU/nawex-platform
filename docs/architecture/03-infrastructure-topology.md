# 03: Multi-Cloud Infrastructure Topology

## Executive Overview

This document outlines the target global footprint of the **Golden Platform**. The goal is to minimise downtime for clinical operations with a **Multi-Cloud Active-Active** strategy.

> **What is implemented today:** independent per-cloud landing zones in [`deploy/terraform/live`](../../deploy/terraform) (AWS, Azure, GCP, OCI) and OpenShift assets. The global load balancer, cross-cluster mesh and private interconnects described below are **design targets** — there is no GSLB or cross-cloud replication code in the repository. See [CLAIMS.md](../CLAIMS.md).

The target orchestration layer spans Amazon Web Services (AWS), Microsoft Azure, **Google Cloud Platform (GCP)**, and Oracle Cloud Infrastructure (OCI), managed via a unified [Terraform](../../deploy/terraform) and GitOps workflow.

## Global Distribution Map

The target design distributes workloads across the following managed Kubernetes clusters so that a regional or provider outage can be survived (not yet validated by a drill):

| Cloud Provider | Managed Service | Primary Region | Role |
| --- | --- | --- | --- |
| **AWS** | [Elastic Kubernetes Service (EKS)](../../deploy/terraform) | `us-east-1` | Primary Inference Plane |
| **Azure** | [Azure Kubernetes Service (AKS)](../../deploy/terraform) | `eastus` | Disaster Recovery & Data Sync |
| **GCP** | [Google Kubernetes Engine (GKE)](../../deploy/terraform) | `us-central1` | **AI/ML Model Training & Big Data Analytics** |
| **OCI** | [Oracle Container Engine (OKE)](../../deploy/terraform) | `us-ashburn-1` | High-Performance Robotics Edge Aggregator |

## Networking & Interconnectivity

* **Global Traffic Management** *(design target)*: An Anycast-based Global Load Balancer (GLB) would route clinical telemetry to the nearest healthy cluster based on latency and health checks.
* **Service Mesh Architecture**: An Istio-based service mesh ([`deploy/helm/service-mesh`](../../deploy/helm/service-mesh)) is intended to provide secure, cross-cluster communication with mTLS, ensuring sensitive healthcare data is encrypted in transit between clouds.
* **GCP Cloud Interconnect** *(design target)*: Would leverage Google’s dedicated backbone for high-speed synchronization of [robotics telemetry](../../src/golden/robotics) datasets used in training the [LSTM/TCN models](../../src/golden/ai).
* **Private Interconnects** *(design target)*: Where available, Equinix Fabric or provider-specific interconnects (e.g., AWS Direct Connect to Azure ExpressRoute) are leveraged to minimize latency.

## Infrastructure as Code (IaC) Standards

All infrastructure is declared using modular [Terraform](../../deploy/terraform) code.

* **Module Reusability**: Standardized modules for VPC/VNet/VPC (GCP), IAM/RBAC, and K8s node groups ensure environmental parity.
* **State Management**: Remote state is stored in KMS-encrypted, versioned buckets with a lock table ([`modules/aws/backend`](../../deploy/terraform/modules/aws/backend)) to prevent race conditions during high-frequency [GitOps](../../deploy/gitops) deployments.

---

### Key Portfolio Enhancement

By adding **GCP (GKE)** specifically for **Model Training**, you demonstrate a sophisticated understanding of cloud specialization: using AWS/Azure for reliable web/inference and GCP for its superior data-processing capabilities.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
