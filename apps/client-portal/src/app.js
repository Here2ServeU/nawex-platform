// ===========================================================================
// Golden Platform
// Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
// ===========================================================================
// apps/client-portal/src/app.js
//
// Executive Demo Portal — Express app + WebSocket feed factory.
// createPortal() wires everything up WITHOUT binding a port, so tests can call
// portal.server.listen(0). The bootstrap lives in src/server.js.
// ===========================================================================
'use strict';

const http = require('node:http');
const path = require('node:path');
const express = require('express');
const helmet = require('helmet');
const client = require('prom-client');
const { WebSocketServer } = require('ws');

const pkg = require('../package.json');
const { DemoSimulator, SafetyState, VERTICALS, isValidVertical } = require('./simulator');

const VERTICAL_LABELS = Object.freeze({
  healthcare: 'Healthcare',
  fintech: 'Financial Services',
  gpu: 'AI Infrastructure / GPU Fleet',
  migration: 'VMware → OpenShift Migration',
});
const { ROI, PROVENANCE } = require('./data');

const SERVICE_NAME = 'golden-client-portal';
const DEFAULT_PLATFORM_NAME = 'Golden Platform';
const FEED_PATH = '/feed';

// Only the third-party origins index.html actually loads from.
const CSP_DIRECTIVES = {
  defaultSrc: ["'self'"],
  scriptSrc: ["'self'", 'https://cdn.jsdelivr.net'],
  styleSrc: ["'self'", 'https://fonts.googleapis.com'],
  // Dynamic bar widths are rendered via style="" attributes.
  styleSrcAttr: ["'unsafe-inline'"],
  fontSrc: ["'self'", 'https://fonts.gstatic.com'],
  imgSrc: ["'self'", 'data:'],
  connectSrc: ["'self'"],
  objectSrc: ["'none'"],
  frameAncestors: ["'none'"],
  // The demo is often served over plain HTTP on localhost / in a kind cluster.
  upgradeInsecureRequests: null,
};

