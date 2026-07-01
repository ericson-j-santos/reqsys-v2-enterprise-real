import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockHandleRedirectPromise = vi.fn()
const mockLoginRedirect = vi.fn()
const mockGetAllAccounts = vi.fn(() => [])
const mockGetConfiguration = vi.fn(() => ({ auth: { clientId: 'test-client-id' } }))
const mockInitialize = vi.fn()
const mockConstructor = vi.fn()

vi.mock('@azure/msal-browser', () => {
  class PublicClientApplication {
    constructor(config) {
      mockConstructor(config)
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

beforeEach(() => {
  vi.resetModules()
  mockConstructor.mockReset()
  mockHandleRedirectPromise.mockReset().mockResolvedValue(null)
  mockLoginRedirect.mockReset().mockResolvedValue(undefined)
  mockInitialize.mockReset().mockResolvedValue(undefined)
  localStorage.clear()
  sessionStorage.clear()
})

describe('getAuthCallbackUri', () => {
  it('retorna o callback publico absoluto registrado no Microsoft Entra ID', async () => {
    const { getAuthCallbackUri } = await import('../msal')
    expect(getAuthCallbackUri()).toBe(`${window.location.origin}/auth/callback.html`)
  })
})

describe('getMsalInstance', () => {
  it('retorna null quando azure_enabled e false', async () => {
    const { api } = await import('../../services/api')
    api.get.mockResolvedValueOnce({ data: { data: { azure_enabled: false } } })
    const { getMsalInstance } = await import('../msal')
    expect(await getMsalInstance()).toBeNull()
  })

  it('retorna instancia MSAL quando azure_enabled e true', async () => {
    const { getMsalInstance } = await import('../msal')
    const instance = await getMsalInstance()
    expect(instance).not.toBeNull()
  })

  it('chama initialize() exatamente uma vez', async () => {
    const { getMsalInstance } = await import('../msal')
    await getMsalInstance()
    await getMsalInstance()
    expect(mockInitialize).toHaveBeenCalledTimes(1)
  })

  it('configura MSAL para redirect no callback publico registrado', async () => {
    const { getMsalInstance } = await import('../msal')
    await getMsalInstance()
    expect(mockConstructor).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: expect.objectContaining({
          redirectUri: `${window.location.origin}/auth/callback.html`,
          navigateToLoginRequestUrl: false,
        }),
        cache: expect.objectContaining({
          cacheLocation: 'sessionStorage',
        }),
      })
    )
  })
})

describe('loginMicrosoftRedirect', () => {
  it('chama loginRedirect com escopos, select_account, callback e redirectStartPage', async () => {
    const { loginMicrosoftRedirect, SCOPES } = await import('../msal')
    await loginMicrosoftRedirect()
    expect(mockLoginRedirect).toHaveBeenCalledWith(
      expect.objectContaining({
        scopes: SCOPES,
        prompt: 'select_account',
        redirectUri: `${window.location.origin}/auth/callback.html`,
        redirectStartPage: `${window.location.origin}/login`,
      })
    )
  })

  it('limpa estado de interacao e retenta em interaction_in_progress', async () => {
    const interactionErr = Object.assign(new Error(), { errorCode: 'interaction_in_progress' })
    mockLoginRedirect
      .mockReset()
      .mockRejectedValueOnce(interactionErr)
      .mockResolvedValueOnce(undefined)

    localStorage.setItem('msal.test-client-id.interaction.status', 'interaction_in_progress')
    localStorage.setItem('msal.test-client-id.request.correlationId', 'abc')

    const { loginMicrosoftRedirect } = await import('../msal')
    await loginMicrosoftRedirect()

    expect(mockLoginRedirect).toHaveBeenCalledTimes(2)
    expect(localStorage.getItem('msal.test-client-id.interaction.status')).toBeNull()
    expect(localStorage.getItem('msal.test-client-id.request.correlationId')).toBeNull()
  })

  it('lanca erro quando Azure AD nao esta configurado', async () => {
    const { api } = await import('../../services/api')
    api.get.mockResolvedValueOnce({ data: { data: { azure_enabled: false } } })
    const { loginMicrosoftRedirect } = await import('../msal')
    await expect(loginMicrosoftRedirect()).rejects.toThrow('Azure AD nao configurado')
  })
})

describe('handleRedirectResult', () => {
  it('retorna null quando nao ha redirect pendente', async () => {
    mockHandleRedirectPromise.mockResolvedValue(null)
    const { handleRedirectResult } = await import('../msal')
    expect(await handleRedirectResult()).toBeNull()
  })

  it('retorna idToken quando ha redirect bem-sucedido', async () => {
    mockHandleRedirectPromise.mockResolvedValue({ idToken: 'eyJ.payload.sig' })
    const { handleRedirectResult } = await import('../msal')
    expect(await handleRedirectResult()).toBe('eyJ.payload.sig')
  })

  it.each([
    'no_token_request_cache_error',
    'state_not_found',
    'no_cached_authority_error',
    'interaction_in_progress',
    'timed_out',
  ])('suprime %s silenciosamente', async (errorCode) => {
    const err = Object.assign(new Error(errorCode), { errorCode })
    mockHandleRedirectPromise.mockRejectedValue(err)
    const { handleRedirectResult } = await import('../msal')
    await expect(handleRedirectResult()).resolves.toBeNull()
  })

  it('propaga erros desconhecidos', async () => {
    const err = Object.assign(new Error('unexpected failure'), { errorCode: 'unknown_error' })
    mockHandleRedirectPromise.mockRejectedValue(err)
    const { handleRedirectResult } = await import('../msal')
    await expect(handleRedirectResult()).rejects.toThrow('unexpected failure')
  })
})
