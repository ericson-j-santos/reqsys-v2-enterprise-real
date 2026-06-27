import axios from 'axios'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

const CORRELATION_STORAGE_KEY = 'reqsys_correlation_id'

const generateCorrelationId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `cid-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const obterCorrelationIdSessao = () => {
  if (typeof sessionStorage === 'undefined') {
    return generateCorrelationId()
  }
  const atual = sessionStorage.getItem(CORRELATION_STORAGE_KEY)
  if (atual) return atual
  const novo = generateCorrelationId()
  sessionStorage.setItem(CORRELATION_STORAGE_KEY, novo)
  return novo
}

export const definirCorrelationIdSessao = (correlationId) => {
  if (typeof sessionStorage !== 'undefined' && correlationId) {
    sessionStorage.setItem(CORRELATION_STORAGE_KEY, correlationId)
  }
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('reqsys_token')
  config.headers['X-Correlation-Id'] = obterCorrelationIdSessao()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
