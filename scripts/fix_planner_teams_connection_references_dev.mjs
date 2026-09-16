#!/usr/bin/env node
import crypto from 'node:crypto'
import fs from 'node:fs/promises'
import { pathToFileURL } from 'node:url'

export const TARGET_FLOWS = [
  'ReqSys - Notificar Teams (Tarefa criada no Planner)',
  'ReqSys - Notificar Teams (Tarefa concluída no Planner)',
]

export const CONNECTORS = {
  planner: {
    key: 'shared_planner',
    connectorId: '/providers/Microsoft.PowerApps/apis/shared_planner',
    displaySuffix: 'Planner → Teams - Planner',
  },
  teams: {
    key: 'shared_teams',
    connectorId: '/providers/Microsoft.PowerApps/apis/shared_teams',
    displaySuffix: 'Planner → Teams - Microsoft Teams',
  },
}

const FLOW_BASE = 'https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple'
const POWER_PLATFORM = 'https://api.powerplatform.com'
const FLOW_API_VERSION = '2016-11-01'
const DATAVERSE_API_VERSION = 'v9.2'
const APPLY = String(process.env.APPLY || '').toLowerCase() === 'true'
const EVIDENCE_PATH =
  process.env.EVIDENCE_PATH ||
  'audit/user-journey/planner-teams-dev/connection-reference-repair.json'

function required(name) {
  const value = String(process.env[name] || '').trim()
  if (!value) throw new Error(`variavel_obrigatoria_ausente:${name}`)
  return value
}

function optional(name) {
  return String(process.env[name] || '').trim()
}

function iso() {
  return new Date().toISOString()
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, item]) => [key, canonicalize(item)]),
    )
  }
  return value
}

export function sha256Json(value) {
  return crypto
    .createHash('sha256')
    .update(JSON.stringify(canonicalize(value)))
    .digest('hex')
}

export function sha256Text(value) {
  return crypto.createHash('sha256').update(String(value)).digest('hex')
}

export function normalizeConnectionId(itemOrId) {
  const raw =
    typeof itemOrId === 'string'
      ? itemOrId
      : String(
          itemOrId?.name ||
            itemOrId?.connectionId ||
            itemOrId?.properties?.connectionId ||
            itemOrId?.id ||
            '',
        )
  const trimmed = raw.trim().replace(/\/+$/, '')
  const marker = '/connections/'
  const idx = trimmed.toLowerCase().lastIndexOf(marker)
  return idx >= 0 ? trimmed.slice(idx + marker.length).split('/')[0] : trimmed
}

export function nativeConnectionReferences(logicalNames) {
  return {
    shared_planner: {
      runtimeSource: 'embedded',
      connection: {
        connectionReferenceLogicalName: logicalNames.planner,
      },
      api: { name: 'shared_planner' },
    },
    shared_teams: {
      runtimeSource: 'embedded',
      connection: {
        connectionReferenceLogicalName: logicalNames.teams,
      },
      api: { name: 'shared_teams' },
    },
  }
}

export function hasExpectedNativeReferences(refs, logicalNames) {
  if (!refs || typeof refs !== 'object') return false
  for (const [kind, connector] of Object.entries(CONNECTORS)) {
    const ref = refs[connector.key]
    if (!ref || ref.connectionName) return false
    if (ref.runtimeSource !== 'embedded') return false
    if (ref?.api?.name !== connector.key) return false
    if (
      ref?.connection?.connectionReferenceLogicalName !== logicalNames[kind]
    ) {
      return false
    }
  }
  return true
}

function safeErrorCode(payload, fallback = 'request_failed') {
  const value =
    payload?.error?.code ||
    payload?.error ||
    payload?.code ||
    payload?.errorCode ||
    fallback
  return String(value).replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 160)
}

async function readResponse(response) {
  const text = await response.text()
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return {}
  }
}

async function requestJson(url, options, allowed, label) {
  const response = await fetch(url, options)
  const payload = await readResponse(response)
  if (!allowed.includes(response.status)) {
    throw new Error(
      `${label}:http_${response.status}:${safeErrorCode(payload)}`,
    )
  }
  return { response, payload }
}

