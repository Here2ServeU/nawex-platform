// ===========================================================================
// Golden Platform
// Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
// ===========================================================================
// apps/client-portal/src/simulator.js
//
// Demo simulation engine. Phases cycle normal -> degrading -> alert ->
// recovering -> normal, which gives executive demos a narrative arc.
// Everything here is SIMULATED data; no real systems are touched.
// ===========================================================================
'use strict';

const VERTICALS = Object.freeze(['healthcare', 'fintech', 'gpu', 'migration']);
const PHASES = Object.freeze(['normal', 'degrading', 'alert', 'recovering']);
const PHASE_SCHEDULE = Object.freeze({ normal: 30, degrading: 15, alert: 12, recovering: 18 });
const AUTONOMY_MODES = Object.freeze(['dry_run', 'supervised', 'autonomous']);

// GPU fleet economics (blended on-demand H100-class cloud pricing).
const GPU_FLEET_SIZE = 256;
const GPU_HOURLY_RATE_USD = 2.48;
const HOURS_PER_MONTH = 730;
const CONSOLIDATION_RECOVERY = 0.7; // share of idle spend recoverable by rightsizing

// VMware -> OpenShift Virtualization migration programme.
const MIG_VMS_DISCOVERED = 1240;
const MIG_TOTAL_WAVES = 8;
const MIG_START_MIGRATED = 312;
const MIG_AVG_VM_TB = 0.27;
// Projected annual VMware licensing avoided at programme completion.
const MIG_ANNUAL_LICENSING_SAVINGS_USD = 1860000;

function isValidVertical(v) {
  return typeof v === 'string' && VERTICALS.includes(v);
}

const clamp01 = (n) => Math.min(1, Math.max(0, n));
const randInt = (min, max) => min + Math.floor(Math.random() * (max - min + 1));
const randRange = (min, max) => min + Math.random() * (max - min);
const randId = () => randInt(10000, 99999);

/**
 * Simulated AI-safety guardrail state. The real enforcement (autonomy modes,
 * per-hour action caps, kill switch) lives in the Python platform; this only
 * mirrors its shape so the demo UI can visualise it.
 */
class SafetyState {
  constructor({ mode = 'supervised', actionCap = 20 } = {}) {
    this.mode = AUTONOMY_MODES.includes(mode) ? mode : 'supervised';
    this.actionCap = actionCap;
    this.actionTimestamps = [];
    this.killSwitchEngaged = false;
  }

  _prune(now) {
    const cutoff = now - 60 * 60 * 1000;
    while (this.actionTimestamps.length && this.actionTimestamps[0] < cutoff) {
      this.actionTimestamps.shift();
    }
    // Kill switch auto-rearms once the rolling hourly window drains below cap.
    if (this.killSwitchEngaged && this.actionTimestamps.length < this.actionCap) {
      this.killSwitchEngaged = false;
    }
  }

  /** Record a remediation action. Returns false when blocked by the guardrails. */
  recordAction(now = Date.now()) {
    this._prune(now);
    if (this.killSwitchEngaged) return false;
    if (this.actionTimestamps.length >= this.actionCap) {
      this.killSwitchEngaged = true;
      return false;
    }
    this.actionTimestamps.push(now);
    if (this.actionTimestamps.length >= this.actionCap) this.killSwitchEngaged = true;
    return true;
  }

  snapshot(now = Date.now()) {
    this._prune(now);
    return {
      autonomyMode: this.mode,
      actionsThisHour: this.actionTimestamps.length,
      actionCap: this.actionCap,
      killSwitch: this.killSwitchEngaged ? 'engaged' : 'armed',
      simulated: true,
    };
  }
}

class DemoSimulator {
  constructor(vertical = 'healthcare', { safety } = {}) {
    if (!isValidVertical(vertical)) {
      throw new Error(`Unknown vertical: ${vertical}`);
    }
    this.vertical = vertical;
    this.phase = 'normal';
    this.tick = 0;
    this.phaseTick = 0;
    this.alertLog = [];
    this.riskHistory = [];
    this.safety = safety || new SafetyState();
    this.migration = { migrated: MIG_START_MIGRATED, rollbacks: 1, lastCompletedWave: 2 };
  }

