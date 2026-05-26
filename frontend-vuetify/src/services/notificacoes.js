import api from './api'

export const notificacoesService = {
  async obterDashboard() {
    const { data } = await api.get('/v1/notificacoes/dashboard')
    return data.data
  },

  async listarFila(status = null, limit = 50) {
    const params = { limit }
    if (status) params.status = status
    const { data } = await api.get('/v1/notificacoes/fila', { params })
    return data.data
  },

  async listarDlq(limit = 100) {
    const { data } = await api.get('/v1/notificacoes/dlq', { params: { limit } })
    return data.data
  },

  async reprocessarDlq(idDlq) {
    const { data } = await api.post(`/v1/notificacoes/dlq/reprocessar/${idDlq}`)
    return data.data
  },

  async listarLogs(limit = 100) {
    const { data } = await api.get('/v1/notificacoes/logs', { params: { limit } })
    return data.data
  },

  async enfileirar(payload) {
    const { data } = await api.post('/v1/notificacoes/enfileirar', payload)
    return data.data
  },
}
