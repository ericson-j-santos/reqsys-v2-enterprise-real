// Fluxo OAuth2/PKCE puro — sem @azure/msal-browser
// Web Crypto API (disponível em todos os browsers modernos)

const KEY_VERIFIER = 'reqsys_pkce_verifier'
const KEY_STATE    = 'reqsys_oauth_state'

function getAuthCallbackUri() {
  return window.location.origin
}

function b64url(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

function generateVerifier() {
  const buf = new Uint8Array(32)
  crypto.getRandomValues(buf)
  return b64url(buf)
}

async function generateChallenge(verifier) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return b64url(buf)
}

// Redireciona para o Microsoft com parâmetros PKCE
export async function initiateAzureLogin(tenantId, clientId) {
  const verifier  = generateVerifier()
  const state     = crypto.randomUUID()
  const challenge = await generateChallenge(verifier)

  sessionStorage.setItem(KEY_VERIFIER, verifier)
  sessionStorage.setItem(KEY_STATE, state)

  const params = new URLSearchParams({
    client_id:             clientId,
    response_type:         'code',
    redirect_uri:          getAuthCallbackUri(),
    scope:                 'openid profile email',
    code_challenge:        challenge,
    code_challenge_method: 'S256',
    state,
    prompt:                'select_account',
    response_mode:         'query',
  })

  window.location.href =
    `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize?${params}`
}

// Lê o código de autorização da URL atual (retorna null se não houver redirect)
export function extractOAuthCallback() {
  const params = new URLSearchParams(window.location.search)
  const code   = params.get('code')
  const state  = params.get('state')
  const error  = params.get('error')

  if (error) {
    sessionStorage.removeItem(KEY_VERIFIER)
    sessionStorage.removeItem(KEY_STATE)
    return { error: params.get('error_description') || error }
  }

  if (!code) return null

  const savedState = sessionStorage.getItem(KEY_STATE)
  const verifier   = sessionStorage.getItem(KEY_VERIFIER)

  if (!verifier || state !== savedState) {
    sessionStorage.removeItem(KEY_VERIFIER)
    sessionStorage.removeItem(KEY_STATE)
    return { error: 'State inválido (possível CSRF). Tente novamente.' }
  }

  sessionStorage.removeItem(KEY_VERIFIER)
  sessionStorage.removeItem(KEY_STATE)

  return { code, verifier, redirectUri: getAuthCallbackUri() }
}
