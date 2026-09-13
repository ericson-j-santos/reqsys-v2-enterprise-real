#!/usr/bin/env node
import fs from 'node:fs/promises'
import crypto from 'node:crypto'

const required = (name) => {
  const value = String(process.env[name] || '').trim()
  if (!value) throw new Error(`variavel_obrigatoria_ausente:${name}`)
  return value
}

const statePath = required('MSAL_STORAGE_STATE_PATH')
const tenantId = required('POWER_PLATFORM_TENANT_ID')
const environmentId = required('POWER_PLATFORM_ENVIRONMENT_ID')
const outputPath = required('POWER_PLATFORM_SQL_PROBE_OUTPUT')

const bundle = JSON.parse(await fs.readFile(statePath, 'utf8'))
let refresh = null
for (const entry of Array.isArray(bundle?.sessionStorage) ? bundle.sessionStorage : []) {
  if (!entry || typeof entry !== 'object') continue
  try {
    const item = JSON.parse(String(entry.value || ''))
    if (item && typeof item === 'object' && item.credentialType === 'RefreshToken' && item.clientId && item.secret) {
      refresh = item
      break
    }
  } catch {}
}
if (!refresh) throw new Error('msal_refresh_token_ausente')

const tokenResponse = await fetch(`https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({
    client_id: String(refresh.clientId),
    grant_type: 'refresh_token',
    refresh_token: String(refresh.secret),
    scope: 'https://api.powerplatform.com/.default',
  }),
})
const tokenPayload = await tokenResponse.json().catch(() => ({}))
if (tokenResponse.status !== 200 || !tokenPayload.access_token) {
  throw new Error(`power_token_http_${tokenResponse.status}`)
}

const response = await fetch(`https://api.powerplatform.com/connectivity/environments/${encodeURIComponent(environmentId)}/connections?api-version=2024-10-01`, {
  headers: { Authorization: `Bearer ${tokenPayload.access_token}`, Accept: 'application/json' },
})
const payload = await response.json().catch(() => ({}))
if (response.status !== 200) throw new Error(`connections_http_${response.status}`)
const values = Array.isArray(payload?.value) ? payload.value : []

const sql = values.filter((item) => JSON.stringify(item).toLowerCase().includes('shared_sql'))
const safe = sql.map((item) => {
  const raw = JSON.stringify(item).toLowerCase()
  const props = item?.properties || {}
  const statusRaw = JSON.stringify([props.status, props.statuses, props.connectionState]).toLowerCase()
  const id = String(item?.name || item?.id || '')
  return {
    connection_hash: crypto.createHash('sha256').update(id).digest('hex').slice(0, 16),
    healthy: !['error','invalid','disconnected','broken','unauthorized'].some((x) => statusRaw.includes(x)),
    gateway_reference_present: raw.includes('gateway'),
    noteri_reference_present: raw.includes('noteri'),
    reqsys_database_reference_present: raw.includes('reqsysintegrationdev'),
  }
})
const result = {
  schema_version: '1.0.0',
  environment: 'dev',
  sql_connections_total: safe.length,
  healthy_sql_connections: safe.filter((x) => x.healthy).length,
  exact_runtime_candidates: safe.filter((x) => x.healthy && x.gateway_reference_present && x.noteri_reference_present && x.reqsys_database_reference_present).length,
  connections: safe,
  secret_value_exposed: false,
  production_touched: false,
  test_touched: false,
}
await fs.mkdir(outputPath.split('/').slice(0, -1).join('/'), { recursive: true })
await fs.writeFile(outputPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({
  sql_connections_total: result.sql_connections_total,
  healthy_sql_connections: result.healthy_sql_connections,
  exact_runtime_candidates: result.exact_runtime_candidates,
}))
