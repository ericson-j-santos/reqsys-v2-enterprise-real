const RETIRED_FLY_HOSTS = new Set(['fly.dev', 'fly.io'])

export function requireProviderNeutralHttpsUrl(value, label = 'Runtime') {
  let parsed
  try {
    parsed = new URL(String(value || '').trim())
  } catch {
    throw new Error(`${label} deve informar uma URL HTTPS explícita`)
  }

  if (parsed.protocol !== 'https:') {
    throw new Error(`${label} deve usar HTTPS`)
  }

  const hostname = parsed.hostname.toLowerCase().replace(/\.$/, '')
  if ([...RETIRED_FLY_HOSTS].some((retired) => hostname === retired || hostname.endsWith(`.${retired}`))) {
    throw new Error(`${label} aponta para Fly.io, retirado definitivamente`)
  }

  return parsed.toString().replace(/\/$/, '')
}
