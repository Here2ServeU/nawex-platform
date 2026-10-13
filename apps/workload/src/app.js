// ===========================================================================
// Golden Platform — reference workload
// Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
// ===========================================================================
// apps/workload/src/app.js
//
// Instrumented Express workload used as the target of the AI-ops agents.
// It emits golden signals (Prometheus + a JSON view for the Python
// ObserverAgent) and exposes BOUNDED chaos endpoints so detection and
// remediation can be exercised on demand.
//
// createApp() builds the app without binding a port; src/server.js does that.
// ===========================================================================
'use strict';

const os = require('node:os');
const { Worker } = require('node:worker_threads');
const express = require('express');
const helmet = require('helmet');
const client = require('prom-client');

const pkg = require('../package.json');

const SERVICE_NAME = 'golden-workload';
const WINDOW_MS = 60_000;
const MAX_SAMPLES = 10_000;
const LEAK_CHUNK_BYTES = 8 * 1024 * 1024;

const DEFAULTS = Object.freeze({
  chaosEnabled: true,
  maxLatencyMs: 10_000,
  maxCpuStressMs: 30_000,
  maxMemoryLeakMb: 256,
  maxErrorSpike: 1000,
});

const CPU_BURN_SOURCE = `
const { workerData } = require('node:worker_threads');
const end = Date.now() + workerData.ms;
let x = 0;
while (Date.now() < end) { for (let i = 0; i < 1e5; i++) x += i; }
`;

class ValidationError extends Error {
  constructor(message) {
    super(message);
    this.status = 400;
  }
}

/** Strict integer parsing: accepts JSON numbers or base-10 digit strings. */
function parseIntParam(name, raw, { min, max, fallback }) {
  if (raw === undefined || raw === null || raw === '') {
    if (fallback !== undefined) return fallback;
    throw new ValidationError(`${name} is required`);
  }
  let n;
  if (typeof raw === 'number') n = raw;
  else if (typeof raw === 'string' && /^-?\d+$/.test(raw.trim())) n = Number(raw.trim());
  else throw new ValidationError(`${name} must be an integer`);
  if (!Number.isInteger(n)) throw new ValidationError(`${name} must be an integer`);
  if (n < min || n > max) throw new ValidationError(`${name} must be between ${min} and ${max}`);
  return n;
}

function parseRate(name, raw) {
  const n = typeof raw === 'number' ? raw : typeof raw === 'string' && raw.trim() !== '' ? Number(raw) : NaN;
  if (!Number.isFinite(n) || n < 0 || n > 1) throw new ValidationError(`${name} must be a number between 0 and 1`);
  return n;
}

function memoryLimitBytes() {
  const total = os.totalmem();
  const constrained = typeof process.constrainedMemory === 'function' ? process.constrainedMemory() : 0;
  return constrained && constrained > 0 && constrained < total ? constrained : total;
}

/** Process CPU % across all available cores, sampled lazily (no timers). */
function createCpuSampler() {
  const cores = Math.max(1, os.availableParallelism?.() ?? os.cpus().length);
  let last = { t: process.hrtime.bigint(), usage: process.cpuUsage() };
  let value = 0;
  return function sample() {
    const now = process.hrtime.bigint();
    const elapsedUs = Number(now - last.t) / 1000;
    if (elapsedUs < 200_000) return value; // keep the previous reading for very short intervals
    const delta = process.cpuUsage(last.usage);
    value = Math.min(100, ((delta.user + delta.system) / (elapsedUs * cores)) * 100);
    last = { t: now, usage: process.cpuUsage() };
    return value;
  };
}

