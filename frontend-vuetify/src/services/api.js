import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' }
})

function gerarCorrelationId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

api.interceptors.request.use(config => {
  const token = localStorage.getItem('reqsys_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['X-Correlation-Id'] = gerarCorrelationId()
  return config
})

export default api
