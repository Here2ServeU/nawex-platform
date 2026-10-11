'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  DemoSimulator,
  SafetyState,
  VERTICALS,
  PHASES,
  PHASE_SCHEDULE,
  isValidVertical,
} = require('../src/simulator');

test('vertical whitelist', () => {
  assert.deepEqual([...VERTICALS], ['healthcare', 'fintech', 'gpu', 'migration']);
  for (const v of VERTICALS) assert.equal(isValidVertical(v), true);
  for (const bad of ['', 'HEALTHCARE', 'crypto', '__proto__', 'constructor', null, undefined, 42, {}, ['gpu']]) {
    assert.equal(isValidVertical(bad), false, `expected ${String(bad)} to be rejected`);
  }
  assert.throws(() => new DemoSimulator('crypto'), /Unknown vertical/);
});

test('phases cycle normal -> degrading -> alert -> recovering -> normal', () => {
  const sim = new DemoSimulator('healthcare');
  const seen = [sim.phase];
  const cycle = Object.values(PHASE_SCHEDULE).reduce((a, b) => a + b, 0);
  for (let i = 0; i < cycle; i++) {
    sim.advance();
    if (seen[seen.length - 1] !== sim.phase) seen.push(sim.phase);
  }
  assert.deepEqual(seen, [...PHASES, 'normal']);
  assert.equal(sim.getRiskHistory().length, 60, 'risk history capped at 60');
});

test('alerts are generated only during the alert phase and capped', () => {
  for (const v of VERTICALS) {
    const sim = new DemoSimulator(v);
    for (let i = 0; i < PHASE_SCHEDULE.normal + PHASE_SCHEDULE.degrading - 1; i++) sim.advance();
    assert.equal(sim.getActiveAlerts().length, 0, `${v}: no alerts before alert phase`);
    for (let i = 0; i < PHASE_SCHEDULE.alert; i++) sim.advance();
    const alerts = sim.getActiveAlerts();
    assert.ok(alerts.length > 0 && alerts.length <= 8);
    for (const a of alerts) {
      assert.ok(['critical', 'high', 'medium'].includes(a.severity));
      assert.equal(typeof a.msg, 'string');
      assert.equal(typeof a.category, 'string');
      assert.ok(!Number.isNaN(Date.parse(a.timestamp)));
    }
  }
});

test('every vertical yields a well-formed state payload', () => {
  for (const v of VERTICALS) {
    const state = new DemoSimulator(v).getState();
    assert.equal(state.type, 'state_update');
    assert.equal(state.metrics.vertical, v);
    assert.ok(state.metrics.riskScore >= 0 && state.metrics.riskScore <= 1);
    assert.ok(state.metrics.roiMonthly.monthlyCost > 0);
    assert.equal(state.explainability.factors.length, 5);
    assert.ok(Array.isArray(state.alerts));
    assert.ok(Array.isArray(state.riskHistory));
    assert.deepEqual(Object.keys(state.safety).sort(), ['actionCap', 'actionsThisHour', 'autonomyMode', 'killSwitch', 'simulated']);
  }
});

test('gpu metrics shape and ranges across all phases', () => {
  const sim = new DemoSimulator('gpu');
  for (const phase of PHASES) {
    sim.phase = phase;
    const m = sim.getMetrics();
    assert.equal(m.vertical, 'gpu');
    assert.equal(m.phase, phase);
    for (const key of [
      'fleetSize', 'gpuUtilizationPct', 'memoryUtilizationPct', 'idleGpus', 'thermalThrottlingEvents',
      'eccErrors', 'avgGpuTempC', 'costPerGpuHourUsd', 'monthlySpendUsd', 'projectedMonthlySavingsUsd',
    ]) {
      assert.equal(typeof m[key], 'number', `${key} is a number`);
      assert.ok(m[key] >= 0, `${key} >= 0`);
    }
    assert.ok(m.gpuUtilizationPct <= 100 && m.memoryUtilizationPct <= 100);
    assert.ok(m.idleGpus <= m.fleetSize);
    assert.ok(m.costPerGpuHourUsd > 1 && m.costPerGpuHourUsd < 5);
    assert.ok(m.projectedMonthlySavingsUsd < m.monthlySpendUsd);
    if (phase === 'alert') {
      assert.ok(m.thermalThrottlingEvents > 0);
      assert.ok(m.eccErrors > 0);
      assert.ok(m.avgGpuTempC >= 85);
    }
    if (phase === 'normal') assert.equal(m.eccErrors, 0);
  }
});

