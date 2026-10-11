'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');

const { createApp, optionsFromEnv, parseIntParam } = require('../src/app');
const pkg = require('../package.json');

async function start(opts = {}) {
  const app = createApp({ maxLatencyMs: 2000, maxCpuStressMs: 3000, maxMemoryLeakMb: 32, ...opts });
  const server = http.createServer(app);
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const base = `http://127.0.0.1:${server.address().port}`;
  const stop = async () => {
    app.locals.shutdown();
    server.closeAllConnections();
    await new Promise((r) => server.close(r));
  };
  return { app, base, stop };
}

const post = (url, body) =>
  fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
  });

const metricsJson = async (base) => (await fetch(`${base}/metrics/json`)).json();

test('golden-workload HTTP surface', async (t) => {
  const { app, base, stop } = await start();
  t.after(stop);
  t.beforeEach(async () => {
    await post(`${base}/ops/heal`);
  });

  await t.test('GET /health', async () => {
    const res = await fetch(`${base}/health`);
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { status: 'ok', service: 'golden-workload', version: pkg.version });
    assert.equal(pkg.name, 'golden-workload');
  });

  await t.test('GET / and GET /api/users', async () => {
    const root = await (await fetch(`${base}/`)).json();
    assert.equal(root.service, 'golden-workload');
    const users = await (await fetch(`${base}/api/users`)).json();
    assert.ok(Array.isArray(users) && users.length === 2);
    assert.equal((await fetch(`${base}/nope`)).status, 404);
  });

  await t.test('GET /metrics is Prometheus text with default metrics + histogram', async () => {
    await fetch(`${base}/api/users`);
    const res = await fetch(`${base}/metrics`);
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /text\/plain/);
    const body = await res.text();
    assert.match(body, /process_cpu_user_seconds_total/);
    assert.match(body, /http_request_duration_seconds_bucket\{.*route="\/api\/users".*\}/);
    assert.match(body, /golden_workload_chaos_latency_injection_ms/);
    assert.match(body, /golden_workload_chaos_cpu_stress_active/);
    assert.doesNotMatch(body, /nawex/i);
  });

  await t.test('GET /metrics/json matches the ObserverAgent contract', async () => {
    const body = await metricsJson(base);
    assert.ok(!Number.isNaN(Date.parse(body.timestamp)));
    for (const k of ['latency_ms', 'error_rate', 'cpu_usage_percent', 'memory_usage_percent']) {
      assert.equal(typeof body.metrics[k], 'number', k);
      assert.ok(body.metrics[k] >= 0, `${k} >= 0`);
    }
    assert.ok(body.metrics.cpu_usage_percent <= 100);
    assert.ok(body.metrics.memory_usage_percent > 0 && body.metrics.memory_usage_percent <= 100);
    assert.equal(body.metrics.error_rate, body.metrics.error_rate_percent);
  });

  await t.test('latency injection: applied, observable, capped and validated', async () => {
    const ok = await post(`${base}/chaos/latency`, { delay_ms: 150 });
    assert.equal(ok.status, 200);
    assert.equal((await ok.json()).delay_ms, 150);
    const t0 = Date.now();
    await fetch(`${base}/api/users`);
    assert.ok(Date.now() - t0 >= 140, 'business route delayed');
    const t1 = Date.now();
    await fetch(`${base}/health`);
    assert.ok(Date.now() - t1 < 140, 'health is not delayed');
    assert.ok((await metricsJson(base)).metrics.latency_ms >= 140);

    // legacy body key
    assert.equal((await post(`${base}/chaos/latency`, { delay: 10 })).status, 200);

    for (const bad of [{ delay_ms: 2001 }, { delay_ms: -1 }, { delay_ms: 1.5 }, { delay_ms: 'abc' }, { delay_ms: true }, {}]) {
      const res = await post(`${base}/chaos/latency`, bad);
      assert.equal(res.status, 400, JSON.stringify(bad));
      assert.match((await res.json()).error, /delay_ms/);
    }
    assert.equal((await post(`${base}/chaos/latency`, '{broken')).status, 400);
    assert.equal(app.locals.state.latencyInjectionMs, 10, 'invalid input left state unchanged');
  });

  await t.test('error injection: rate validated and 5xx reflected in error_rate', async () => {
    for (const bad of [{ rate: 1.5 }, { rate: -0.1 }, { rate: 'x' }, {}]) {
      assert.equal((await post(`${base}/chaos/errors`, bad)).status, 400, JSON.stringify(bad));
    }
    assert.equal((await post(`${base}/chaos/errors`, { rate: 1 })).status, 200);
    for (let i = 0; i < 4; i++) assert.equal((await fetch(`${base}/api/users`)).status, 500);
    assert.equal((await metricsJson(base)).metrics.error_rate, 100);
    assert.equal((await post(`${base}/chaos/errors`, { rate: 0 })).status, 200);
    assert.equal((await fetch(`${base}/api/users`)).status, 200);
  });

  await t.test('error spike: bounded count', async () => {
    const res = await post(`${base}/chaos/error-spike`);
    assert.equal(res.status, 200);
    assert.equal((await res.json()).count, 50);
    assert.equal((await metricsJson(base)).metrics.error_rate, 100);
    assert.equal((await post(`${base}/chaos/error-spike`, { count: 1001 })).status, 400);
    assert.equal((await post(`${base}/chaos/error-spike`, { count: 0 })).status, 400);
  });

  await t.test('CPU stress: bounded duration, validated, single-flight, healable', async () => {
    for (const bad of [{ duration_ms: 3001 }, { duration_ms: 50 }, { duration_ms: 'soon' }, { workers: 0 }, { workers: 100000 }]) {
      assert.equal((await post(`${base}/chaos/cpu`, bad)).status, 400, JSON.stringify(bad));
    }
    const res = await post(`${base}/chaos/cpu`, { duration_ms: 1500, workers: 1 });
    assert.equal(res.status, 202);
    assert.deepEqual(await res.json(), { status: 'cpu_stress_started', duration_ms: 1500, workers: 1, max_duration_ms: 3000 });
    assert.equal((await post(`${base}/chaos/cpu`, { duration_ms: 200 })).status, 409);
    let body = await metricsJson(base);
    assert.equal(body.chaos_state.cpu_stress_active, true);
    assert.ok(body.chaos_state.cpu_stress_remaining_ms <= 1500);
    // Event loop stays responsive while workers burn CPU.
    const t0 = Date.now();
    assert.equal((await fetch(`${base}/health`)).status, 200);
    assert.ok(Date.now() - t0 < 500);
    await post(`${base}/ops/heal`);
    body = await metricsJson(base);
    assert.equal(body.chaos_state.cpu_stress_active, false);
  });

  await t.test('CPU stress ends on its own at the deadline', async () => {
    assert.equal((await post(`${base}/chaos/cpu`, { duration_ms: 150, workers: 1 })).status, 202);
    const deadline = Date.now() + 3000;
    while (app.locals.state.cpuWorkers.size > 0 && Date.now() < deadline) await new Promise((r) => setTimeout(r, 25));
    assert.equal(app.locals.state.cpuWorkers.size, 0);
  });

  await t.test('memory leak: bounded by cap, legacy GET alias, healable', async () => {
    const res = await post(`${base}/chaos/memory`, { intensity: 2 });
    assert.equal(res.status, 200);
    assert.equal((await res.json()).leaked_mb, 16);
    const legacy = await fetch(`${base}/chaos/stress-test?intensity=1`);
    assert.equal(legacy.status, 200);
    assert.equal((await legacy.json()).leaked_mb, 24);
    assert.equal((await post(`${base}/chaos/memory`, { intensity: 2 })).status, 409, 'cap is 32 MB = 4 chunks');
    assert.equal((await post(`${base}/chaos/memory`, { intensity: 11 })).status, 400);
    assert.equal((await fetch(`${base}/chaos/stress-test?intensity=abc`)).status, 400);
    await post(`${base}/ops/heal`);
    assert.equal((await metricsJson(base)).chaos_state.leaked_mb, 0);
  });

  await t.test('POST /ops/heal resets all chaos state', async () => {
    await post(`${base}/chaos/latency`, { delay_ms: 5 });
    await post(`${base}/chaos/errors`, { rate: 0.5 });
    const res = await post(`${base}/ops/heal`);
    assert.equal(res.status, 200);
    assert.equal((await res.json()).status, 'healed');
    const { chaos_state: c, metrics: m } = await metricsJson(base);
    assert.equal(c.latency_injection_ms, 0);
    assert.equal(c.error_injection_rate, 0);
    assert.equal(m.error_rate, 0);
    assert.equal(m.latency_ms, 0);
  });
});

