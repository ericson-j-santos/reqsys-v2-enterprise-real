#!/usr/bin/env node
import fs from 'node:fs/promises'
import crypto from 'node:crypto'

const API_URL = required('API_URL').replace(/\/$/, '')
const MSAL_STORAGE_STATE_PATH = required('MSAL_STORAGE_STATE_PATH')
const TENANT_ID = required('POWER_PLATFORM_TENANT_ID')
const GRAPH_CLIENT_ID = required('POWER_PLATFORM_CLIENT_ID')
const GRAPH_CLIENT_SECRET = required('POWER_PLATFORM_CLIENT_SECRET')
const GROUP_ID = required('WSJF_DEV_GROUP_ID')
const PLAN_ID = required('WSJF_DEV_PLAN_ID')
const BUCKET_ID = required('WSJF_DEV_BUCKET_ID')
const TEAM_ID = required('PLANNER_TEAMS_DEV_TEAM_ID')
const CHANNEL_ID = required('PLANNER_TEAMS_DEV_CHANNEL_ID')
const EVIDENCE_PATH = process.env.EVIDENCE_PATH || 'audit/user-journey/planner-teams-dev/acceptance.json'
const FLOW_BASE = 'https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple'
const GRAPH = 'https://graph.microsoft.com/v1.0'
const POWER_PLATFORM = 'https://api.powerplatform.com'
const POLL_SECONDS = Number(process.env.PLANNER_TEAMS_POLL_SECONDS || '420')

function required(name) {
  const value = String(process.env[name] || '').trim()
  if (!value) throw new Error(`variavel_obrigatoria_ausente:${name}`)
  return value
}

function iso() { return new Date().toISOString() }
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)) }

async function jsonResponse(response, label, allowed = [200]) {
  const text = await response.text()
  let payload = {}
  try { payload = text ? JSON.parse(text) : {} } catch { payload = { raw: text.slice(0, 500) } }
  if (!allowed.includes(response.status)) {
    const body = JSON.stringify(payload).slice(0, 1000)
    throw new Error(`${label}:http_${response.status}:${body}`)
  }
  return payload
}

function findLocalStorage(bundle, name) {
  for (const origin of bundle?.storageState?.origins || []) {
    const found = (origin.localStorage || []).find((item) => item?.name === name)
    if (found?.value) return found.value
  }
  return ''
}

function findRefreshToken(bundle) {
  const candidates = []
  for (const entry of bundle?.sessionStorage || []) {
    if (!entry?.value) continue
    try {
      const item = JSON.parse(entry.value)
      const type = String(item?.credentialType || '').toLowerCase()
      const key = String(entry.name || '').toLowerCase()
      if ((type === 'refreshtoken' || key.includes('refreshtoken')) && item?.secret && item?.clientId) {
        candidates.push({ refreshToken: item.secret, clientId: item.clientId })
      }
    } catch { /* entrada nao JSON */ }
  }
  if (!candidates.length) throw new Error('msal_refresh_token_ausente')
  const unique = new Map(candidates.map((item) => [item.clientId, item]))
  if (unique.size > 1) throw new Error(`msal_refresh_token_ambiguo:${unique.size}_clientes`)
  return [...unique.values()][0]
}