  _advanceMigration() {
    const m = this.migration;
    if (this.phase === 'alert') {
      if (Math.random() < 0.25) m.rollbacks++;
      m.migrated += randInt(0, 1);
    } else {
      m.migrated += this.phase === 'degrading' ? randInt(0, 2) : randInt(1, 4);
    }
    // Loop the demo once the migratable estate has been moved.
    if (m.migrated >= MIG_VMS_DISCOVERED - 20) {
      m.migrated = MIG_START_MIGRATED;
      m.rollbacks = 1;
    }
  }

  _migrationWave() {
    const perWave = MIG_VMS_DISCOVERED / MIG_TOTAL_WAVES;
    return Math.min(MIG_TOTAL_WAVES, 1 + Math.floor(this.migration.migrated / perWave));
  }

  advance() {
    this.tick++;
    this.phaseTick++;
    if (this.phaseTick >= PHASE_SCHEDULE[this.phase]) {
      this.phaseTick = 0;
      this.phase = PHASES[(PHASES.indexOf(this.phase) + 1) % PHASES.length];
    }
    if (this.vertical === 'migration') this._advanceMigration();
    const metrics = this.getMetrics();
    this.riskHistory.push(metrics.riskScore);
    if (this.riskHistory.length > 60) this.riskHistory.shift();
    if (this.phase === 'alert') {
      this.alertLog.unshift(this._generateAlert());
      if (this.alertLog.length > 30) this.alertLog.pop();
      // Roughly every other alert tick the platform proposes/takes an action.
      if (Math.random() < 0.5) this.safety.recordAction();
    }
  }

  _risk(base) {
    const jitter = (Math.random() - 0.5) * 0.06;
    return +clamp01(base[this.phase] + jitter).toFixed(3);
  }

  getMetrics() {
    const alert = this.phase === 'alert';
    if (this.vertical === 'healthcare') {
      return {
        vertical: 'healthcare',
        phase: this.phase,
        riskScore: this._risk({ normal: 0.18, degrading: 0.45, alert: 0.82, recovering: 0.35 }),
        patientsMonitored: randInt(24, 27),
        ehrIngestRate: randInt(180, 239),
        clinicalAlerts: alert ? randInt(3, 6) : randInt(0, 1),
        phiAnomalies: alert ? randInt(1, 3) : 0,
        ehrSloHealth: alert ? randInt(72, 81) : randInt(97, 99),
        hipaaCompliance: alert ? 94.2 : 99.1,
        roiMonthly: {
          monthlyCost: 17500,
          monthlyProtected: 480000 + randInt(0, 19999),
          roiRatio: 27,
          paybackDays: 1.1,
        },
      };
    }
    if (this.vertical === 'fintech') {
      return {
        vertical: 'fintech',
        phase: this.phase,
        riskScore: this._risk({ normal: 0.14, degrading: 0.42, alert: 0.79, recovering: 0.31 }),
        transactionsPerSec: randInt(340, 419),
        fraudScore: +clamp01((alert ? 0.74 : 0.22) + (Math.random() - 0.5) * 0.06).toFixed(3),
        activeAlerts: alert ? randInt(2, 6) : 0,
        gatewaySloHealth: alert ? randInt(74, 83) : randInt(98, 99),
        fraudSavingsToday: randInt(42000, 49999),
        pciCompliance: alert ? 96.8 : 99.6,
        roiMonthly: {
          monthlyCost: 17500,
          monthlyProtected: 620000 + randInt(0, 29999),
          roiRatio: 35,
          paybackDays: 0.9,
        },
      };
    }
    if (this.vertical === 'gpu') return this._gpuMetrics();
    return this._migrationMetrics();
  }

