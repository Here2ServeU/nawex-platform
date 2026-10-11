import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<400'],
    http_req_failed: ['rate<0.02'],
  },
};

// k6 run -e BASE_URL=http://localhost:8090 -e API_KEY=dev-key tools/k6/transaction-load.js
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8090';
const API_KEY = __ENV.API_KEY || '';

export default function () {
  const payload = JSON.stringify({
    account_id: 'acct-k6',
    amount: 99.99,
    currency: 'USD',
    merchant: 'Golden Platform Load Test',
    merchant_category_code: '5732',
    channel: 'online',
    country_code: 'US',
    fraud_score: 0.12,
  });

  const params = {
    headers: { 'Content-Type': 'application/json', ...(API_KEY ? { 'X-API-Key': API_KEY } : {}) },
  };

  const res = http.post(`${BASE_URL}/api/v1/transactions`, payload, params);

  check(res, {
    'status is 201': (r) => r.status === 201,
    'has transaction id': (r) => !!r.json('id'),
  });

  sleep(1);
}