async function acquireDelegated(state, scope) {
  const body = new URLSearchParams({
    client_id: state.clientId,
    grant_type: 'refresh_token',
    refresh_token: state.refreshToken,
    scope,
    client_info: '1',
  })
  const response = await fetch(`https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  const payload = await jsonResponse(response, `token:${scope}`, [200])
  if (!payload.access_token) throw new Error(`access_token_ausente:${scope}`)
  if (payload.refresh_token) state.refreshToken = payload.refresh_token
  return payload.access_token
}

async function acquireGraphAppToken() {
  const body = new URLSearchParams({
    client_id: GRAPH_CLIENT_ID,
    client_secret: GRAPH_CLIENT_SECRET,
    grant_type: 'client_credentials',
    scope: 'https://graph.microsoft.com/.default',
  })
  const response = await fetch(`https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token`, {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body,
  })
  const payload = await jsonResponse(response, 'graph_app_token', [200])
  if (!payload.access_token) throw new Error('graph_app_access_token_ausente')
  return payload.access_token
}

async function reqsys(path, reqsysToken, options = {}) {
  const headers = { Accept: 'application/json', ...(options.headers || {}) }
  if (reqsysToken) headers.Authorization = `Bearer ${reqsysToken}`
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json'
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })
  return jsonResponse(response, `reqsys:${path}`, options.allowed || [200])
}

function unwrap(payload) {
  if (payload?.data?.data && typeof payload.data.data === 'object') return payload.data.data
  if (payload?.data && typeof payload.data === 'object') return payload.data
  return payload
}

function chooseDevEnvironment(status) {
  const ambientes = Array.isArray(status?.ambientes) ? status.ambientes : []
  const explicit = String(process.env.WSJF_DEV_ENVIRONMENT_ID || '').trim()
  if (explicit) {
    const found = ambientes.find((item) => String(item?.id || '') === explicit)
    if (!found) throw new Error('ambiente_dev_explicito_nao_encontrado')
    return found
  }
  const matches = ambientes.filter((item) => {
    const text = [item?.id, item?.nome, item?.tipo, item?.url].filter(Boolean).join(' ').toLowerCase()
    return /(^|[^a-z])dev([^a-z]|$)|development|desenvolvimento/.test(text)
  })
  if (matches.length !== 1) throw new Error(`ambiente_dev_ambiguo:${matches.length}`)
  return matches[0]
}

function chooseConnection(items, marker, envName) {
  const explicit = String(process.env[envName] || '').trim()
  const matches = items.filter((item) => {
    const props = item?.properties || {}
    const apiId = String(props.apiId || props.connectorId || item?.type || '').toLowerCase()
    return apiId.includes(marker)
  })
  if (explicit) {
    const found = matches.find((item) => String(item?.name || item?.id || '') === explicit)
    if (!found) throw new Error(`conexao_explicita_nao_encontrada:${envName}`)
    return found
  }
  const healthy = matches.filter((item) => {
    const props = item?.properties || {}
    const raw = JSON.stringify([props.status, props.statuses, props.connectionState]).toLowerCase()
    return !/(error|invalid|disconnected|broken|unauthorized)/.test(raw)
  })
  const candidates = healthy.length ? healthy : matches
  if (candidates.length !== 1) throw new Error(`conexao_${marker}_ambigua:${candidates.length}`)
  return candidates[0]
}

function connectionId(item) { return String(item?.name || item?.id || '').trim() }
function connectionName(item) { return String(item?.properties?.displayName || item?.name || item?.id || '') }

async function flowAction(environmentId, flowId, action, flowToken) {
  const url = `${FLOW_BASE}/environments/${encodeURIComponent(environmentId)}/flows/${encodeURIComponent(flowId)}/${action}?api-version=2016-11-01`
  const response = await fetch(url, { method: 'POST', headers: { Authorization: `Bearer ${flowToken}` } })
  if (![200, 202, 204].includes(response.status)) {
    const text = (await response.text()).slice(0, 1000)
    throw new Error(`flow_${action}:http_${response.status}:${text}`)
  }
  return { status: response.status }
}

async function listFlowRuns(environmentId, flowId, flowToken, since) {
  const url = `${FLOW_BASE}/environments/${encodeURIComponent(environmentId)}/flows/${encodeURIComponent(flowId)}/runs?api-version=2016-11-01`
  const response = await fetch(url, { headers: { Authorization: `Bearer ${flowToken}` } })
  const payload = await jsonResponse(response, 'flow_runs', [200])
  return (payload.value || []).filter((run) => {
    const start = Date.parse(run?.properties?.startTime || run?.properties?.createdTime || 0)
    return Number.isFinite(start) && start >= Date.parse(since) - 60_000
  }).map((run) => ({
    id: run?.name || run?.id || '',
    status: run?.properties?.status || '',
    start_time: run?.properties?.startTime || run?.properties?.createdTime || '',
    end_time: run?.properties?.endTime || '',
  }))
}

async function graph(method, path, token, body, allowed = [200]) {
  const headers = { Authorization: `Bearer ${token}`, Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const response = await fetch(`${GRAPH}${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  })
  return jsonResponse(response, `graph:${method}:${path.split('?')[0]}`, allowed)
}

