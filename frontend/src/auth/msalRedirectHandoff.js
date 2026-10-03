const HANDOFF_VERSION = 1

export const MSAL_REDIRECT_HANDOFF_KEY = 'reqsys_msal_redirect_handoff_v1'
export const MSAL_REDIRECT_HANDOFF_TTL_MS = 10 * 60 * 1000

const TEMPORARY_KEY_SUFFIXES = [
  'request.origin',
  'urlHash',
  'request.params',
  'code.verifier',
  'request.native',
]

function storageOrNull(name) {
  try {
    return typeof window !== 'undefined' ? window[name] : null
  } catch {
    return null
  }
}

function callbackParams(locationLike = window.location) {
  const search = new URLSearchParams(String(locationLike?.search || '').replace(/^\?/, ''))
  const hash = new URLSearchParams(String(locationLike?.hash || '').replace(/^#/, ''))
  return [search, hash]
}

function hasMicrosoftResponse(params) {
  return params.has('state')
    && (params.has('code') || params.has('error') || params.has('session_state'))
}

function callbackState(locationLike) {
  const params = callbackParams(locationLike).find(hasMicrosoftResponse)
  return String(params?.get('state') || '')
}

function requestState(entries, clientId) {
  try {
    const encoded = entries?.[`msal.${clientId}.request.params`]
    const normalized = String(encoded || '').replace(/-/g, '+').replace(/_/g, '/')
    const padding = normalized.length % 4
    const padded = padding ? `${normalized}${'='.repeat(4 - padding)}` : normalized
    const bytes = Uint8Array.from(atob(padded), (char) => char.codePointAt(0))
    const request = JSON.parse(new TextDecoder().decode(bytes))
    return typeof request?.state === 'string' && request.state.length <= 4096
      ? request.state
      : ''
  } catch {
    return ''
  }
}

export function isMicrosoftRedirectResponse(locationLike = window.location) {
  return callbackParams(locationLike).some(hasMicrosoftResponse)
}

export function getMicrosoftRedirectResponse(locationLike = window.location) {
  const [search, hash] = callbackParams(locationLike)
  if (hasMicrosoftResponse(search)) return String(locationLike?.search || '')
  if (hasMicrosoftResponse(hash)) return String(locationLike?.hash || '')
  return ''
}

export function clearMicrosoftRedirectResponse(
  locationLike = window.location,
  historyLike = window.history
) {
  const [search, hash] = callbackParams(locationLike)
  const clearSearch = hasMicrosoftResponse(search)
  const clearHash = hasMicrosoftResponse(hash)
  if (!clearSearch && !clearHash) return false
  const nextSearch = clearSearch ? '' : String(locationLike.search || '')
  const nextHash = clearHash ? '' : String(locationLike.hash || '')
  historyLike.replaceState(historyLike.state, '', `${locationLike.pathname || '/'}${nextSearch}${nextHash}`)
  return true
}

function allowedTemporaryKeys(clientId) {
  return [
    'msal.interaction.status',
    ...TEMPORARY_KEY_SUFFIXES.map((suffix) => `msal.${clientId}.${suffix}`),
  ]
}

function parseSigninStatus(raw, clientId) {
  try {
    const status = JSON.parse(raw)
    return status?.clientId === clientId && status?.type === 'signin'
  } catch {
    return false
  }
}

function readValidHandoff({
  now = Date.now(),
  persistentStorage = storageOrNull('localStorage'),
  locationLike = typeof window !== 'undefined' ? window.location : null,
  expectedRedirectUri = null,
  expectedClientId = null,
  consume = false,
} = {}) {
  if (!persistentStorage) return null

  let raw = null
  try {
    raw = persistentStorage.getItem(MSAL_REDIRECT_HANDOFF_KEY)
  } catch {
    return null
  }
  if (!raw) return null

  try {
    const handoff = JSON.parse(raw)
    const validWindow = Number.isFinite(handoff?.createdAt)
      && Number.isFinite(handoff?.expiresAt)
      && handoff.createdAt <= now
      && handoff.expiresAt >= now
      && handoff.expiresAt - handoff.createdAt <= MSAL_REDIRECT_HANDOFF_TTL_MS
    const clientId = String(handoff?.clientId || '')
    const tenantId = String(handoff?.tenantId || '')
    const redirectUri = String(handoff?.redirectUri || '')
    const entries = handoff?.entries
    const interactionStatus = entries?.['msal.interaction.status']
    const state = String(handoff?.state || '')

    if (
      handoff?.version !== HANDOFF_VERSION
      || !validWindow
      || !clientId
      || !tenantId
      || !redirectUri.startsWith('https://')
      || (expectedRedirectUri && redirectUri !== expectedRedirectUri)
      || !entries
      || typeof entries !== 'object'
      || !parseSigninStatus(interactionStatus, clientId)
      || !state
      || requestState(entries, clientId) !== state
    ) {
      persistentStorage.removeItem(MSAL_REDIRECT_HANDOFF_KEY)
      return null
    }

    if (!isMicrosoftRedirectResponse(locationLike)) return null
    if (expectedClientId && clientId !== expectedClientId) return null
    if (callbackState(locationLike) !== state) return null
    if (consume) persistentStorage.removeItem(MSAL_REDIRECT_HANDOFF_KEY)

    return { clientId, tenantId, redirectUri, state, entries }
  } catch {
    try {
      persistentStorage.removeItem(MSAL_REDIRECT_HANDOFF_KEY)
    } catch {
      // Storage indisponível: não há handoff seguro para consumir.
    }
    return null
  }
}

export function peekMsalRedirectHandoff(options = {}) {
  return readValidHandoff({ ...options, consume: false })
}

export function persistMsalRedirectHandoff({
  clientId,
  tenantId,
  redirectUri,
  now = Date.now(),
  sessionStorage = storageOrNull('sessionStorage'),
  persistentStorage = storageOrNull('localStorage'),
} = {}) {
  if (!clientId || !tenantId || !redirectUri || !sessionStorage || !persistentStorage) return false

  try {
    const entries = Object.fromEntries(
      allowedTemporaryKeys(clientId)
        .map((key) => [key, sessionStorage.getItem(key)])
        .filter(([, value]) => typeof value === 'string' && value.length > 0)
    )
    const requiredKeys = [
      'msal.interaction.status',
      `msal.${clientId}.request.params`,
      `msal.${clientId}.code.verifier`,
      `msal.${clientId}.request.origin`,
    ]
    if (
      !requiredKeys.every((key) => entries[key])
      || !parseSigninStatus(entries['msal.interaction.status'], clientId)
    ) return false
    const state = requestState(entries, clientId)
    if (!state) return false

    persistentStorage.setItem(MSAL_REDIRECT_HANDOFF_KEY, JSON.stringify({
      version: HANDOFF_VERSION,
      clientId,
      tenantId,
      redirectUri,
      createdAt: now,
      expiresAt: now + MSAL_REDIRECT_HANDOFF_TTL_MS,
      state,
      entries,
    }))
    return true
  } catch {
    return false
  }
}

export function restoreMsalRedirectHandoff({
  clientId,
  expectedRedirectUri = null,
  now = Date.now(),
  sessionStorage = storageOrNull('sessionStorage'),
  persistentStorage = storageOrNull('localStorage'),
  locationLike = typeof window !== 'undefined' ? window.location : null,
} = {}) {
  if (!clientId || !sessionStorage || !persistentStorage) return false

  const handoff = readValidHandoff({
    now,
    persistentStorage,
    locationLike,
    expectedRedirectUri,
    expectedClientId: clientId,
    consume: true,
  })
  if (!handoff || handoff.clientId !== clientId) return false

  try {
    const allowed = new Set(allowedTemporaryKeys(clientId))
    Object.entries(handoff.entries).forEach(([key, value]) => {
      if (allowed.has(key) && typeof value === 'string' && !sessionStorage.getItem(key)) {
        sessionStorage.setItem(key, value)
      }
    })
    return true
  } catch {
    return false
  }
}
