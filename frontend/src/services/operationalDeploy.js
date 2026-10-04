import { api } from './api'

const BASE_PATH = '/v1/actions-runtime/operational-deploy'

export async function carregarCatalogoDeploy() {
  const response = await api.get(`${BASE_PATH}/catalog`)
  return response.data?.data || {}
}

export async function validarDeploy(aplicacao) {
  const response = await api.post(`${BASE_PATH}/validate`, { aplicacao, confirmar: false })
  return response.data?.data || {}
}

export async function executarDeploy(aplicacao) {
  const response = await api.post(`${BASE_PATH}/execute`, { aplicacao, confirmar: true })
  return response.data?.data || {}
}

export function mensagemErroDeploy(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  if (status === 401) return 'Sua sessão expirou. Autentique-se novamente.'
  if (status === 403) return 'Ação restrita a administradores autorizados.'
  if (status === 409) return typeof detail === 'string' ? detail : 'Confirmação obrigatória não atendida.'
  if (status === 422) return typeof detail === 'string' ? detail : 'Aplicação ou operação inválida.'
  if (status === 502) return typeof detail === 'string' ? detail : 'Falha ao acionar o executor governado.'
  return typeof detail === 'string' ? detail : error?.message || 'Falha inesperada na operação.'
}
