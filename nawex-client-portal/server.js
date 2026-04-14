// ===========================================================================
// NAWEX - Nawex Platform
// Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
// ===========================================================================
// nawex-client-portal/server.js
//
// Executive Demo Portal — Express + WebSocket server.
// Streams live simulated AI insights to the browser dashboard.
// Serves the branded single-page client-facing UI at localhost:3001.
// ===========================================================================

'use strict';

const express = require('express');
const cors    = require('cors');
const helmet  = require('helmet');
const http    = require('http');
const path    = require('path');
const { WebSocketServer } = require('ws');

const app    = express();
const server = http.createServer(app);
const wss    = new WebSocketServer({ server, path: '/feed' });

app.use(cors());
app.use(helmet({ contentSecurityPolicy: false })); // CSP off — CDN scripts needed
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const PORT = process.env.PORT || 3001;
const START_TIME = Date.now();

// ---------------------------------------------------------------------------
// Demo Simulation Engine
// ---------------------------------------------------------------------------
// Phases cycle: normal → degrading → alert → recovering → normal
// This creates the narrative arc that makes demos compelling to clients.
// ---------------------------------------------------------------------------

const PHASE_SCHEDULE = { normal: 30, degrading: 15, alert: 12, recovering: 18 };

class DemoSimulator {
  constructor(vertical = 'healthcare') {
    this.vertical   = vertical;
    this.phase      = 'normal';
    this.tick       = 0;
    this.phaseTick  = 0;
    this.alertLog   = [];
    this.riskHistory = [];
  }

  advance() {
    this.tick++;
    this.phaseTick++;
    if (this.phaseTick >= PHASE_SCHEDULE[this.phase]) {
      this.phaseTick = 0;
      const phases = ['normal', 'degrading', 'alert', 'recovering'];
      const idx    = phases.indexOf(this.phase);
      this.phase   = phases[(idx + 1) % phases.length];
    }
    const metrics = this.getMetrics();
    this.riskHistory.push(metrics.riskScore);
    if (this.riskHistory.length > 60) this.riskHistory.shift();
    if (this.phase === 'alert') {
      const alert = this._generateAlert();
      this.alertLog.unshift(alert);
      if (this.alertLog.length > 30) this.alertLog.pop();
    }
  }

  getMetrics() {
    const jitter = () => (Math.random() - 0.5) * 0.06;

    if (this.vertical === 'healthcare') {
      const baseRisk = { normal: 0.18, degrading: 0.45, alert: 0.82, recovering: 0.35 }[this.phase];
      const riskScore = Math.min(1, Math.max(0, baseRisk + jitter()));
      return {
        vertical:           'healthcare',
        phase:              this.phase,
        riskScore:          +riskScore.toFixed(3),
        patientsMonitored:  24 + Math.floor(Math.random() * 4),
        ehrIngestRate:      Math.floor(180 + Math.random() * 60),
        clinicalAlerts:     this.phase === 'alert' ? Math.floor(3 + Math.random() * 4) : Math.floor(Math.random() * 2),
        phiAnomalies:       this.phase === 'alert' ? Math.floor(1 + Math.random() * 3) : 0,
        ehrSloHealth:       this.phase === 'alert' ? Math.floor(72 + Math.random() * 10) : Math.floor(97 + Math.random() * 3),
        hipaaCompliance:    this.phase === 'alert' ? 94.2 : 99.1,
        roiMonthly:         this._healthcareROI(),
      };
    } else {
      const baseRisk = { normal: 0.14, degrading: 0.42, alert: 0.79, recovering: 0.31 }[this.phase];
      const riskScore = Math.min(1, Math.max(0, baseRisk + jitter()));
      return {
        vertical:             'fintech',
        phase:                this.phase,
        riskScore:            +riskScore.toFixed(3),
        transactionsPerSec:   Math.floor(340 + Math.random() * 80),
        fraudScore:           +(Math.min(1, Math.max(0, (this.phase === 'alert' ? 0.74 : 0.22) + jitter())).toFixed(3)),
        activeAlerts:         this.phase === 'alert' ? Math.floor(2 + Math.random() * 5) : 0,
        gatewaySloHealth:     this.phase === 'alert' ? Math.floor(74 + Math.random() * 10) : Math.floor(98 + Math.random() * 2),
        fraudSavingsToday:    Math.floor(42000 + Math.random() * 8000),
        pciCompliance:        this.phase === 'alert' ? 96.8 : 99.6,
        roiMonthly:           this._fintechROI(),
      };
    }
  }

