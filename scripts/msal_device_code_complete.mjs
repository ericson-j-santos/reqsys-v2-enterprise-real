#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  appendSummary,
  authorizationInstruction,
  pendingPayload,
  privatePayload,
  requestDeviceCode,
  totalWaitSeconds,
  waitSecondsFromMinutes,
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function parseJsonEntry(raw) {
  try {
    const value = JSON.parse(String(raw ?? ''))
    const object = value && typeof value === 'object' && !Array.isArray(value) ? value : null
    return { validJson: true, object }
  } catch {
    return { validJson: false, object: null }
  }
}

export function applyRefreshToken(bundle, tokenPayload, clientId) {
  if (!bundle || typeof bundle !== 'object' || Array.isArray(bundle)) {
    throw new Error('msal_bundle_invalido')
  }
  const refreshToken = String(tokenPayload?.refresh_token || '')
  if (!refreshToken) throw new Error('device_code_refresh_token_ausente')
  const effectiveClientId = String(clientId || '').trim()
  if (!effectiveClientId) throw new Error('device_code_client_id_ausente')

  const entries = Array.isArray(bundle.sessionStorage) ? [...bundle.sessionStorage] : []
  let replaced = false
  const normalized = []

  for (const entry of entries) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue

    const parsedEntry = parseJsonEntry(entry.value)
    if (parsedEntry.validJson && !parsedEntry.object) continue

    const parsed = parsedEntry.object
    const type = String(parsed?.credentialType || '').toLowerCase()
    const sameClient = !parsed?.clientId || String(parsed.clientId) === effectiveClientId
    if (!replaced && type === 'refreshtoken' && sameClient) {
      const updated = {
        ...parsed,
        credentialType: 'RefreshToken',
        clientId: effectiveClientId,
        secret: refreshToken,
      }
      if (Number.isFinite(Number(tokenPayload?.refresh_token_expires_in))) {
        updated.expiresOn = Math.floor(Date.now() / 1000) + Number(tokenPayload.refresh_token_expires_in)
      } else {
        delete updated.expiresOn
      }
      normalized.push({ ...entry, value: JSON.stringify(updated) })
      replaced = true
      continue
    }
    normalized.push(entry)
  }

  if (!replaced) {
    normalized.push({
      name: `device-code-refreshtoken-${effectiveClientId}`,
      value: JSON.stringify({
        credentialType: 'RefreshToken',
        clientId: effectiveClientId,
        secret: refreshToken,
      }),
    })
  }

  return {
    ...bundle,
    schemaVersion: Number(bundle.schemaVersion || 1),
    authSource: 'device_code',
    sessionStorage: normalized,
    deviceCodeAuthorizedAt: new Date().toISOString(),
  }
}

export function pollDecision(payload, status) {
  if (status === 200) return 'success'
  const error = String(payload?.error || '')
  if (error === 'authorization_pending') return 'retry'
  if (error === 'slow_down') return 'slow_down'
  if (error === 'authorization_declined') return 'declined'
  if (error === 'expired_token') return 'expired'
  return 'failure'
}

export const MAX_DEVICE_CODE_ATTEMPTS = 6

export function deviceDeadline(device, now) {
  const generatedAt = Date.parse(device?.generated_at || '')
  const base = Number.isFinite(generatedAt) ? generatedAt : now
  const expiresIn = Math.max(60, Number(device?.expires_in || 900))
  return base + expiresIn * 1000
}

