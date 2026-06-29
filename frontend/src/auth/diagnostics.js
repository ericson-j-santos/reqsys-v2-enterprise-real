import { getAuthCallbackUri } from './msal'

const LOCAL_ORIGIN_PREFIXES = ['http://localhost:', 'http://127.0.0.1:']

export function redirectUriAtual() {
  return getAuthCallbackUri()
}

function isLocalOrigin(origin) {
  return LOCAL_ORIGIN_PREFIXES.some((prefix) => origin.startsWith(prefix))
}

export function redirectUriDivergente(expectedRedirectUri, canonicalRedirectUris = []) {
  const esperado = (expectedRedirectUri || '').replace(/\/$/, '')
  const atual = redirectUriAtual()
  if (!esperado) return false
  if (atual === esperado) return false
  if (canonicalRedirectUris.includes(atual)) return false
  if (isLocalOrigin(atual) && canonicalRedirectUris.some((uri) => isLocalOrigin(uri))) return false
  return true
}

export function traduzirErroAzure(mensagem, expectedRedirectUri = '') {
  if (!mensagem) return mensagem

  const texto = String(mensagem)
  const redirect = (expectedRedirectUri || redirectUriAtual()).replace(/\/$/, '')

  if (texto.includes('AADSTS50011') || texto.includes('redirect_uri') || texto.includes('callback.html')) {
    return [
      'O redirect URI enviado nao esta registrado no Microsoft Entra ID.',
      `Registre "${redirect}" como Redirect URI da plataforma SPA.`,
      'Nao use /auth/callback.html. Depois, limpe o cache ou teste em janela anonima.',
    ].join(' ')
  }

  return texto
}

export function resumoValidacaoAuth(config) {
  const esperado = (config?.expected_redirect_uri || '').replace(/\/$/, '')
  const atual = redirectUriAtual()
  const canonicalUris = config?.auth_diagnostics?.canonical_redirect_uris || []
  const divergente = redirectUriDivergente(esperado, canonicalUris)
  const divergenteEsperado = Boolean(esperado && atual !== esperado)
  const alinhadoComEsperado = !esperado || atual === esperado
  const alinhadoComCanonico = canonicalUris.length === 0 || canonicalUris.includes(atual)
    || (isLocalOrigin(atual) && canonicalUris.some((uri) => isLocalOrigin(uri)))

  return {
    atual,
    esperado,
    divergente,
    divergenteEsperado,
    alinhado: alinhadoComEsperado && alinhadoComCanonico,
    azurePronto: Boolean(config?.azure_enabled && config?.auth_status === 'ready'),
    ambienteLabel: config?.auth_diagnostics?.environment_label || config?.environment || '—',
    canonicalUris,
    hint: config?.auth_diagnostics?.entra_registration_hint || '',
    authStatus: config?.auth_status || 'unknown',
    azureEnabled: Boolean(config?.azure_enabled),
  }
}
