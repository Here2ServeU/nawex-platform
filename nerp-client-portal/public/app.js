// ===========================================================================
// NERP Executive Client Portal — Frontend Application
// Rev. Dr. Emmanuel Naweji — AI Research Platform
// ===========================================================================
'use strict';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const WS_URL       = `ws://${location.host}/feed`;
const API_BASE     = '';
const RECONNECT_MS = 4000;
const PHASE_LABELS = { normal: 'System Normal', degrading: 'Degrading', alert: '⚠ ALERT ACTIVE', recovering: 'Recovering' };

const HC_STATS = [
  { id: 'statA', label: 'Patients Monitored',   key: 'patientsMonitored',  unit: 'active',         fmt: v => v },
  { id: 'statB', label: 'EHR Ingest Rate',       key: 'ehrIngestRate',      unit: 'records/min',    fmt: v => v },
  { id: 'statC', label: 'Clinical Alerts',       key: 'clinicalAlerts',     unit: 'active',         fmt: v => v, alertKey: true },
  { id: 'statD', label: 'HIPAA Compliance',      key: 'hipaaCompliance',    unit: '% SLA',          fmt: v => v.toFixed(1) },
];

const FT_STATS = [
  { id: 'statA', label: 'Transactions / sec',    key: 'transactionsPerSec', unit: 'TPS',            fmt: v => v },
  { id: 'statB', label: 'Fraud Risk Score',      key: 'fraudScore',         unit: 'composite',      fmt: v => v.toFixed(3), alertKey: true },
  { id: 'statC', label: 'Active Fraud Alerts',   key: 'activeAlerts',       unit: 'flagged',        fmt: v => v, alertKey: true },
  { id: 'statD', label: 'PCI Compliance',        key: 'pciCompliance',      unit: '% SLA',          fmt: v => v.toFixed(1) },
];

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let ws               = null;
let currentVertical  = 'healthcare';
let riskChart        = null;
let gaugeChart       = null;
let riskHistory      = Array(60).fill(0);
let reconnectTimer   = null;
let provenanceLoaded = false;

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  initGaugeChart();
  initRiskChart();
  renderStatsRow();
  loadProvenance();
  connectWS();
});

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
function connectWS() {
  if (ws) ws.close();
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setConnStatus(true);
    clearTimeout(reconnectTimer);
  };

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      if (data.type === 'state_update') handleStateUpdate(data);
    } catch (_) {}
  };

  ws.onerror = ws.onclose = () => {
    setConnStatus(false);
    reconnectTimer = setTimeout(connectWS, RECONNECT_MS);
  };
}

function setConnStatus(ok) {
  document.getElementById('connDot').className   = `conn-dot ${ok ? 'connected' : 'error'}`;
  document.getElementById('connLabel').textContent = ok ? 'Live Data Stream' : 'Reconnecting…';
}

// ---------------------------------------------------------------------------
// State Update Handler
// ---------------------------------------------------------------------------
function handleStateUpdate(data) {
  const { metrics, alerts, explainability, riskHistory: rh } = data;
  if (!metrics) return;

  updatePhaseBadge(metrics.phase);
  updateGauge(metrics.riskScore);
  updateRiskChart(rh);
  updateStatsRow(metrics);
  updateROIPanel(metrics);
  updateAlertTicker(alerts);
  updateExplainability(explainability);
}

// ---------------------------------------------------------------------------
// Phase Badge
// ---------------------------------------------------------------------------
function updatePhaseBadge(phase) {
  const el = document.getElementById('phaseBadge');
  el.textContent  = PHASE_LABELS[phase] || phase;
  el.className    = `phase-badge ${phase}`;
}

// ---------------------------------------------------------------------------
// Risk Gauge (doughnut)
// ---------------------------------------------------------------------------
function initGaugeChart() {
  const ctx = document.getElementById('gaugeChart').getContext('2d');
  gaugeChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [0.18, 0.82],
        backgroundColor: ['#10B981', '#1E3A5F'],
        borderWidth: 0,
        hoverOffset: 0,
      }]
    },
    options: {
      cutout: '72%',
      circumference: 270,
      rotation: -135,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { duration: 600 },
      responsive: false,
    }
  });
}

