import axios from 'axios'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

const generateCorrelationId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `cid-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('reqsys_token')
  config.headers['X-Correlation-Id'] = generateCorrelationId()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
