#!/usr/bin/env node
import fs from 'node:fs/promises'
import crypto from 'node:crypto'
import { pathToFileURL } from 'node:url'

const GRAPH = 'https://graph.microsoft.com/v1.0'

function env(name, fallback = '') {
  return String(process.env[name] || fallback).trim()
}

function required(name) {
  const value = env(name)
  if (!value) throw new Error(`variavel_obrigatoria_ausente:${name}`)
  return value
}

function iso() { return new Date().toISOString() }
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)) }

async function readJson(response) {
  const text = await response.text()
  try { return text ? JSON.parse(text) : {} } catch { return { raw: text.slice(0, 1000) } }
}

async function checkedJson(response, label, allowed = [200]) {
  const payload = await readJson(response)
  if (!allowed.includes(response.status)) {
    throw new Error(`${label}:http_${response.status}:${JSON.stringify(payload).slice(0, 1200)}`)
  }
  return payload
}

export function messageContainsTitle(message, title) {
  if (!message || !title) return false
  return JSON.stringify(message).includes(title)
}

export function evaluateContract({ normalFound, e2eFound }) {
  if (e2eFound) return { passed: false, reason: 'ct01_e2e_message_observed' }
  if (!normalFound) return { passed: false, reason: 'ct02_normal_message_not_observed' }
  return { passed: true, reason: 'contract_satisfied' }
}

export function filterMessagesSince(messages, startedAt) {
  const floor = Date.parse(startedAt) - 60_000
  return (messages || []).filter((message) => {
    const value = Date.parse(message?.createdDateTime || message?.lastModifiedDateTime || 0)
    return Number.isFinite(value) && value >= floor
  })
}

async function graphToken(tenantId, clientId, clientSecret) {
  const response = await fetch(`https://login.microsoftonline.com/${encodeURIComponent(tenantId)}/oauth2/v2.0/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: 'client_credentials',
      scope: 'https://graph.microsoft.com/.default',
    }),
  })
  const payload = await checkedJson(response, 'graph_token', [200])
  if (!payload.access_token) throw new Error('graph_access_token_ausente')
  return payload.access_token
}

async function graph(method, path, token, body, allowed = [200]) {
  const headers = { Authorization: `Bearer ${token}`, Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const response = await fetch(`${GRAPH}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 403 && path.includes('/messages')) {
    throw new Error('graph_teams_read_forbidden:conceder_ChannelMessage.Read.Group_ou_ChannelMessage.Read.All_ao_app_de_teste')
  }
  return checkedJson(response, `graph:${method}:${path.split('?')[0]}`, allowed)
}

async function createPlannerTask(token, planId, bucketId, title) {
  return graph('POST', '/planner/tasks', token, { planId, bucketId, title }, [201])
}

async function deletePlannerTask(token, taskId) {
  const current = await graph('GET', `/planner/tasks/${encodeURIComponent(taskId)}`, token, undefined, [200])
  const etag = current['@odata.etag']
  if (!etag) throw new Error(`planner_etag_ausente:${taskId}`)
  const response = await fetch(`${GRAPH}/planner/tasks/${encodeURIComponent(taskId)}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}`, 'If-Match': etag },
  })
  if (response.status !== 204) {
    const payload = await readJson(response)
    throw new Error(`planner_cleanup_http_${response.status}:${taskId}:${JSON.stringify(payload).slice(0, 500)}`)
  }
}

async function listChannelMessages(token, teamId, channelId, startedAt) {
  const payload = await graph(
    'GET',
    `/teams/${encodeURIComponent(teamId)}/channels/${encodeURIComponent(channelId)}/messages?$top=50`,
    token,
    undefined,
    [200],
  )
  return filterMessagesSince(payload.value || [], startedAt)
}

