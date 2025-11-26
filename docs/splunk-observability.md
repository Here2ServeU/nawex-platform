# Splunk Observability Integration

This document explains how Splunk is integrated into the Express AI-Driven Multi-Cloud Resilience Platform.

## Components

- Splunk Enterprise on:
  - AWS EC2
  - Azure VM
  - GCP Compute Engine
  - OCI Compute
- HEC endpoint exposed on port 8088
- Fluent Bit forwarders on the Splunk VM
- Kubernetes-wide forwarders via Helm (`helm/splunk-forwarder`)
- GitOps (ArgoCD & FluxCD) to manage forwarder rollout

## Flow

1. Terraform provisions Splunk VM and installs:
   - Splunk Enterprise
   - HEC token + inputs
   - Local Fluent Bit

2. Helm installs `splunk-forwarder` DaemonSet into clusters:
   - Collects `/var/log/*.log`
   - Sends to `splunk_hec_endpoint` from Terraform output.

3. GitOps keeps forwarder config in sync across clusters:
   - ArgoCD Application: `gitops/argocd/app-splunk-forwarder.yaml`
   - Flux HelmRelease: `gitops/flux/apps/resources/splunk-forwarder-helmrelease.yaml`

4. SRE and AIOps layers:
   - Use Splunk data for anomaly detection, SLO burn analysis, incident investigations.