  _migrationMetrics() {
    const p = this.phase;
    const m = this.migration;
    const blocked = { normal: [14, 18], degrading: [19, 26], alert: [27, 38], recovering: [18, 23] }[p];
    const vmsBlocked = randInt(blocked[0], blocked[1]);
    const vmsNeedsRemediation = randInt(88, 104) + (p === 'alert' ? randInt(6, 14) : 0);
    const vmsAssessed = Math.min(MIG_VMS_DISCOVERED, 1100 + Math.floor(m.migrated / 10));
    const vmsReady = vmsAssessed - vmsBlocked - vmsNeedsRemediation;
    const successRange = { normal: [98.6, 99.8], degrading: [96.5, 98.4], alert: [91.0, 95.5], recovering: [96.8, 98.9] }[p];
    const lagRange = { normal: [2, 6], degrading: [8, 14], alert: [15, 28], recovering: [6, 11] }[p];
    const migratedShare = m.migrated / MIG_VMS_DISCOVERED;
    return {
      vertical: 'migration',
      phase: p,
      riskScore: this._risk({ normal: 0.17, degrading: 0.43, alert: 0.78, recovering: 0.32 }),
      vmsDiscovered: MIG_VMS_DISCOVERED,
      vmsAssessed,
      vmsReady,
      vmsNeedsRemediation,
      vmsBlocked,
      currentWave: this._migrationWave(),
      totalWaves: MIG_TOTAL_WAVES,
      vmsMigrated: m.migrated,
      inFlightMigrations: p === 'alert' ? randInt(2, 6) : randInt(6, 14),
      dataTransferredTb: +(m.migrated * MIG_AVG_VM_TB).toFixed(1),
      cutoverSuccessRatePct: +randRange(successRange[0], successRange[1]).toFixed(1),
      rollbackCount: m.rollbacks,
      precopyLagMin: randInt(lagRange[0], lagRange[1]),
      estimatedLicensingSavingsUsdPerYear: MIG_ANNUAL_LICENSING_SAVINGS_USD,
      realizedLicensingSavingsUsdPerYear: Math.round(MIG_ANNUAL_LICENSING_SAVINGS_USD * migratedShare),
      roiMonthly: {
        monthlyCost: 17500,
        monthlyProtected: 245000 + randInt(0, 9999),
        roiRatio: 14,
        paybackDays: 2.1,
      },
    };
  }

  _gpuMetrics() {
    const p = this.phase;
    const util = { normal: [74, 82], degrading: [60, 68], alert: [52, 61], recovering: [68, 76] }[p];
    const mem = { normal: [66, 74], degrading: [72, 80], alert: [84, 93], recovering: [70, 77] }[p];
    const idle = { normal: [3, 8], degrading: [10, 16], alert: [12, 24], recovering: [6, 11] }[p];
    const temp = { normal: [66, 73], degrading: [76, 82], alert: [85, 91], recovering: [72, 78] }[p];
    const idleGpus = randInt(idle[0], idle[1]);
    const rate = +(GPU_HOURLY_RATE_USD + randRange(-0.04, 0.04)).toFixed(2);
    const monthlySpend = Math.round(GPU_FLEET_SIZE * rate * HOURS_PER_MONTH);
    const projectedMonthlySavings = Math.round(idleGpus * rate * HOURS_PER_MONTH * CONSOLIDATION_RECOVERY);
    return {
      vertical: 'gpu',
      phase: p,
      riskScore: this._risk({ normal: 0.16, degrading: 0.44, alert: 0.8, recovering: 0.33 }),
      fleetSize: GPU_FLEET_SIZE,
      gpuUtilizationPct: +randRange(util[0], util[1]).toFixed(1),
      memoryUtilizationPct: +randRange(mem[0], mem[1]).toFixed(1),
      idleGpus,
      thermalThrottlingEvents: p === 'alert' ? randInt(3, 9) : p === 'degrading' ? randInt(0, 2) : 0,
      eccErrors: p === 'alert' ? randInt(1, 4) : 0,
      avgGpuTempC: randInt(temp[0], temp[1]),
      costPerGpuHourUsd: rate,
      monthlySpendUsd: monthlySpend,
      projectedMonthlySavingsUsd: projectedMonthlySavings,
      roiMonthly: {
        monthlyCost: 17500,
        monthlyProtected: 285000 + randInt(0, 14999),
        roiRatio: 16,
        paybackDays: 1.8,
      },
    };
  }