  _generateAlert() {
    const ts = new Date().toISOString();
    if (this.vertical === 'healthcare') {
      const alerts = [
        { severity: 'critical', msg: `PT-${this._randId()} — SpO₂ dropped to ${(82 + Math.random() * 5).toFixed(0)}% in ICU`, category: 'Clinical Safety' },
        { severity: 'critical', msg: `PT-${this._randId()} — Tachycardia: HR ${(131 + Math.random() * 30).toFixed(0)} bpm in ED`, category: 'Clinical Safety' },
        { severity: 'high',     msg: `USR-${this._randId()} — Bulk PHI export: ${Math.floor(150 + Math.random() * 400)} records after hours`, category: 'PHI Anomaly' },
        { severity: 'high',     msg: `EHR Gateway p99 latency: ${(210 + Math.random() * 80).toFixed(0)}ms — SLO breach`, category: 'System Reliability' },
        { severity: 'medium',   msg: `PT-${this._randId()} — Hypertensive crisis: BP ${(195 + Math.random() * 25).toFixed(0)}/110`, category: 'Clinical Safety' },
        { severity: 'medium',   msg: `Contractor ${this._randId()} accessing cross-dept records during weekend`, category: 'PHI Anomaly' },
      ];
      return { ...alerts[Math.floor(Math.random() * alerts.length)], timestamp: ts };
    } else {
      const alerts = [
        { severity: 'critical', msg: `TXN-${this._randId()} — Fraud score 0.${(87 + Math.floor(Math.random() * 12))}: geo-impossible travel $${(1800 + Math.floor(Math.random() * 2000)).toLocaleString()}`, category: 'Fraud Detection' },
        { severity: 'critical', msg: `ACC-${this._randId()} — Velocity abuse: ${Math.floor(18 + Math.random() * 12)} transactions in 60s`, category: 'Fraud Detection' },
        { severity: 'high',     msg: `GW-002 — p99 latency ${(185 + Math.random() * 120).toFixed(0)}ms — SLO breach detected`, category: 'Payment Reliability' },
        { severity: 'high',     msg: `Settlement BATCH-${Math.floor(Math.random() * 20 + 1).toString().padStart(3,'0')} at risk — ${(130 + Math.random() * 60).toFixed(0)} min to clearing window`, category: 'Settlement Risk' },
        { severity: 'medium',   msg: `Unusual MCC-7995 (gambling) cluster: ${Math.floor(8 + Math.random() * 12)} accounts, fraud score escalating`, category: 'Fraud Detection' },
        { severity: 'medium',   msg: `AML flag: structured transactions below reporting threshold — BSA review triggered`, category: 'Compliance' },
      ];
      return { ...alerts[Math.floor(Math.random() * alerts.length)], timestamp: ts };
    }
  }

  _healthcareROI() {
    return {
      monthlyCost: 17500,
      monthlyProtected: 480000 + Math.floor(Math.random() * 20000),
      roiRatio: 27,
      paybackDays: 1.1,
    };
  }

  _fintechROI() {
    return {
      monthlyCost: 17500,
      monthlyProtected: 620000 + Math.floor(Math.random() * 30000),
      roiRatio: 35,
      paybackDays: 0.9,
    };
  }

  getExplainability() {
    if (this.vertical === 'healthcare') {
      return {
        title: 'Top Clinical Risk Contributors',
        factors: [
          { name: 'Vital Sign Anomaly (SpO₂/HR)',  weight: 0.35, value: (this.phase === 'alert' ? 0.91 : 0.18) },
          { name: 'After-Hours PHI Access Pattern', weight: 0.25, value: (this.phase === 'alert' ? 0.82 : 0.05) },
          { name: 'Cross-Dept Record Access',       weight: 0.20, value: (this.phase === 'alert' ? 0.74 : 0.02) },
          { name: 'EHR Latency SLO Deviation',      weight: 0.12, value: (this.phase === 'alert' ? 0.67 : 0.15) },
          { name: 'Patient Acuity Level',            weight: 0.08, value: 0.55 },
        ],
      };
    } else {
      return {
        title: 'Top Fraud Risk Contributors',
        factors: [
          { name: 'Transaction Amount Anomaly (z-score)', weight: 0.30, value: (this.phase === 'alert' ? 0.94 : 0.22) },
          { name: 'Velocity Pattern (trans/hour)',        weight: 0.25, value: (this.phase === 'alert' ? 0.89 : 0.12) },
          { name: 'Geographic Risk (jurisdiction)',       weight: 0.15, value: (this.phase === 'alert' ? 0.78 : 0.08) },
          { name: 'Channel Risk (CNP vs POS)',            weight: 0.15, value: (this.phase === 'alert' ? 0.65 : 0.25) },
          { name: 'Merchant Category (MCC)',              weight: 0.15, value: (this.phase === 'alert' ? 0.55 : 0.05) },
        ],
      };
    }
  }

