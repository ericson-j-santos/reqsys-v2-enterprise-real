#!/usr/bin/env node

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const MANIFEST_PATH = process.env.ACCESS_VALIDATION_MANIFEST
  || resolve(ROOT, 'infra/public-access-urls.json')

const timeoutMs = Number.parseInt(process.env.ACCESS_VALIDATION_TIMEOUT_MS || '20000', 10)
const outputPath = process.env.ACCESS_VALIDATION_OUTPUT || 'artifacts/public-access-validation/public-access-validation.json'
const failOnUnavailable = (process.env.ACCESS_VALIDATION_FAIL_ON_UNAVAILABLE || 'true').toLowerCase() !== 'false'

function nowIso() {
  return new Date().toISOString()
}

async function loadTargets() {
  const raw = await readFile(MANIFEST_PATH, 'utf8')
  const manifest = JSON.parse(raw)
  return manifest.targets || []
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
        'User-Agent': 'ReqSysAccessValidator/1.1',
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

function isJsonResponse(result) {
  return Boolean(result.contentType && result.contentType.includes('application/json'))
}

async function validateTarget(target) {
  const checkedAt = nowIso()
  const retries = Number.isFinite(target.coldStartRetries) ? target.coldStartRetries : 0
  let lastError = null

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const result = await fetchWithTimeout(target.url)
      const statusExpected = target.expectedStatus.includes(result.status)
      const jsonExpected = target.expectJson ? isJsonResponse(result) : true

      return {
        ...target,
        checkedAt,
        attempt,
        reachable: true,
        status: result.status,
        statusExpected,
        jsonExpected,
        durationMs: result.durationMs,
        contentType: result.contentType,
        error: null,
        passed: statusExpected && jsonExpected,
      }
    } catch (error) {
      lastError = error?.name === 'AbortError' ? `timeout após ${timeoutMs}ms` : error?.message || String(error)
      if (attempt < retries) {
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 3000))
      }
    }
  }

  return {
    ...target,
    checkedAt,
    attempt: retries,
    reachable: false,
    status: null,
    statusExpected: false,
    jsonExpected: false,
    durationMs: null,
    contentType: null,
    error: lastError,
    passed: false,
  }
}

function buildAnalytics(results) {
  const total = results.length
  const required = results.filter((item) => item.required !== false)
  const optional = results.filter((item) => item.required === false)
  const reachable = results.filter((item) => item.reachable).length
  const passed = results.filter((item) => item.passed).length
  const requiredPassed = required.filter((item) => item.passed).length

  const byEnvironment = results.reduce((acc, item) => {
    acc[item.environment] ||= { total: 0, reachable: 0, passed: 0, required: 0, requiredPassed: 0 }
    acc[item.environment].total += 1
    if (item.reachable) acc[item.environment].reachable += 1
    if (item.passed) acc[item.environment].passed += 1
    if (item.required !== false) {
      acc[item.environment].required += 1
      if (item.passed) acc[item.environment].requiredPassed += 1
    }
    return acc
  }, {})

  const durations = results
    .map((item) => item.durationMs)
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b)

  return {
    total,
    requiredTotal: required.length,
    optionalTotal: optional.length,
    reachable,
    passed,
    requiredPassed,
    unavailable: total - reachable,
    failed: total - passed,
    requiredFailed: required.length - requiredPassed,
    reachablePercent: total ? Math.round((reachable / total) * 10000) / 100 : 0,
    passedPercent: total ? Math.round((passed / total) * 10000) / 100 : 0,
    avgDurationMs: durations.length
      ? Math.round(durations.reduce((sum, value) => sum + value, 0) / durations.length)
      : null,
    maxDurationMs: durations.length ? durations[durations.length - 1] : null,
    byEnvironment,
  }
}

const targets = await loadTargets()
const results = []
for (const target of targets) {
  // Execução sequencial para reduzir ruído em ambientes gratuitos.
  // eslint-disable-next-line no-await-in-loop
  results.push(await validateTarget(target))
}

const analytics = buildAnalytics(results)
const payload = {
  schemaVersion: '1.1.0',
  artifact: 'public-access-validation',
  issue: 'REQSYS#323',
  manifest: MANIFEST_PATH.replace(`${ROOT}/`, ''),
  generatedAt: nowIso(),
  timeoutMs,
  failOnUnavailable,
  analytics,
  environments: analytics.byEnvironment,
  results,
}

await mkdir(dirname(outputPath), { recursive: true })
await writeFile(outputPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')

console.log(JSON.stringify({ ...payload, outputPath }, null, 2))

const hasRequiredFailure = results.some((item) => item.required !== false && !item.passed)
if (failOnUnavailable && hasRequiredFailure) {
  process.exitCode = 1
}
