// ===========================================================================
// Golden Platform
// Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
// ===========================================================================
// apps/client-portal/src/data.js — static demo content (ROI cases, provenance).
// ===========================================================================
'use strict';

const ROI = Object.freeze({
  healthcare: {
    vertical: 'healthcare',
    tier: 'professional',
    monthly_cost_usd: 17500,
    monthly_value_protected_usd: 480000,
    roi_ratio: 27.4,
    payback_days: 1.1,
    annual_net_benefit_usd: 5550000,
    breakdown: {
      readmission_prevention: { annual_usd: 3200000, label: '30-Day Readmission Prevention', pct_of_total: 66.4 },
      phi_breach_avoidance: { annual_usd: 1450000, label: 'PHI Breach & HIPAA Exposure', pct_of_total: 30.1 },
      ehr_downtime_reduction: { annual_usd: 166000, label: 'EHR Downtime & Workflow Loss', pct_of_total: 3.5 },
    },
    executive_summary:
      'The platform generates 27x ROI, protecting $480K/month in risk exposure on a $17,500/month contract. The platform pays for itself in 1.1 days through readmission prevention, PHI breach avoidance, and EHR reliability — with $5.55M in net annual benefit.',
  },
  fintech: {
    vertical: 'fintech',
    tier: 'professional',
    monthly_cost_usd: 17500,
    monthly_value_protected_usd: 620000,
    roi_ratio: 35.4,
    payback_days: 0.9,
    annual_net_benefit_usd: 7230000,
    breakdown: {
      fraud_prevention: { annual_usd: 5100000, label: 'Fraud Loss Prevention (Net)', pct_of_total: 68.2 },
      payment_reliability: { annual_usd: 1680000, label: 'Payment Downtime & SLO Breaches', pct_of_total: 22.5 },
      compliance_automation: { annual_usd: 690000, label: 'AML/BSA Compliance Automation', pct_of_total: 9.3 },
    },
    executive_summary:
      'The platform generates 35x ROI for your institution, protecting $620K/month in fraud, downtime, and compliance exposure on a $17,500/month contract. The platform recovers its cost in 0.9 days, with $7.23M in net annual benefit.',
  },
  gpu: {
    vertical: 'gpu',
    tier: 'professional',
    monthly_cost_usd: 17500,
    monthly_value_protected_usd: 285000,
    roi_ratio: 16.3,
    payback_days: 1.8,
    annual_net_benefit_usd: 3210000,
    breakdown: {
      idle_consolidation: { annual_usd: 1224000, label: 'Idle GPU Consolidation & Rightsizing', pct_of_total: 35.8 },
      job_interruption_avoidance: { annual_usd: 1476000, label: 'Training-Job Interruption Avoidance', pct_of_total: 43.2 },
      hardware_lifecycle: { annual_usd: 720000, label: 'Thermal/ECC Hardware Lifecycle', pct_of_total: 21.0 },
    },
    executive_summary:
      'The platform generates 16x ROI on a 256-GPU fleet, recovering $285K/month through idle-capacity consolidation, proactive thermal/ECC remediation, and fewer interrupted training runs on a $17,500/month contract — $3.21M in net annual benefit.',
  },
  migration: {
    vertical: 'migration',
    tier: 'professional',
    monthly_cost_usd: 17500,
    monthly_value_protected_usd: 245000,
    roi_ratio: 14.0,
    payback_days: 2.1,
    annual_net_benefit_usd: 2730000,
    breakdown: {
      licensing_savings: { annual_usd: 1860000, label: 'VMware Licensing Avoided (OpenShift)', pct_of_total: 63.3 },
      migration_automation: { annual_usd: 720000, label: 'Migration Labor Automation', pct_of_total: 24.5 },
      cutover_downtime_avoidance: { annual_usd: 360000, label: 'Cutover Downtime & Rollback Avoidance', pct_of_total: 12.2 },
    },
    executive_summary:
      'The platform generates 14x ROI on a 1,240-VM VMware → OpenShift Virtualization programme: $1.86M/yr in licensing avoided at completion, automated wave planning and validation, and fewer failed cutovers on a $17,500/month contract — $2.73M in net annual benefit.',
  },
});