  _generateAlert() {
    const timestamp = new Date().toISOString();
    let alerts;
    if (this.vertical === 'healthcare') {
      alerts = [
        { severity: 'critical', msg: `PT-${randId()} — SpO₂ dropped to ${randInt(82, 86)}% in ICU`, category: 'Clinical Safety' },
        { severity: 'critical', msg: `PT-${randId()} — Tachycardia: HR ${randInt(131, 160)} bpm in ED`, category: 'Clinical Safety' },
        { severity: 'high', msg: `USR-${randId()} — Bulk PHI export: ${randInt(150, 549)} records after hours`, category: 'PHI Anomaly' },
        { severity: 'high', msg: `EHR Gateway p99 latency: ${randInt(210, 289)}ms — SLO breach`, category: 'System Reliability' },
        { severity: 'medium', msg: `PT-${randId()} — Hypertensive crisis: BP ${randInt(195, 219)}/110`, category: 'Clinical Safety' },
        { severity: 'medium', msg: `Contractor ${randId()} accessing cross-dept records during weekend`, category: 'PHI Anomaly' },
      ];
    } else if (this.vertical === 'fintech') {
      alerts = [
        { severity: 'critical', msg: `TXN-${randId()} — Fraud score 0.${randInt(87, 98)}: geo-impossible travel $${randInt(1800, 3799).toLocaleString('en-US')}`, category: 'Fraud Detection' },
        { severity: 'critical', msg: `ACC-${randId()} — Velocity abuse: ${randInt(18, 29)} transactions in 60s`, category: 'Fraud Detection' },
        { severity: 'high', msg: `GW-002 — p99 latency ${randInt(185, 304)}ms — SLO breach detected`, category: 'Payment Reliability' },
        { severity: 'high', msg: `Settlement BATCH-${String(randInt(1, 20)).padStart(3, '0')} at risk — ${randInt(130, 189)} min to clearing window`, category: 'Settlement Risk' },
        { severity: 'medium', msg: `Unusual MCC-7995 (gambling) cluster: ${randInt(8, 19)} accounts, fraud score escalating`, category: 'Fraud Detection' },
        { severity: 'medium', msg: 'AML flag: structured transactions below reporting threshold — BSA review triggered', category: 'Compliance' },
      ];
    } else if (this.vertical === 'migration') {
      const wave = this._migrationWave();
      const vm = ['erp-db-02', 'sap-app-04', 'fileserver-01', 'oracle-rac-03', 'citrix-vda-11', 'exchange-mbx-02'][randInt(0, 5)];
      const prevWave = Math.max(1, wave - 1);
      const waveSize = randInt(38, 52);
      alerts = [
        { severity: 'critical', msg: `Wave ${wave}: VM ${vm} blocked — RDM disk unsupported, remediation required`, category: 'Assessment' },
        { severity: 'critical', msg: `Wave ${wave}: cutover of ${vm} failed validation — rolled back to vSphere`, category: 'Cutover' },
        { severity: 'high', msg: `Warm migration precopy lag > ${randInt(15, 28)} min on ${vm}`, category: 'Data Transfer' },
        { severity: 'high', msg: `Wave ${wave}: VLAN ${randInt(100, 399)} has no NetworkAttachmentDefinition mapping — ${randInt(3, 9)} VMs on hold`, category: 'Network Mapping' },
        { severity: 'medium', msg: `Cutover window for wave ${prevWave} completed — ${waveSize}/${waveSize} VMs validated`, category: 'Cutover' },
        { severity: 'medium', msg: `VM ${vm}: VMware Tools / guest agent swap pending — virtio drivers staged`, category: 'Remediation' },
      ];
    } else {
      const node = `gpu-node-${String(randInt(1, 32)).padStart(2, '0')}`;
      alerts = [
        { severity: 'critical', msg: `GPU node ${node}: thermal throttling (${randInt(86, 92)}°C) — migrating training job`, category: 'Thermal' },
        { severity: 'critical', msg: `GPU node ${node}: ${randInt(2, 6)} uncorrectable ECC errors on GPU${randInt(0, 7)} — cordoned, draining workloads`, category: 'Hardware Health' },
        { severity: 'high', msg: `${randInt(8, 16)} GPUs idle >2h — consolidation recommended`, category: 'Cost Optimization' },
        { severity: 'high', msg: `Training job llm-ft-${randId()}: HBM utilization ${randInt(94, 99)}% — OOM risk, checkpointing`, category: 'Capacity' },
        { severity: 'medium', msg: `Inference pool a100-serve: ${randInt(31, 44)}% utilization — rightsizing saves ~$${randInt(18, 42)}K/mo`, category: 'Cost Optimization' },
        { severity: 'medium', msg: `NCCL all-reduce p99 ${randInt(40, 75)}ms on rack r${randInt(1, 8)} — NVLink degradation suspected`, category: 'Interconnect' },
      ];
    }
    return { ...alerts[Math.floor(Math.random() * alerts.length)], timestamp };
  }

