import { getAuthCallbackUri } from './msal'

export function redirectUriAtual() {
  return getAuthCallbackUri()
}

export function redirectUriDivergente(expectedRedirectUri) {
  const esperado = (expectedRedirectUri || '').replace(/\/$/, '')
  const atual = redirectUriAtual()
  if (!esperado) return false
  return atual !== esperado
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
  const divergente = redirectUriDivergente(esperado)

  return {
    atual,
    esperado,
    divergente,
    azurePronto: Boolean(config?.azure_enabled && config?.auth_status === 'ready'),
  }
}