function createApp(options = {}) {
  const cfg = { ...DEFAULTS, ...options };
  const cpuCores = Math.max(1, os.availableParallelism?.() ?? os.cpus().length);

  const state = {
    latencyInjectionMs: 0,
    errorInjectionRate: 0,
    cpuWorkers: new Set(),
    cpuStressUntil: 0,
    leaks: [],
    samples: [], // { t, ms, err, synthetic }
  };
  const sampleCpu = createCpuSampler();

  // ---------------------------------------------------------------- metrics
  const register = new client.Registry();
  register.setDefaultLabels({ service: SERVICE_NAME });
  client.collectDefaultMetrics({ register });
  const httpDuration = new client.Histogram({
    name: 'http_request_duration_seconds',
    help: 'HTTP request duration in seconds',
    labelNames: ['method', 'route', 'status_code'],
    buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registers: [register],
  });
  new client.Gauge({
    name: 'golden_workload_chaos_latency_injection_ms',
    help: 'Injected latency applied to business routes (ms)',
    registers: [register],
    collect() {
      this.set(state.latencyInjectionMs);
    },
  });
  new client.Gauge({
    name: 'golden_workload_chaos_error_injection_rate',
    help: 'Probability (0-1) that a business request fails with 500',
    registers: [register],
    collect() {
      this.set(state.errorInjectionRate);
    },
  });
  new client.Gauge({
    name: 'golden_workload_chaos_cpu_stress_active',
    help: '1 while a CPU stress run is active',
    registers: [register],
    collect() {
      this.set(state.cpuWorkers.size > 0 ? 1 : 0);
    },
  });
  new client.Gauge({
    name: 'golden_workload_chaos_leaked_bytes',
    help: 'Bytes held by the simulated memory leak',
    registers: [register],
    collect() {
      this.set(state.leaks.length * LEAK_CHUNK_BYTES);
    },
  });

  // ------------------------------------------------------------ helpers
  function pruneSamples(now = Date.now()) {
    const cutoff = now - WINDOW_MS;
    let i = 0;
    while (i < state.samples.length && state.samples[i].t < cutoff) i++;
    if (i) state.samples.splice(0, i);
    if (state.samples.length > MAX_SAMPLES) state.samples.splice(0, state.samples.length - MAX_SAMPLES);
  }

  function goldenSignals() {
    pruneSamples();
    const real = state.samples.filter((s) => !s.synthetic);
    const errors = state.samples.filter((s) => s.err).length;
    const observedLatency = real.length ? real.reduce((a, s) => a + s.ms, 0) / real.length : 0;
    const latency = real.length ? observedLatency : state.latencyInjectionMs;
    const errorRatePct = state.samples.length ? (errors / state.samples.length) * 100 : 0;
    const rss = process.memoryUsage().rss;
    return {
      latency_ms: Math.round(latency),
      error_rate: +errorRatePct.toFixed(2),
      cpu_usage_percent: +sampleCpu().toFixed(1),
      memory_usage_percent: +((rss / memoryLimitBytes()) * 100).toFixed(1),
      memory_usage_mb: Math.round(rss / 1024 / 1024),
      request_count: real.length,
    };
  }

  function stopCpuStress() {
    for (const w of state.cpuWorkers) w.terminate();
    state.cpuWorkers.clear();
    state.cpuStressUntil = 0;
  }

  function resetChaos() {
    stopCpuStress();
    state.latencyInjectionMs = 0;
    state.errorInjectionRate = 0;
    state.leaks = [];
    state.samples = [];
  }

  // -------------------------------------------------------------------- app
  const app = express();
  app.disable('x-powered-by');
  app.use(helmet());
  app.use(express.json({ limit: '4kb' }));

  app.use((req, res, next) => {
    const end = httpDuration.startTimer();
    res.on('finish', () => {
      const route = req.route ? req.baseUrl + req.route.path : 'unmatched';
      end({ method: req.method, route, status_code: res.statusCode });
    });
    next();
  });

  // Business routes: subject to latency/error injection and counted in the
  // golden-signal window. Observability, chaos and ops routes are not.
  const business = express.Router();
  function instrumented(req, res, next) {
    const start = process.hrtime.bigint();
    res.on('finish', () => {
      const ms = Number(process.hrtime.bigint() - start) / 1e6;
      state.samples.push({ t: Date.now(), ms, err: res.statusCode >= 500, synthetic: false });
      if (state.samples.length > MAX_SAMPLES) pruneSamples();
    });
    const proceed = () => {
      if (state.errorInjectionRate > 0 && Math.random() < state.errorInjectionRate) {
        return res.status(500).json({ error: 'Injected failure (chaos)' });
      }
      next();
    };
    if (state.latencyInjectionMs > 0) setTimeout(proceed, state.latencyInjectionMs);
    else proceed();
  }

  business.get('/', instrumented, (req, res) => {
    res.json({ service: SERVICE_NAME, version: pkg.version, status: 'operational' });
  });

  business.get('/api/users', instrumented, (req, res) => {
    res.json([
      { id: 1, name: 'Alice', role: 'admin' },
      { id: 2, name: 'Bob', role: 'user' },
    ]);
  });

  // ------------------------------------------------------- observability
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

  // JSON golden signals polled by the Python ObserverAgent.
  app.get('/metrics/json', (req, res) => {
    const m = goldenSignals();
    res.json({
      timestamp: new Date().toISOString(),
      service: SERVICE_NAME,
      window_seconds: WINDOW_MS / 1000,
      metrics: {
        latency_ms: m.latency_ms,
        error_rate: m.error_rate, // percent (0-100) of 5xx in the window
        error_rate_percent: m.error_rate, // alias matching the analyzer threshold key
        cpu_usage_percent: m.cpu_usage_percent,
        memory_usage_percent: m.memory_usage_percent,
        memory_usage_mb: m.memory_usage_mb,
        request_count: m.request_count,
      },
      chaos_state: {
        latency_injection_ms: state.latencyInjectionMs,
        error_injection_rate: state.errorInjectionRate,
        cpu_stress_active: state.cpuWorkers.size > 0,
        cpu_stress_remaining_ms: Math.max(0, state.cpuStressUntil - Date.now()),
        leaked_mb: (state.leaks.length * LEAK_CHUNK_BYTES) / 1024 / 1024,
      },
    });
  });

  // ---------------------------------------------------------------- chaos
  const chaos = express.Router();
  chaos.use((req, res, next) => {
    if (!cfg.chaosEnabled) return res.status(403).json({ error: 'Chaos endpoints are disabled (CHAOS_ENABLED=false)' });
    next();
  });

  chaos.post('/latency', (req, res) => {
    const body = req.body ?? {};
    const delay = parseIntParam('delay_ms', body.delay_ms ?? body.delay, { min: 0, max: cfg.maxLatencyMs });
    state.latencyInjectionMs = delay;
    res.json({ status: delay > 0 ? 'latency_injected' : 'latency_cleared', delay_ms: delay, max_delay_ms: cfg.maxLatencyMs });
  });

  chaos.post('/errors', (req, res) => {
    const rate = parseRate('rate', (req.body ?? {}).rate);
    state.errorInjectionRate = rate;
    res.json({ status: rate > 0 ? 'error_injection_active' : 'error_injection_cleared', rate });
  });

  // Legacy: record N synthetic 5xx samples so error_rate spikes immediately.
  chaos.post('/error-spike', (req, res) => {
    const count = parseIntParam('count', (req.body ?? {}).count, { min: 1, max: cfg.maxErrorSpike, fallback: 50 });
    const t = Date.now();
    for (let i = 0; i < count; i++) state.samples.push({ t, ms: 0, err: true, synthetic: true });
    pruneSamples(t);
    res.json({ status: 'error_spike_injected', count });
  });

  chaos.post('/cpu', (req, res) => {
    const body = req.body ?? {};
    const durationMs = parseIntParam('duration_ms', body.duration_ms, { min: 100, max: cfg.maxCpuStressMs, fallback: 5000 });
    const workers = parseIntParam('workers', body.workers, { min: 1, max: cpuCores, fallback: cpuCores });
    if (state.cpuWorkers.size > 0) {
      return res.status(409).json({ error: 'CPU stress already active', remaining_ms: Math.max(0, state.cpuStressUntil - Date.now()) });
    }
    state.cpuStressUntil = Date.now() + durationMs;
    for (let i = 0; i < workers; i++) {
      const w = new Worker(CPU_BURN_SOURCE, { eval: true, workerData: { ms: durationMs } });
      w.unref();
      const done = () => {
        state.cpuWorkers.delete(w);
        if (state.cpuWorkers.size === 0) state.cpuStressUntil = 0;
      };
      w.once('exit', done);
      w.once('error', done);
      state.cpuWorkers.add(w);
    }
    res.status(202).json({ status: 'cpu_stress_started', duration_ms: durationMs, workers, max_duration_ms: cfg.maxCpuStressMs });
  });

  function leakMemory(intensity, res) {
    const maxChunks = Math.floor((cfg.maxMemoryLeakMb * 1024 * 1024) / LEAK_CHUNK_BYTES);
    if (state.leaks.length + intensity > maxChunks) {
      return res.status(409).json({
        error: `Memory leak cap reached (${cfg.maxMemoryLeakMb} MB). POST /ops/heal to release.`,
        leaked_mb: (state.leaks.length * LEAK_CHUNK_BYTES) / 1024 / 1024,
      });
    }
    for (let i = 0; i < intensity; i++) state.leaks.push(Buffer.alloc(LEAK_CHUNK_BYTES, 1));
    res.json({
      status: 'memory_leak_injected',
      leaked_mb: (state.leaks.length * LEAK_CHUNK_BYTES) / 1024 / 1024,
      max_leak_mb: cfg.maxMemoryLeakMb,
    });
  }

  chaos.post('/memory', (req, res) => {
    const intensity = parseIntParam('intensity', (req.body ?? {}).intensity, { min: 1, max: 10, fallback: 1 });
    leakMemory(intensity, res);
  });

  // Legacy alias used by scripts/tools/chaos_demo.sh.
  chaos.get('/stress-test', (req, res) => {
    const intensity = parseIntParam('intensity', req.query.intensity, { min: 1, max: 10, fallback: 1 });
    leakMemory(intensity, res);
  });

  app.use('/chaos', chaos);

  // ---------------------------------------------------------- remediation
  app.post('/ops/heal', (req, res) => {
    resetChaos();
    res.json({ status: 'healed', message: 'Chaos cleared: latency, errors, CPU stress and memory leak reset.' });
  });

  app.use(business);

  app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
  });

  // eslint-disable-next-line no-unused-vars
  app.use((err, req, res, next) => {
    const status = err.status || err.statusCode || 500;
    res.status(status).json({ error: status >= 500 ? 'Internal server error' : err.message });
  });

  app.locals.state = state;
  app.locals.register = register;
  app.locals.config = cfg;
  app.locals.shutdown = () => stopCpuStress();
  return app;
}

function optionsFromEnv(env = process.env) {
  const int = (v, d) => {
    const n = Number.parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : d;
  };
  return {
    chaosEnabled: !['false', '0', 'no', 'off'].includes(String(env.CHAOS_ENABLED ?? 'true').toLowerCase()),
    maxLatencyMs: int(env.CHAOS_MAX_LATENCY_MS, DEFAULTS.maxLatencyMs),
    maxCpuStressMs: int(env.CHAOS_MAX_CPU_STRESS_MS, DEFAULTS.maxCpuStressMs),
    maxMemoryLeakMb: int(env.CHAOS_MAX_MEMORY_LEAK_MB, DEFAULTS.maxMemoryLeakMb),
  };
}

module.exports = { createApp, optionsFromEnv, parseIntParam, SERVICE_NAME, DEFAULTS };