  getExplainability() {
    const hot = this.phase === 'alert';
    if (this.vertical === 'healthcare') {
      return {
        title: 'Top Clinical Risk Contributors',
        factors: [
          { name: 'Vital Sign Anomaly (SpO₂/HR)', weight: 0.35, value: hot ? 0.91 : 0.18 },
          { name: 'After-Hours PHI Access Pattern', weight: 0.25, value: hot ? 0.82 : 0.05 },
          { name: 'Cross-Dept Record Access', weight: 0.2, value: hot ? 0.74 : 0.02 },
          { name: 'EHR Latency SLO Deviation', weight: 0.12, value: hot ? 0.67 : 0.15 },
          { name: 'Patient Acuity Level', weight: 0.08, value: 0.55 },
        ],
      };
    }
    if (this.vertical === 'fintech') {
      return {
        title: 'Top Fraud Risk Contributors',
        factors: [
          { name: 'Transaction Amount Anomaly (z-score)', weight: 0.3, value: hot ? 0.94 : 0.22 },
          { name: 'Velocity Pattern (trans/hour)', weight: 0.25, value: hot ? 0.89 : 0.12 },
          { name: 'Geographic Risk (jurisdiction)', weight: 0.15, value: hot ? 0.78 : 0.08 },
          { name: 'Channel Risk (CNP vs POS)', weight: 0.15, value: hot ? 0.65 : 0.25 },
          { name: 'Merchant Category (MCC)', weight: 0.15, value: hot ? 0.55 : 0.05 },
        ],
      };
    }
    if (this.vertical === 'migration') {
      return {
        title: 'Top Migration Risk Contributors',
        factors: [
          { name: 'Unsupported Disk/Device Config (RDM, passthrough)', weight: 0.3, value: hot ? 0.86 : 0.17 },
          { name: 'Warm-Migration Precopy Lag', weight: 0.25, value: hot ? 0.79 : 0.12 },
          { name: 'Network/VLAN Mapping Gaps', weight: 0.2, value: hot ? 0.71 : 0.09 },
          { name: 'Application Dependency Coupling', weight: 0.15, value: hot ? 0.64 : 0.26 },
          { name: 'Target Storage-Class Throughput', weight: 0.1, value: hot ? 0.57 : 0.14 },
        ],
      };
    }
    return {
      title: 'Top GPU Fleet Risk Contributors',
      factors: [
        { name: 'Thermal Headroom (°C to throttle)', weight: 0.3, value: hot ? 0.88 : 0.14 },
        { name: 'Idle Capacity (GPU-hours wasted)', weight: 0.25, value: hot ? 0.76 : 0.21 },
        { name: 'HBM Memory Pressure', weight: 0.2, value: hot ? 0.81 : 0.32 },
        { name: 'ECC Error Rate (DCGM)', weight: 0.15, value: hot ? 0.69 : 0.03 },
        { name: 'Scheduler Queue Depth', weight: 0.1, value: hot ? 0.58 : 0.18 },
      ],
    };
  }

  getActiveAlerts() {
    return this.alertLog.slice(0, 8);
  }

  getRiskHistory() {
    return [...this.riskHistory];
  }

  getSafety() {
    return this.safety.snapshot();
  }

  /** Full payload pushed over the WebSocket feed. */
  getState() {
    return {
      type: 'state_update',
      metrics: this.getMetrics(),
      alerts: this.getActiveAlerts(),
      explainability: this.getExplainability(),
      riskHistory: this.getRiskHistory(),
      safety: this.getSafety(),
    };
  }
}

module.exports = {
  VERTICALS,
  PHASES,
  PHASE_SCHEDULE,
  AUTONOMY_MODES,
  DemoSimulator,
  SafetyState,
  isValidVertical,
};
