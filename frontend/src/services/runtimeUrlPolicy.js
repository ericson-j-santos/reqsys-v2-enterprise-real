const RETIRED_FLY_HOSTS = new Set(['fly.dev', 'fly.io'])

export function isRetiredFlyUrl(value, baseOrigin = globalThis.location?.origin) {
  const raw = String(value || '').trim()
  if (!raw || raw.startsWith('/')) return false

  try {
    const parsed = new URL(raw, baseOrigin)
    const host = parsed.hostname.toLowerCase().replace(/\.$/, '')
    return [...RETIRED_FLY_HOSTS].some(
      (retired) => host === retired || host.endsWith(`.${retired}`),
    )
  } catch {
    return false
  }
}

export function requireProviderNeutralRuntimeUrl(value, label = 'execução endereço') {
  if (isRetiredFlyUrl(value)) {
    throw new Error(`${label} aponta para Fly.io, retirado definitivamente`)
  }
  return value
}
