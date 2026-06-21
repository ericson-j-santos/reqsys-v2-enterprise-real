import { describe, it, expect, beforeEach } from 'vitest'
import { api } from '../api'

// Executa manualmente o interceptor de request configurado em services/api.js,
// validando os headers que ele injeta.
function runRequestInterceptor(config) {
  const handler = api.interceptors.request.handlers.find(Boolean)
  return handler.fulfilled(config)
}

describe('services/api — interceptor de request', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('usa /api como baseURL padrão', () => {
    expect(api.defaults.baseURL).toBe('/api')
  })

  it('injeta um X-Correlation-Id em toda requisição', () => {
    const config = runRequestInterceptor({ headers: {} })
    expect(config.headers['X-Correlation-Id']).toBeTruthy()
  })

  it('gera correlation ids distintos a cada requisição', () => {
    const a = runRequestInterceptor({ headers: {} })
    const b = runRequestInterceptor({ headers: {} })
    expect(a.headers['X-Correlation-Id']).not.toBe(b.headers['X-Correlation-Id'])
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