function updateGauge(score) {
  const color = score > 0.65 ? '#EF4444' : score > 0.40 ? '#F59E0B' : '#10B981';
  gaugeChart.data.datasets[0].data = [score, 1 - score];
  gaugeChart.data.datasets[0].backgroundColor = [color, '#1E3A5F'];
  gaugeChart.update('active');

  const el = document.getElementById('gaugeValue');
  el.textContent = score.toFixed(2);
  el.style.color  = color;
}

// ---------------------------------------------------------------------------
// Risk Time-Series Chart
// ---------------------------------------------------------------------------
function initRiskChart() {
  const ctx = document.getElementById('riskChart').getContext('2d');
  const labels = Array(60).fill('').map((_, i) => (60 - i) + 's ago');

  riskChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'AI Risk Score',
        data: Array(60).fill(0.18),
        borderColor: '#3B82F6',
        backgroundColor: 'rgba(59, 130, 246, 0.08)',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.4,
      }]
    },
    options: {
      animation: { duration: 400 },
      scales: {
        x: { display: false },
        y: {
          min: 0, max: 1,
          ticks: { color: '#94A3B8', stepSize: 0.25, callback: v => (v * 100).toFixed(0) + '%' },
          grid: { color: '#1E3A5F' },
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `Risk: ${(ctx.parsed.y * 100).toFixed(1)}%`,
          }
        }
      },
      responsive: true,
      maintainAspectRatio: true,
    }
  });
}

function updateRiskChart(history) {
  if (!history || !history.length) return;
  riskChart.data.datasets[0].data = history;
  const lastVal = history[history.length - 1] || 0;
  const color = lastVal > 0.65 ? '#EF4444' : lastVal > 0.40 ? '#F59E0B' : '#3B82F6';
  riskChart.data.datasets[0].borderColor = color;
  riskChart.data.datasets[0].backgroundColor = color + '14';
  riskChart.update('active');
}

// ---------------------------------------------------------------------------
// Stat Cards
// ---------------------------------------------------------------------------
function renderStatsRow() {
  const defs = currentVertical === 'healthcare' ? HC_STATS : FT_STATS;
  const row  = document.getElementById('statsRow');
  row.innerHTML = defs.map(d => `
    <div class="stat-card" id="${d.id}">
      <div class="stat-label">${d.label}</div>
      <div class="stat-value" id="${d.id}Val">—</div>
      <div class="stat-unit">${d.unit}</div>
    </div>
  `).join('');
}

function updateStatsRow(metrics) {
  const defs = currentVertical === 'healthcare' ? HC_STATS : FT_STATS;
  defs.forEach(d => {
    const el = document.getElementById(d.id + 'Val');
    if (!el) return;
    const val = metrics[d.key];
    if (val === undefined) return;
    el.textContent = d.fmt(val);
    const isHot = d.alertKey && val > (currentVertical === 'healthcare' ? 0 : 0.5);
    el.style.color = (d.alertKey && val > 0)
      ? (metrics.phase === 'alert' ? 'var(--red)' : 'var(--amber)')
      : 'var(--white)';
  });
}

// ---------------------------------------------------------------------------
// ROI Panel
// ---------------------------------------------------------------------------
function updateROIPanel(metrics) {
  const roi = metrics.roiMonthly;
  if (!roi) return;
  document.getElementById('roiMain').textContent = roi.roiRatio + 'x';
  document.getElementById('roiCost').textContent  = '$' + roi.monthlyCost.toLocaleString();
  document.getElementById('roiProtected').textContent = formatUSD(roi.monthlyProtected);
  document.getElementById('roiPayback').textContent   = roi.paybackDays + ' days';

  // Fetch full breakdown once per vertical
  fetchROI(currentVertical);
}

let lastROIVertical = null;
function fetchROI(vertical) {
  if (vertical === lastROIVertical) return;
  lastROIVertical = vertical;
  fetch(`${API_BASE}/api/roi/${vertical}`)
    .then(r => r.json())
    .then(data => {
      document.getElementById('roiAnnual').textContent = formatUSD(data.annual_net_benefit_usd);
      renderBreakdown(data.breakdown);
    })
    .catch(() => {});
}

