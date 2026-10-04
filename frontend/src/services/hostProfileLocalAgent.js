import { api } from './api'

const VALID_PROFILES = new Set(['NORMAL', 'ESTUDO'])

function validarPayload(payload) {
  if (!payload || payload.success !== true || !payload.data) {
    const detail = payload?.detail || payload?.errors?.[0]?.message || 'serviço do modo ESTUDO retornou resposta inválida.'
    throw new Error(detail)
  }
  const data = payload.data
  if (!VALID_PROFILES.has(data.profile)) throw new Error('serviço retornou perfil inválido.')
  if (String(data.host || '').toLowerCase() !== 'noteri') {
    throw new Error(`Estado pertence ao host ${data.host || 'desconhecido'}, não ao Noteri.`)
  }
  return data
}

function normalizarErro(error) {
  const detail = error?.response?.data?.detail
    || error?.response?.data?.errors?.[0]?.message
    || error?.message
    || 'Modo ESTUDO indisponível.'
  return new Error(String(detail))
}

export async function obterPerfilNoteri() {
  try {
    const response = await api.get('/v1/noteri/profile', {
      headers: { 'Cache-Control': 'no-store' },
    })
    return validarPayload(response.data)
  } catch (error) {
    throw normalizarErro(error)
  }
}

export async function alterarPerfilNoteri(profile, correlationId) {
  const normalized = String(profile || '').trim().toUpperCase()
  if (!VALID_PROFILES.has(normalized)) throw new Error('Perfil deve ser NORMAL ou ESTUDO.')
  const correlation = String(correlationId || '').trim()
  if (correlation.length < 8 || correlation.length > 128) {
    throw new Error('Correlation ID deve ter entre 8 e 128 caracteres.')
  }

  let changed
  try {
    const response = await api.post('/v1/noteri/profile', {
      profile: normalized,
      correlation_id: correlation,
    })
    changed = validarPayload(response.data)
  } catch (error) {
    throw normalizarErro(error)
  }

  const readback = await obterPerfilNoteri()
  if (
    readback.profile !== normalized
    || readback.accepts_new_development !== (normalized === 'NORMAL')
  ) {
    throw new Error('Leitura independente divergiu do perfil solicitado.')
  }

  return {
    ...readback,
    changed: Boolean(changed.changed),
    request_correlation_id: changed.request_correlation_id || correlation,
  }
}

export const __hostProfileLocalAgentInternals = {
  VALID_PROFILES,
}
