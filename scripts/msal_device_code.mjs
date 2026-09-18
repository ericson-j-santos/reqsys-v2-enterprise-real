#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'

export const POWER_PLATFORM_SCOPES = [
  'https://api.powerplatform.com/EnvironmentManagement.Environments.Read',
  'https://api.powerplatform.com/Connectivity.Connections.Read',
]

export const REQUESTED_PERMISSIONS = [
  'EnvironmentManagement.Environments.Read',
  'Connectivity.Connections.Read',
]

export const DEFAULT_TOTAL_WAIT_SECONDS = 900
export const MIN_TOTAL_WAIT_SECONDS = 300
export const MAX_TOTAL_WAIT_SECONDS = 3000

export function deviceCodeScope() {
  return `openid profile email offline_access ${POWER_PLATFORM_SCOPES.join(' ')}`
}

export function totalWaitSeconds(rawValue) {
  const parsed = Number(String(rawValue ?? '').trim())
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_TOTAL_WAIT_SECONDS
  return Math.min(MAX_TOTAL_WAIT_SECONDS, Math.max(MIN_TOTAL_WAIT_SECONDS, Math.floor(parsed)))
}

export function waitSecondsFromMinutes(rawValue) {
  const parsed = Number(String(rawValue ?? '').trim())
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_TOTAL_WAIT_SECONDS
  return totalWaitSeconds(Math.floor(parsed) * 60)
}

export async function requestDeviceCode({ tenantId, clientId, fetchImpl = fetch, now = () => Date.now() }) {
  const response = await fetchImpl(`https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/devicecode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: clientId, scope: deviceCodeScope() }),
  })
  const payload = await response.json().catch(() => ({}))
  if (response.status !== 200 || !payload.device_code || !payload.user_code) {
    throw new Error(`device_code_http_${response.status}:${JSON.stringify(payload).slice(0, 900)}`)
  }
  return {
    client_id: clientId,
    device_code: String(payload.device_code),
    user_code: String(payload.user_code),
    verification_uri: String(payload.verification_uri || payload.verification_url || 'https://microsoft.com/devicelogin'),
    expires_in: Number(payload.expires_in || 900),
    interval: Number(payload.interval || 5),
    generated_at: new Date(now()).toISOString(),
  }
}

export function pendingPayload(device, attempt = 1) {
  return {
    required: true,
    status: 'awaiting_microsoft_authorization',
    verification_uri: device.verification_uri,
    user_code: device.user_code,
    expires_in_seconds: device.expires_in,
    generated_at: device.generated_at,
    attempt,
    requested_permissions: [...REQUESTED_PERMISSIONS],
  }
}

export function privatePayload(device) {
  return {
    client_id: device.client_id,
    device_code: device.device_code,
    expires_in: device.expires_in,
    interval: device.interval,
    generated_at: device.generated_at,
  }
}

export function authorizationInstruction(device, attempt = 1) {
  const suffix = attempt > 1 ? ` (código renovado — tentativa ${attempt})` : ''
  return `Abra ${device.verification_uri} e informe ${device.user_code}${suffix}.`
}

export async function writeJson(pathname, payload, options = {}) {
  await fs.mkdir(path.dirname(path.resolve(pathname)), { recursive: true })
  await fs.writeFile(pathname, `${JSON.stringify(payload, null, 2)}\n`, { encoding: 'utf8', ...options })
}

export async function appendSummary(summaryPath, markdown) {
  if (!summaryPath) return false
  await fs.appendFile(summaryPath, markdown, 'utf8')
  return true
}