test('gpu alerts include thermal throttling and idle-consolidation narratives', () => {
  const sim = new DemoSimulator('gpu');
  const msgs = new Set();
  for (let i = 0; i < 300; i++) msgs.add(sim._generateAlert().msg);
  const all = [...msgs].join('\n');
  assert.match(all, /GPU node gpu-node-\d{2}: thermal throttling \(\d+°C\) — migrating training job/);
  assert.match(all, /\d+ GPUs idle >2h — consolidation recommended/);
});

test('migration metrics shape, consistency and progression', () => {
  const sim = new DemoSimulator('migration');
  const first = sim.getMetrics();
  for (const key of [
    'vmsDiscovered', 'vmsAssessed', 'vmsReady', 'vmsNeedsRemediation', 'vmsBlocked', 'currentWave', 'totalWaves',
    'vmsMigrated', 'inFlightMigrations', 'dataTransferredTb', 'cutoverSuccessRatePct', 'rollbackCount',
    'precopyLagMin', 'estimatedLicensingSavingsUsdPerYear', 'realizedLicensingSavingsUsdPerYear',
  ]) {
    assert.equal(typeof first[key], 'number', `${key} is a number`);
    assert.ok(first[key] >= 0, `${key} >= 0`);
  }
  assert.equal(first.vmsReady + first.vmsNeedsRemediation + first.vmsBlocked, first.vmsAssessed);
  assert.ok(first.vmsAssessed <= first.vmsDiscovered);
  assert.ok(first.currentWave >= 1 && first.currentWave <= first.totalWaves);
  assert.ok(first.cutoverSuccessRatePct <= 100);
  assert.ok(first.realizedLicensingSavingsUsdPerYear <= first.estimatedLicensingSavingsUsdPerYear);

  for (let i = 0; i < 30; i++) sim.advance(); // normal phase migrates VMs
  const later = sim.getMetrics();
  assert.ok(later.vmsMigrated > first.vmsMigrated, 'VMs migrate over time');
  assert.ok(later.dataTransferredTb >= first.dataTransferredTb);
});

test('migration alerts include blocked-VM, precopy-lag and cutover narratives', () => {
  const sim = new DemoSimulator('migration');
  const all = Array.from({ length: 300 }, () => sim._generateAlert().msg).join('\n');
  assert.match(all, /Wave \d+: VM [\w-]+ blocked — RDM disk unsupported, remediation required/);
  assert.match(all, /Warm migration precopy lag > \d+ min on [\w-]+/);
  assert.match(all, /Cutover window for wave \d+ completed — (\d+)\/\1 VMs validated/);
});

test('safety state enforces the hourly action cap and kill switch', () => {
  const s = new SafetyState({ mode: 'autonomous', actionCap: 3 });
  const t0 = 1_000_000;
  assert.equal(s.snapshot(t0).killSwitch, 'armed');
  assert.equal(s.recordAction(t0), true);
  assert.equal(s.recordAction(t0 + 1), true);
  assert.equal(s.recordAction(t0 + 2), true);
  assert.equal(s.snapshot(t0 + 3).killSwitch, 'engaged');
  assert.equal(s.recordAction(t0 + 4), false, 'blocked once cap reached');
  assert.equal(s.snapshot(t0 + 5).actionsThisHour, 3);
  // After the hour window drains the kill switch re-arms.
  const later = t0 + 60 * 60 * 1000 + 10;
  assert.deepEqual(s.snapshot(later), {
    autonomyMode: 'autonomous', actionsThisHour: 0, actionCap: 3, killSwitch: 'armed', simulated: true,
  });
  assert.equal(new SafetyState({ mode: 'yolo' }).mode, 'supervised', 'unknown mode falls back to supervised');
});