function renderBreakdown(breakdown) {
  if (!breakdown) return;
  const items = Object.values(breakdown);
  const total = items.reduce((s, i) => s + i.annual_usd, 0);
  const html  = items.map(item => `
    <div class="breakdown-bar">
      <div class="breakdown-bar-label">
        <span>${item.label}</span>
        <span>${item.pct_of_total}%</span>
      </div>
      <div class="breakdown-bar-track">
        <div class="breakdown-bar-fill" style="width:${item.pct_of_total}%"></div>
      </div>
    </div>
  `).join('');
  document.getElementById('roiBreakdown').innerHTML = html;
}

// ---------------------------------------------------------------------------
// Alert Ticker
// ---------------------------------------------------------------------------
let lastTickerAlerts = [];
function updateAlertTicker(alerts) {
  if (!alerts || !alerts.length) return;
  if (JSON.stringify(alerts) === JSON.stringify(lastTickerAlerts)) return;
  lastTickerAlerts = alerts;

  const inner = document.getElementById('tickerInner');
  // Double the alerts to create seamless loop
  const allAlerts = [...alerts, ...alerts];
  inner.innerHTML = allAlerts.map(a => `
    <span class="ticker-item">
      <span class="ticker-dot ${a.severity || 'medium'}"></span>
      <span>${a.category ? '[' + a.category + '] ' : ''}${a.msg}</span>
    </span>
  `).join('');
}

// ---------------------------------------------------------------------------
// Explainability
// ---------------------------------------------------------------------------
function updateExplainability(explain) {
  if (!explain) return;
  document.getElementById('explainTitle').textContent = explain.title || 'Top Risk Contributing Factors';
  const container = document.getElementById('explainFactors');
  container.innerHTML = explain.factors.map(f => {
    const pct    = Math.round(f.value * 100);
    const isHigh = f.value > 0.5;
    return `
      <div class="factor-bar">
        <div class="factor-label-row">
          <span class="factor-name">${f.name}</span>
          <span class="factor-score" style="color:${isHigh ? 'var(--amber)' : 'var(--green)'}">${pct}%</span>
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
  if (provenanceLoaded) return;
  fetch(`${API_BASE}/api/research/provenance`)
    .then(r => r.json())
    .then(data => {
      provenanceLoaded = true;
      renderProvenance(data.models);
    })
    .catch(() => {});
}

function renderProvenance(models) {
  const vertical = currentVertical;
  const relevant = vertical === 'healthcare'
    ? models.filter(m => m.name.includes('LSTM') || m.name.includes('PHI') || m.name.includes('Clinical') || m.name.includes('TCN'))
    : models.filter(m => m.name.includes('LSTM') || m.name.includes('Fraud') || m.name.includes('TCN'));

  document.getElementById('provenanceGrid').innerHTML = relevant.slice(0, 4).map(m => `
    <div class="model-card">
      <div class="model-name">${m.name}</div>
      <div class="model-type">${m.type}</div>
      <div class="model-metrics">
        <div class="model-metric">P: <span>${m.precision}</span></div>
        <div class="model-metric">R: <span>${m.recall}</span></div>
      </div>
    </div>
  `).join('');
}

// ---------------------------------------------------------------------------
// Vertical Switch
// ---------------------------------------------------------------------------
function switchVertical(vertical) {
  if (vertical === currentVertical) return;
  currentVertical = vertical;
  lastROIVertical = null;
  provenanceLoaded = false;

  document.getElementById('btnHospital').className = `toggle-btn ${vertical === 'healthcare' ? 'active' : ''}`;
  document.getElementById('btnBank').className      = `toggle-btn ${vertical === 'fintech'    ? 'active' : ''}`;

  fetch(`${API_BASE}/api/vertical`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vertical }),
  }).catch(() => {});

  renderStatsRow();
  loadProvenance();

  // Reset charts
  riskChart.data.datasets[0].data = Array(60).fill(0.15);
  riskChart.update('active');
  updateGauge(0.15);
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function formatUSD(amount) {
  if (amount >= 1_000_000) return '$' + (amount / 1_000_000).toFixed(2) + 'M';
  if (amount >= 1_000)     return '$' + Math.round(amount / 1_000) + 'K';
  return '$' + amount.toLocaleString();
}