function findRefreshToken(bundle) {
  const candidates = []
  for (const entry of bundle?.sessionStorage || []) {
    if (!entry?.value) continue
    try {
      const item = JSON.parse(entry.value)
      const type = String(item?.credentialType || '').toLowerCase()
      const key = String(entry.name || '').toLowerCase()
      if (
        (type === 'refreshtoken' || key.includes('refreshtoken')) &&
        item?.secret &&
        item?.clientId
      ) {
        candidates.push({
          refreshToken: String(item.secret),
          clientId: String(item.clientId),
        })
      }
    } catch {
      // Ignore non-JSON session entries.
    }
  }
  const unique = new Map(candidates.map((item) => [item.clientId, item]))
  if (!unique.size) throw new Error('msal_refresh_token_ausente')
  if (unique.size > 1) {
    throw new Error(`msal_refresh_token_ambiguo:${unique.size}_clientes`)
  }
  return [...unique.values()][0]
}

async function acquireDelegated(state, tenantId, scope, includeOpenId = false) {
  const effectiveScope = includeOpenId
    ? `openid profile email offline_access ${scope}`
    : scope
  const response = await fetch(
    `https://login.microsoftonline.com/${encodeURIComponent(tenantId)}/oauth2/v2.0/token`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id: state.clientId,
        grant_type: 'refresh_token',
        refresh_token: state.refreshToken,
        scope: effectiveScope,
        client_info: '1',
      }),
    },
  )
  const payload = await readResponse(response)
  if (response.status !== 200 || !payload.access_token) {
    const error = safeErrorCode(payload, `http_${response.status}`)
    throw new Error(`delegated_token:${error}`)
  }
  if (includeOpenId && !payload.id_token) {
    throw new Error('delegated_token:id_token_ausente')
  }
  if (payload.refresh_token) state.refreshToken = payload.refresh_token
  return includeOpenId ? payload : payload.access_token
}

async function acquireByDeviceCode(clientId, tenantId) {
  const privatePath = required('DEVICE_CODE_PRIVATE_PATH')
  let device = null
  try {
    device = JSON.parse(await fs.readFile(privatePath, 'utf8'))
  } catch {
    throw new Error('device_code_privado_ausente')
  }
  if (!device?.device_code) throw new Error('device_code_privado_invalido')

  const effectiveClientId = String(device.client_id || clientId)
  const generatedAt = Date.parse(device.generated_at || iso())
  const deadline = generatedAt + Number(device.expires_in || 900) * 1000
  let interval = Math.max(5, Number(device.interval || 5))

  while (Date.now() < deadline) {
    await sleep(interval * 1000)
    const response = await fetch(
      `https://login.microsoftonline.com/${encodeURIComponent(tenantId)}/oauth2/v2.0/token`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: effectiveClientId,
          grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
          device_code: device.device_code,
        }),
      },
    )
    const payload = await readResponse(response)
    if (response.status === 200) {
      if (!payload.access_token || !payload.refresh_token) {
        throw new Error('device_code_resposta_incompleta')
      }
      return payload
    }
    if (payload.error === 'authorization_pending') continue
    if (payload.error === 'slow_down') {
      interval += 5
      continue
    }
    throw new Error(
      `device_code_token:${safeErrorCode(payload, `http_${response.status}`)}`,
    )
  }
  throw new Error('device_code_expirado_sem_autorizacao')
}

async function acquirePowerPlatformToken(state, tenantId) {
  try {
    return await acquireDelegated(
      state,
      tenantId,
      'https://api.powerplatform.com/.default',
    )
  } catch (error) {
    const message = String(error?.message || error)
    if (
      !message.includes('AADSTS700084') &&
      !message.includes('AADSTS700082') &&
      !message.includes('invalid_grant')
    ) {
      throw error
    }
    const tokens = await acquireByDeviceCode(state.clientId, tenantId)
    state.refreshToken = tokens.refresh_token
    return tokens.access_token
  }
}

async function acquireDataverseToken(state, tenantId, environmentUrl) {
  const scope = `${environmentUrl.replace(/\/+$/, '')}/.default`
  try {
    return {
      token: await acquireDelegated(state, tenantId, scope),
      source: 'delegated',
    }
  } catch (delegatedError) {
    const clientId = optional('POWER_PLATFORM_CLIENT_ID')
    const clientSecret = optional('POWER_PLATFORM_CLIENT_SECRET')
    if (!clientId || !clientSecret) throw delegatedError
    const response = await fetch(
      `https://login.microsoftonline.com/${encodeURIComponent(tenantId)}/oauth2/v2.0/token`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: clientId,
          client_secret: clientSecret,
          grant_type: 'client_credentials',
          scope,
        }),
      },
    )
    const payload = await readResponse(response)
    if (response.status !== 200 || !payload.access_token) {
      throw new Error(
        `dataverse_token:http_${response.status}:${safeErrorCode(payload)}`,
      )
    }
    return { token: payload.access_token, source: 'app_only_fallback' }
  }
}

