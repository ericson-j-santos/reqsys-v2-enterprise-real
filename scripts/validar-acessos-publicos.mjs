#!/usr/bin/env node

const DEFAULT_TARGETS = [
  { name: 'prod-app-fly', environment: 'prod', type: 'app', provider: 'fly', url: 'https://reqsys-app.fly.dev/', expectedStatus: [200, 301, 302, 401, 403] },
  { name: 'prod-app-duckdns', environment: 'prod', type: 'app', provider: 'duckdns', url: 'https://tieriprod.duckdns.org/', expectedStatus: [200, 301, 302, 401, 403] },
  { name: 'prod-api-health', environment: 'prod', type: 'api', provider: 'fly', url: 'https://reqsys-api.fly.dev/health', expectedStatus: [200] },
  { name: 'stg-app-fly', environment: 'staging', type: 'app', provider: 'fly', url: 'https://reqsys-app-stg.fly.dev/', expectedStatus: [200, 301, 302, 401, 403] },
  { name: 'stg-app-duckdns', environment: 'staging', type: 'app', provider: 'duckdns', url: 'https://tierin.duckdns.org/', expectedStatus: [200, 301, 302, 401, 403] },
  { name: 'stg-api-health', environment: 'staging', type: 'api', provider: 'fly', url: 'https://reqsys-api-stg.fly.dev/health', expectedStatus: [200] },
  { name: 'dev-app-fly', environment: 'dev', type: 'app', provider: 'fly', url: 'https://reqsys-app-dev.fly.dev/', expectedStatus: [200, 301, 302, 401, 403] },
  { name: 'dev-app-duckdns', environment: 'dev', type: 'app', provider: 'duckdns', url: 'https://tieridev.duckdns.org/', expectedStatus: [200, 301, 302, 401, 403] },
  { name: 'dev-api-health', environment: 'dev', type: 'api', provider: 'fly', url: 'https://reqsys-api-dev.fly.dev/health', expectedStatus: [200] },
]

const timeoutMs = Number.parseInt(process.env.ACCESS_VALIDATION_TIMEOUT_MS || '15000', 10)
const failOnUnavailable = (process.env.ACCESS_VALIDATION_FAIL_ON_UNAVAILABLE || 'true').toLowerCase() !== 'false'

function nowIso() {
  return new Date().toISOString()
}

async function fetchWithTimeout(url) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  const startedAt = performance.now()

  try {
    const response = await fetch(url, {
      method: 'GET',
      redirect: 'manual',
      signal: controller.signal,
      headers: {
        'User-Agent': 'ReqSysAccessValidator/1.0',
        Accept: 'application/json,text/html;q=0.9,*/*;q=0.8',
      },
    })

    return {
      ok: true,
      status: response.status,
      durationMs: Math.round(performance.now() - startedAt),
      contentType: response.headers.get('content-type') || null,
    }
  } finally {
    clearTimeout(timer)
  }
}

async function validateTarget(target) {
  const checkedAt = nowIso()

  try {
    const result = await fetchWithTimeout(target.url)
    const statusExpected = target.expectedStatus.includes(result.status)

    return {
      ...target,
      checkedAt,
      reachable: true,
      status: result.status,
      statusExpected,
      durationMs: result.durationMs,
      contentType: result.contentType,
      error: null,
    }
  } catch (error) {
    return {
      ...target,
      checkedAt,
      reachable: false,
      status: null,
      statusExpected: false,
      durationMs: null,
      contentType: null,
      error: error?.name === 'AbortError' ? `timeout após ${timeoutMs}ms` : error?.message || String(error),
    }
  }
}

function buildAnalytics(results) {
  const total = results.length
  const reachable = results.filter((item) => item.reachable).length
  const expected = results.filter((item) => item.statusExpected).length
  const byEnvironment = results.reduce((acc, item) => {
    acc[item.environment] ||= { total: 0, reachable: 0, expected: 0 }
    acc[item.environment].total += 1
    if (item.reachable) acc[item.environment].reachable += 1
    if (item.statusExpected) acc[item.environment].expected += 1
    return acc
  }, {})

  const durations = results
    .map((item) => item.durationMs)
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b)

  const maxDurationMs = durations.length ? durations[durations.length - 1] : null
  const avgDurationMs = durations.length
    ? Math.round(durations.reduce((sum, value) => sum + value, 0) / durations.length)
    : null

  return {
    total,
    reachable,
    expected,
    unavailable: total - reachable,
    unexpectedStatus: total - expected,
    reachablePercent: total ? Math.round((reachable / total) * 10000) / 100 : 0,
    expectedPercent: total ? Math.round((expected / total) * 10000) / 100 : 0,
    avgDurationMs,
    maxDurationMs,
    byEnvironment,
  }
}

const results = []
for (const target of DEFAULT_TARGETS) {
  // Execução sequencial para reduzir ruído em ambientes gratuitos.
  // eslint-disable-next-line no-await-in-loop
  results.push(await validateTarget(target))
}

const analytics = buildAnalytics(results)
const payload = {
  generatedAt: nowIso(),
  timeoutMs,
  failOnUnavailable,
  analytics,
  results,
}

console.log(JSON.stringify(payload, null, 2))

const hasFailure = results.some((item) => !item.reachable || !item.statusExpected)
if (failOnUnavailable && hasFailure) {
  process.exitCode = 1
}
