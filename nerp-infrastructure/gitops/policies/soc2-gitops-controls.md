# SOC 2 Compliant GitOps Controls

**Security, Compliance, and Auditability Framework**

This repository is strictly architected to support **SOC 2 Type II** and **ISO 27001** compliance. By utilizing GitOps as the single source of truth, we enforce a strict separation of duties and maintain an immutable audit trail for all infrastructure changes.

---

## 1. Change Management & Peer Review

All modifications to the production environment—whether infrastructure or application code—must follow a strict lifecycle:

* **Pull Request Requirement:** Direct pushes to the `main` branch are disabled. All changes must originate from a feature branch submitted via Pull Request (PR).
* **Mandatory Review:** A minimum of one peer review (Code Owner) is required before merging.
* **Traceability:** Every commit represents a signed, timestamped record containing:
    * **Author:** Who made the change.
    * **Context:** Why the change was made (linked to Jira/Ticket ID).
    * **Diff:** Exactly what lines of configuration were altered.

## 2. Least Privilege & Separation of Duties

We enforce a strict boundary between human operators and the production cluster.

* **No Direct Write Access:** Engineers do not have `kubectl write` or `admin` permissions in the production cluster.
* **Machine Automation:** Only the **ArgoCD** and **Flux** controllers possess the necessary Service Account permissions to apply changes.
* **Read-Only Repository:** The cluster controllers have read-only access to this Git repository, preventing tampering from the compromised cluster side.

## 3. Continuous Audit Logging

Compliance is not a snapshot; it is a continuous state maintained by the Git history.

* **Immutable History:** The Git log serves as the legal record of all changes. History cannot be rewritten on protected branches.
* **Reconciliation Logs:** ArgoCD and Flux provide a secondary audit log confirming that the cluster state successfully converged with the Git state.
* **Drift Remediation:** Any unauthorized manual change to the cluster is immediately detected and overwritten by the automated controllers, ensuring the "Code is Law" principle.

## 4. Disaster Recovery & Rollbacks

In the event of a failure, the GitOps workflow provides an instant, tested recovery mechanism.

* **Instant Rollback:** Reverting a PR in Git triggers the controllers to immediately restore the previous known-good state in the cluster.
* **Mean Time to Recovery (MTTR):** Remediation times are measured in minutes, determined solely by the reconciliation interval (approx. 60 seconds).

## 5. Auditor Evidence Strategy

When demonstrating compliance to external auditors, use the following artifacts:

1. **Change Log:** Export the Git commit history for the audit period.
2. **Access Review:** Show GitHub/GitLab permission settings to prove branch protection and PR requirements.
3. **Drift Proof:** Demonstrate the "Drift Detection" policy by manually modifying a resource and showing its automatic correction.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