async function observeContract({ token, teamId, channelId, startedAt, e2eTitle, normalTitle, timeoutSeconds, pollMs, settleSeconds }) {
  const deadline = Date.now() + timeoutSeconds * 1000
  let polls = 0
  let normalMessage = null
  let e2eMessage = null

  while (Date.now() <= deadline) {
    polls += 1
    const messages = await listChannelMessages(token, teamId, channelId, startedAt)
    e2eMessage = messages.find((message) => messageContainsTitle(message, e2eTitle)) || null
    normalMessage = messages.find((message) => messageContainsTitle(message, normalTitle)) || null

    if (e2eMessage) {
      return { polls, normalMessage, e2eMessage, normalObservedAt: normalMessage ? iso() : null, settlePolls: 0 }
    }

    if (normalMessage) {
      const settleDeadline = Date.now() + settleSeconds * 1000
      let settlePolls = 0
      while (Date.now() < settleDeadline) {
        settlePolls += 1
        await sleep(Math.min(pollMs, Math.max(1, settleDeadline - Date.now())))
        const settledMessages = await listChannelMessages(token, teamId, channelId, startedAt)
        e2eMessage = settledMessages.find((message) => messageContainsTitle(message, e2eTitle)) || null
        if (e2eMessage) break
      }
      return { polls, normalMessage, e2eMessage, normalObservedAt: iso(), settlePolls }
    }

    const remaining = deadline - Date.now()
    if (remaining <= 0) break
    await sleep(Math.min(pollMs, remaining))
  }

  return { polls, normalMessage, e2eMessage, normalObservedAt: null, settlePolls: 0 }
}

