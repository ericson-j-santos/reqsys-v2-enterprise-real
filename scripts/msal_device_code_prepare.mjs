#!/usr/bin/env node
import fs from 'node:fs/promises'

const statePath = required('MSAL_STORAGE_STATE_PATH')
const tenantId = required('POWER_PLATFORM_TENANT_ID')
const privatePath = required('DEVICE_CODE_PRIVATE_PATH')
const publicPath = required('DEVICE_CODE_PUBLIC_PATH')

const POWER_PLATFORM_SCOPES = [
  'https://api.powerplatform.com/EnvironmentManagement.Environments.Read',
  'https://api.powerplatform.com/Connectivity.Connections.Read',
]

function required(name) {
  const value = String(process.env[name] || '').trim()
  if (!value) throw new Error(`variavel_obrigatoria_ausente:${name}`)
  return value
}

function findRefresh(bundle) {
  for (const entry of bundle?.sessionStorage || []) {
    try {
      const item = JSON.parse(entry.value)
      if (item?.credentialType === 'RefreshToken' && item?.clientId && item?.secret) return item
    } catch { /* ignore */ }
  }
  throw new Error('msal_refresh_token_ausente')
}

const bundle = JSON.parse(await fs.readFile(statePath, 'utf8'))
const refresh = findRefresh(bundle)
const expiresOn = Number(refresh.expiresOn || 0)
const stillValid = Number.isFinite(expiresOn) && expiresOn > Math.floor(Date.now() / 1000) + 300

await fs.mkdir(publicPath.split('/').slice(0, -1).join('/'), { recursive: true })

if (stillValid) {
  await fs.writeFile(publicPath, JSON.stringify({
    required: false,
    status: 'existing_session_valid',
    expires_at: new Date(expiresOn * 1000).toISOString(),
  }, null, 2) + '\n')
  console.log('Sessao MSAL existente ainda valida; device code nao necessario.')
  process.exit(0)
}

const response = await fetch(`https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/devicecode`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({
    client_id: refresh.clientId,
    scope: `openid profile email offline_access ${POWER_PLATFORM_SCOPES.join(' ')}`,
  }),
})
const payload = await response.json().catch(() => ({}))
if (response.status !== 200 || !payload.device_code || !payload.user_code) {
  throw new Error(`device_code_http_${response.status}:${JSON.stringify(payload).slice(0, 900)}`)
}

const verificationUri = payload.verification_uri || payload.verification_url || 'https://microsoft.com/devicelogin'
await fs.writeFile(privatePath, JSON.stringify({
  client_id: refresh.clientId,
  device_code: payload.device_code,
  expires_in: payload.expires_in,
  interval: payload.interval,
  generated_at: new Date().toISOString(),
}, null, 2) + '\n', { mode: 0o600 })
await fs.chmod(privatePath, 0o600).catch(() => {})

await fs.writeFile(publicPath, JSON.stringify({
  required: true,
  status: 'awaiting_microsoft_authorization',
  verification_uri: verificationUri,
  user_code: payload.user_code,
  expires_in_seconds: payload.expires_in,
  generated_at: new Date().toISOString(),
  requested_permissions: [
    'EnvironmentManagement.Environments.Read',
    'Connectivity.Connections.Read',
  ],
}, null, 2) + '\n')

console.log('Device code preparado com permissoes minimas de leitura; apenas URL, user_code e nomes das permissoes foram publicados.')