async function createPlannerTask(token, title) {
  return graph('POST', '/planner/tasks', token, { planId: PLAN_ID, bucketId: BUCKET_ID, title }, [201])
}

async function deletePlannerTask(token, taskId) {
  const current = await graph('GET', `/planner/tasks/${encodeURIComponent(taskId)}`, token, undefined, [200])
  const etag = current['@odata.etag']
  if (!etag) throw new Error(`planner_etag_ausente:${taskId}`)
  const response = await fetch(`${GRAPH}/planner/tasks/${encodeURIComponent(taskId)}`, {
    method: 'DELETE', headers: { Authorization: `Bearer ${token}`, 'If-Match': etag },
  })
  if (response.status !== 204) throw new Error(`planner_cleanup_http_${response.status}:${taskId}`)
}

const evidence = {
  schema_version: '1.0.0',
  capability: 'planner-teams-notify-dev-acceptance',
  environment: 'dev',
  started_at: iso(),
  completed_at: null,
  status: 'running',
  correlation_id: crypto.randomUUID(),
  mocked: false,
  simulated: false,
  tokens_persisted: false,
  tasks: [],
  flows: [],
  checks: {},
}

let graphToken = ''
let flowToken = ''
let environmentId = ''
const createdTaskIds = []
const startedFlowIds = []