  getActiveAlerts() { return this.alertLog.slice(0, 8); }
  getRiskHistory()   { return [...this.riskHistory]; }
  _randId()          { return Math.floor(10000 + Math.random() * 89999); }
}

// ---------------------------------------------------------------------------
// Global simulator state — switches vertical on API call
// ---------------------------------------------------------------------------
let simulator = new DemoSimulator('healthcare');

// Advance simulation every 3 seconds
setInterval(() => {
  simulator.advance();
  const payload = {
    type:           'state_update',
    metrics:        simulator.getMetrics(),
    alerts:         simulator.getActiveAlerts(),
    explainability: simulator.getExplainability(),
    riskHistory:    simulator.getRiskHistory(),
  };
  wss.clients.forEach(client => {
    if (client.readyState === 1) {
      client.send(JSON.stringify(payload));
    }
  });
}, 3000);

// ---------------------------------------------------------------------------
// REST API Routes
// ---------------------------------------------------------------------------

app.get('/api/health', (req, res) => {
  res.json({
    status:    'ok',
    version:   '2.0.0',
    uptime_s:  Math.floor((Date.now() - START_TIME) / 1000),
    vertical:  simulator.vertical,
    phase:     simulator.phase,
  });
});

app.get('/api/vertical', (req, res) => {
  res.json({ current: simulator.vertical });
});

app.post('/api/vertical', (req, res) => {
  const { vertical } = req.body;
  if (!['healthcare', 'fintech'].includes(vertical)) {
    return res.status(400).json({ error: 'vertical must be healthcare or fintech' });
  }
  simulator = new DemoSimulator(vertical);
  res.json({ switched_to: vertical, ok: true });
});

app.get('/api/metrics/:vertical', (req, res) => {
  const v = req.params.vertical;
  if (!['healthcare', 'fintech'].includes(v)) {
    return res.status(400).json({ error: 'Unknown vertical' });
  }
  const snap = new DemoSimulator(v);
  snap.phase = simulator.vertical === v ? simulator.phase : 'normal';
  res.json(snap.getMetrics());
});

app.get('/api/alerts/:vertical', (req, res) => {
  res.json({ alerts: simulator.getActiveAlerts(), vertical: simulator.vertical });
});

app.get('/api/roi/:vertical', (req, res) => {
  const v = req.params.vertical;
  if (v === 'healthcare') {
    res.json({
      vertical:               'healthcare',
      tier:                   'professional',
      monthly_cost_usd:       17500,
      monthly_value_protected_usd: 480000,
      roi_ratio:              27.4,
      payback_days:           1.1,
      annual_net_benefit_usd: 5550000,
      breakdown: {
        readmission_prevention: { annual_usd: 3200000, label: '30-Day Readmission Prevention', pct_of_total: 66.4 },
        phi_breach_avoidance:   { annual_usd: 1450000, label: 'PHI Breach & HIPAA Exposure',   pct_of_total: 30.1 },
        ehr_downtime_reduction: { annual_usd: 166000,  label: 'EHR Downtime & Workflow Loss',  pct_of_total: 3.5 },
      },
      executive_summary: 'NAWEX generates 27x ROI, protecting $480K/month in risk exposure on a $17,500/month contract. The platform pays for itself in 1.1 days through readmission prevention, PHI breach avoidance, and EHR reliability — with $5.55M in net annual benefit.',
    });
  } else {
    res.json({
      vertical:               'fintech',
      tier:                   'professional',
      monthly_cost_usd:       17500,
      monthly_value_protected_usd: 620000,
      roi_ratio:              35.4,
      payback_days:           0.9,
      annual_net_benefit_usd: 7230000,
      breakdown: {
        fraud_prevention:       { annual_usd: 5100000, label: 'Fraud Loss Prevention (Net)',        pct_of_total: 68.2 },
        payment_reliability:    { annual_usd: 1680000, label: 'Payment Downtime & SLO Breaches',    pct_of_total: 22.5 },
        compliance_automation:  { annual_usd: 690000,  label: 'AML/BSA Compliance Automation',      pct_of_total: 9.3 },
      },
      executive_summary: 'NAWEX generates 35x ROI for your institution, protecting $620K/month in fraud, downtime, and compliance exposure on a $17,500/month contract. The platform recovers its cost in 0.9 days, with $7.23M in net annual benefit.',
    });
  }
});

