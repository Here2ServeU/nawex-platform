'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { once } = require('node:events');
const WebSocket = require('ws');

const { createPortal, portalOptionsFromEnv } = require('../src/app');
const pkg = require('../package.json');

async function startPortal(opts = {}) {
  const portal = createPortal({ tickMs: 50, ...opts });
  portal.server.listen(0, '127.0.0.1');
  await once(portal.server, 'listening');
  const { port } = portal.server.address();
  return { portal, base: `http://127.0.0.1:${port}`, wsUrl: `ws://127.0.0.1:${port}/feed` };
}

function nextMessage(ws) {
  return new Promise((resolve, reject) => {
    ws.once('message', (data) => resolve(JSON.parse(data.toString())));
    ws.once('error', reject);
  });
}

test('HTTP API', async (t) => {
  const { portal, base } = await startPortal();
  t.after(() => portal.close({ timeoutMs: 500 }));

  await t.test('GET /health', async () => {
    const res = await fetch(`${base}/health`);
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { status: 'ok', service: 'golden-client-portal', version: pkg.version });
  });

  await t.test('GET /metrics exposes Prometheus text with default + http histogram', async () => {
    await fetch(`${base}/api/vertical`);
    const res = await fetch(`${base}/metrics`);
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /text\/plain/);
    const body = await res.text();
    assert.match(body, /process_cpu_user_seconds_total/);
    assert.match(body, /nodejs_heap_size_used_bytes/);
    assert.match(body, /http_request_duration_seconds_bucket\{.*route="\/api\/vertical".*\}/);
    assert.match(body, /golden_client_portal_ws_connections/);
    assert.doesNotMatch(body, /nawex/i);
  });

  await t.test('security headers include a CSP restricted to used CDNs', async () => {
    const res = await fetch(`${base}/`);
    assert.equal(res.status, 200);
    const csp = res.headers.get('content-security-policy');
    assert.ok(csp, 'CSP header present');
    assert.match(csp, /script-src 'self' https:\/\/cdn\.jsdelivr\.net/);
    assert.match(csp, /font-src 'self' https:\/\/fonts\.gstatic\.com/);
    assert.match(csp, /object-src 'none'/);
    assert.doesNotMatch(csp, /unsafe-eval/);
    assert.doesNotMatch(csp, /script-src[^;]*unsafe-inline/);
    assert.equal(res.headers.get('x-powered-by'), null);
    const html = await res.text();
    assert.doesNotMatch(html, /\son[a-z]+="/i, 'no inline event handlers (blocked by CSP)');
    assert.doesNotMatch(html, /NAWEX/i);
    for (const v of ['healthcare', 'fintech', 'gpu', 'migration']) assert.match(html, new RegExp(`data-vertical="${v}"`));
  });

  await t.test('GET /api/config is branding-neutral and env-configurable', async () => {
    const cfg = await (await fetch(`${base}/api/config`)).json();
    assert.equal(cfg.platformName, 'Golden Platform');
    assert.equal(cfg.consoleTitle, 'Golden Platform — Executive Console');
    assert.deepEqual(Object.keys(cfg.verticals), ['healthcare', 'fintech', 'gpu', 'migration']);
    assert.equal(cfg.verticals.migration, 'VMware → OpenShift Migration');
    assert.equal(portalOptionsFromEnv({ PLATFORM_NAME: 'Acme Ops' }).platformName, 'Acme Ops');
  });

  await t.test('GET /api/health (legacy)', async () => {
    const body = await (await fetch(`${base}/api/health`)).json();
    assert.equal(body.status, 'ok');
    assert.ok(['healthcare', 'fintech', 'gpu', 'migration'].includes(body.vertical));
    assert.equal(typeof body.uptime_s, 'number');
  });

  await t.test('POST /api/vertical validates against the whitelist', async () => {
    for (const bad of [{ vertical: 'crypto' }, { vertical: '__proto__' }, { vertical: ['gpu'] }, {}]) {
      const res = await fetch(`${base}/api/vertical`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(bad),
      });
      assert.equal(res.status, 400, JSON.stringify(bad));
    }
    const noBody = await fetch(`${base}/api/vertical`, { method: 'POST' });
    assert.equal(noBody.status, 400);
    const malformed = await fetch(`${base}/api/vertical`, {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: '{nope',
    });
    assert.equal(malformed.status, 400);
    const tooBig = await fetch(`${base}/api/vertical`, {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ vertical: 'x'.repeat(10_000) }),
    });
    assert.equal(tooBig.status, 413);

    for (const v of ['gpu', 'migration']) {
      const ok = await fetch(`${base}/api/vertical`, {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ vertical: v }),
      });
      assert.equal(ok.status, 200);
      assert.deepEqual(await ok.json(), { switched_to: v, ok: true });
      assert.equal((await (await fetch(`${base}/api/vertical`)).json()).current, v);
    }
  });

  await t.test('GET /api/metrics|alerts|roi/:vertical for every vertical', async () => {
    for (const v of ['healthcare', 'fintech', 'gpu', 'migration']) {
      const m = await (await fetch(`${base}/api/metrics/${v}`)).json();
      assert.equal(m.vertical, v);
      const a = await (await fetch(`${base}/api/alerts/${v}`)).json();
      assert.equal(a.vertical, v);
      assert.ok(Array.isArray(a.alerts));
      const roi = await (await fetch(`${base}/api/roi/${v}`)).json();
      assert.equal(roi.vertical, v);
      const pctSum = Object.values(roi.breakdown).reduce((s, b) => s + b.pct_of_total, 0);
      assert.ok(Math.abs(pctSum - 100) < 0.2, `${v} breakdown sums to 100 (got ${pctSum})`);
      assert.doesNotMatch(roi.executive_summary, /NAWEX/i);
    }
    const gpu = await (await fetch(`${base}/api/metrics/gpu`)).json();
    assert.equal(typeof gpu.projectedMonthlySavingsUsd, 'number');
    const mig = await (await fetch(`${base}/api/metrics/migration`)).json();
    assert.equal(typeof mig.estimatedLicensingSavingsUsdPerYear, 'number');
  });

  await t.test('unknown verticals are rejected with 400 on every :vertical route', async () => {
    for (const route of ['metrics', 'alerts', 'roi']) {
      const res = await fetch(`${base}/api/${route}/crypto`);
      assert.equal(res.status, 400, route);
    }
  });

  await t.test('GET /api/safety and /api/research/provenance', async () => {
    const s = await (await fetch(`${base}/api/safety`)).json();
    assert.ok(['dry_run', 'supervised', 'autonomous'].includes(s.autonomyMode));
    assert.ok(['armed', 'engaged'].includes(s.killSwitch));
    assert.equal(s.simulated, true);
    const p = await (await fetch(`${base}/api/research/provenance`)).json();
    assert.ok(p.models.some((m) => m.verticals.includes('gpu')));
    assert.ok(p.models.some((m) => m.verticals.includes('migration')));
  });

  await t.test('unknown route returns JSON 404', async () => {
    const res = await fetch(`${base}/api/does-not-exist`);
    assert.equal(res.status, 404);
  });
});

