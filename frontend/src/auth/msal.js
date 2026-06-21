import { PublicClientApplication, NavigationClient } from '@azure/msal-browser'
import { api } from '../services/api'

let _instance = null
let _redirectUri = null

async function fetchAuthConfig() {
  try {
    const { data } = await api.get('/v1/auth/config')
    return data.data
  } catch {
    return { azure_enabled: false }
  }
}

class NoReloadNavigationClient extends NavigationClient {
  navigateInternal(_url, _options) {
    return Promise.resolve(false)
  }
}

export async function getMsalInstance() {
  if (_instance) return _instance

  const serverConfig = await fetchAuthConfig()
  if (!serverConfig.azure_enabled) return null

  _redirectUri = `${window.location.origin}/auth/callback.html`

  _instance = new PublicClientApplication({
    auth: {
      clientId: serverConfig.azure_client_id,
      authority: `https://login.microsoftonline.com/${serverConfig.azure_tenant_id}`,
      redirectUri: _redirectUri,
      postLogoutRedirectUri: window.location.origin + '/login',
      navigateToLoginRequestUrl: false,
    },
    cache: {
      cacheLocation: 'sessionStorage',
      storeAuthStateInCookie: true,
    },
    system: {
      allowNativeBroker: false,
      asyncPopups: true,
      windowHashTimeout: 120000,
      iframeHashTimeout: 120000,
      loadFrameTimeout: 120000,
      navigationClient: new NoReloadNavigationClient(),
    },
  })

  await _instance.initialize()
  return _instance
}

export const SCOPES = ['openid', 'profile', 'email']

function clearInteractionState(clientId) {
  const prefixes = [`msal.${clientId}`, 'msal.']
  const markers = [
    'interaction',
    'request',
    'nonce',
    'state',
    'authority',
    'login',
    'token',
  ]

  ;[localStorage, sessionStorage].forEach((store) => {
    Object.keys(store)
      .filter((key) => prefixes.some((prefix) => key.startsWith(prefix)))
      .filter((key) => markers.some((marker) => key.toLowerCase().includes(marker)))
      .forEach((key) => store.removeItem(key))
  })
}

async function executarLoginPopup(msal) {
  return msal.loginPopup({
    scopes: SCOPES,
    prompt: 'select_account',
    redirectUri: _redirectUri || `${window.location.origin}/auth/callback.html`,
  })
}

// Popup mode com callback estático: evita carregar a SPA no retorno da Microsoft.
// Retorna o idToken diretamente para o caller processar.
export async function loginMicrosoftPopup() {
  const msal = await getMsalInstance()
  if (!msal) throw new Error('Azure AD não configurado no servidor')

  const clientId = msal.getConfiguration().auth.clientId
  clearInteractionState(clientId)

  try {
    const result = await executarLoginPopup(msal)
    return result?.idToken ?? null
  } catch (err) {
    if (err.errorCode === 'interaction_in_progress') {
      clearInteractionState(clientId)
      const result = await executarLoginPopup(msal)
      return result?.idToken ?? null
    }
    if (err.errorCode === 'timed_out') {
      throw new Error('Login Microsoft expirou antes de retornar para o ReqSys. Tente novamente após a publicação desta correção.')
    }
    throw err
  }
}

// Mantido como fallback para sessões de redirect que possam estar em trânsito
export async function handleRedirectResult() {
  const msal = await getMsalInstance()
  if (!msal) return null
  try {
    const response = await msal.handleRedirectPromise({ navigateToLoginRequestUrl: false })
    return response?.idToken ?? null
  } catch (err) {
    const ignorable = [
      'no_token_request_cache_error',
      'state_not_found',
      'no_cached_authority_error',
      'interaction_in_progress',
      'timed_out',
    ]
    if (ignorable.includes(err.errorCode)) return null
    throw err
  }
}

export async function logoutMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) return
  const account = msal.getAllAccounts()[0]
  if (account) {
    try { await msal.logoutRedirect({ account }) } catch { /* silencioso */ }
  }
}