async function pollToken({ tenantId, device, fetchImpl }) {
  const response = await fetchImpl(`https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: String(device.client_id),
      grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
      device_code: String(device.device_code),
    }),
  })
  const payload = await response.json().catch(() => ({}))
  return { payload, decision: pollDecision(payload, response.status), status: response.status }
}

/**
 * Aguarda a autorização Microsoft renovando o device code sempre que ele expirar,
 * até esgotar o orçamento total de espera. Um único code expirado deixa de encerrar
 * a execução: a janela humana passa a ser o orçamento, não os ~15 min do Entra ID.
 */
export async function authorizeWithRenewal({
  tenantId,
  device,
  totalDeadline,
  now = () => Date.now(),
  sleepImpl = sleep,
  fetchImpl = fetch,
  requestDeviceCodeImpl = requestDeviceCode,
  onRenewedDeviceCode = async () => {},
}) {
  let current = device
  let attempt = Number(device?.attempt || 1)
  let intervalSeconds = Math.max(5, Number(current.interval || 5))
  let deadline = Math.min(deviceDeadline(current, now()), totalDeadline)

  while (now() < totalDeadline) {
    if (now() >= deadline) {
      // Não gera um código que ninguém teria tempo de usar nem excede o teto de tentativas.
      if (totalDeadline - now() <= intervalSeconds * 1000) break
      if (attempt >= MAX_DEVICE_CODE_ATTEMPTS) break
      attempt += 1
      current = await requestDeviceCodeImpl({ tenantId, clientId: String(current.client_id), fetchImpl, now })
      intervalSeconds = Math.max(5, Number(current.interval || 5))
      deadline = Math.min(deviceDeadline(current, now()), totalDeadline)
      await onRenewedDeviceCode(current, attempt)
      continue
    }

    await sleepImpl(intervalSeconds * 1000)
    const { payload, decision, status } = await pollToken({ tenantId, device: current, fetchImpl })
    if (decision === 'retry') continue
    if (decision === 'slow_down') {
      intervalSeconds += 5
      continue
    }
    if (decision === 'declined') throw new Error('device_code_autorizacao_recusada')
    if (decision === 'expired') {
      deadline = now()
      continue
    }
    if (decision === 'failure') throw new Error(`device_code_token_http_${status}_${String(payload?.error || 'unknown')}`)
    return { tokenPayload: payload, device: current, attempt }
  }

  throw new Error('device_code_expirado_sem_autorizacao')
}

async function readJson(pathname) {
  return JSON.parse(await fs.readFile(pathname, 'utf8'))
}

async function main() {
  const statePath = required('MSAL_STORAGE_STATE_PATH')
  const tenantId = required('POWER_PLATFORM_TENANT_ID')
  const privatePath = required('DEVICE_CODE_PRIVATE_PATH')
  const publicPath = required('DEVICE_CODE_PUBLIC_PATH')
  const summaryPath = optional('GITHUB_STEP_SUMMARY')
  const waitMinutes = optional('DEVICE_CODE_TOTAL_WAIT_MINUTES')
  const waitSeconds = waitMinutes
    ? waitSecondsFromMinutes(waitMinutes)
    : totalWaitSeconds(optional('DEVICE_CODE_TOTAL_WAIT_SECONDS'))

  const publicState = await readJson(publicPath)
  if (publicState?.required === false && publicState?.status === 'existing_session_valid') {
    console.log('Sessão MSAL existente ainda válida; nenhuma autorização adicional foi necessária.')
    return
  }

  const device = await readJson(privatePath)
  if (!device?.device_code || !device?.client_id) throw new Error('device_code_privado_incompleto')

  const generatedAt = Date.parse(device.generated_at || new Date().toISOString())
  const totalDeadline = (Number.isFinite(generatedAt) ? generatedAt : Date.now()) + waitSeconds * 1000

  console.log(`Janela total de autorização: ${waitSeconds}s; o device code é renovado automaticamente enquanto houver orçamento.`)

  const { tokenPayload, device: authorizedDevice, attempt } = await authorizeWithRenewal({
    tenantId,
    device,
    totalDeadline,
    async onRenewedDeviceCode(renewed, renewedAttempt) {
      await writeJson(privatePath, privatePayload(renewed), { mode: 0o600 })
      await fs.chmod(privatePath, 0o600).catch(() => {})
      await writeJson(publicPath, pendingPayload(renewed, renewedAttempt))
      const instruction = authorizationInstruction(renewed, renewedAttempt)
      console.log(`::notice title=Autorização Microsoft pendente::${instruction}`)
      await appendSummary(
        summaryPath,
        `\n## Autorização Microsoft — código renovado (tentativa ${renewedAttempt})\n\n`
        + `Abra [${renewed.verification_uri}](${renewed.verification_uri}) e informe **\`${renewed.user_code}\`**. `
        + 'O job continuará automaticamente.\n',
      )
    },
  })

  if (!tokenPayload.access_token || !tokenPayload.refresh_token) {
    throw new Error('device_code_resposta_incompleta')
  }

  const bundle = await readJson(statePath)
  const updated = applyRefreshToken(bundle, tokenPayload, String(authorizedDevice.client_id))
  await fs.writeFile(statePath, `${JSON.stringify(updated, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 })
  await fs.chmod(statePath, 0o600).catch(() => {})

  await writeJson(publicPath, {
    required: false,
    status: 'authorized_ephemeral',
    authorized_at: new Date().toISOString(),
    auth_source: 'device_code',
    session_persisted: false,
    device_code_attempts: attempt,
  })

  await fs.rm(privatePath, { force: true }).catch(() => {})
  console.log('Autorização Microsoft concluída; sessão efêmera atualizada sem publicar tokens.')
}

const __filename = fileURLToPath(import.meta.url)
if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  main().catch((error) => {
    console.error(`Falha ao concluir autorização Microsoft: ${error instanceof Error ? error.message : 'erro_desconhecido'}`)
    process.exitCode = 1
  })
}
