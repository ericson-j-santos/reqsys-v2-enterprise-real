import api from './api'

const BASE_URL = '/v1/teams-gateway/notificacoes'

export const notificacoesService = {
  async obterDashboard() {
    const { data } = await api.get(`${BASE_URL}/dashboard`)
    return data.data
  },

  async listarFila(status = null, limit = 50) {
    const params = { limit }
    if (status) params.status = status
    const { data } = await api.get(`${BASE_URL}/fila`, { params })
    return data.data
  },

  async listarDlq(limit = 100) {
    const { data } = await api.get(`${BASE_URL}/dlq`, { params: { limit } })
    return data.data
  },

  async reprocessarDlq(idDlq) {
    const { data } = await api.post(`${BASE_URL}/dlq/reprocessar/${idDlq}`)
    return data.data
  },

  async listarLogs(limit = 100) {
    const { data } = await api.get(`${BASE_URL}/logs`, { params: { limit } })
    return data.data
  },

  async enfileirar(payload) {
    const { data } = await api.post(`${BASE_URL}/enfileirar`, payload)
    return data.data
  },
}
