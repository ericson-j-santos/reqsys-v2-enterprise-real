import { api } from './api'

const BASE_PATH = '/v1/ocr'

export function detalheErroOcr(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  if (status === 401) return 'Sua sessão expirou. Autentique-se novamente.'
  if (status === 403) return 'A revisão OCR é restrita a administradores autorizados.'
  if (status === 404) return 'Resultado OCR não encontrado.'
  if (status === 409) return typeof detail === 'string' ? detail : 'O item já foi decidido ou mudou de estado.'
  if (status === 503) return typeof detail === 'string' ? detail : 'OCR não está pronto neste ambiente.'
  if (status === 422) return typeof detail === 'string' ? detail : 'O documento não pôde ser processado.'
  return typeof detail === 'string' ? detail : error?.message || 'Falha inesperada no OCR.'
}

export async function obterReadinessOcr() {
  const response = await api.get(`${BASE_PATH}/readiness`)
  return response.data?.data || {}
}

export async function listarRevisoesOcr(status = 'PENDENTE', limite = 100) {
  const response = await api.get(`${BASE_PATH}/review`, { params: { status, limite } })
  return response.data?.data?.items || []
}

export async function detalharRevisaoOcr(jobId) {
  const response = await api.get(`${BASE_PATH}/review/${encodeURIComponent(jobId)}`)
  return response.data?.data
}

export async function decidirRevisaoOcr(jobId, decisao, observacao = '') {
  const response = await api.post(`${BASE_PATH}/review/${encodeURIComponent(jobId)}/decision`, {
    decisao,
    observacao,
  })
  return response.data?.data
}

export async function processarDocumentoOcr(payload) {
  const response = await api.post(`${BASE_PATH}/jobs`, payload)
  return response.data?.data
}