app.get('/api/research/provenance', (req, res) => {
  res.json({
    models: [
      {
        name:        'LSTM SLI Predictor',
        type:        'Deep Learning — Long Short-Term Memory',
        reference:   'Hochreiter & Schmidhuber (1997); Sagheer & Kotb (2019)',
        precision:   '95.6%',
        recall:      '92.3%',
        description: 'Forecasts service-level indicator violations 6 intervals ahead using 24-step lookback sequences. Hidden size: 64; Layers: 2; Dropout: 0.1.',
      },
      {
        name:        'TCN SLI Predictor',
        type:        'Deep Learning — Temporal Convolutional Network',
        reference:   'Bai, Kolter & Koltun (2018)',
        precision:   '94.8%',
        recall:      '91.7%',
        description: 'Causal dilated convolutions for non-autoregressive SLI forecasting. Ensemble-blended with LSTM for robustness.',
      },
      {
        name:        'Fraud Detection Engine',
        type:        'Composite ML — 5-Signal Weighted Ensemble',
        reference:   'Federal Reserve Payments Study 2024; BSA/AML Compliance Framework',
        precision:   '95.6%',
        recall:      '92.3%',
        description: 'Bayesian composite scorer: amount anomaly (30%), velocity (25%), geo risk (15%), channel risk (15%), MCC risk (15%). Aligned with SAR filing explainability requirements.',
      },
      {
        name:        'PHI Anomaly Detector',
        type:        'Composite ML — HIPAA-Aligned Access Risk Model',
        reference:   'NIST SP 800-66r2; HIPAA §164.312(b)',
        precision:   '96.1%',
        recall:      '93.8%',
        description: 'Five-signal PHI access risk model aligned with HIPAA Minimum Necessary Standard. Audit-ready explainability for OCR investigations.',
      },
      {
        name:        'Clinical Safety Monitor',
        type:        'Rule-Based + ML Ensemble — NEWS2 Aligned',
        reference:   'Royal College of Physicians NEWS2 Score (2017); Sepsis-3 Criteria (2016)',
        precision:   '97.1%',
        recall:      '94.5%',
        description: 'Real-time vital sign monitoring with department-weighted risk stratification. Aligned with Joint Commission NPSG.06.01.01 clinical alarm management.',
      },
    ],
    author:      'Rev. Dr. Emmanuel Naweji, PhD',
    institution: 'Nawex Platform Research Division',
    methodology: 'Bayesian Expected-Value Framework | IEEE 2024 AI Reliability Standards',
  });
});

// ---------------------------------------------------------------------------
// WebSocket connection handler
// ---------------------------------------------------------------------------
wss.on('connection', (ws) => {
  // Send current state immediately on connect
  const initial = {
    type:           'state_update',
    metrics:        simulator.getMetrics(),
    alerts:         simulator.getActiveAlerts(),
    explainability: simulator.getExplainability(),
    riskHistory:    simulator.getRiskHistory(),
  };
  ws.send(JSON.stringify(initial));
});

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------
server.listen(PORT, () => {
  console.log(`\n╔════════════════════════════════════════════════════════╗`);
  console.log(`║  NAWEX Executive Client Portal                          ║`);
  console.log(`║  Rev. Dr. Emmanuel Naweji — AI Research Platform       ║`);
  console.log(`╠════════════════════════════════════════════════════════╣`);
  console.log(`║  Dashboard:  http://localhost:${PORT}                      ║`);
  console.log(`║  API Health: http://localhost:${PORT}/api/health            ║`);
  console.log(`║  ROI API:    http://localhost:${PORT}/api/roi/healthcare     ║`);
  console.log(`║  WebSocket:  ws://localhost:${PORT}/feed                    ║`);
  console.log(`╚════════════════════════════════════════════════════════╝\n`);
});
