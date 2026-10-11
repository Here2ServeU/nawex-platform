// Golden Platform — mixed smoke/load test across the platform API and domain services.
//   k6 run tools/k6/load-test.js
//   k6 run -e HOST=http://localhost -e API_KEY=dev-key tools/k6/load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 20,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.02'],
    'http_req_duration{kind:score}': ['p(95)<300'],
  },
};

const HOST = __ENV.HOST || 'http://localhost';
const API_KEY = __ENV.API_KEY || '';
const headers = { 'Content-Type': 'application/json', ...(API_KEY ? { 'X-API-Key': API_KEY } : {}) };

const HEALTH_TARGETS = [8000, 8090, 8091, 8092, 8093, 8094, 8095, 8096, 8097];

export default function () {
  const port = HEALTH_TARGETS[Math.floor(Math.random() * HEALTH_TARGETS.length)];
  const health = http.get(`${HOST}:${port}/health`, { tags: { kind: 'health' } });
  check(health, { 'health is 200': (r) => r.status === 200 });

  const txn = JSON.stringify({
    transaction_id: `k6-${__VU}-${__ITER}`,
    account_id: `acct-${__VU}`,
    amount: Math.round(Math.random() * 5000 * 100) / 100,
    currency: 'USD',
    channel: 'online',
    country_code: 'US',
    merchant_category_code: '5732',
  });

  const viaApi = http.post(`${HOST}:8000/v1/fraud/score`, txn, { headers, tags: { kind: 'score' } });
  check(viaApi, { 'api fraud score 200': (r) => r.status === 200 });

  const direct = http.post(`${HOST}:8091/score`, txn, { headers, tags: { kind: 'score' } });
  check(direct, { 'fraud-detector 200': (r) => r.status === 200 });

  sleep(1);
}
