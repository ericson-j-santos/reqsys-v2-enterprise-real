import { verifyAsync as verifyEd25519Fallback } from '@noble/ed25519'

import { isRetiredFlyUrl } from './runtimeUrlPolicy'

const GITHUB_PAGES_HOST = 'ericson-j-santos.github.io'
const GITHUB_PAGES_PREFIX = '/reqsys-v2-enterprise-real/dev/'

function decodeBase64(value) {
  const bytes = Uint8Array.from(atob(value), (char) => char.charCodeAt(0))
  return bytes
}

function decodeBase64Json(value) {
  return JSON.parse(new TextDecoder().decode(decodeBase64(value)))
}

function isAllowedRuntimeUrl(value, suffix) {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'https:'
      && !isRetiredFlyUrl(parsed.toString())
      && parsed.hostname.endsWith(suffix)
  } catch {
    return false
  }
}

export function isGitHubPagesDevRuntime(locationLike = window.location) {
  return locationLike.hostname === GITHUB_PAGES_HOST
    && locationLike.pathname.startsWith(GITHUB_PAGES_PREFIX)
}

export async function verifyLocatorEnvelope(envelope, config, options = {}) {
  if (!envelope || envelope.v !== 1 || !envelope.payload_b64 || !envelope.signature_b64) return null

  const cryptoImpl = options.cryptoImpl || crypto
  const now = options.now ?? Math.floor(Date.now() / 1000)
  const publicKey = decodeBase64(config.public_key_b64)
  const signature = decodeBase64(envelope.signature_b64)
  const signedPayload = new TextEncoder().encode(envelope.payload_b64)
  let valid = false
  try {
    const key = await cryptoImpl.subtle.importKey(
      'raw',
      publicKey,
      { name: 'Ed25519' },
      false,
      ['verify'],
    )
    valid = await cryptoImpl.subtle.verify({ name: 'Ed25519' }, key, signature, signedPayload)
  } catch {
    // Safari/WebViews antigos não implementam Ed25519 no Web Crypto. O
    // fallback é uma verificação criptográfica local, não uma aceitação sem
    // assinatura; os mesmos bytes e a mesma chave pública continuam exigidos.
    const fallback = options.verifyEd25519Fallback || verifyEd25519Fallback
    valid = await fallback(signature, signedPayload, publicKey)
  }
  if (!valid) return null

  const payload = decodeBase64Json(envelope.payload_b64)
  if (payload.environment !== config.environment) return null
  if (!Number.isFinite(payload.issued_at) || !Number.isFinite(payload.expires_at)) return null
  if (payload.issued_at > now + 60 || payload.expires_at <= now) return null
  if (!Array.isArray(payload.urls) || !payload.urls.includes(payload.selected_url)) return null
  if (!payload.urls.every((url) => isAllowedRuntimeUrl(url, config.allowed_url_suffix))) return null

  const contract = payload.runtime_contract
  if (!contract || contract.version !== config.required_runtime_contract) return null
  if (contract.static_frontend_required !== true || contract.vite_hmr_forbidden !== true) return null
  if (!Array.isArray(contract.required_endpoints)) return null
  if (!config.required_endpoints.every((endpoint) => contract.required_endpoints.includes(endpoint))) return null
  return payload
}

export function selectLatestValidLocator(messages, config, options = {}) {
  return messages
    .filter((item) => item?.event === 'message' && item?.title === 'reqsys-dev-locator')
    .reverse()
    .reduce(async (selectedPromise, item) => {
      const selected = await selectedPromise
      if (selected) return selected
      try {
        return await verifyLocatorEnvelope(JSON.parse(item.message), config, options)
      } catch {
        return null
      }
    }, Promise.resolve(null))
}

let resolutionPromise = null

export async function resolvePublicRuntimeApiBase(options = {}) {
  const locationLike = options.locationLike || window.location
  if (!isGitHubPagesDevRuntime(locationLike)) return null

  const fetchImpl = options.fetchImpl || fetch
  const baseUrl = new URL(import.meta.env.BASE_URL, locationLike.origin)
  const configResponse = await fetchImpl(new URL('runtime-locator.json', baseUrl), { cache: 'no-store' })
  if (!configResponse.ok) throw new Error(`runtime_locator_config_http_${configResponse.status}`)
  const config = await configResponse.json()

  const locatorUrl = `https://ntfy.sh/${encodeURIComponent(config.topic)}/json?poll=1&since=1h`
  const locatorResponse = await fetchImpl(locatorUrl, { cache: 'no-store' })
  if (!locatorResponse.ok) throw new Error(`runtime_locator_http_${locatorResponse.status}`)
  const rows = (await locatorResponse.text()).trim().split(/\r?\n/).filter(Boolean)
  const messages = rows.map((row) => JSON.parse(row))
  const payload = await selectLatestValidLocator(messages, config, options)
  if (!payload) throw new Error('runtime_locator_sem_estado_assinado_vigente')
  return `${payload.selected_url.replace(/\/+$/, '')}/api`
}

export function ensurePublicRuntimeApiBase(options = {}) {
  if (!resolutionPromise) resolutionPromise = resolvePublicRuntimeApiBase(options)
  return resolutionPromise
}

export function resetPublicRuntimeResolutionForTests() {
  resolutionPromise = null
}
