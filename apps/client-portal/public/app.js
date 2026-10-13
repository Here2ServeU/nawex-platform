// ===========================================================================
// Golden Platform — Executive Console frontend (vanilla JS)
// ===========================================================================
'use strict';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/feed`;
const API_BASE = '';
const RECONNECT_MS = 4000;
const PHASE_LABELS = { normal: 'System Normal', degrading: 'Degrading', alert: '⚠ ALERT ACTIVE', recovering: 'Recovering' };

const fmtInt = (v) => Number(v).toLocaleString('en-US');
const fmtPct = (v) => Number(v).toFixed(1);

// alertWhen(value, metrics) -> true when the stat should be highlighted.
const STAT_DEFS = {
  healthcare: [
    { label: 'Patients Monitored', key: 'patientsMonitored', unit: 'active', fmt: fmtInt },
    { label: 'EHR Ingest Rate', key: 'ehrIngestRate', unit: 'records/min', fmt: fmtInt },
    { label: 'Clinical Alerts', key: 'clinicalAlerts', unit: 'active', fmt: fmtInt, alertWhen: (v) => v > 0 },
    { label: 'HIPAA Compliance', key: 'hipaaCompliance', unit: '% SLA', fmt: fmtPct },
  ],
  fintech: [
    { label: 'Transactions / sec', key: 'transactionsPerSec', unit: 'TPS', fmt: fmtInt },
    { label: 'Fraud Risk Score', key: 'fraudScore', unit: 'composite', fmt: (v) => v.toFixed(3), alertWhen: (v) => v > 0.5 },
    { label: 'Active Fraud Alerts', key: 'activeAlerts', unit: 'flagged', fmt: fmtInt, alertWhen: (v) => v > 0 },
    { label: 'PCI Compliance', key: 'pciCompliance', unit: '% SLA', fmt: fmtPct },
  ],
  gpu: [
    { label: 'Fleet GPU Utilization', key: 'gpuUtilizationPct', unit: '% of fleet', fmt: fmtPct, alertWhen: (v) => v < 65 },
    { label: 'GPU Memory Utilization', key: 'memoryUtilizationPct', unit: '% HBM', fmt: fmtPct, alertWhen: (v) => v > 85 },
    { label: 'Idle GPUs', key: 'idleGpus', unit: (m) => `of ${m.fleetSize} GPUs`, fmt: fmtInt, alertWhen: (v) => v >= 10 },
    { label: 'Thermal Throttling', key: 'thermalThrottlingEvents', unit: (m) => `events · avg ${m.avgGpuTempC}°C`, fmt: fmtInt, alertWhen: (v) => v > 0 },
    { label: 'ECC Errors', key: 'eccErrors', unit: 'uncorrectable', fmt: fmtInt, alertWhen: (v) => v > 0 },
    { label: '$ / GPU-hour', key: 'costPerGpuHourUsd', unit: 'blended on-demand', fmt: (v) => '$' + v.toFixed(2) },
    { label: 'Monthly GPU Spend', key: 'monthlySpendUsd', unit: 'run-rate', fmt: (v) => formatUSD(v) },
    { label: 'Projected Savings', key: 'projectedMonthlySavingsUsd', unit: '/ month from rightsizing', fmt: (v) => formatUSD(v), good: true },
  ],
  migration: [
    { label: 'VMs Discovered', key: 'vmsDiscovered', unit: (m) => `${fmtInt(m.vmsAssessed)} assessed`, fmt: fmtInt },
    { label: 'Current Wave', key: 'currentWave', unit: 'migration wave', fmt: (v, m) => `${v} / ${m.totalWaves}` },
    { label: 'VMs Migrated', key: 'vmsMigrated', unit: (m) => `of ${fmtInt(m.vmsDiscovered)}`, fmt: fmtInt, good: true },
    { label: 'In-flight Migrations', key: 'inFlightMigrations', unit: (m) => `precopy lag ${m.precopyLagMin} min`, fmt: fmtInt },
    { label: 'Data Transferred', key: 'dataTransferredTb', unit: 'TB', fmt: (v) => v.toFixed(1) },
    { label: 'Cutover Success', key: 'cutoverSuccessRatePct', unit: '% validated', fmt: fmtPct, alertWhen: (v) => v < 97 },
    { label: 'Rollbacks', key: 'rollbackCount', unit: 'to vSphere', fmt: fmtInt, alertWhen: (v) => v > 2 },
    { label: 'Licensing Savings', key: 'estimatedLicensingSavingsUsdPerYear', unit: (m) => `/ yr · ${formatUSD(m.realizedLicensingSavingsUsdPerYear)} realized`, fmt: (v) => formatUSD(v), good: true },
  ],
};

const PROVENANCE_LIMIT = 4;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let ws = null;
let currentVertical = 'healthcare';
let riskChart = null;
let gaugeChart = null;
let reconnectTimer = null;
let provenanceModels = null;
let lastROIVertical = null;
let lastTickerAlerts = '';
let switchPendingUntil = 0; // ignore stale updates right after a local switch

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.toggle-btn[data-vertical]').forEach((btn) => {
    btn.addEventListener('click', () => switchVertical(btn.dataset.vertical));
  });
  initGaugeChart();
  initRiskChart();
  renderStatsRow();
  loadConfig();
  loadProvenance();
  connectWS();
});

// ---------------------------------------------------------------------------
// Config / branding
// ---------------------------------------------------------------------------
function loadConfig() {
  fetch(`${API_BASE}/api/config`)
    .then((r) => r.json())
    .then((cfg) => {
      if (cfg.platformName) {
        document.getElementById('brandName').textContent = cfg.platformName;
        document.getElementById('brandLogo').textContent = cfg.platformName.trim().charAt(0).toUpperCase() || 'G';
      }
      if (cfg.consoleTitle) document.title = cfg.consoleTitle;
      if (cfg.defaultVertical && cfg.defaultVertical !== currentVertical) applyVertical(cfg.defaultVertical);
    })
    .catch(() => {});
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
function connectWS() {
  if (ws) {
    ws.onclose = null;
    ws.close();
  }
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setConnStatus(true);
    clearTimeout(reconnectTimer);
  };

  ws.onmessage = (evt) => {
    let data;
    try {
      data = JSON.parse(evt.data);
    } catch {
      return;
    }
    if (data.type === 'state_update') handleStateUpdate(data);
  };

  ws.onclose = () => {
    setConnStatus(false);
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectWS, RECONNECT_MS);
  };
  ws.onerror = () => ws.close();
}

function setConnStatus(ok) {
  document.getElementById('connDot').className = `conn-dot ${ok ? 'connected' : 'error'}`;
  document.getElementById('connLabel').textContent = ok ? 'Live Data Stream' : 'Reconnecting…';
}

// ---------------------------------------------------------------------------
// State Update Handler
// ---------------------------------------------------------------------------
function handleStateUpdate(data) {
  const { metrics, alerts, explainability, riskHistory, safety } = data;
  if (!metrics) return;
  // Another viewer may have switched the vertical server-side; follow it.
  if (metrics.vertical && metrics.vertical !== currentVertical) {
    if (Date.now() < switchPendingUntil || !STAT_DEFS[metrics.vertical]) return;
    applyVertical(metrics.vertical);
  }

  updatePhaseBadge(metrics.phase);
  updateGauge(metrics.riskScore);
  updateRiskChart(riskHistory);
  updateStatsRow(metrics);
  updateMigrationPanel(metrics);
  updateROIPanel(metrics);
  updateAlertTicker(alerts);
  updateExplainability(explainability);
  updateSafety(safety);
}

function updatePhaseBadge(phase) {
  const el = document.getElementById('phaseBadge');
  el.textContent = PHASE_LABELS[phase] || phase;
  el.className = `phase-badge ${phase}`;
}

// ---------------------------------------------------------------------------
// AI Safety panel
// ---------------------------------------------------------------------------
function updateSafety(safety) {
  if (!safety) return;
  const mode = ['dry_run', 'supervised', 'autonomous'].includes(safety.autonomyMode) ? safety.autonomyMode : 'supervised';
  const modeEl = document.getElementById('safetyMode');
  modeEl.textContent = mode;
  modeEl.className = `safety-value mode-${mode}`;

  const cap = Math.max(1, Number(safety.actionCap) || 1);
  const used = Number(safety.actionsThisHour) || 0;
  document.getElementById('safetyActions').textContent = used;
  document.getElementById('safetyCap').textContent = cap;
  const fill = document.getElementById('safetyFill');
  fill.style.width = `${Math.min(100, (used / cap) * 100)}%`;
  fill.className = `safety-fill ${used / cap >= 1 ? 'full' : used / cap >= 0.75 ? 'warn' : ''}`;

  const engaged = safety.killSwitch === 'engaged';
  const killEl = document.getElementById('safetyKill');
  killEl.textContent = engaged ? 'ENGAGED — autonomy halted' : 'armed';
  killEl.className = `safety-value ${engaged ? 'kill-engaged' : 'kill-armed'}`;
}

// ---------------------------------------------------------------------------
// Risk Gauge (doughnut)
// ---------------------------------------------------------------------------
function riskColor(score) {
  return score > 0.65 ? '#EF4444' : score > 0.4 ? '#F59E0B' : '#10B981';
}

function initGaugeChart() {
  const ctx = document.getElementById('gaugeChart').getContext('2d');
  gaugeChart = new Chart(ctx, {
    type: 'doughnut',
    data: { datasets: [{ data: [0.18, 0.82], backgroundColor: ['#10B981', '#1E3A5F'], borderWidth: 0, hoverOffset: 0 }] },
    options: {
      cutout: '72%',
      circumference: 270,
      rotation: -135,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { duration: 600 },
      responsive: false,
    },
  });
}

function updateGauge(score) {
  const color = riskColor(score);
  gaugeChart.data.datasets[0].data = [score, 1 - score];
  gaugeChart.data.datasets[0].backgroundColor = [color, '#1E3A5F'];
  gaugeChart.update('active');
  const el = document.getElementById('gaugeValue');
  el.textContent = score.toFixed(2);
  el.style.color = color;
}

// ---------------------------------------------------------------------------
// Risk Time-Series Chart
// ---------------------------------------------------------------------------
function initRiskChart() {
  const ctx = document.getElementById('riskChart').getContext('2d');
  riskChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: Array.from({ length: 60 }, (_, i) => `${60 - i}s ago`),
      datasets: [{
        label: 'AI Risk Score',
        data: Array(60).fill(0.18),
        borderColor: '#3B82F6',
        backgroundColor: 'rgba(59, 130, 246, 0.08)',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.4,
      }],
    },
    options: {
      animation: { duration: 400 },
      scales: {
        x: { display: false },
        y: {
          min: 0,
          max: 1,
          ticks: { color: '#94A3B8', stepSize: 0.25, callback: (v) => `${(v * 100).toFixed(0)}%` },
          grid: { color: '#1E3A5F' },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => `Risk: ${(c.parsed.y * 100).toFixed(1)}%` } },
      },
      responsive: true,
      maintainAspectRatio: true,
    },
  });
}

function updateRiskChart(history) {
  if (!history || !history.length) return;
  const lastVal = history[history.length - 1] || 0;
  const color = lastVal > 0.65 ? '#EF4444' : lastVal > 0.4 ? '#F59E0B' : '#3B82F6';
  riskChart.data.datasets[0].data = history;
  riskChart.data.datasets[0].borderColor = color;
  riskChart.data.datasets[0].backgroundColor = `${color}14`;
  riskChart.update('active');
}

// ---------------------------------------------------------------------------
// Stat Cards
// ---------------------------------------------------------------------------
function renderStatsRow() {
  const defs = STAT_DEFS[currentVertical];
  const row = document.getElementById('statsRow');
  row.className = `stats-row cols-${defs.length > 4 ? 'wide' : '4'}`;
  row.innerHTML = defs.map((d, i) => `
    <div class="stat-card">
      <div class="stat-label">${escapeHtml(d.label)}</div>
      <div class="stat-value" id="stat${i}Val">—</div>
      <div class="stat-unit" id="stat${i}Unit">${typeof d.unit === 'string' ? escapeHtml(d.unit) : ''}</div>
    </div>
  `).join('');
}

function updateStatsRow(metrics) {
  STAT_DEFS[currentVertical].forEach((d, i) => {
    const el = document.getElementById(`stat${i}Val`);
    const val = metrics[d.key];
    if (!el || val === undefined) return;
    el.textContent = d.fmt(val, metrics);
    if (typeof d.unit === 'function') document.getElementById(`stat${i}Unit`).textContent = d.unit(metrics);
    let color = 'var(--white)';
    if (d.good) color = 'var(--green)';
    if (d.alertWhen && d.alertWhen(val, metrics)) color = metrics.phase === 'alert' ? 'var(--red)' : 'var(--amber)';
    el.style.color = color;
  });
}

// ---------------------------------------------------------------------------
// Migration panel (assessment bar + wave track)
// ---------------------------------------------------------------------------
function updateMigrationPanel(m) {
  const panel = document.getElementById('migrationPanel');
  if (m.vertical !== 'migration') {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const total = Math.max(1, m.vmsReady + m.vmsNeedsRemediation + m.vmsBlocked);
  document.getElementById('assessReady').style.width = `${(m.vmsReady / total) * 100}%`;
  document.getElementById('assessRemediate').style.width = `${(m.vmsNeedsRemediation / total) * 100}%`;
  document.getElementById('assessBlocked').style.width = `${(m.vmsBlocked / total) * 100}%`;
  document.getElementById('legendReady').textContent = fmtInt(m.vmsReady);
  document.getElementById('legendRemediate').textContent = fmtInt(m.vmsNeedsRemediation);
  document.getElementById('legendBlocked').textContent = fmtInt(m.vmsBlocked);

  const waves = [];
  for (let w = 1; w <= m.totalWaves; w++) {
    const state = w < m.currentWave ? 'done' : w === m.currentWave ? (m.phase === 'alert' ? 'active alert' : 'active') : 'pending';
    waves.push(`<div class="wave ${state}"><span>Wave ${w}</span></div>`);
  }
  document.getElementById('waveTrack').innerHTML = waves.join('');
}

// ---------------------------------------------------------------------------
// ROI Panel
// ---------------------------------------------------------------------------
function updateROIPanel(metrics) {
  const roi = metrics.roiMonthly;
  if (!roi) return;
  document.getElementById('roiMain').textContent = `${roi.roiRatio}x`;
  document.getElementById('roiCost').textContent = `$${roi.monthlyCost.toLocaleString('en-US')}`;
  document.getElementById('roiProtected').textContent = formatUSD(roi.monthlyProtected);
  document.getElementById('roiPayback').textContent = `${roi.paybackDays} days`;
  fetchROI(currentVertical);
}

function fetchROI(vertical) {
  if (vertical === lastROIVertical) return;
  lastROIVertical = vertical;
  fetch(`${API_BASE}/api/roi/${encodeURIComponent(vertical)}`)
    .then((r) => r.json())
    .then((data) => {
      document.getElementById('roiAnnual').textContent = formatUSD(data.annual_net_benefit_usd);
      renderBreakdown(data.breakdown);
    })
    .catch(() => {
      lastROIVertical = null;
    });
}

function renderBreakdown(breakdown) {
  if (!breakdown) return;
  document.getElementById('roiBreakdown').innerHTML = Object.values(breakdown).map((item) => `
    <div class="breakdown-bar">
      <div class="breakdown-bar-label">
        <span>${escapeHtml(item.label)}</span>
        <span>${Number(item.pct_of_total)}%</span>
      </div>
      <div class="breakdown-bar-track">
        <div class="breakdown-bar-fill" style="width:${Number(item.pct_of_total)}%"></div>
      </div>
    </div>
  `).join('');
}

// ---------------------------------------------------------------------------
// Alert Ticker
// ---------------------------------------------------------------------------
function updateAlertTicker(alerts) {
  if (!alerts || !alerts.length) return;
  const key = JSON.stringify(alerts);
  if (key === lastTickerAlerts) return;
  lastTickerAlerts = key;
  const sev = (s) => (['critical', 'high', 'medium'].includes(s) ? s : 'medium');
  // Doubled to create a seamless scrolling loop.
  document.getElementById('tickerInner').innerHTML = [...alerts, ...alerts].map((a) => `
    <span class="ticker-item">
      <span class="ticker-dot ${sev(a.severity)}"></span>
      <span>${a.category ? `[${escapeHtml(a.category)}] ` : ''}${escapeHtml(a.msg)}</span>
    </span>
  `).join('');
}

// ---------------------------------------------------------------------------
// Explainability
// ---------------------------------------------------------------------------
function updateExplainability(explain) {
  if (!explain) return;
  document.getElementById('explainTitle').textContent = explain.title || 'Top Risk Contributing Factors';
  document.getElementById('explainFactors').innerHTML = explain.factors.map((f) => {
    const pct = Math.round(f.value * 100);
    const isHigh = f.value > 0.5;
    return `
      <div class="factor-bar">
        <div class="factor-label-row">
          <span class="factor-name">${escapeHtml(f.name)}</span>
          <span class="factor-score ${isHigh ? 'hot' : 'cool'}">${pct}%</span>
        </div>
        <div class="factor-track">
          <div class="factor-fill ${isHigh ? 'high' : ''}" style="width:${pct}%"></div>
        </div>
      </div>
    `;
  }).join('');
}

// ---------------------------------------------------------------------------
// Research Provenance
// ---------------------------------------------------------------------------
function loadProvenance() {
  if (provenanceModels) return renderProvenance();
  fetch(`${API_BASE}/api/research/provenance`)
    .then((r) => r.json())
    .then((data) => {
      provenanceModels = data.models || [];
      renderProvenance();
    })
    .catch(() => {});
}

function renderProvenance() {
  if (!provenanceModels) return;
  // Vertical-specific models first, then shared forecasting models.
  const specific = provenanceModels.filter((m) => m.verticals && m.verticals.length === 1 && m.verticals[0] === currentVertical);
  const shared = provenanceModels.filter((m) => m.verticals && m.verticals.length > 1 && m.verticals.includes(currentVertical));
  document.getElementById('provenanceGrid').innerHTML = [...specific, ...shared].slice(0, PROVENANCE_LIMIT).map((m) => `
    <div class="model-card" title="${escapeHtml(m.reference)}">
      <div class="model-name">${escapeHtml(m.name)}</div>
      <div class="model-type">${escapeHtml(m.type)}</div>
      <div class="model-metrics">
        <div class="model-metric">P: <span>${escapeHtml(m.precision)}</span></div>
        <div class="model-metric">R: <span>${escapeHtml(m.recall)}</span></div>
      </div>
    </div>
  `).join('');
}

// ---------------------------------------------------------------------------
// Vertical Switch
// ---------------------------------------------------------------------------
function applyVertical(vertical) {
  if (!STAT_DEFS[vertical]) return;
  currentVertical = vertical;
  lastROIVertical = null;
  document.querySelectorAll('.toggle-btn[data-vertical]').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.vertical === vertical);
    btn.setAttribute('aria-pressed', String(btn.dataset.vertical === vertical));
  });
  document.getElementById('migrationPanel').hidden = vertical !== 'migration';
  renderStatsRow();
  renderProvenance();
}

function switchVertical(vertical) {
  if (!STAT_DEFS[vertical] || vertical === currentVertical) return;
  applyVertical(vertical);
  switchPendingUntil = Date.now() + 2000;
  fetch(`${API_BASE}/api/vertical`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vertical }),
  }).catch(() => {});
  riskChart.data.datasets[0].data = Array(60).fill(0.15);
  riskChart.update('active');
  updateGauge(0.15);
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function formatUSD(amount) {
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(2)}M`;
  if (amount >= 1_000) return `$${Math.round(amount / 1_000)}K`;
  return `$${Number(amount).toLocaleString('en-US')}`;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}