try {
  const bundle = JSON.parse(await fs.readFile(MSAL_STORAGE_STATE_PATH, 'utf8'))
  const reqsysToken = findLocalStorage(bundle, 'reqsys_token')
  if (!reqsysToken) throw new Error('reqsys_token_ausente_no_storage_state')
  const refreshState = findRefreshToken(bundle)

  const powerToken = await acquireDelegated(refreshState, 'https://api.powerplatform.com/.default')
  flowToken = await acquireDelegated(refreshState, 'https://service.flow.microsoft.com/.default')
  graphToken = await acquireGraphAppToken()
  evidence.checks.delegated_power_platform_token = 'acquired'
  evidence.checks.delegated_flow_management_token = 'acquired'
  evidence.checks.graph_app_token = 'acquired'

  const statusPayload = unwrap(await reqsys('/v1/hub-lowcode/copilot-memory/install/status', reqsysToken))
  const environment = chooseDevEnvironment(statusPayload)
  environmentId = String(environment.id || '').trim()
  const environmentUrl = String(environment.url || '').trim()
  if (!environmentId || !environmentUrl) throw new Error('ambiente_dev_sem_id_ou_url')
  evidence.power_platform = { environment_id: environmentId, environment_name: environment.nome || '', environment_url: environmentUrl }

  const connectionsResponse = await fetch(
    `${POWER_PLATFORM}/connectivity/environments/${encodeURIComponent(environmentId)}/connections?api-version=2024-10-01`,
    { headers: { Authorization: `Bearer ${powerToken}`, Accept: 'application/json' } },
  )
  const connectionsPayload = await jsonResponse(connectionsResponse, 'power_platform_connections', [200])
  const connections = Array.isArray(connectionsPayload.value) ? connectionsPayload.value : []
  const plannerConnection = chooseConnection(connections, 'shared_planner', 'WSJF_DEV_PLANNER_CONNECTION_ID')
  const teamsConnection = chooseConnection(connections, 'shared_teams', 'PLANNER_TEAMS_DEV_TEAMS_CONNECTION_ID')
  evidence.connections = {
    planner: { id: connectionId(plannerConnection), name: connectionName(plannerConnection) },
    teams: { id: connectionId(teamsConnection), name: connectionName(teamsConnection) },
  }

  const deployPayload = {
    environment_id: environmentId,
    environment_url: environmentUrl,
    group_id: GROUP_ID,
    plan_id: PLAN_ID,
    planner_connection_id: connectionId(plannerConnection),
    teams_team_id: TEAM_ID,
    teams_channel_id: CHANNEL_ID,
    teams_connection_id: connectionId(teamsConnection),
    target_environment: 'dev',
    confirmar: true,
    correlation_id: evidence.correlation_id,
  }
  const deployed = unwrap(await reqsys('/v1/hub-lowcode/planner-teams-notify/deploy', reqsysToken, {
    method: 'POST',
    headers: { 'X-Power-Automate-Token': flowToken },
    body: JSON.stringify(deployPayload),
  }))
  if (!deployed?.dispatched || deployed?.status !== 'implantado') {
    throw new Error(`provisionamento_nao_implantado:${JSON.stringify(deployed).slice(0, 1200)}`)
  }
  evidence.checks.provisioning = 'implanted'
  evidence.flows = (deployed.flows || []).map((flow) => ({ evento: flow.evento, flow_id: flow.flow_id, flow_url: flow.flow_url }))

  for (const flow of evidence.flows) {
    await flowAction(environmentId, flow.flow_id, 'start', flowToken)
    startedFlowIds.push(flow.flow_id)
  }
  evidence.checks.flow_activation = 'started'

  const marker = Date.now()
  const e2eTitle = `REQSYS-E2E-NOTIFY-FILTER-${marker}`
  const normalTitle = `REQSYS-NOTIFY-FILTER-NORMAL-${marker}`
  const e2eTask = await createPlannerTask(graphToken, e2eTitle)
  createdTaskIds.push(e2eTask.id)
  const normalTask = await createPlannerTask(graphToken, normalTitle)
  createdTaskIds.push(normalTask.id)
  evidence.tasks = [
    { kind: 'e2e', id: e2eTask.id, title: e2eTitle, expected_teams: 'skipped' },
    { kind: 'normal', id: normalTask.id, title: normalTitle, expected_teams: 'succeeded' },
  ]
  evidence.checks.planner_tasks_created = 2
  evidence.observation_window_started_at = iso()

  await sleep(POLL_SECONDS * 1000)

  for (const flow of evidence.flows) {
    flow.runs = await listFlowRuns(environmentId, flow.flow_id, flowToken, evidence.observation_window_started_at)
  }
  const createdFlow = evidence.flows.find((flow) => flow.evento === 'criada')
  evidence.checks.created_flow_runs_observed = createdFlow?.runs?.length || 0
  if ((createdFlow?.runs?.length || 0) < 2) {
    throw new Error(`execucoes_flow_criada_insuficientes:${createdFlow?.runs?.length || 0}`)
  }

  evidence.status = 'runtime_executed_awaiting_teams_observation'
} catch (error) {
  evidence.status = 'failed'
  evidence.error = `${error?.name || 'Error'}:${String(error?.message || error).slice(0, 1800)}`
  process.exitCode = 1
} finally {
  evidence.cleanup = { tasks: [], flows: [] }
  if (graphToken) {
    for (const taskId of createdTaskIds) {
      try {
        await deletePlannerTask(graphToken, taskId)
        evidence.cleanup.tasks.push({ id: taskId, status: 'deleted' })
      } catch (error) {
        evidence.cleanup.tasks.push({ id: taskId, status: 'failed', error: String(error?.message || error).slice(0, 300) })
        process.exitCode = 1
      }
    }
  }
  if (flowToken && environmentId) {
    for (const flowId of startedFlowIds) {
      try {
        await flowAction(environmentId, flowId, 'stop', flowToken)
        evidence.cleanup.flows.push({ id: flowId, status: 'stopped' })
      } catch (error) {
        evidence.cleanup.flows.push({ id: flowId, status: 'failed', error: String(error?.message || error).slice(0, 300) })
        process.exitCode = 1
      }
    }
  }
  evidence.completed_at = iso()
  await fs.mkdir(EVIDENCE_PATH.split('/').slice(0, -1).join('/'), { recursive: true })
  await fs.writeFile(EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + '\n', 'utf8')
  console.log(JSON.stringify({
    status: evidence.status,
    correlation_id: evidence.correlation_id,
    tasks: evidence.tasks.map(({ kind, title, expected_teams }) => ({ kind, title, expected_teams })),
    created_flow_runs_observed: evidence.checks.created_flow_runs_observed || 0,
    evidence_path: EVIDENCE_PATH,
  }))
}
