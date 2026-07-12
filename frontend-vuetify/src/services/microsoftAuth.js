import {
  BrowserCacheLocation,
  PublicClientApplication,
} from '@azure/msal-browser'
import api from './api'

let msal
let clientKey = ''

function unwrap(response) {
  return response?.data?.data ?? response?.data ?? response
}

async function getConfig() {
  const response = await api.get('/v1/auth/config')
  return unwrap(response)
}

async function getMsal(config) {
  const key = `${config.azure_tenant_id}:${config.azure_client_id}`
  if (msal && clientKey === key) return msal

  msal = new PublicClientApplication({
    auth: {
      clientId: config.azure_client_id,
      authority: `https://login.microsoftonline.com/${config.azure_tenant_id}`,
      redirectUri: window.location.origin,
    },
    cache: {
      cacheLocation: BrowserCacheLocation.LocalStorage,
      storeAuthStateInCookie: false,
    },
  })
  clientKey = key
  await msal.initialize()
  return msal
}

export async function loginMicrosoft() {
  const config = await getConfig()
  if (!config.azure_enabled || !config.azure_tenant_id || !config.azure_client_id) {
    throw new Error(config.operator_action || 'Login Microsoft indisponivel neste ambiente.')
  }

  const app = await getMsal(config)
  const result = await app.loginPopup({
    scopes: ['openid', 'profile', 'email'],
    prompt: 'select_account',
  })

  if (!result.idToken) {
    throw new Error('Microsoft Entra nao retornou id_token.')
  }

  const response = await api.post('/v1/auth/azure', { id_token: result.idToken })
  return unwrap(response)
}
