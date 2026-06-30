import { describe, it, expect, beforeEach } from 'vitest'
import apiDefault, { api, definirCorrelationIdSessao, obterCorrelationIdSessao } from '../api'

// Executa manualmente o interceptor de request configurado em services/api.js,
// validando os headers que ele injeta.
function runRequestInterceptor(config) {
  const handler = api.interceptors.request.handlers.find(Boolean)
  return handler.fulfilled(config)
}

describe('services/api — interceptor de request', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
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
})
