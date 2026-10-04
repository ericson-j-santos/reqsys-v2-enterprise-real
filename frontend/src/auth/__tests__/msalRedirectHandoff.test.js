import { beforeEach, describe, expect, it } from 'vitest'
import {
  MSAL_REDIRECT_HANDOFF_KEY,
  MSAL_REDIRECT_HANDOFF_TTL_MS,
  clearMicrosoftRedirectResponse,
  getMicrosoftRedirectResponse,
  isMicrosoftRedirectResponse,
  peekMsalRedirectHandoff,
  persistMsalRedirectHandoff,
  restoreMsalRedirectHandoff,
} from '../msalRedirectHandoff'

const clientId = 'client-id-mobile'
const tenantId = 'tenant-id-mobile'
const redirectUri = 'https://example.test/app/auth/callback.html'
const now = 1_800_000_000_000
const oauthState = 'opaque-msal-state'

function encodedRequestParams(state = oauthState) {
  return btoa(JSON.stringify({ state, correlationId: 'corr-test' }))
}

function seedTransaction() {
  sessionStorage.setItem('msal.interaction.status', JSON.stringify({
    clientId,
    type: 'signin',
  }))
  sessionStorage.setItem(`msal.${clientId}.request.params`, encodedRequestParams())
  sessionStorage.setItem(`msal.${clientId}.code.verifier`, 'pkce-verifier')
  sessionStorage.setItem(`msal.${clientId}.request.origin`, 'https://example.test/app/login')
  sessionStorage.setItem(`msal.${clientId}.idtoken`, 'must-not-be-copied')
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/')
})

