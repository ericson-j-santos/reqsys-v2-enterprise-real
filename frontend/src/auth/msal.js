import { PublicClientApplication } from '@azure/msal-browser'
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

export async function getMsalInstance() {
  if (_instance) return _instance

  const serverConfig = await fetchAuthConfig()
  if (!serverConfig.azure_enabled) return null

  _instance = new PublicClientApplication({
    auth: {
      clientId: serverConfig.azure_client_id,
      authority: `https://login.microsoftonline.com/${serverConfig.azure_tenant_id}`,
      redirectUri: window.location.origin,        // URI principal (sem /blank.html)
      postLogoutRedirectUri: window.location.origin + '/login',
    },
    cache: {
      cacheLocation: 'localStorage',
      storeAuthStateInCookie: true,
    },
    system: { allowNativeBroker: false },
  })

  await _instance.initialize()
  return _instance
}

export const SCOPES = ['openid', 'profile', 'email']

// Redireciona a página inteira para o Microsoft — sem popup, sem race condition
export async function loginMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) throw new Error('Azure AD não configurado no servidor')
  await msal.loginRedirect({ scopes: SCOPES, prompt: 'select_account' })
}

// Chamado em main.js ANTES do Vue montar — processa o retorno do redirect
export async function handleRedirectResult() {
  const msal = await getMsalInstance()
  if (!msal) return null
  try {
    const response = await msal.handleRedirectPromise()
    return response?.idToken ?? null
  } catch (err) {
    const ignorable = [
      'no_token_request_cache_error',
      'state_not_found',
      'no_cached_authority_error',
      'interaction_in_progress',
    ]
    if (ignorable.includes(err.errorCode)) return null
    console.warn('[MSAL]', err.errorCode, err.message)
    return null
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
