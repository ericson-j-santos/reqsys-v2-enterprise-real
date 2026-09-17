#!/usr/bin/env node
import fs from 'node:fs/promises'

import {
  pendingPayload,
  privatePayload,
  requestDeviceCode,
  writeJson,
} from './msal_device_code.mjs'

function required(name) {
  const value = String(process.env[name] || '').trim()
  if (!value) throw new Error(`variavel_obrigatoria_ausente:${name}`)
  return value
}

const statePath = required('MSAL_STORAGE_STATE_PATH')
const tenantId = required('POWER_PLATFORM_TENANT_ID')
const privatePath = required('DEVICE_CODE_PRIVATE_PATH')
const publicPath = required('DEVICE_CODE_PUBLIC_PATH')

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

if (stillValid) {
  await writeJson(publicPath, {
    required: false,
    status: 'existing_session_valid',
    expires_at: new Date(expiresOn * 1000).toISOString(),
  })
  console.log('Sessao MSAL existente ainda valida; device code nao necessario.')
  process.exit(0)
}

const device = await requestDeviceCode({ tenantId, clientId: refresh.clientId })

await writeJson(privatePath, privatePayload(device), { mode: 0o600 })
await fs.chmod(privatePath, 0o600).catch(() => {})
await writeJson(publicPath, pendingPayload(device, 1))

console.log('Device code preparado com permissoes minimas de leitura; apenas URL, user_code e nomes das permissoes foram publicados.')