function normalizeEnvironment(item) {
  const props = item?.properties || {}
  const linked = props.linkedEnvironmentMetadata || {}
  return {
    id: String(item?.id || item?.name || props.environmentId || ''),
    name: String(
      item?.displayName ||
        props.displayName ||
        linked.instanceName ||
        item?.name ||
        '',
    ),
    type: String(
      item?.type || props.environmentSku || props.environmentType || '',
    ),
    url: String(
      item?.url ||
        props.environmentUrl ||
        linked.instanceUrl ||
        linked.instanceApiUrl ||
        '',
    ),
  }
}

function isProductionEnvironment(environment) {
  const text =
    `${environment.id} ${environment.name} ${environment.type} ${environment.url}`.toLowerCase()
  return /(^|[^a-z])(prod|production|producao)([^a-z]|$)/.test(text)
}

async function discoverEnvironment(powerToken, expectedEnvironmentId) {
  const { payload } = await requestJson(
    `${POWER_PLATFORM}/environmentmanagement/environments?api-version=2024-10-01`,
    {
      headers: {
        Authorization: `Bearer ${powerToken}`,
        Accept: 'application/json',
      },
    },
    [200],
    'power_platform_environments',
  )
  const environments = (Array.isArray(payload.value) ? payload.value : []).map(
    normalizeEnvironment,
  )
  const environment = environments.find(
    (item) => item.id === expectedEnvironmentId,
  )
  if (!environment) {
    throw new Error('ambiente_dev_explicito_nao_encontrado')
  }
  if (isProductionEnvironment(environment)) {
    throw new Error('ambiente_dev_explicito_classificado_como_producao')
  }
  if (!environment.url) throw new Error('ambiente_dev_sem_url_dataverse')
  return environment
}

function connectionApiId(item) {
  return String(
    item?.properties?.apiId ||
      item?.properties?.connectorId ||
      item?.type ||
      '',
  ).toLowerCase()
}

function connectionHealthy(item) {
  const props = item?.properties || {}
  const status = JSON.stringify([
    props.status,
    props.statuses,
    props.connectionState,
  ]).toLowerCase()
  return !/(error|invalid|disconnected|broken|unauthorized)/.test(status)
}

export function chooseConnection(items, connectorMarker, explicitId = '') {
  const matches = items.filter((item) =>
    connectionApiId(item).includes(connectorMarker.toLowerCase()),
  )
  if (explicitId) {
    const normalizedExplicit = normalizeConnectionId(explicitId)
    const found = matches.find(
      (item) => normalizeConnectionId(item) === normalizedExplicit,
    )
    if (!found) {
      throw new Error(
        `conexao_explicita_nao_encontrada:${connectorMarker}`,
      )
    }
    if (!connectionHealthy(found)) {
      throw new Error(`conexao_explicita_nao_saudavel:${connectorMarker}`)
    }
    return found
  }

  const healthy = matches.filter(connectionHealthy)
  if (healthy.length !== 1) {
    throw new Error(
      `conexao_${connectorMarker}_ambigua:saudaveis=${healthy.length}:total=${matches.length}`,
    )
  }
  return healthy[0]
}

async function listConnections(powerToken, environmentId) {
  const { payload } = await requestJson(
    `${POWER_PLATFORM}/connectivity/environments/${encodeURIComponent(environmentId)}/connections?api-version=2024-10-01`,
    {
      headers: {
        Authorization: `Bearer ${powerToken}`,
        Accept: 'application/json',
      },
    },
    [200],
    'power_platform_connections',
  )
  return Array.isArray(payload.value) ? payload.value : []
}

function flowUrl(environmentId, flowId = '') {
  const base = `${FLOW_BASE}/environments/${encodeURIComponent(environmentId)}/flows`
  return flowId
    ? `${base}/${encodeURIComponent(flowId)}?api-version=${FLOW_API_VERSION}`
    : `${base}?api-version=${FLOW_API_VERSION}`
}

