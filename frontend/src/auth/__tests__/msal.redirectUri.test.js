import { describe, it, expect, vi, beforeEach } from 'vitest'

// Captura a configuração passada ao construir o PublicClientApplication,
// para validar qual redirectUri o MSAL recebe.
let configCapturada = null

vi.mock('@azure/msal-browser', () => {
  class PublicClientApplication {
    constructor(cfg) {
      configCapturada = cfg
      this.initialize = vi.fn().mockResolvedValue(undefined)
      this.handleRedirectPromise = vi.fn().mockResolvedValue(null)
      this.loginPopup = vi.fn()
      this.getAllAccounts = vi.fn(() => [])
      this.getConfiguration = vi.fn(() => ({ auth: { clientId: 'c' } }))
    }
  }
  class NavigationClient {}
  return { PublicClientApplication, NavigationClient }
})

const mockGet = vi.fn()
vi.mock('../../services/api', () => ({ api: { get: mockGet, post: vi.fn() } }))

const baseConfig = {
  azure_enabled: true,
  azure_tenant_id: 'tenant-123',
  azure_client_id: 'client-456',
}

beforeEach(() => {
  vi.resetModules()
  configCapturada = null
  mockGet.mockReset()
})

describe('getMsalInstance — redirectUri configurável', () => {
  it('usa azure_redirect_uri do backend quando fornecido', async () => {
    mockGet.mockResolvedValue({
      data: { data: { ...baseConfig, azure_redirect_uri: 'https://reqsys-app.fly.dev' } },
    })
    const { getMsalInstance } = await import('../msal')
    await getMsalInstance()
    expect(configCapturada.auth.redirectUri).toBe('https://reqsys-app.fly.dev')
  })

  it('cai para window.location.origin quando azure_redirect_uri é nulo', async () => {
    mockGet.mockResolvedValue({
      data: { data: { ...baseConfig, azure_redirect_uri: null } },
    })
    const { getMsalInstance } = await import('../msal')
    await getMsalInstance()
    expect(configCapturada.auth.redirectUri).toBe(window.location.origin)
  })

  it('cai para window.location.origin quando o campo está ausente', async () => {
    mockGet.mockResolvedValue({ data: { data: { ...baseConfig } } })
    const { getMsalInstance } = await import('../msal')
    await getMsalInstance()
    expect(configCapturada.auth.redirectUri).toBe(window.location.origin)
  })
})