async function main() {
  const targetEnvironment = required('TARGET_ENVIRONMENT').toLowerCase()
  if (targetEnvironment !== 'dev') throw new Error(`ambiente_nao_autorizado:${targetEnvironment}`)

  const tenantId = required('POWER_PLATFORM_TENANT_ID')
  const clientId = required('POWER_PLATFORM_CLIENT_ID')
  const clientSecret = required('POWER_PLATFORM_CLIENT_SECRET')
  const planId = required('WSJF_DEV_PLAN_ID')
  const bucketId = required('WSJF_DEV_BUCKET_ID')
  const teamId = required('PLANNER_TEAMS_DEV_TEAM_ID')
  const channelId = required('PLANNER_TEAMS_DEV_CHANNEL_ID')
  const timeoutSeconds = Number(env('PLANNER_TEAMS_POLL_SECONDS', '420'))
  const pollMs = Number(env('PLANNER_TEAMS_RUN_POLL_INTERVAL_MS', '30000'))
  const settleSeconds = Number(env('PLANNER_TEAMS_SETTLE_SECONDS', '45'))
  const evidencePath = env('EVIDENCE_PATH', 'audit/runtime-e2e/planner-teams/acceptance.json')

  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 60 || timeoutSeconds > 600) {
    throw new Error(`poll_timeout_invalido:${timeoutSeconds}`)
  }
  if (!Number.isFinite(pollMs) || pollMs < 5000 || pollMs > 60000) {
    throw new Error(`poll_interval_invalido:${pollMs}`)
  }
  if (!Number.isFinite(settleSeconds) || settleSeconds < 15 || settleSeconds > 120) {
    throw new Error(`settle_invalido:${settleSeconds}`)
  }

  const evidence = {
    schema_version: '1.0.0',
    capability: 'planner-teams-runtime-e2e-continuous',
    mode: 'steady_state_black_box',
    environment: targetEnvironment,
    run_id: env('GITHUB_RUN_ID'),
    run_attempt: env('GITHUB_RUN_ATTEMPT'),
    commit_sha: env('GITHUB_SHA'),
    correlation_id: crypto.randomUUID(),
    started_at: iso(),
    completed_at: null,
    status: 'running',
    mocked: false,
    simulated: false,
    tokens_persisted: false,
    criteria: {
      ct01: 'tarefa REQSYS-E2E-* nao pode produzir mensagem no Teams',
      ct02: 'tarefa normal deve produzir mensagem no Teams',
      positive_control_required: true,
    },
    timing: {
      poll_timeout_seconds: timeoutSeconds,
      poll_interval_seconds: pollMs / 1000,
      settle_seconds: settleSeconds,
    },
    tasks: [],
    observations: {},
    cleanup: [],
  }

  let token = ''
  const taskIds = []
  try {
    token = await graphToken(tenantId, clientId, clientSecret)
    evidence.checks = { graph_app_token: 'acquired' }

    // Preflight de leitura evita criar tarefas quando a identidade nao consegue
    // comprovar o resultado no Teams.
    await listChannelMessages(token, teamId, channelId, evidence.started_at)
    evidence.checks.teams_read = 'available'

    const marker = `${Date.now()}-${env('GITHUB_RUN_ID', 'local')}`
    const e2eTitle = `REQSYS-E2E-AUTOMATED-${marker}`
    const normalTitle = `REQSYS-AUTOMATED-CONTROL-NORMAL-${marker}`

    const e2eTask = await createPlannerTask(token, planId, bucketId, e2eTitle)
    taskIds.push(e2eTask.id)
    const normalTask = await createPlannerTask(token, planId, bucketId, normalTitle)
    taskIds.push(normalTask.id)

    evidence.tasks = [
      { kind: 'e2e', id: e2eTask.id, title: e2eTitle, expected_teams: 'absent' },
      { kind: 'normal', id: normalTask.id, title: normalTitle, expected_teams: 'present' },
    ]
    evidence.tasks_created_at = iso()

    const observed = await observeContract({
      token,
      teamId,
      channelId,
      startedAt: evidence.tasks_created_at,
      e2eTitle,
      normalTitle,
      timeoutSeconds,
      pollMs,
      settleSeconds,
    })

    evidence.observations = {
      polls: observed.polls,
      settle_polls: observed.settlePolls,
      normal_message: observed.normalMessage ? {
        id: String(observed.normalMessage.id || ''),
        created_at: String(observed.normalMessage.createdDateTime || ''),
      } : null,
      e2e_message: observed.e2eMessage ? {
        id: String(observed.e2eMessage.id || ''),
        created_at: String(observed.e2eMessage.createdDateTime || ''),
      } : null,
      normal_observed_at: observed.normalObservedAt,
    }

    if (observed.normalMessage?.createdDateTime) {
      const latency = Date.parse(observed.normalMessage.createdDateTime) - Date.parse(evidence.tasks_created_at)
      if (Number.isFinite(latency)) evidence.observations.trigger_to_teams_latency_seconds = Math.max(0, Math.round(latency / 1000))
    }

    const contract = evaluateContract({
      normalFound: Boolean(observed.normalMessage),
      e2eFound: Boolean(observed.e2eMessage),
    })
    evidence.contract = contract
    if (!contract.passed) throw new Error(contract.reason)

    evidence.status = 'passed'
  } catch (error) {
    evidence.status = 'failed'
    evidence.error = `${error?.name || 'Error'}:${String(error?.message || error).slice(0, 1600)}`
    process.exitCode = 1
  } finally {
    if (token) {
      for (const taskId of taskIds) {
        try {
          await deletePlannerTask(token, taskId)
          evidence.cleanup.push({ id: taskId, status: 'deleted' })
        } catch (error) {
          evidence.cleanup.push({ id: taskId, status: 'failed', error: String(error?.message || error).slice(0, 400) })
          evidence.status = 'failed'
          process.exitCode = 1
        }
      }
    }

    evidence.completed_at = iso()
    const directory = evidencePath.split('/').slice(0, -1).join('/')
    if (directory) await fs.mkdir(directory, { recursive: true })
    await fs.writeFile(evidencePath, JSON.stringify(evidence, null, 2) + '\n', 'utf8')
    console.log(JSON.stringify({
      status: evidence.status,
      correlation_id: evidence.correlation_id,
      contract: evidence.contract || null,
      observations: evidence.observations,
      cleanup: evidence.cleanup,
      evidence_path: evidencePath,
      error: evidence.error || null,
    }))
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(process.argv[1]).href : ''
if (invokedPath === import.meta.url) {
  await main()
}
