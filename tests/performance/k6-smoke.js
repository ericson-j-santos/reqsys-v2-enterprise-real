import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: Number(__ENV.K6_VUS || 5),
  duration: __ENV.K6_DURATION || '20s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<750'],
    checks: ['rate>0.99'],
  },
};

const baseUrl = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export default function () {
  const response = http.get(`${baseUrl}/health`, {
    headers: { 'X-Correlation-ID': `k6-${__VU}-${__ITER}` },
    tags: { endpoint: 'health' },
  });

  check(response, {
    'health retorna 2xx': (r) => r.status >= 200 && r.status < 300,
    'health responde em até 750 ms': (r) => r.timings.duration < 750,
  });
  sleep(0.2);
}
