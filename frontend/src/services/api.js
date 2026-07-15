import axios from 'axios'
import {
  clearJourneyFeedback,
  showJourneyError,
  showJourneyLoading,
  showJourneySuccess,
} from './userJourneyFeedback'
import { emitDashboardEmptyResult, isEmptyDashboardResponse } from './dashboardEmptyStateIntegration'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

const CORRELATION_STORAGE_KEY = 'reqsys_correlation_id'
const JOURNEY_PATHS = ['/govbi', '/runtime', '/dashboard', '/monitoramento', '/analytics']
export const GOVBI_EMPTY_EVENT = 'reqsys:govbi-empty-result'

const generateCorrelationId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `cid-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const obterCorrelationIdSessao = () => {
  if (typeof sessionStorage === 'undefined') return generateCorrelationId()
  const atual = sessionStorage.getItem(CORRELATION_STORAGE_KEY)
  if (atual) return atual
  const novo = generateCorrelationId()
  sessionStorage.setItem(CORRELATION_STORAGE_KEY, novo)
  return novo
}

export const definirCorrelationIdSessao = (correlationId) => {
  if (typeof sessionStorage !== 'undefined' && correlationId) sessionStorage.setItem(CORRELATION_STORAGE_KEY, correlationId)
}

export const isJourneyRequest = (config = {}) => {
  const url = String(config.url || '')
  return JOURNEY_PATHS.some((path) => url.includes(path))
}

export const journeyLoadingMessage = (config = {}) => {
  const url = String(config.url || '')
  if (url.includes('/govbi')) return 'GovBI IA está processando sua solicitação…'
  if (url.includes('/runtime')) return 'Atualizando informações do runtime…'
  if (url.includes('/monitoramento')) return 'Atualizando monitoramento operacional…'
  if (url.includes('/analytics')) return 'Atualizando indicadores analíticos…'
  return 'Atualizando dashboard operacional…'
}

export const extractGovBIRows = (payload) => [
  payload?.resultado?.linhas,
  payload?.data?.resultado?.linhas,
  payload?.linhas,
  payload?.data?.linhas,
].find(Array.isArray)

export const isEmptyGovBIResponse = (response = {}) => {
  const url = String(response?.config?.url || '')
  const method = String(response?.config?.method || 'get').toLowerCase()
  const rows = extractGovBIRows(response?.data)
  return url.includes('/govbi/perguntas') && method === 'post' && Array.isArray(rows) && rows.length === 0
}

function emitGovBIEmptyResult(response) {
  if (typeof window === 'undefined') return
  const retryConfig = response?.config
  window.dispatchEvent(new CustomEvent(GOVBI_EMPTY_EVENT, {
    detail: {
      reason: 'A consulta foi concluída, mas nenhum registro corresponde aos filtros informados.',
      retry: retryConfig ? () => api.request(retryConfig) : null,
    },
  }))
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('reqsys_token')
  config.headers['X-Correlation-Id'] = obterCorrelationIdSessao()
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (isJourneyRequest(config)) showJourneyLoading(journeyLoadingMessage(config))
  return config
})

export default api

function limparSessaoExpirada() {
  localStorage.removeItem('reqsys_token')
  localStorage.removeItem('reqsys_usuario')
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    const destino = `${window.location.pathname}${window.location.search}`
    window.location.assign(`/login?redirect=${encodeURIComponent(destino)}`)
  }
}

api.interceptors.response.use(
  (response) => {
    if (isJourneyRequest(response?.config)) {
      const method = String(response?.config?.method || 'get').toLowerCase()
      if (isEmptyGovBIResponse(response)) {
        clearJourneyFeedback()
        emitGovBIEmptyResult(response)
      } else if (isEmptyDashboardResponse(response)) {
        clearJourneyFeedback()
        emitDashboardEmptyResult(response)
      } else if (['post', 'put', 'patch', 'delete'].includes(method)) {
        showJourneySuccess('Operação concluída. As informações exibidas foram atualizadas.')
      } else {
        clearJourneyFeedback()
      }
    }
    return response
  },
  (error) => {
    if (error?.response?.status === 401) {
      clearJourneyFeedback()
      limparSessaoExpirada()
    } else if (isJourneyRequest(error?.config)) {
      const retryConfig = error.config
      showJourneyError('Não foi possível atualizar esta jornada. Verifique a conexão e tente novamente.', () => api.request(retryConfig))
    }
    return Promise.reject(error)
  },
)