const PROVENANCE = Object.freeze({
  models: [
    {
      name: 'LSTM SLI Predictor',
      type: 'Deep Learning — Long Short-Term Memory',
      reference: 'Hochreiter & Schmidhuber (1997); Sagheer & Kotb (2019)',
      precision: '95.6%',
      recall: '92.3%',
      verticals: ['healthcare', 'fintech', 'gpu', 'migration'],
      description:
        'Forecasts service-level indicator violations 6 intervals ahead using 24-step lookback sequences. Hidden size: 64; Layers: 2; Dropout: 0.1.',
    },
    {
      name: 'TCN SLI Predictor',
      type: 'Deep Learning — Temporal Convolutional Network',
      reference: 'Bai, Kolter & Koltun (2018)',
      precision: '94.8%',
      recall: '91.7%',
      verticals: ['healthcare', 'fintech', 'gpu', 'migration'],
      description: 'Causal dilated convolutions for non-autoregressive SLI forecasting. Ensemble-blended with LSTM for robustness.',
    },
    {
      name: 'Fraud Detection Engine',
      type: 'Composite ML — 5-Signal Weighted Ensemble',
      reference: 'Federal Reserve Payments Study 2024; BSA/AML Compliance Framework',
      precision: '95.6%',
      recall: '92.3%',
      verticals: ['fintech'],
      description:
        'Bayesian composite scorer: amount anomaly (30%), velocity (25%), geo risk (15%), channel risk (15%), MCC risk (15%). Aligned with SAR filing explainability requirements.',
    },
    {
      name: 'PHI Anomaly Detector',
      type: 'Composite ML — HIPAA-Aligned Access Risk Model',
      reference: 'NIST SP 800-66r2; HIPAA §164.312(b)',
      precision: '96.1%',
      recall: '93.8%',
      verticals: ['healthcare'],
      description:
        'Five-signal PHI access risk model aligned with HIPAA Minimum Necessary Standard. Audit-ready explainability for OCR investigations.',
    },
    {
      name: 'Clinical Safety Monitor',
      type: 'Rule-Based + ML Ensemble — NEWS2 Aligned',
      reference: 'Royal College of Physicians NEWS2 Score (2017); Sepsis-3 Criteria (2016)',
      precision: '97.1%',
      recall: '94.5%',
      verticals: ['healthcare'],
      description:
        'Real-time vital sign monitoring with department-weighted risk stratification. Aligned with Joint Commission NPSG.06.01.01 clinical alarm management.',
    },
    {
      name: 'GPU Fleet Rightsizing Optimizer',
      type: 'Utilization Forecasting + Bin-Packing',
      reference: 'Jeon et al. (2019) USENIX ATC; Weng et al. (2022) NSDI',
      precision: '93.9%',
      recall: '90.8%',
      verticals: ['gpu'],
      description:
        'Forecasts per-pool GPU demand from DCGM utilization series and recommends consolidation of idle capacity with job-aware bin-packing.',
    },
    {
      name: 'GPU Thermal & ECC Anomaly Detector',
      type: 'Composite ML — DCGM Telemetry Risk Model',
      reference: 'Ostrouchov et al. (2020) SC20; NVIDIA DCGM Health Checks',
      precision: '95.2%',
      recall: '92.6%',
      verticals: ['gpu'],
      description:
        'Combines temperature headroom, throttle reasons, and ECC/XID error rates to predict node failure and pre-emptively migrate training jobs.',
    },
    {
      name: 'Migration Wave Planner',
      type: 'Dependency-Graph Clustering + Constraint Scheduling',
      reference: 'Red Hat Migration Toolkit for Virtualization (Forklift) validation rules',
      precision: '94.4%',
      recall: '91.2%',
      verticals: ['migration'],
      description:
        'Groups VMs into waves from network-flow dependency graphs, flags blockers (RDM, passthrough, unsupported guests) before cutover, and balances waves against storage throughput.',
    },
    {
      name: 'Cutover Risk Predictor',
      type: 'Gradient-Boosted Classifier — Cutover Outcome Model',
      reference: 'Friedman (2001) Gradient Boosting; KubeVirt live/warm migration telemetry',
      precision: '93.7%',
      recall: '90.5%',
      verticals: ['migration'],
      description:
        'Predicts cutover failure and rollback likelihood from precopy lag, change-block-tracking delta size, and post-boot validation signals.',
    },
  ],
  author: 'Rev. Dr. Emmanuel Naweji, PhD',
  institution: 'Platform Research Division',
  methodology: 'Bayesian Expected-Value Framework | IEEE 2024 AI Reliability Standards',
});

module.exports = { ROI, PROVENANCE };
