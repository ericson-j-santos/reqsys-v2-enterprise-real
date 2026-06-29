import { PublicClientApplication } from '@azure/msal-browser'
import { api } from '../services/api'

let _instance = null

export function getAuthCallbackUri() {
  return window.location.origin
}

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
      redirectUri: getAuthCallbackUri(),
      postLogoutRedirectUri: window.location.origin + '/login',
      navigateToLoginRequestUrl: false,
    },
    cache: {
      cacheLocation: 'sessionStorage',
      storeAuthStateInCookie: true,
    },
    system: {
      allowNativeBroker: false,
      windowHashTimeout: 120000,
      iframeHashTimeout: 120000,
      loadFrameTimeout: 120000,
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

async function executarLoginRedirect(msal) {
  return msal.loginRedirect({
    scopes: SCOPES,
    prompt: 'select_account',
    redirectUri: getAuthCallbackUri(),
    redirectStartPage: window.location.origin + '/login',
  })
}

// Redirect mode: evita popup travado e deixa a SPA finalizar o retorno no boot.
export async function loginMicrosoftRedirect() {
  const msal = await getMsalInstance()
  if (!msal) throw new Error('Azure AD nao configurado no servidor')

  const clientId = msal.getConfiguration().auth.clientId
  clearInteractionState(clientId)

  try {
    await executarLoginRedirect(msal)
  } catch (err) {
    if (err.errorCode === 'interaction_in_progress') {
      clearInteractionState(clientId)
      await executarLoginRedirect(msal)
      return
    }
    throw err
  }
}

// Mantido como fallback para sessoes de redirect que possam estar em transito.
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