test('chaos endpoints can be disabled', async (t) => {
  const { base, stop } = await start({ chaosEnabled: false });
  t.after(stop);
  for (const [path, body] of [['/chaos/latency', { delay_ms: 1 }], ['/chaos/cpu', {}], ['/chaos/memory', {}], ['/chaos/errors', { rate: 1 }]]) {
    assert.equal((await post(`${base}${path}`, body)).status, 403, path);
  }
  assert.equal((await fetch(`${base}/health`)).status, 200);
});

test('optionsFromEnv parses caps and CHAOS_ENABLED', () => {
  const o = optionsFromEnv({ CHAOS_ENABLED: 'false', CHAOS_MAX_LATENCY_MS: '5000', CHAOS_MAX_CPU_STRESS_MS: 'bogus' });
  assert.equal(o.chaosEnabled, false);
  assert.equal(o.maxLatencyMs, 5000);
  assert.equal(o.maxCpuStressMs, 30000);
  assert.equal(optionsFromEnv({}).chaosEnabled, true);
  assert.equal(optionsFromEnv({}).maxLatencyMs, 10000);
});

test('parseIntParam', () => {
  assert.equal(parseIntParam('x', '42', { min: 0, max: 100 }), 42);
  assert.equal(parseIntParam('x', undefined, { min: 0, max: 100, fallback: 7 }), 7);
  assert.throws(() => parseIntParam('x', undefined, { min: 0, max: 1 }), /required/);
  assert.throws(() => parseIntParam('x', '1e3', { min: 0, max: 10000 }), /integer/);
  assert.throws(() => parseIntParam('x', 101, { min: 0, max: 100 }), /between/);
});