describe('MSAL redirect handoff', () => {
  it('detecta respostas Microsoft em query e fragment', () => {
    expect(isMicrosoftRedirectResponse({ search: '?code=a&state=b', hash: '' })).toBe(true)
    expect(isMicrosoftRedirectResponse({ search: '', hash: '#code=a&state=b' })).toBe(true)
    expect(isMicrosoftRedirectResponse({ search: '', hash: '#error=access_denied&state=b' })).toBe(true)
    expect(isMicrosoftRedirectResponse({ search: '?code=a', hash: '' })).toBe(false)
    expect(isMicrosoftRedirectResponse({ search: '?filtro=aberto', hash: '#secao' })).toBe(false)
    expect(getMicrosoftRedirectResponse({ search: '?code=a&state=b', hash: '' })).toBe('?code=a&state=b')
    expect(getMicrosoftRedirectResponse({ search: '', hash: '#code=a&state=b' })).toBe('#code=a&state=b')
  })

  it('remove a resposta em query sem apagar o fragmento da aplicacao', () => {
    window.history.replaceState({}, '', '/app/?code=a&state=b#secao')

    expect(clearMicrosoftRedirectResponse()).toBe(true)
    expect(window.location.pathname).toBe('/app/')
    expect(window.location.search).toBe('')
    expect(window.location.hash).toBe('#secao')
  })

  it('remove a resposta em fragmento sem apagar a query da aplicacao', () => {
    window.history.replaceState({}, '', '/app/?filtro=aberto#code=a&state=b')

    expect(clearMicrosoftRedirectResponse()).toBe(true)
    expect(window.location.search).toBe('?filtro=aberto')
    expect(window.location.hash).toBe('')
  })

  it('persiste somente o estado temporario permitido, com TTL', () => {
    seedTransaction()

    expect(persistMsalRedirectHandoff({ clientId, tenantId, redirectUri, now })).toBe(true)
    const handoff = JSON.parse(localStorage.getItem(MSAL_REDIRECT_HANDOFF_KEY))

    expect(handoff.expiresAt).toBe(now + MSAL_REDIRECT_HANDOFF_TTL_MS)
    expect(handoff.state).toBe(oauthState)
    expect(handoff.entries[`msal.${clientId}.code.verifier`]).toBe('pkce-verifier')
    expect(handoff.entries[`msal.${clientId}.idtoken`]).toBeUndefined()
    expect(JSON.stringify(handoff)).not.toContain('must-not-be-copied')
  })

  it('restaura o estado no novo contexto e consome o handoff uma unica vez', () => {
    seedTransaction()
    persistMsalRedirectHandoff({ clientId, tenantId, redirectUri, now })
    sessionStorage.clear()
    const locationLike = { search: '', hash: `#code=auth-code&state=${oauthState}` }

    expect(peekMsalRedirectHandoff({ now, locationLike, expectedRedirectUri: redirectUri })?.tenantId).toBe(tenantId)
    expect(restoreMsalRedirectHandoff({ clientId, now, locationLike, expectedRedirectUri: redirectUri })).toBe(true)
    expect(sessionStorage.getItem(`msal.${clientId}.code.verifier`)).toBe('pkce-verifier')
    expect(localStorage.getItem(MSAL_REDIRECT_HANDOFF_KEY)).toBeNull()
    expect(restoreMsalRedirectHandoff({ clientId, now, locationLike })).toBe(false)
  })

  it('rejeita handoff expirado sem restaurar o verifier', () => {
    seedTransaction()
    persistMsalRedirectHandoff({ clientId, tenantId, redirectUri, now })
    sessionStorage.clear()

    expect(restoreMsalRedirectHandoff({
      clientId,
      now: now + MSAL_REDIRECT_HANDOFF_TTL_MS + 1,
      locationLike: { search: `?code=auth-code&state=${oauthState}`, hash: '' },
    })).toBe(false)
    expect(sessionStorage.getItem(`msal.${clientId}.code.verifier`)).toBeNull()
    expect(localStorage.getItem(MSAL_REDIRECT_HANDOFF_KEY)).toBeNull()
  })

  it('remove handoff expirado no proximo boot mesmo fora do callback', () => {
    seedTransaction()
    persistMsalRedirectHandoff({ clientId, tenantId, redirectUri, now })

    expect(peekMsalRedirectHandoff({
      now: now + MSAL_REDIRECT_HANDOFF_TTL_MS + 1,
      locationLike: { search: '', hash: '' },
    })).toBeNull()
    expect(localStorage.getItem(MSAL_REDIRECT_HANDOFF_KEY)).toBeNull()
  })

  it('nao restaura transacao de outro clientId', () => {
    seedTransaction()
    persistMsalRedirectHandoff({ clientId, tenantId, redirectUri, now })
    sessionStorage.clear()

    expect(restoreMsalRedirectHandoff({
      clientId: 'outro-client',
      now,
      locationLike: { search: `?code=auth-code&state=${oauthState}`, hash: '' },
    })).toBe(false)
    expect(sessionStorage.length).toBe(0)
    expect(localStorage.getItem(MSAL_REDIRECT_HANDOFF_KEY)).not.toBeNull()
  })

  it('rejeita handoff destinado a outro redirect URI', () => {
    seedTransaction()
    persistMsalRedirectHandoff({ clientId, tenantId, redirectUri, now })
    sessionStorage.clear()

    expect(restoreMsalRedirectHandoff({
      clientId,
      now,
      expectedRedirectUri: 'https://example.test/outro/callback.html',
      locationLike: { search: '', hash: `#code=auth-code&state=${oauthState}` },
    })).toBe(false)
    expect(sessionStorage.length).toBe(0)
  })

  it('nao consome o handoff quando o callback pertence a outra tentativa', () => {
    seedTransaction()
    persistMsalRedirectHandoff({ clientId, tenantId, redirectUri, now })
    sessionStorage.clear()

    expect(restoreMsalRedirectHandoff({
      clientId,
      now,
      locationLike: { search: '', hash: '#code=auth-code&state=outro-state' },
    })).toBe(false)
    expect(localStorage.getItem(MSAL_REDIRECT_HANDOFF_KEY)).not.toBeNull()
    expect(sessionStorage.length).toBe(0)
  })
})
