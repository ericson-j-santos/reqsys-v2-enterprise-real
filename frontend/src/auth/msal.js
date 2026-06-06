import { PublicClientApplication } from '@azure/msal-browser'
import { api } from '../services/api'

let _instance = null
let _config = null

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

  _config = await fetchAuthConfig()
  if (!_config.azure_enabled) return null

  const msalConfig = {
    auth: {
      clientId: _config.azure_client_id,
      authority: `https://login.microsoftonline.com/${_config.azure_tenant_id}`,
      redirectUri: window.location.origin,
    },
    cache: {
      cacheLocation: 'sessionStorage',
      storeAuthStateInCookie: false,
    },
  }

  _instance = new PublicClientApplication(msalConfig)
  await _instance.initialize()
  return _instance
}

export const SCOPES = ['openid', 'profile', 'email', 'User.Read']

export async function loginMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) throw new Error('Azure AD não configurado')

  let response
  try {
    response = await msal.loginPopup({ scopes: SCOPES })
  } catch (popupErr) {
    // Popup bloqueado → fallback para redirect
    if (popupErr.errorCode === 'popup_window_error' || popupErr.errorCode === 'empty_window_error') {
      await msal.loginRedirect({ scopes: SCOPES })
      return null
    }
    throw popupErr
  }

  return response.idToken
}

export async function handleRedirectResult() {
  const msal = await getMsalInstance()
  if (!msal) return null
  const response = await msal.handleRedirectPromise()
  return response?.idToken ?? null
}

export async function logoutMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) return
  const account = msal.getAllAccounts()[0]
  if (account) {
    await msal.logoutPopup({ account }).catch(() =>
      msal.logoutRedirect({ account })
    )
  }
}
