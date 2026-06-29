import { describe, it, expect, vi } from 'vitest'

vi.mock('../msal', () => ({
  getAuthCallbackUri: vi.fn(() => 'https://reqsys-app-stg.fly.dev'),
}))

describe('auth diagnostics', () => {
  it('detecta divergencia entre redirect atual e esperado', async () => {
    const { redirectUriDivergente } = await import('../diagnostics')
    expect(redirectUriDivergente('https://reqsys-web-stg.fly.dev')).toBe(true)
    expect(redirectUriDivergente('https://reqsys-app-stg.fly.dev')).toBe(false)
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

  it('resume validacao auth com status pronto', async () => {
    const { resumoValidacaoAuth } = await import('../diagnostics')
    const resumo = resumoValidacaoAuth({
      azure_enabled: true,
      auth_status: 'ready',
      expected_redirect_uri: 'https://reqsys-app-stg.fly.dev',
    })
    expect(resumo.atual).toBe('https://reqsys-app-stg.fly.dev')
    expect(resumo.divergente).toBe(false)
    expect(resumo.azurePronto).toBe(true)
  })
})
