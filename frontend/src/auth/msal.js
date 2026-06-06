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

// Remove estado de interação travado que causa interaction_in_progress
function clearInteractionState(clientId) {
  const prefix = `msal.${clientId}`
  ;[localStorage, sessionStorage].forEach(store => {
    Object.keys(store)
      .filter(k => k.startsWith(prefix) && (k.includes('interaction') || k.includes('request')))
      .forEach(k => store.removeItem(k))
  })
}

// Redireciona a página inteira para o Microsoft — sem popup, sem race condition
export async function loginMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) throw new Error('Azure AD não configurado no servidor')
  try {
    await msal.loginRedirect({ scopes: SCOPES, prompt: 'select_account' })
  } catch (err) {
    if (err.errorCode === 'interaction_in_progress') {
      // Limpar estado travado e tentar uma vez mais
      clearInteractionState(msal.getConfiguration().auth.clientId)
      await msal.loginRedirect({ scopes: SCOPES, prompt: 'select_account' })
      return
    }
    throw err
  }
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
