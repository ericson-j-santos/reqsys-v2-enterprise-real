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

  const config = await fetchAuthConfig()
  if (!config.azure_enabled) return null

  const msalConfig = {
    auth: {
      clientId: config.azure_client_id,
      authority: `https://login.microsoftonline.com/${config.azure_tenant_id}`,
      redirectUri: window.location.origin,
    },
    cache: {
      cacheLocation: 'localStorage',
      storeAuthStateInCookie: true, // compatibilidade Safari/iOS
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
    const response = await msal.loginPopup({ scopes: SCOPES, prompt: 'select_account' })
    return response.idToken
  } catch (err) {
    // Popup bloqueado pelo browser
    if (
      err.errorCode === 'popup_window_error' ||
      err.errorCode === 'empty_window_error' ||
      err.errorCode === 'user_cancelled'
    ) {
      throw err
    }
    throw new Error(`Falha no login Microsoft: ${err.message ?? err.errorCode ?? err}`)
  }
}

// Chamado no onMounted para processar qualquer redirect pendente silenciosamente
export async function handleRedirectResult() {
  const msal = await getMsalInstance()
  if (!msal) return null
  try {
    const response = await msal.handleRedirectPromise()
    return response?.idToken ?? null
  } catch (err) {
    // no_token_request_cache_error = não havia redirect pendente, ignorar
    if (
      err.errorCode === 'no_token_request_cache_error' ||
      err.errorCode === 'state_not_found' ||
      err.errorCode === 'no_cached_authority_error'
    ) {
      return null
    }
    throw err
  }
}

export async function logoutMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) return
  const account = msal.getAllAccounts()[0]
  if (account) {
    try {
      await msal.logoutPopup({ account })
    } catch {
      // silencioso — sessão local já foi limpa pelo auth store
    }
  }
}
