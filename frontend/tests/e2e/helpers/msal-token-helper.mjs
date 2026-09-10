import { PublicClientApplication } from '@azure/msal-browser'

window.__reqsysAcquireDelegatedToken = async function acquireDelegatedToken(scopes) {
  const reqsysToken = window.localStorage.getItem('reqsys_token') || ''
  const response = await window.fetch('/api/v1/auth/config', {
    headers: reqsysToken ? { Authorization: `Bearer ${reqsysToken}` } : {},
  })
  if (!response.ok) {
    throw new Error(`auth_config_http_${response.status}`)
  }
  const payload = await response.json()
  const config = payload?.data || payload?.data?.data || payload
  if (!config?.azure_enabled || !config?.azure_client_id || !config?.azure_tenant_id) {
    throw new Error('azure_auth_config_incompleta')
  }

  const msal = new PublicClientApplication({
    auth: {
      clientId: config.azure_client_id,
      authority: `https://login.microsoftonline.com/${config.azure_tenant_id}`,
      redirectUri: `${window.location.origin}/auth/callback`,
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

  await msal.initialize()
  const account = msal.getAllAccounts()[0]
  if (!account) throw new Error('msal_account_ausente')
  const token = await msal.acquireTokenSilent({ scopes, account })
  if (!token?.accessToken) throw new Error('access_token_ausente')
  return token.accessToken
}
