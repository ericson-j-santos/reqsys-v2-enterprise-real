import { api } from './api'

const BASE_PATH = '/v1/auth'

export async function carregarStatusSessoes() {
  const response = await api.get(`${BASE_PATH}/sessions/admin/status`)
  return response.data?.data || {}
}

export async function atualizarMinhaSessao() {
  const response = await api.post(`${BASE_PATH}/session/refresh`)
  return response.data?.data || {}
}

export async function invalidarTodasSessoes(confirmacao, motivo) {
  const response = await api.post(`${BASE_PATH}/sessions/admin/invalidate-all`, {
    confirmacao,
    motivo,
  })
  return response.data?.data || {}
}

export function mensagemErroSessao(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  if (status === 401) return 'A sessão atual foi invalidada ou expirou. Autentique-se novamente.'
  if (status === 403) return 'Ação restrita a administradores autorizados.'
  if (status === 409) return typeof detail === 'string' ? detail : 'Confirmação de segurança inválida.'
  if (status === 422) return 'Informe um motivo válido para a ação de segurança.'
  return typeof detail === 'string' ? detail : error?.message || 'Falha ao gerenciar a sessão.'
}
