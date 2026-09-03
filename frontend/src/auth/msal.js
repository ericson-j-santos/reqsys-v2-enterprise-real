import { PublicClientApplication } from '@azure/msal-browser'
import { api } from '../services/api'
import {
  getAuthCallbackUri,
  getLoginRedirectStartPageUri,
  getPostLogoutRedirectUri,
} from './env'

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
      redirectUri: getAuthCallbackUri(),
      postLogoutRedirectUri: getPostLogoutRedirectUri(),
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

// Escopos delegados do Graph para mensageria Teams (ChatMessage.Send/Chat.ReadWrite
// ja consentidos tenant-wide no app registration — sem prompt de consentimento extra).
export const TEAMS_GRAPH_SCOPES = ['ChatMessage.Send', 'Chat.ReadWrite']

// Escopo delegado do Power Platform. Conexoes Planner/Excel Online autorizadas
// no Power Automate sao pessoais do usuario — so um token delegado (nao um
// credential app-only) consegue enxerga-las.
export const POWER_PLATFORM_SCOPES = ['https://api.powerplatform.com/.default']

// Escopo delegado do Power Automate (api.flow.microsoft.com). Essa API nao
// aceita credencial app-only (client_credentials) para criar/atualizar
// fluxos — so token delegado do proprio usuario.
export const FLOW_MANAGEMENT_SCOPES = ['https://service.flow.microsoft.com/.default']

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
    redirectStartPage: getLoginRedirectStartPageUri(),
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

// Renova a sessao do ReqSys silenciosamente quando ha uma conta Microsoft em
// cache mas nenhum id_token pendente de redirect (ex.: reqsys_token expirou
// com a aba ja aberta, ou o usuario abriu uma URL direta em uma aba nova).
// Usa a sessao SSO do navegador via iframe oculto — sem popup, sem redirect
// visivel. Retorna null em qualquer falha (silenciosa ou nao): no pior caso
// a tela de login normal aparece, exatamente como antes desta funcao existir.
export async function acquireIdTokenSilent() {
  const msal = await getMsalInstance()
  if (!msal) return null

  const account = msal.getAllAccounts()[0]
  if (!account) return null

  try {
    const response = await msal.acquireTokenSilent({ scopes: SCOPES, account })
    return response?.idToken ?? null
  } catch {
    return null
  }
}

// Adquire um access_token delegado do Graph para mensageria Teams (chat 1:1/grupo).
// Tenta silencioso primeiro (funciona sem interacao, ja que o escopo ja foi
// consentido); só abre popup se o silent falhar por exigir interacao.
export async function acquireTeamsGraphToken() {
  const msal = await getMsalInstance()
  if (!msal) throw new Error('Azure AD nao configurado no servidor')

  const account = msal.getAllAccounts()[0]
  if (!account) throw new Error('Nenhuma conta Microsoft logada — faça acesso novamente')

  const request = { scopes: TEAMS_GRAPH_SCOPES, account }
  try {
    const response = await msal.acquireTokenSilent(request)
    return response.accessToken
  } catch (err) {
    if (err.name === 'InteractionRequiredAuthError' || String(err.errorCode || '').includes('interaction_required')) {
      const response = await msal.acquireTokenPopup(request)
      return response.accessToken
    }
    throw err
  }
}

// Adquire um access_token delegado do Power Platform (conexoes pessoais do
// usuario no Power Automate). Mesmo padrao de acquireTeamsGraphToken: tenta
// silencioso, cai para popup só se exigir interação. Retorna null quando não
// há conta Microsoft logada (ex.: acesso via login demo) em vez de lançar,
// já que essa tela deve continuar utilizável sem esse recurso.
export async function acquirePowerPlatformToken() {
  const msal = await getMsalInstance()
  if (!msal) return null

  const account = msal.getAllAccounts()[0]
  if (!account) return null

  const request = { scopes: POWER_PLATFORM_SCOPES, account }
  try {
    const response = await msal.acquireTokenSilent(request)
    return response.accessToken
  } catch (err) {
    if (err.name === 'InteractionRequiredAuthError' || String(err.errorCode || '').includes('interaction_required')) {
      const response = await msal.acquireTokenPopup(request)
      return response.accessToken
    }
    throw err
  }
}

// Adquire um access_token delegado do Power Automate (criar/atualizar o
// fluxo real). Mesmo padrao de acquirePowerPlatformToken: tenta silencioso,
// cai para popup só se exigir interação. Retorna null quando não há conta
// Microsoft logada, para o backend responder com uma mensagem clara em vez
// de uma exceção crua.
export async function acquireFlowManagementToken() {
  const msal = await getMsalInstance()
  if (!msal) return null

  const account = msal.getAllAccounts()[0]
  if (!account) return null

  const request = { scopes: FLOW_MANAGEMENT_SCOPES, account }
  try {
    const response = await msal.acquireTokenSilent(request)
    return response.accessToken
  } catch (err) {
    if (err.name === 'InteractionRequiredAuthError' || String(err.errorCode || '').includes('interaction_required')) {
      const response = await msal.acquireTokenPopup(request)
      return response.accessToken
    }
    throw err
  }
}

// Conta MSAL atualmente logada (ou null). Usado para identificar o proprio
// usuario ao montar rotulos de chat (excluir "eu mesmo" da lista de membros).
export async function getContaAtual() {
  const msal = await getMsalInstance()
  if (!msal) return null
  return msal.getAllAccounts()[0] || null
}

export async function logoutMicrosoft() {
  const msal = await getMsalInstance()
  if (!msal) return
  const account = msal.getAllAccounts()[0]
  if (account) {
    try { await msal.logoutRedirect({ account }) } catch { /* silencioso */ }
  }
}
