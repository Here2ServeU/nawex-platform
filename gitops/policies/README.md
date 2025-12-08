# GitOps Policy & Compliance Framework

This directory documents the **Governance Layer** of the platform. While the `argocd` and `flux` directories handle the *mechanics* of deployment, this directory defines the *rules* that ensure those deployments are secure, compliant, and auditable.

It serves as the bridge between **DevOps** (speed) and **SecOps/Audit** (control), proving that our automated workflows satisfy strict regulatory requirements like **SOC 2 Type II**.

## Directory Structure

* **`soc2-gitops-controls.md`**: A compliance mapping document. It details exactly how our GitOps workflow satisfies specific SOC 2 controls (e.g., *CC8.1 Change Management*).
    * **Key Insight:** "The Pull Request *is* the Change Request ticket. The Merge Approval *is* the CAB approval."
* **`drift-detection.md`**: The operational playbook for handling "Configuration Drift."
    * **Key Insight:** Defines the "Code is Law" policy—how we detect, alert on, and auto-remediate manual changes made directly to the cluster (Shadow IT).

## Core Capabilities & SRE Value

### 1. Compliance as Code
* **Problem:** "Audit Week" is a nightmare of screenshots and spreadsheet hunting.
* **Solution:** By moving all infrastructure changes into Git, we create an **Immutable Audit Trail**.
* **Impact:** **Continuous Compliance.** We don't "prepare" for audits; we are always audit-ready. The Git log provides the *Who, What, When, and Why* for every single production change.

### 2. The "Break-Glass" Protocol
* **Problem:** Strictly enforcing GitOps can hinder emergency response during a P0 outage.
* **Solution:** The `drift-detection.md` policy outlines our "Emergency Access" procedure. Engineers can manually patch the cluster to stop the bleeding, but the system will alert on the drift immediately, triggering a "Reconciliation Ticket" to backport the fix to Git.
* **Impact:** **Pragmatic Reliability.** We balance strict control with the need for speed during incidents.

### 3. Change Management Automation
* **Problem:** Developers waiting 3 days for a Change Advisory Board (CAB) meeting.
* **Solution:** We automate the CAB. If a PR passes all CI checks (Linting, Security Scan, Unit Tests), it is automatically approved for Staging.
* **Impact:** **Velocity.** We maintain high governance standards without slowing down the release lifecycle.

## Operational Standards

**Policy: Manual Changes**
> *Any manual change made via `kubectl` that is not backported to this repository within 24 hours will be automatically overwritten by the GitOps controller.*

**Policy: Secret Management**
> *No plain-text secrets are allowed in this repo. All secrets must be encrypted via Sealed Secrets or referenced via External Secrets Operator.*

### Interview Talking Point:

> I created this `policies` directory because I know that **SRE is about more than just uptime; it's about trust.** I use documents like `soc2-gitops-controls.md` to show auditors that our automated pipeline isn't a 'wild west'—it's actually *more* controlled than the old manual processes. I map every Git action to a compliance control, turning our GitHub repo into our primary evidence locker.
