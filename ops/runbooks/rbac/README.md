# Role-Based Access Control (RBAC) for Golden Platform

This folder contains production-oriented RBAC templates for Kubernetes, ensuring compliance with **least privilege** principles and supporting **SOC 2 control** objectives. Access is segmented based on operational need for the Golden Platform microservices and the Backstage IDP infrastructure.

## Core Principles

* **Least Privilege:** Users and service accounts are granted only the permissions essential to perform their required tasks.
* **Auditability:** All production access is tracked, logged, and reviewed.
* **No Cluster-Admin:** Direct `cluster-admin` access is restricted to break-glass scenarios only.

## Defined Roles

| Role | Primary Responsibilities | Access Level Summary | Template Example |
| :--- | :--- | :--- | :--- |
| **SRE / Platform** | Incident response, infrastructure management, GitOps tool administration. | Full control over Namespace resources, exec access to specific platform pods (e.g., PostgreSQL for debug). | [`k8s_rbac_sre.yaml`](./k8s_rbac_sre.yaml) |
| **App Developers** | Deploying/managing their own microservices, viewing logs/metrics. | CRUD (Create, Read, Update, Delete) on Deployment, Service, ConfigMap for *their* Namespace; Read-only for other infrastructure. | (Template not included, but defined) |
| **Read-only Observers** | Auditing, monitoring, troubleshooting by viewing resources. | Read-only access to most resources (Pods, Events, Logs, Services) across non-sensitive Namespaces. | [`k8s_rbac_readonly.yaml`](./k8s_rbac_readonly.yaml) |

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