test('WebSocket /feed', async (t) => {
  const { portal, wsUrl } = await startPortal({ maxConnections: 2, maxPayload: 256, autonomyMode: 'dry_run' });
  t.after(() => portal.close({ timeoutMs: 500 }));

  await t.test('sends an initial state_update and periodic updates', async () => {
    const ws = new WebSocket(wsUrl);
    const first = await nextMessage(ws);
    assert.equal(first.type, 'state_update');
    assert.ok(first.metrics && first.explainability && first.safety);
    assert.equal(first.safety.autonomyMode, 'dry_run');
    portal.start();
    const second = await nextMessage(ws);
    assert.equal(second.type, 'state_update');
    ws.close();
    await once(ws, 'close');
  });

  await t.test('set_vertical is validated server-side', async () => {
    const ws = new WebSocket(wsUrl);
    await nextMessage(ws);
    ws.send(JSON.stringify({ type: 'set_vertical', vertical: 'crypto' }));
    let msg;
    do msg = await nextMessage(ws); while (msg.type === 'state_update');
    assert.equal(msg.type, 'error');
    assert.equal(portal.getCurrentVertical() === 'crypto', false);

    ws.send(JSON.stringify({ type: 'set_vertical', vertical: 'migration' }));
    do msg = await nextMessage(ws); while (msg.metrics?.vertical !== 'migration');
    assert.equal(portal.getCurrentVertical(), 'migration');

    ws.send('not json');
    do msg = await nextMessage(ws); while (msg.type === 'state_update');
    assert.equal(msg.type, 'error');
    ws.close();
    await once(ws, 'close');
  });

  await t.test('oversized messages close the socket (maxPayload)', async () => {
    const ws = new WebSocket(wsUrl);
    await nextMessage(ws);
    ws.send('x'.repeat(1024));
    const [code] = await once(ws, 'close');
    assert.equal(code, 1009, 'Message Too Big');
  });

  await t.test('connections beyond the cap are rejected with 503', async () => {
    // Let the server drop the previous sockets.
    while (portal.wss.clients.size > 0) await new Promise((r) => setTimeout(r, 10));
    const a = new WebSocket(wsUrl);
    const b = new WebSocket(wsUrl);
    await Promise.all([nextMessage(a), nextMessage(b)]);
    const c = new WebSocket(wsUrl);
    const [, res] = await once(c, 'unexpected-response');
    assert.equal(res.statusCode, 503);
    a.close();
    b.close();
    await Promise.all([once(a, 'close'), once(b, 'close')]);
  });

  await t.test('cross-origin upgrades are rejected', async () => {
    const ws = new WebSocket(wsUrl, { origin: 'https://evil.example' });
    const [, res] = await once(ws, 'unexpected-response');
    assert.equal(res.statusCode, 403);
  });

  await t.test('other upgrade paths are rejected', async () => {
    const ws = new WebSocket(wsUrl.replace('/feed', '/nope'));
    const [, res] = await once(ws, 'unexpected-response');
    assert.equal(res.statusCode, 404);
  });
});

test('close() is idempotent-safe when never listened', async () => {
  const portal = createPortal();
  await portal.close({ timeoutMs: 100 });
});
