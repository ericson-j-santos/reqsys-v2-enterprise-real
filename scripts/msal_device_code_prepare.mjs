#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  pendingPayload,
  privatePayload,
  requestDeviceCode,
  writeJson,
} from './msal_device_code.mjs'

function optional(name) {
  return String(process.env[name] || '').trim()
}

function required(name) {
  const value = optional(name)
  if (!value) throw new Error(`variavel_obrigatoria_ausente:${name}`)
  return value
}

export function findRefresh(bundle) {
  for (const entry of bundle?.sessionStorage || []) {
    try {
      const item = JSON.parse(entry.value)
      if (item?.credentialType === 'RefreshToken' && item?.clientId && item?.secret) return item
    } catch { /* ignore */ }
  }
  return null
}

export function resolveDeviceClientId(refresh, bootstrapClientId) {
  const fromRefresh = String(refresh?.clientId || '').trim()
  if (fromRefresh) return fromRefresh
  const fromBootstrap = String(bootstrapClientId || '').trim()
  if (fromBootstrap) return fromBootstrap
  throw new Error('msal_refresh_token_ausente_sem_bootstrap_client_id')
}

export async function main() {
  const statePath = required('MSAL_STORAGE_STATE_PATH')
  const tenantId = required('POWER_PLATFORM_TENANT_ID')
  const privatePath = required('DEVICE_CODE_PRIVATE_PATH')
  const publicPath = required('DEVICE_CODE_PUBLIC_PATH')
  const bootstrapClientId = optional('MSAL_BOOTSTRAP_CLIENT_ID')

  const bundle = JSON.parse(await fs.readFile(statePath, 'utf8'))
  const refresh = findRefresh(bundle)
  const expiresOn = Number(refresh?.expiresOn || 0)
  const stillValid = Boolean(refresh) && Number.isFinite(expiresOn) && expiresOn > Math.floor(Date.now() / 1000) + 300

  if (stillValid) {
    await writeJson(publicPath, {
      required: false,
      status: 'existing_session_valid',
      expires_at: new Date(expiresOn * 1000).toISOString(),
    })
    console.log('Sessao MSAL existente ainda valida; device code nao necessario.')
    return
  }

  const clientId = resolveDeviceClientId(refresh, bootstrapClientId)
  const device = await requestDeviceCode({ tenantId, clientId })

  await writeJson(privatePath, privatePayload(device), { mode: 0o600 })
  await fs.chmod(privatePath, 0o600).catch(() => {})
  await writeJson(publicPath, pendingPayload(device, 1))

  console.log('Device code preparado com permissoes minimas; apenas URL, user_code e nomes das permissoes foram publicados.')
}

const __filename = fileURLToPath(import.meta.url)
if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  main().catch((error) => {
    console.error(`Falha ao preparar autorização Microsoft: ${error instanceof Error ? error.message : 'erro_desconhecido'}`)
    process.exitCode = 1
  })
}
