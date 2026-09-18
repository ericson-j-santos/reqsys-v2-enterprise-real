import { api } from './api'

export async function carregarPainelPentaho(limite = 20) {
  const { data } = await api.get('/integracoes/pentaho/dashboard', { params: { limite } })
  return data
}

export async function reprocessarLotePentaho(loteId) {
  const { data } = await api.post(`/integracoes/pentaho/lotes/${encodeURIComponent(loteId)}/reprocessar`)
  return data
}
