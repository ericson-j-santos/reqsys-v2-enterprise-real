import { api } from './api'

export const POLITICAS_TEAMS_CANONICAS = [
  {
    id: 'hitl-approvers',
    titulo: 'Aprovadores HITL',
    descricao: 'Pessoas autorizadas a aprovar ou rejeitar ações que exigem intervenção humana.',
  },
  {
    id: 'reqsys-operations',
    titulo: 'Operação ReqSys',
    descricao: 'Pessoas responsáveis pela operação e acompanhamento do ReqSys.',
  },
]

const BASE_PATH = '/v1/teams-gateway/recipient-policies'

export function mascararDestino(destinoId = '') {
  const valor = String(destinoId || '').trim()
  if (!valor) return 'Não informado'
  const indiceArroba = valor.indexOf('@')
  if (indiceArroba > 1) {
    const local = valor.slice(0, indiceArroba)
    const dominio = valor.slice(indiceArroba)
    return `${local.slice(0, 2)}${'*'.repeat(Math.max(4, local.length - 2))}${dominio}`
  }
  if (valor.length <= 6) return `${valor.slice(0, 1)}***`
  return `${valor.slice(0, 3)}${'*'.repeat(Math.min(12, valor.length - 5))}${valor.slice(-2)}`
}

export function detalheErroPolitica(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  if (status === 401) return 'Sua sessão expirou. Autentique-se novamente.'
  if (status === 403) return 'Ação restrita a administradores autorizados.'
  if (status === 409) return typeof detail === 'string' ? detail : 'Já existe um cadastro equivalente nesta política.'
  if (status === 422) return 'Os dados informados não atendem ao contrato da política.'
  return typeof detail === 'string' ? detail : error?.message || 'Falha inesperada ao administrar a política.'
}

export async function listarDestinatarios(politica, apenasAtivos = false) {
  const response = await api.get(`${BASE_PATH}/recipients`, {
    params: { politica, apenas_ativos: apenasAtivos },
  })
  return response.data?.data?.items || []
}

export async function criarDestinatario(payload) {
  const response = await api.post(`${BASE_PATH}/recipients`, payload)
  return response.data?.data
}

export async function atualizarDestinatario(id, payload) {
  const response = await api.patch(`${BASE_PATH}/recipients/${id}`, payload)
  return response.data?.data
}

export async function removerDestinatario(id) {
  const response = await api.delete(`${BASE_PATH}/recipients/${id}`)
  return response.data?.data
}

export async function executarReadiness(politica) {
  const response = await api.post(`${BASE_PATH}/${encodeURIComponent(politica)}/messages`, {
    destino_tipo: 'auto',
    modo: 'auto',
    destino_id: null,
    texto: 'ReqSys recipient-policy readiness probe',
    autor: 'reqsys-readiness-ui',
    permitir_fallback: false,
    dry_run: true,
    delivery_mode: 'first_success',
    metadata: {
      titulo: 'ReqSys Teams policy readiness',
      probe: true,
      origem: 'admin-ui',
    },
  })
  const data = response.data?.data || {}
  return {
    politica,
    pronto: data.dry_run === true && data.entregue === true && data.fallback_usado !== true,
    dryRun: data.dry_run === true,
    fallbackUsado: data.fallback_usado === true,
    motivo: data.motivo || null,
    erro: data.erro || null,
    correlationId: data.correlation_id || null,
  }
}
