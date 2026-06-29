import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGetAuthCallbackUri = vi.fn(() => 'https://reqsys-app-stg.fly.dev')

vi.mock('../msal', () => ({
  getAuthCallbackUri: (...args) => mockGetAuthCallbackUri(...args),
}))

const baseConfig = {
  azure_enabled: true,
  auth_status: 'ready',
  environment: 'homologacao',
  expected_redirect_uri: 'https://reqsys-app-stg.fly.dev',
  auth_diagnostics: {
    environment_label: 'Homologacao',
    canonical_redirect_uris: [
      'https://reqsys-app-stg.fly.dev',
      'https://tierin.duckdns.org',
      'https://reqsys-web-stg.fly.dev',
    ],
    entra_registration_hint: 'Registre cada origem como SPA no Microsoft Entra ID, sem /auth/callback.html.',
  },
}

describe('auth diagnostics', () => {
  beforeEach(() => {
    mockGetAuthCallbackUri.mockReset()
    mockGetAuthCallbackUri.mockReturnValue('https://reqsys-app-stg.fly.dev')
  })

  it('detecta divergencia quando origem nao e canonica nem esperada', async () => {
    const { redirectUriDivergente } = await import('../diagnostics')
    expect(redirectUriDivergente('https://reqsys-app-stg.fly.dev', baseConfig.auth_diagnostics.canonical_redirect_uris)).toBe(false)
    expect(redirectUriDivergente('https://reqsys-web-stg.fly.dev', baseConfig.auth_diagnostics.canonical_redirect_uris)).toBe(false)
    mockGetAuthCallbackUri.mockReturnValue('https://outro-dominio.example')
    expect(redirectUriDivergente('https://reqsys-app-stg.fly.dev', baseConfig.auth_diagnostics.canonical_redirect_uris)).toBe(true)
  })

  it('traduz AADSTS50011 para orientacao operacional', async () => {
    const { traduzirErroAzure } = await import('../diagnostics')
    const msg = traduzirErroAzure(
      "AADSTS50011: redirect URI 'https://reqsys-app-stg.fly.dev/auth/callback.html' does not match",
      'https://reqsys-app-stg.fly.dev',
    )
    expect(msg).toContain('https://reqsys-app-stg.fly.dev')
    expect(msg).toContain('SPA')
    expect(msg).toContain('Nao use /auth/callback.html')
  })

  it('resume validacao auth alinhada em homologacao', async () => {
    const { resumoValidacaoAuth } = await import('../diagnostics')
    const resumo = resumoValidacaoAuth(baseConfig)
    expect(resumo.atual).toBe('https://reqsys-app-stg.fly.dev')
    expect(resumo.divergente).toBe(false)
    expect(resumo.alinhado).toBe(true)
    expect(resumo.ambienteLabel).toBe('Homologacao')
    expect(resumo.canonicalUris).toHaveLength(3)
  })

  it('lista origens canonicas de producao', async () => {
    const { resumoValidacaoAuth } = await import('../diagnostics')
    const resumo = resumoValidacaoAuth({
      ...baseConfig,
      environment: 'producao',
      expected_redirect_uri: 'https://reqsys-app.fly.dev',
      auth_diagnostics: {
        environment_label: 'Producao',
        canonical_redirect_uris: [
          'https://reqsys-app.fly.dev',
          'https://tieriprod.duckdns.org',
        ],
        entra_registration_hint: 'hint',
      },
    })
    expect(resumo.canonicalUris).toContain('https://tieriprod.duckdns.org')
  })
})
