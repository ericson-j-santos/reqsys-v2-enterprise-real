import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Mocks declarados antes dos vi.mock() ─────────────────────────────────────
const mockHandleRedirectPromise = vi.fn()
const mockLoginRedirect = vi.fn()
const mockGetAllAccounts = vi.fn(() => [])
const mockGetConfiguration = vi.fn(() => ({ auth: { clientId: 'test-client-id' } }))
const mockInitialize = vi.fn()

// PublicClientApplication precisa ser uma classe real (constructor) para suportar `new`
vi.mock('@azure/msal-browser', () => {
  class PublicClientApplication {
    constructor() {
      this.initialize = mockInitialize
      this.handleRedirectPromise = mockHandleRedirectPromise
      this.loginRedirect = mockLoginRedirect
      this.getAllAccounts = mockGetAllAccounts
      this.getConfiguration = mockGetConfiguration
    }
  }
  return { PublicClientApplication }
})

vi.mock('../../services/api', () => ({
  api: {
    get: vi.fn().mockResolvedValue({
      data: {
        data: {
          azure_enabled: true,
          azure_tenant_id: '6d09c88c-test',
          azure_client_id: 'test-client-id',
        },
      },
    }),
    post: vi.fn(),
  },
}))

// Resetar módulos entre testes para limpar o singleton _instance
beforeEach(() => {
  vi.resetModules()
  mockHandleRedirectPromise.mockReset().mockResolvedValue(null)
  mockLoginRedirect.mockReset().mockResolvedValue(undefined)
  mockInitialize.mockReset().mockResolvedValue(undefined)
  localStorage.clear()
  sessionStorage.clear()
})

// ─── getMsalInstance ──────────────────────────────────────────────────────────

describe('getMsalInstance', () => {
  it('retorna null quando azure_enabled é false', async () => {
    const { api } = await import('../../services/api')
    api.get.mockResolvedValueOnce({ data: { data: { azure_enabled: false } } })
    const { getMsalInstance } = await import('../msal')
    expect(await getMsalInstance()).toBeNull()
  })

  it('retorna instância MSAL quando azure_enabled é true', async () => {
    const { getMsalInstance } = await import('../msal')
    const instance = await getMsalInstance()
    expect(instance).not.toBeNull()
  })

  it('chama initialize() exatamente uma vez (singleton)', async () => {
    const { getMsalInstance } = await import('../msal')
    await getMsalInstance()
    await getMsalInstance()
    expect(mockInitialize).toHaveBeenCalledTimes(1)
  })
})

// ─── handleRedirectResult ────────────────────────────────────────────────────

describe('handleRedirectResult', () => {
  it('retorna null quando não há redirect pendente', async () => {
    mockHandleRedirectPromise.mockResolvedValue(null)
    const { handleRedirectResult } = await import('../msal')
    expect(await handleRedirectResult()).toBeNull()
  })

  it('retorna idToken quando há redirect bem-sucedido', async () => {
    mockHandleRedirectPromise.mockResolvedValue({ idToken: 'eyJ.payload.sig' })
    const { handleRedirectResult } = await import('../msal')
    expect(await handleRedirectResult()).toBe('eyJ.payload.sig')
  })

  it.each([
    'no_token_request_cache_error',
    'state_not_found',
    'no_cached_authority_error',
    'interaction_in_progress',
  ])('suprime %s silenciosamente (retorna null)', async (errorCode) => {
    const err = Object.assign(new Error(errorCode), { errorCode })
    mockHandleRedirectPromise.mockRejectedValue(err)
    const { handleRedirectResult } = await import('../msal')
    await expect(handleRedirectResult()).resolves.toBeNull()
  })

  it('propaga erros desconhecidos (não suprime)', async () => {
    const err = Object.assign(new Error('unexpected failure'), { errorCode: 'unknown_error' })
    mockHandleRedirectPromise.mockRejectedValue(err)
    const { handleRedirectResult } = await import('../msal')
    await expect(handleRedirectResult()).rejects.toThrow('unexpected failure')
  })
})

// ─── loginMicrosoft ───────────────────────────────────────────────────────────

describe('loginMicrosoft', () => {
  it('chama loginRedirect com openid/profile/email e select_account', async () => {
    const { loginMicrosoft, SCOPES } = await import('../msal')
    await loginMicrosoft()
    expect(mockLoginRedirect).toHaveBeenCalledWith(
      expect.objectContaining({ scopes: SCOPES, prompt: 'select_account' })
    )
  })

  it('limpa chaves de interação do localStorage e retenta em interaction_in_progress', async () => {
    const interactionErr = Object.assign(new Error(), { errorCode: 'interaction_in_progress' })
    mockLoginRedirect
      .mockRejectedValueOnce(interactionErr)
      .mockResolvedValueOnce(undefined)

    localStorage.setItem('msal.test-client-id.interaction.status', 'interaction_in_progress')
    localStorage.setItem('msal.test-client-id.request.correlationId', 'abc')

    const { loginMicrosoft } = await import('../msal')
    await loginMicrosoft()

    expect(mockLoginRedirect).toHaveBeenCalledTimes(2)
    expect(localStorage.getItem('msal.test-client-id.interaction.status')).toBeNull()
    expect(localStorage.getItem('msal.test-client-id.request.correlationId')).toBeNull()
  })

  it('lança erro quando Azure AD não está configurado', async () => {
    const { api } = await import('../../services/api')
    api.get.mockResolvedValueOnce({ data: { data: { azure_enabled: false } } })
    const { loginMicrosoft } = await import('../msal')
    await expect(loginMicrosoft()).rejects.toThrow('Azure AD não configurado')
  })
})
