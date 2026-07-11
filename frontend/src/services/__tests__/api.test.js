import { describe, it, expect, beforeEach, vi } from 'vitest'
import apiDefault, { api, definirCorrelationIdSessao, obterCorrelationIdSessao } from '../api'

// Executa manualmente o interceptor de request configurado em services/api.js,
// validando os headers que ele injeta.
function runRequestInterceptor(config) {
  const handler = api.interceptors.request.handlers.find(Boolean)
  return handler.fulfilled(config)
}

function runResponseRejected(error) {
  const handler = api.interceptors.response.handlers.find(Boolean)
  return handler.rejected(error)
}

describe('services/api — interceptor de request', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('usa /api como baseURL padrão', () => {
    expect(api.defaults.baseURL).toBe('/api')
  })

  it('mantém export default compatível com imports legados', () => {
    expect(apiDefault).toBe(api)
  })

  it('injeta um X-Correlation-Id em toda requisição', () => {
    const config = runRequestInterceptor({ headers: {} })
    expect(config.headers['X-Correlation-Id']).toBeTruthy()
  })

  it('reutiliza correlation id da sessão entre requisições', () => {
    const a = runRequestInterceptor({ headers: {} })
    const b = runRequestInterceptor({ headers: {} })
    expect(a.headers['X-Correlation-Id']).toBe(b.headers['X-Correlation-Id'])
  })

  it('permite sobrescrever correlation id da sessão', () => {
    definirCorrelationIdSessao('corr-sessao-fixa')
    const config = runRequestInterceptor({ headers: {} })
    expect(config.headers['X-Correlation-Id']).toBe('corr-sessao-fixa')
    expect(obterCorrelationIdSessao()).toBe('corr-sessao-fixa')
  })

  it('anexa Authorization quando há token no localStorage', () => {
    localStorage.setItem('reqsys_token', 'jwt-abc')
    const config = runRequestInterceptor({ headers: {} })
    expect(config.headers.Authorization).toBe('Bearer jwt-abc')
  })

  it('não anexa Authorization quando não há token', () => {
    const config = runRequestInterceptor({ headers: {} })
    expect(config.headers.Authorization).toBeUndefined()
  })

  it('limpa sessão e redireciona para login preservando rota em 401', async () => {
    localStorage.setItem('reqsys_token', 'jwt-expirado')
    localStorage.setItem('reqsys_usuario', JSON.stringify({ email: 'user@example.com' }))
    window.history.pushState({}, '', '/requisitos?aba=lista')
    const assign = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { pathname: '/requisitos', search: '?aba=lista', assign },
    })

    await expect(runResponseRejected({ response: { status: 401 } })).rejects.toMatchObject({ response: { status: 401 } })

    expect(localStorage.getItem('reqsys_token')).toBeNull()
    expect(localStorage.getItem('reqsys_usuario')).toBeNull()
    expect(assign).toHaveBeenCalledWith('/login?redirect=%2Frequisitos%3Faba%3Dlista')
  })
})