async function listFlowSummaries(flowToken, environmentId) {
  const items = []
  let next = flowUrl(environmentId)
  while (next) {
    const { payload } = await requestJson(
      next,
      {
        headers: {
          Authorization: `Bearer ${flowToken}`,
          Accept: 'application/json',
        },
      },
      [200],
      'flow_list',
    )
    items.push(...(Array.isArray(payload.value) ? payload.value : []))
    next = String(payload.nextLink || payload['@odata.nextLink'] || '').trim()
  }
  return items
}

async function getFlow(flowToken, environmentId, flowId) {
  const { payload } = await requestJson(
    flowUrl(environmentId, flowId),
    {
      headers: {
        Authorization: `Bearer ${flowToken}`,
        Accept: 'application/json',
      },
    },
    [200],
    'flow_get',
  )
  return payload
}

async function patchFlow(
  flowToken,
  environmentId,
  flowId,
  properties,
  label = 'flow_patch',
) {
  return requestJson(
    flowUrl(environmentId, flowId),
    {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${flowToken}`,
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ properties }),
    },
    [200, 201],
    label,
  )
}

function dataverseHeaders(token, solutionUniqueName = '') {
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'OData-MaxVersion': '4.0',
    'OData-Version': '4.0',
  }
  if (solutionUniqueName) {
    headers['MSCRM.SolutionUniqueName'] = solutionUniqueName
  }
  return headers
}

function dataverseUrl(environmentUrl, path, params = {}) {
  const base = environmentUrl.replace(/\/+$/, '')
  const url = new URL(`${base}/api/data/${DATAVERSE_API_VERSION}/${path}`)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

async function dataverseGet(
  environmentUrl,
  dataverseToken,
  path,
  params,
  label,
) {
  const { payload } = await requestJson(
    dataverseUrl(environmentUrl, path, params),
    { headers: dataverseHeaders(dataverseToken) },
    [200],
    label,
  )
  return payload
}

function odataString(value) {
  return String(value).replaceAll("'", "''")
}

async function findDataverseWorkflow(
  environmentUrl,
  dataverseToken,
  displayName,
) {
  const payload = await dataverseGet(
    environmentUrl,
    dataverseToken,
    'workflows',
    {
      $select: 'workflowid,name,category,statecode,statuscode',
      $filter: `category eq 5 and name eq '${odataString(displayName)}'`,
    },
    'dataverse_workflow',
  )
  const rows = Array.isArray(payload.value) ? payload.value : []
  if (rows.length !== 1) {
    throw new Error(
      `dataverse_workflow_ambiguo:${displayName}:total=${rows.length}`,
    )
  }
  return rows[0]
}

async function solutionIdsForComponent(
  environmentUrl,
  dataverseToken,
  componentId,
) {
  const payload = await dataverseGet(
    environmentUrl,
    dataverseToken,
    'solutioncomponents',
    {
      $select: '_solutionid_value,objectid,componenttype',
      $filter: `objectid eq ${componentId}`,
    },
    'dataverse_solutioncomponents',
  )
  return new Set(
    (payload.value || [])
      .map((row) => String(row._solutionid_value || '').toLowerCase())
      .filter(Boolean),
  )
}

async function readSolutions(environmentUrl, dataverseToken) {
  const payload = await dataverseGet(
    environmentUrl,
    dataverseToken,
    'solutions',
    {
      $select:
        'solutionid,uniquename,friendlyname,ismanaged,isvisible,_publisherid_value',
    },
    'dataverse_solutions',
  )
  return Array.isArray(payload.value) ? payload.value : []
}

export function selectTargetSolution(
  solutions,
  commonSolutionIds,
  explicitUniqueName = '',
) {
  const common = solutions.filter((solution) =>
    commonSolutionIds.has(String(solution.solutionid || '').toLowerCase()),
  )
  if (explicitUniqueName) {
    const exact = common.filter(
      (solution) => solution.uniquename === explicitUniqueName,
    )
    if (exact.length !== 1) {
      throw new Error(
        `solution_explicita_nao_encontrada_ou_ambigua:${explicitUniqueName}`,
      )
    }
    if (exact[0].ismanaged) {
      throw new Error('solution_explicita_gerenciada_nao_permitida')
    }
    return exact[0]
  }

  const excluded = new Set(['default', 'active', 'system', 'basic'])
  const candidates = common.filter((solution) => {
    const unique = String(solution.uniquename || '').toLowerCase()
    return !solution.ismanaged && !excluded.has(unique)
  })
  if (candidates.length === 1) return candidates[0]

  const reqsys = candidates.filter((solution) =>
    `${solution.uniquename || ''} ${solution.friendlyname || ''}`
      .toLowerCase()
      .includes('reqsys'),
  )
  if (reqsys.length === 1) return reqsys[0]

  throw new Error(
    `solution_custom_comum_ambigua:total=${candidates.length}:reqsys=${reqsys.length}`,
  )
}

async function getPublisherPrefix(
  environmentUrl,
  dataverseToken,
  publisherId,
) {
  if (!publisherId) throw new Error('solution_sem_publisher')
  const payload = await dataverseGet(
    environmentUrl,
    dataverseToken,
    `publishers(${publisherId})`,
    { $select: 'customizationprefix,uniquename,friendlyname' },
    'dataverse_publisher',
  )
  const prefix = String(payload.customizationprefix || '')
    .trim()
    .toLowerCase()
  if (!/^[a-z][a-z0-9]{1,10}$/.test(prefix)) {
    throw new Error('publisher_prefix_invalido')
  }
  return prefix
}

async function findConnectionReference(
  environmentUrl,
  dataverseToken,
  logicalName,
) {
  const payload = await dataverseGet(
    environmentUrl,
    dataverseToken,
    'connectionreferences',
    {
      $select:
        'connectionreferenceid,connectionreferencelogicalname,connectionreferencedisplayname,connectorid,connectionid,statecode,statuscode,ismanaged',
      $filter: `connectionreferencelogicalname eq '${odataString(logicalName)}'`,
    },
    'dataverse_connectionreference',
  )
  const rows = Array.isArray(payload.value) ? payload.value : []
  if (rows.length > 1) {
    throw new Error(`connectionreference_logical_ambiguo:${logicalName}`)
  }
  return rows[0] || null
}

async function ensureReferenceMembership(
  environmentUrl,
  dataverseToken,
  referenceId,
  solutionId,
) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const ids = await solutionIdsForComponent(
      environmentUrl,
      dataverseToken,
      referenceId,
    )
    if (ids.has(String(solutionId).toLowerCase())) return true
    if (attempt < 4) await sleep(1500)
  }
  return false
}

async function createOrUpdateConnectionReference({
  environmentUrl,
  dataverseToken,
  solution,
  logicalName,
  displayName,
  connectorId,
  connectionId,
}) {
  const normalizedConnection = normalizeConnectionId(connectionId)
  let current = await findConnectionReference(
    environmentUrl,
    dataverseToken,
    logicalName,
  )

  if (current) {
    if (current.ismanaged) {
      throw new Error(`connectionreference_gerenciada:${logicalName}`)
    }
    if (
      String(current.connectorid || '').toLowerCase() !==
      connectorId.toLowerCase()
    ) {
      throw new Error(`connectionreference_connector_divergente:${logicalName}`)
    }

    const memberships = await solutionIdsForComponent(
      environmentUrl,
      dataverseToken,
      current.connectionreferenceid,
    )
    const targetId = String(solution.solutionid).toLowerCase()
    const otherCustomMembership = [...memberships].some(
      (id) => id !== targetId,
    )
    if (otherCustomMembership && !memberships.has(targetId)) {
      throw new Error(
        `connectionreference_ja_pertence_a_outra_solution:${logicalName}`,
      )
    }

    if (APPLY) {
      await requestJson(
        dataverseUrl(
          environmentUrl,
          `connectionreferences(${current.connectionreferenceid})`,
        ),
        {
          method: 'PATCH',
          headers: dataverseHeaders(
            dataverseToken,
            solution.uniquename,
          ),
          body: JSON.stringify({
            connectionreferencedisplayname: displayName,
            connectorid: connectorId,
            connectionid: normalizedConnection,
            promptingbehavior: 0,
          }),
        },
        [204],
        'connectionreference_patch',
      )
    }
  } else if (APPLY) {
    await requestJson(
      dataverseUrl(environmentUrl, 'connectionreferences'),
      {
        method: 'POST',
        headers: dataverseHeaders(dataverseToken, solution.uniquename),
        body: JSON.stringify({
          connectionreferencedisplayname: displayName,
          connectionreferencelogicalname: logicalName,
          connectorid: connectorId,
          connectionid: normalizedConnection,
          promptingbehavior: 0,
          statecode: 0,
          statuscode: 1,
        }),
      },
      [201, 204],
      'connectionreference_create',
    )
  }

  if (!APPLY && !current) {
    return {
      logicalName,
      action: 'would_create',
      referenceId: null,
      membershipConfirmed: false,
      connectionIdHash: sha256Text(normalizedConnection),
    }
  }

  current = await findConnectionReference(
    environmentUrl,
    dataverseToken,
    logicalName,
  )
  if (!current) {
    throw new Error(`connectionreference_nao_encontrada_apos_write:${logicalName}`)
  }
  if (
    String(current.connectorid || '').toLowerCase() !== connectorId.toLowerCase()
  ) {
    throw new Error(`connectionreference_connector_invalido:${logicalName}`)
  }
  if (
    normalizeConnectionId(current.connectionid) !== normalizedConnection
  ) {
    throw new Error(`connectionreference_connectionid_invalido:${logicalName}`)
  }
  if (Number(current.statecode) !== 0) {
    throw new Error(`connectionreference_inativa:${logicalName}`)
  }

  const membershipConfirmed = await ensureReferenceMembership(
    environmentUrl,
    dataverseToken,
    current.connectionreferenceid,
    solution.solutionid,
  )
  if (!membershipConfirmed) {
    throw new Error(`connectionreference_fora_da_solution:${logicalName}`)
  }

  return {
    logicalName,
    action: 'ensured',
    referenceId: current.connectionreferenceid,
    membershipConfirmed,
    connectionIdHash: sha256Text(normalizedConnection),
  }
}

async function writeEvidence(evidence) {
  await fs.mkdir(
    EVIDENCE_PATH.split('/').slice(0, -1).join('/'),
    { recursive: true },
  )
  await fs.writeFile(
    EVIDENCE_PATH,
    `${JSON.stringify(evidence, null, 2)}\n`,
    'utf8',
  )
}

async function main() {
  const evidence = {
    schema_version: '1.0.0',
    capability: 'planner-teams-connection-reference-repair',
    environment: 'dev',
    started_at: iso(),
    completed_at: null,
    apply: APPLY,
    status: 'running',
    source_sha: optional('GITHUB_SHA'),
    run_id: optional('GITHUB_RUN_ID'),
    run_attempt: optional('GITHUB_RUN_ATTEMPT'),
    secrets_persisted: false,
    target_flows: TARGET_FLOWS,
    checks: {},
    flows: [],
    connection_references: {},
  }

  const originals = new Map()
  const patchedFlowIds = []
  let flowToken = ''
  let environmentId = ''

  try {
    const tenantId = required('POWER_PLATFORM_TENANT_ID')
    const expectedEnvironmentId = required('WSJF_DEV_ENVIRONMENT_ID')
    const statePath = required('MSAL_STORAGE_STATE_PATH')
    const bundle = JSON.parse(await fs.readFile(statePath, 'utf8'))
    const refreshState = findRefreshToken(bundle)

    const powerToken = await acquirePowerPlatformToken(
      refreshState,
      tenantId,
    )
    flowToken = await acquireDelegated(
      refreshState,
      tenantId,
      'https://service.flow.microsoft.com/.default',
    )
    evidence.checks.power_platform_token = 'acquired'
    evidence.checks.flow_management_token = 'acquired'

    const environment = await discoverEnvironment(
      powerToken,
      expectedEnvironmentId,
    )
    environmentId = environment.id
    evidence.power_platform = {
      environment_id: environment.id,
      environment_name: environment.name,
      environment_type: environment.type,
      environment_url: environment.url,
    }
    evidence.checks.environment = 'dev_exact_match'

    const connections = await listConnections(
      powerToken,
      environment.id,
    )
    const plannerConnection = chooseConnection(
      connections,
      'shared_planner',
      optional('WSJF_DEV_PLANNER_CONNECTION_ID'),
    )
    const teamsConnection = chooseConnection(
      connections,
      'shared_teams',
      optional('PLANNER_TEAMS_DEV_TEAMS_CONNECTION_ID'),
    )
    const plannerConnectionId = normalizeConnectionId(plannerConnection)
    const teamsConnectionId = normalizeConnectionId(teamsConnection)
    evidence.connections = {
      planner: {
        id_sha256: sha256Text(plannerConnectionId),
        healthy: true,
      },
      teams: {
        id_sha256: sha256Text(teamsConnectionId),
        healthy: true,
      },
    }
    evidence.checks.connections = 'healthy_exact_or_unique'

    const summaries = await listFlowSummaries(flowToken, environment.id)
    const flowTargets = []
    for (const displayName of TARGET_FLOWS) {
      const matches = summaries.filter(
        (item) => item?.properties?.displayName === displayName,
      )
      if (matches.length !== 1) {
        throw new Error(
          `flow_ambiguo:${displayName}:total=${matches.length}`,
        )
      }
      const flowId = String(matches[0].name || '')
      if (!flowId) throw new Error(`flow_sem_id:${displayName}`)
      const full = await getFlow(flowToken, environment.id, flowId)
      const properties = full.properties || {}
      originals.set(flowId, {
        displayName,
        definition: properties.definition,
        connectionReferences: properties.connectionReferences || {},
        state: String(properties.state || ''),
      })
      flowTargets.push({ displayName, flowId, full })
    }
    evidence.checks.flows = 'two_exact_matches'

    const dataverse = await acquireDataverseToken(
      refreshState,
      tenantId,
      environment.url,
    )
    evidence.checks.dataverse_token = dataverse.source

    const dvWorkflows = []
    const memberships = []
    for (const flow of flowTargets) {
      const workflow = await findDataverseWorkflow(
        environment.url,
        dataverse.token,
        flow.displayName,
      )
      dvWorkflows.push(workflow)
      memberships.push(
        await solutionIdsForComponent(
          environment.url,
          dataverse.token,
          workflow.workflowid,
        ),
      )
    }

    const commonSolutionIds = new Set(
      [...memberships[0]].filter((id) => memberships[1].has(id)),
    )
    if (!commonSolutionIds.size) {
      throw new Error('flows_sem_solution_comum')
    }
    const solutions = await readSolutions(environment.url, dataverse.token)
    const solution = selectTargetSolution(
      solutions,
      commonSolutionIds,
      optional('PLANNER_TEAMS_SOLUTION_UNIQUE_NAME'),
    )
    evidence.solution = {
      solution_id: solution.solutionid,
      unique_name: solution.uniquename,
      friendly_name: solution.friendlyname,
      managed: Boolean(solution.ismanaged),
    }
    evidence.checks.solution = 'unmanaged_common_solution'

    const publisherPrefix = await getPublisherPrefix(
      environment.url,
      dataverse.token,
      solution._publisherid_value,
    )
    const logicalNames = {
      planner: `${publisherPrefix}_sharedplanner_plannerteams`,
      teams: `${publisherPrefix}_sharedteams_plannerteams`,
    }
    evidence.connection_reference_logical_names = logicalNames

    evidence.connection_references.planner =
      await createOrUpdateConnectionReference({
        environmentUrl: environment.url,
        dataverseToken: dataverse.token,
        solution,
        logicalName: logicalNames.planner,
        displayName: `${solution.friendlyname} - ${CONNECTORS.planner.displaySuffix}`,
        connectorId: CONNECTORS.planner.connectorId,
        connectionId: plannerConnectionId,
      })
    evidence.connection_references.teams =
      await createOrUpdateConnectionReference({
        environmentUrl: environment.url,
        dataverseToken: dataverse.token,
        solution,
        logicalName: logicalNames.teams,
        displayName: `${solution.friendlyname} - ${CONNECTORS.teams.displaySuffix}`,
        connectorId: CONNECTORS.teams.connectorId,
        connectionId: teamsConnectionId,
      })

    const desiredReferences = nativeConnectionReferences(logicalNames)
    let changesNeeded = 0

    for (const flow of flowTargets) {
      const before = originals.get(flow.flowId)
      const definitionHashBefore = sha256Json(before.definition)
      const alreadyNative = hasExpectedNativeReferences(
        before.connectionReferences,
        logicalNames,
      )
      if (!alreadyNative) changesNeeded += 1

      if (APPLY && !alreadyNative) {
        await patchFlow(
          flowToken,
          environment.id,
          flow.flowId,
          {
            displayName: flow.displayName,
            definition: before.definition,
            connectionReferences: desiredReferences,
            state: before.state,
          },
          'flow_patch_native_connectionreferences',
        )
        patchedFlowIds.push(flow.flowId)
      }

      evidence.flows.push({
        display_name: flow.displayName,
        flow_id: flow.flowId,
        definition_sha256_before: definitionHashBefore,
        state_before: before.state,
        native_before: alreadyNative,
        change_required: !alreadyNative,
      })
    }

    evidence.checks.plan_changes_needed = changesNeeded

    if (!APPLY) {
      evidence.status =
        changesNeeded === 0 ? 'already_compliant' : 'plan_ready'
      evidence.completed_at = iso()
      await writeEvidence(evidence)
      console.log(
        JSON.stringify({
          status: evidence.status,
          changes_needed: changesNeeded,
          target_flows: TARGET_FLOWS.length,
          solution: solution.uniquename,
        }),
      )
      return
    }

    for (const flowEntry of evidence.flows) {
      const after = await getFlow(
        flowToken,
        environment.id,
        flowEntry.flow_id,
      )
      const properties = after.properties || {}
      flowEntry.definition_sha256_after = sha256Json(
        properties.definition,
      )
      flowEntry.state_after = String(properties.state || '')
      flowEntry.native_after = hasExpectedNativeReferences(
        properties.connectionReferences,
        logicalNames,
      )
      flowEntry.definition_unchanged =
        flowEntry.definition_sha256_before ===
        flowEntry.definition_sha256_after
      flowEntry.state_unchanged =
        flowEntry.state_before === flowEntry.state_after

      if (!flowEntry.native_after) {
        throw new Error(
          `flow_connectionreferences_nao_persistiram:${flowEntry.display_name}`,
        )
      }
      if (!flowEntry.definition_unchanged) {
        throw new Error(
          `flow_definition_alterada_indevidamente:${flowEntry.display_name}`,
        )
      }
      if (!flowEntry.state_unchanged) {
        throw new Error(
          `flow_state_alterado_indevidamente:${flowEntry.display_name}`,
        )
      }
    }

    const afterChangesNeeded = evidence.flows.filter(
      (flow) => !flow.native_after,
    ).length
    evidence.checks.post_write_native_references = 'passed'
    evidence.checks.definition_integrity = 'passed'
    evidence.checks.state_integrity = 'passed'
    evidence.checks.idempotency_replan_changes_needed =
      afterChangesNeeded

    if (afterChangesNeeded !== 0) {
      throw new Error(
        `idempotencia_replan_falhou:changes=${afterChangesNeeded}`,
      )
    }

    evidence.status =
      changesNeeded === 0 ? 'already_compliant' : 'repaired'
    evidence.completed_at = iso()
    await writeEvidence(evidence)
    console.log(
      JSON.stringify({
        status: evidence.status,
        changed_flows: changesNeeded,
        validated_flows: evidence.flows.length,
        definition_integrity: 'passed',
        state_integrity: 'passed',
        idempotency_replan_changes_needed: 0,
      }),
    )
  } catch (error) {
    const primaryError = String(error?.message || error).slice(0, 500)
    evidence.status = 'failed'
    evidence.error_code = primaryError.replace(
      /(Bearer|secret|token)=?\S*/gi,
      '$1=[REDACTED]',
    )

    if (APPLY && flowToken && environmentId && patchedFlowIds.length) {
      evidence.rollback = []
      for (const flowId of [...patchedFlowIds].reverse()) {
        const before = originals.get(flowId)
        try {
          await patchFlow(
            flowToken,
            environmentId,
            flowId,
            {
              displayName: before.displayName,
              definition: before.definition,
              connectionReferences: before.connectionReferences,
              state: before.state,
            },
            'flow_patch_rollback',
          )
          const afterRollback = await getFlow(
            flowToken,
            environmentId,
            flowId,
          )
          const props = afterRollback.properties || {}
          evidence.rollback.push({
            flow_id: flowId,
            status:
              sha256Json(props.definition) ===
                sha256Json(before.definition) &&
              String(props.state || '') === before.state &&
              sha256Json(props.connectionReferences || {}) ===
                sha256Json(before.connectionReferences || {})
                ? 'verified'
                : 'verification_failed',
          })
        } catch (rollbackError) {
          evidence.rollback.push({
            flow_id: flowId,
            status: 'failed',
            error_code: String(
              rollbackError?.message || rollbackError,
            )
              .replace(/(Bearer|secret|token)=?\S*/gi, '$1=[REDACTED]')
              .slice(0, 240),
          })
        }
      }
    }

    evidence.completed_at = iso()
    await writeEvidence(evidence).catch(() => {})
    console.error(
      JSON.stringify({
        status: 'failed',
        error_code: evidence.error_code,
        rollback: evidence.rollback || [],
      }),
    )
    process.exitCode = 1
  }
}

const invokedPath = process.argv[1]
if (
  invokedPath &&
  import.meta.url === pathToFileURL(invokedPath).href
) {
  await main()
}