function parseList(value) {
  return String(value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * @param {object} [opts]
 * @param {number} [opts.tickMs=3000]          simulator tick interval
 * @param {number} [opts.maxConnections=100]   concurrent WebSocket cap
 * @param {number} [opts.maxPayload=4096]      max inbound WS message bytes
 * @param {string} [opts.autonomyMode]         simulated autonomy mode
 * @param {number} [opts.actionCap=20]         simulated per-hour action cap
 * @param {string[]} [opts.allowedOrigins]     extra Origins allowed on /feed
 * @param {string} [opts.platformName]         display name shown in the UI
 */
function createPortal(opts = {}) {
  const tickMs = opts.tickMs ?? 3000;
  const maxConnections = opts.maxConnections ?? 100;
  const maxPayload = opts.maxPayload ?? 4096;
  const allowedOrigins = new Set(opts.allowedOrigins ?? []);
  const platformName = String(opts.platformName || DEFAULT_PLATFORM_NAME).slice(0, 80);
  const safety = new SafetyState({ mode: opts.autonomyMode ?? 'supervised', actionCap: opts.actionCap ?? 20 });

  // One simulator per vertical so REST lookups return live data for any of them.
  const sims = {};
  for (const v of VERTICALS) sims[v] = new DemoSimulator(v, { safety });
  let current = 'healthcare';

  // ---------------------------------------------------------------- metrics
  const register = new client.Registry();
  register.setDefaultLabels({ service: SERVICE_NAME });
  client.collectDefaultMetrics({ register });
  const httpDuration = new client.Histogram({
    name: 'http_request_duration_seconds',
    help: 'HTTP request duration in seconds',
    labelNames: ['method', 'route', 'status_code'],
    buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
    registers: [register],
  });
  const wsConnections = new client.Gauge({
    name: 'golden_client_portal_ws_connections',
    help: 'Open WebSocket feed connections',
    registers: [register],
  });
  const wsRejected = new client.Counter({
    name: 'golden_client_portal_ws_rejected_total',
    help: 'WebSocket upgrades rejected',
    labelNames: ['reason'],
    registers: [register],
  });

  // -------------------------------------------------------------------- app
  const app = express();
  app.disable('x-powered-by');
  app.use(helmet({ contentSecurityPolicy: { useDefaults: true, directives: CSP_DIRECTIVES } }));

  app.use((req, res, next) => {
    const end = httpDuration.startTimer();
    res.on('finish', () => {
      let route = 'unmatched';
      if (req.route) route = req.baseUrl + req.route.path;
      else if (res.statusCode < 400) route = 'static';
      end({ method: req.method, route, status_code: res.statusCode });
    });
    next();
  });

  app.use(express.json({ limit: '4kb' }));
  app.use(express.static(path.join(__dirname, '..', 'public'), { index: 'index.html' }));

  const startTime = Date.now();

  app.get('/health', (req, res) => {
    res.json({ status: 'ok', service: SERVICE_NAME, version: pkg.version });
  });

  app.get('/metrics', async (req, res, next) => {
    try {
      res.set('Content-Type', register.contentType);
      res.send(await register.metrics());
    } catch (err) {
      next(err);
    }
  });

  // Legacy detailed health (kept for existing demo scripts).
  app.get('/api/health', (req, res) => {
    res.json({
      status: 'ok',
      service: SERVICE_NAME,
      version: pkg.version,
      uptime_s: Math.floor((Date.now() - startTime) / 1000),
      vertical: current,
      phase: sims[current].phase,
    });
  });

  // UI configuration (branding is configurable via PLATFORM_NAME).
  app.get('/api/config', (req, res) => {
    res.json({
      platformName,
      consoleTitle: `${platformName} — Executive Console`,
      verticals: VERTICAL_LABELS,
      defaultVertical: current,
      version: pkg.version,
    });
  });

  app.get('/api/vertical', (req, res) => {
    res.json({ current, available: VERTICALS });
  });

  function switchVertical(vertical) {
    current = vertical;
    // Restart the narrative arc for the newly selected vertical.
    sims[vertical] = new DemoSimulator(vertical, { safety });
    broadcast(sims[current].getState());
  }

  app.post('/api/vertical', (req, res) => {
    const vertical = req.body?.vertical;
    if (!isValidVertical(vertical)) {
      return res.status(400).json({ error: `vertical must be one of: ${VERTICALS.join(', ')}` });
    }
    switchVertical(vertical);
    res.json({ switched_to: vertical, ok: true });
  });

  // Validate :vertical once for every route that takes it.
  app.param('vertical', (req, res, next, vertical) => {
    if (!isValidVertical(vertical)) {
      return res.status(400).json({ error: `Unknown vertical. Expected one of: ${VERTICALS.join(', ')}` });
    }
    next();
  });

  app.get('/api/metrics/:vertical', (req, res) => {
    res.json(sims[req.params.vertical].getMetrics());
  });

  app.get('/api/alerts/:vertical', (req, res) => {
    const v = req.params.vertical;
    res.json({ alerts: sims[v].getActiveAlerts(), vertical: v });
  });

  app.get('/api/roi/:vertical', (req, res) => {
    res.json(ROI[req.params.vertical]);
  });

  app.get('/api/safety', (req, res) => {
    res.json(safety.snapshot());
  });

  app.get('/api/research/provenance', (req, res) => {
    res.json(PROVENANCE);
  });

  app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
  });

  // eslint-disable-next-line no-unused-vars
  app.use((err, req, res, next) => {
    const status = err.status || err.statusCode || 500;
    res.status(status).json({ error: status >= 500 ? 'Internal server error' : err.message });
  });

  // ------------------------------------------------------------- websocket
  const server = http.createServer(app);
  const wss = new WebSocketServer({ noServer: true, maxPayload, clientTracking: true });

  function reject(socket, code, text, reason) {
    wsRejected.inc({ reason });
    socket.write(`HTTP/1.1 ${code} ${text}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`);
    socket.destroy();
  }

  server.on('upgrade', (req, socket, head) => {
    let pathname;
    try {
      pathname = new URL(req.url, 'http://localhost').pathname;
    } catch {
      return reject(socket, 400, 'Bad Request', 'bad_url');
    }
    if (pathname !== FEED_PATH) return reject(socket, 404, 'Not Found', 'path');

    const origin = req.headers.origin;
    if (origin && !allowedOrigins.has(origin)) {
      let sameHost = false;
      try {
        sameHost = new URL(origin).host === req.headers.host;
      } catch {
        sameHost = false;
      }
      if (!sameHost) return reject(socket, 403, 'Forbidden', 'origin');
    }

    if (wss.clients.size >= maxConnections) return reject(socket, 503, 'Service Unavailable', 'capacity');

    wss.handleUpgrade(req, socket, head, (ws) => wss.emit('connection', ws, req));
  });

  function send(ws, payload) {
    if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(payload));
  }

  function broadcast(payload) {
    const data = JSON.stringify(payload);
    for (const ws of wss.clients) {
      if (ws.readyState === ws.OPEN) ws.send(data);
    }
  }

  wss.on('connection', (ws) => {
    wsConnections.set(wss.clients.size);
    ws.isAlive = true;
    ws.on('pong', () => {
      ws.isAlive = true;
    });
    ws.on('close', () => wsConnections.set(wss.clients.size));
    ws.on('error', () => ws.terminate());
    ws.on('message', (raw, isBinary) => {
      if (isBinary) return send(ws, { type: 'error', error: 'binary messages not supported' });
      let msg;
      try {
        msg = JSON.parse(raw.toString('utf8'));
      } catch {
        return send(ws, { type: 'error', error: 'invalid JSON' });
      }
      if (msg && msg.type === 'set_vertical') {
        if (!isValidVertical(msg.vertical)) {
          return send(ws, { type: 'error', error: `vertical must be one of: ${VERTICALS.join(', ')}` });
        }
        return switchVertical(msg.vertical);
      }
      if (msg && msg.type === 'ping') return send(ws, { type: 'pong' });
      return send(ws, { type: 'error', error: 'unknown message type' });
    });
    send(ws, sims[current].getState());
  });

  // ---------------------------------------------------------------- ticker
  let ticker = null;

  function tick() {
    for (const v of VERTICALS) sims[v].advance();
    broadcast(sims[current].getState());
    // Heartbeat: drop clients that did not answer the previous ping.
    for (const ws of wss.clients) {
      if (ws.isAlive === false) {
        ws.terminate();
        continue;
      }
      ws.isAlive = false;
      ws.ping();
    }
  }

  function start() {
    if (!ticker) ticker = setInterval(tick, tickMs);
    return portal;
  }

  function close({ timeoutMs = 10000 } = {}) {
    if (ticker) clearInterval(ticker);
    ticker = null;
    for (const ws of wss.clients) ws.close(1001, 'server shutting down');
    return new Promise((resolve) => {
      const force = setTimeout(() => {
        for (const ws of wss.clients) ws.terminate();
        server.closeAllConnections?.();
      }, timeoutMs);
      force.unref();
      wss.close(() => {
        if (!server.listening) {
          clearTimeout(force);
          return resolve();
        }
        server.close(() => {
          clearTimeout(force);
          resolve();
        });
        server.closeIdleConnections?.();
      });
    });
  }

  const portal = {
    app,
    server,
    wss,
    register,
    start,
    close,
    tick,
    getSimulator: (v = current) => sims[v],
    getCurrentVertical: () => current,
  };
  return portal;
}

function portalOptionsFromEnv(env = process.env) {
  const int = (v, d) => {
    const n = Number.parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : d;
  };
  return {
    tickMs: int(env.TICK_MS, 3000),
    maxConnections: int(env.WS_MAX_CONNECTIONS, 100),
    maxPayload: int(env.WS_MAX_PAYLOAD_BYTES, 4096),
    autonomyMode: env.AUTONOMY_MODE || 'supervised',
    actionCap: int(env.ACTION_CAP_PER_HOUR, 20),
    allowedOrigins: parseList(env.WS_ALLOWED_ORIGINS),
    platformName: env.PLATFORM_NAME || DEFAULT_PLATFORM_NAME,
  };
}

module.exports = { createPortal, portalOptionsFromEnv, SERVICE_NAME, CSP_DIRECTIVES, VERTICAL_LABELS };
