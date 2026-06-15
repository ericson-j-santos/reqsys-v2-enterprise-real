import { PublicClientApplication, NavigationClient } from '@azure/msal-browser'
import { api } from '../services/api'

let _instance = null

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

  _instance = new PublicClientApplication({
    auth: {
      clientId: serverConfig.azure_client_id,
      authority: `https://login.microsoftonline.com/${serverConfig.azure_tenant_id}`,
      redirectUri: window.location.origin,
      postLogoutRedirectUri: window.location.origin + '/login',
    },
    cache: {
      cacheLocation: 'localStorage',
      storeAuthStateInCookie: true,
    },
    system: {
      allowNativeBroker: false,
      navigationClient: new NoReloadNavigationClient(),
    },
  })

  await _instance.initialize()
  return _instance
}

export const SCOPES = ['openid', 'profile', 'email']

function clearInteractionState(clientId) {
  const prefix = `msal.${clientId}`
  ;[localStorage, sessionStorage].forEach(store => {
    Object.keys(store)
      .filter(k => k.startsWith(prefix) && (k.includes('interaction') || k.includes('request')))
      .forEach(k => store.removeItem(k))
  })
}

// Popup mode: sem page reload, sem handleRedirectPromise, sem race conditions.
// Retorna o idToken diretamente para o caller processar.
export async function loginMicrosoftPopup() {
  const msal = await getMsalInstance()
  if (!msal) throw new Error('Azure AD não configurado no servidor')
  try {
    const result = await msal.loginPopup({ scopes: SCOPES, prompt: 'select_account' })
    return result?.idToken ?? null
  } catch (err) {
    if (err.errorCode === 'interaction_in_progress') {
      clearInteractionState(msal.getConfiguration().auth.clientId)
      const result = await msal.loginPopup({ scopes: SCOPES, prompt: 'select_account' })
      return result?.idToken ?? null
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
