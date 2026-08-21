#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'
import { performance as nodePerformance } from 'node:perf_hooks'
import process from 'node:process'
import { chromium } from 'playwright'

const VERSION = '1.0.0'

function parseArgs(argv) {
  const options = {
    url: process.env.REQSYS_APP_URL || 'https://reqsys-app.fly.dev',
    output: 'artifacts/performance/browser-performance.json',
    budgets: 'config/runtime-performance-budgets.json',
    strict: false,
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--strict') {
      options.strict = true
    } else if (arg === '--url') {
      options.url = argv[++index]
    } else if (arg === '--output') {
      options.output = argv[++index]
    } else if (arg === '--budgets') {
      options.budgets = argv[++index]
    } else {
      throw new Error(`Argumento desconhecido: ${arg}`)
    }
  }
  return options
}

function percentile(values, q) {
  if (!values.length) return 0
  const ordered = [...values].sort((a, b) => a - b)
  const position = (ordered.length - 1) * q
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  if (lower === upper) return Number(ordered[lower].toFixed(2))
  const weight = position - lower
  return Number(
    (ordered[lower] * (1 - weight) + ordered[upper] * weight).toFixed(2),
  )
}

function evaluateBudget(metrics, budget) {
  const checks = [
    ['event_loop_lag_p95_ms', 'max_event_loop_lag_p95_ms'],
    ['event_loop_lag_max_ms', 'max_event_loop_lag_max_ms'],
    ['max_long_task_ms', 'max_long_task_ms'],
    ['lcp_ms', 'max_lcp_ms'],
    ['heap_after_gc_mb', 'max_heap_after_gc_mb'],
    ['gc_roundtrip_ms', 'max_gc_roundtrip_ms'],
  ]
  return checks
    .filter(([metric, target]) => budget[target] != null && metrics[metric] != null)
    .filter(([metric, target]) => Number(metrics[metric]) > Number(budget[target]))
    .map(
      ([metric, target]) =>
        `${metric}=${Number(metrics[metric]).toFixed(2)} viola ${target}=${Number(
          budget[target],
        ).toFixed(2)}`,
    )
}

async function measureEventLoopLag(page, intervalMs = 50, samples = 40) {
  return page.evaluate(
    async ({ intervalMs, samples }) => {
      const delays = []
      let expected = performance.now() + intervalMs
      await new Promise((resolve) => {
        const timer = setInterval(() => {
          const now = performance.now()
          delays.push(Math.max(0, now - expected))
          expected = now + intervalMs
          if (delays.length >= samples) {
            clearInterval(timer)
            resolve()
          }
        }, intervalMs)
      })
      return delays
    },
    { intervalMs, samples },
  )
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  const policy = JSON.parse(await fs.readFile(options.budgets, 'utf8'))
  if (policy.schema_version !== '1.0.0' || !policy.browser) {
    throw new Error('Policy de browser ausente ou incompatível')
  }

  const browser = await chromium.launch({
    headless: true,
    args: ['--js-flags=--expose-gc'],
  })

  let report
  try {
    const context = await browser.newContext()
    const page = await context.newPage()

    await page.addInitScript(() => {
      window.__reqsysPerformance = {
        longTasks: [],
        lcp: null,
      }
      try {
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            window.__reqsysPerformance.longTasks.push(entry.duration)
          }
        }).observe({ type: 'longtask', buffered: true })
      } catch {
        // Browser sem Long Tasks API: métrica ficará indisponível.
      }
      try {
        new PerformanceObserver((list) => {
          const entries = list.getEntries()
          const last = entries[entries.length - 1]
          if (last) {
            window.__reqsysPerformance.lcp = last.renderTime || last.loadTime || last.startTime
          }
        }).observe({ type: 'largest-contentful-paint', buffered: true })
      } catch {
        // Browser sem LCP observer: métrica ficará indisponível.
      }
    })

    const navigationStarted = nodePerformance.now()
    const response = await page.goto(options.url, {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    })
    const navigationRoundtripMs = nodePerformance.now() - navigationStarted

    if (!response || response.status() >= 400) {
      throw new Error(`Navegação falhou: HTTP ${response?.status() ?? 'sem resposta'}`)
    }

    await page.waitForTimeout(1200)
    const eventLoopLags = await measureEventLoopLag(page)

    const cdpsession = await context.newCDPSession(page)
    const heapBefore = await cdpsession.send('Runtime.getHeapUsage')
    const gcStarted = nodePerformance.now()
    await cdpsession.send('HeapProfiler.collectGarbage')
    const gcRoundtripMs = nodePerformance.now() - gcStarted
    const heapAfter = await cdpsession.send('Runtime.getHeapUsage')

    const browserMetrics = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0]
      const data = window.__reqsysPerformance || { longTasks: [], lcp: null }
      return {
        lcp_ms: data.lcp == null ? null : Number(data.lcp.toFixed(2)),
        long_tasks: data.longTasks.map((value) => Number(value.toFixed(2))),
        dom_content_loaded_ms: nav ? Number(nav.domContentLoadedEventEnd.toFixed(2)) : null,
        load_event_ms: nav ? Number(nav.loadEventEnd.toFixed(2)) : null,
      }
    })

    const maxLongTask =
      browserMetrics.long_tasks.length > 0
        ? Math.max(...browserMetrics.long_tasks)
        : 0
    const heapBeforeMb = heapBefore.usedSize / (1024 * 1024)
    const heapAfterMb = heapAfter.usedSize / (1024 * 1024)

    const metrics = {
      navigation_roundtrip_ms: Number(navigationRoundtripMs.toFixed(2)),
      dom_content_loaded_ms: browserMetrics.dom_content_loaded_ms,
      load_event_ms: browserMetrics.load_event_ms,
      lcp_ms: browserMetrics.lcp_ms,
      event_loop_lag_p95_ms: percentile(eventLoopLags, 0.95),
      event_loop_lag_max_ms: Number(Math.max(...eventLoopLags).toFixed(2)),
      long_task_count: browserMetrics.long_tasks.length,
      max_long_task_ms: Number(maxLongTask.toFixed(2)),
      heap_before_gc_mb: Number(heapBeforeMb.toFixed(2)),
      heap_after_gc_mb: Number(heapAfterMb.toFixed(2)),
      heap_reclaimed_mb: Number(Math.max(0, heapBeforeMb - heapAfterMb).toFixed(2)),
      gc_roundtrip_ms: Number(gcRoundtripMs.toFixed(2)),
    }

    const violations = evaluateBudget(metrics, policy.browser)
    report = {
      schema_version: '1.0.0',
      gate_version: VERSION,
      contract: 'reqsys-browser-performance-budget',
      url: options.url,
      strict: options.strict,
      policy_version: policy.policy_version,
      generated_at: new Date().toISOString(),
      status: violations.length ? 'blocked' : 'passed',
      metrics,
      budget: policy.browser,
      violations,
    }

    await context.close()
  } finally {
    await browser.close()
  }

  await fs.mkdir(path.dirname(options.output), { recursive: true })
  await fs.writeFile(options.output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  console.log(JSON.stringify({ status: report.status, violations: report.violations.length }))
  if (options.strict && report.violations.length) {
    process.exitCode = 1
  }
}

main().catch((error) => {
  console.error(`browser_performance_gate_error: ${error.stack || error.message}`)
  process.exitCode = 2
})
