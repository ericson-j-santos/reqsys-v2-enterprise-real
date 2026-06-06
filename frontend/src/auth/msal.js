import { PublicClientApplication } from '@azure/msal-browser'
import { api } from '../services/api'

let _instance = null
let _authConfig = null

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

  _authConfig = {
    clientId: serverConfig.azure_client_id,
    authority: `https://login.microsoftonline.com/${serverConfig.azure_tenant_id}`,
  }

  // Salva config no localStorage para que blank.html possa inicializar MSAL
  // sem precisar chamar o backend (janelas do mesmo origin compartilham localStorage)
  localStorage.setItem('reqsys_msal_config', JSON.stringify(_authConfig))

  const msalConfig = {
    auth: {
      ..._authConfig,
      redirectUri: `${window.location.origin}/blank.html`,
      postLogoutRedirectUri: `${window.location.origin}/login`,
    },
    cache: {
      cacheLocation: 'localStorage',
      storeAuthStateInCookie: true,
    },
    system: {
      allowNativeBroker: false,
    },
  }

  _instance = new PublicClientApplication(msalConfig)
  await _instance.initialize()
  return _instance
}

export const SCOPES = ['openid', 'profile', 'email']

export async function loginMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) throw new Error('Azure AD não configurado no servidor')

  try {
    const response = await msal.loginPopup({
      scopes: SCOPES,
      prompt: 'select_account',
    })
    return response.idToken
  } catch (err) {
    const code = err.errorCode ?? ''
    if (code === 'user_cancelled') throw err
    if (code === 'popup_window_error' || code === 'empty_window_error') {
      // Popup bloqueado — usa redirect como fallback
      await msal.loginRedirect({ scopes: SCOPES, prompt: 'select_account' })
      return null
    }
    throw new Error(`Falha no login Microsoft (${code || (err.message ?? String(err))})`)
  }
}

// Processa retorno de redirect (fallback quando popup está bloqueado)
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
    throw err
  }
}

export async function logoutMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) return
  localStorage.removeItem('reqsys_msal_config')
  const account = msal.getAllAccounts()[0]
  if (account) {
    try { await msal.logoutPopup({ account }) } catch {
      try { await msal.logoutRedirect({ account }) } catch { /* silencioso */ }
    }
  }
}
