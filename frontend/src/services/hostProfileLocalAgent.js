const DEFAULT_AGENT_URL = import.meta.env.VITE_NOTERI_HOST_PROFILE_AGENT_URL || 'http://127.0.0.1:8765'
const VALID_PROFILES = new Set(['NORMAL', 'ESTUDO'])
const DEFAULT_TIMEOUT_MS = 2500

function normalizarBaseUrl(value) {
  return String(value || DEFAULT_AGENT_URL).replace(/\/$/, '')
}

function validarPayload(payload) {
  if (!payload || payload.ok !== true) throw new Error(payload?.error || 'Agente local retornou resposta inválida.')
  if (!VALID_PROFILES.has(payload.profile)) throw new Error('Agente local retornou perfil inválido.')
  if (String(payload.host || '').toLowerCase() !== 'noteri') {
    throw new Error(`Agente local pertence ao host ${payload.host || 'desconhecido'}, não ao Noteri.`)
  }
  return payload
}

async function localFetch(path, options = {}, { baseUrl = DEFAULT_AGENT_URL, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${normalizarBaseUrl(baseUrl)}${path}`, {
      ...options,
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      signal: controller.signal,
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      const message = payload?.error || 'Agente local indisponível.'
      throw new Error(message)
    }
    return payload
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('Agente local do Noteri não respondeu no tempo esperado.')
    }
    throw error
  } finally {
    clearTimeout(timer)
  }
}

export async function obterPerfilNoteri(options = {}) {
  return validarPayload(await localFetch('/v1/profile', {}, options))
}

export async function alterarPerfilNoteri(profile, correlationId, options = {}) {
  const normalized = String(profile || '').trim().toUpperCase()
  if (!VALID_PROFILES.has(normalized)) throw new Error('Perfil deve ser NORMAL ou ESTUDO.')
  const correlation = String(correlationId || '').trim()
  if (correlation.length < 8 || correlation.length > 128) {
    throw new Error('Correlation ID deve ter entre 8 e 128 caracteres.')
  }

  const changed = validarPayload(await localFetch('/v1/profile', {
    method: 'POST',
    body: JSON.stringify({
      host: 'Noteri',
      profile: normalized,
      correlation_id: correlation,
    }),
  }, options))

  const readback = await obterPerfilNoteri(options)
  if (readback.profile !== normalized || readback.accepts_new_development !== (normalized === 'NORMAL')) {
    throw new Error('Leitura independente divergiu do perfil solicitado.')
  }
  return {
    ...readback,
    changed: Boolean(changed.changed),
    request_correlation_id: changed.request_correlation_id || correlation,
  }
}

export const __hostProfileLocalAgentInternals = {
  DEFAULT_AGENT_URL,
  VALID_PROFILES,
  normalizarBaseUrl,
}
