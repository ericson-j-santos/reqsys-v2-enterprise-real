import { api } from './api'
import { acquirePowerPlatformToken } from '../auth/msal'

const BASE = '/v1/hub-lowcode/copilot-memory'
const INSTALL = `${BASE}/install`

const unwrap = (response) => response.data?.data || {}

export async function carregarStatusInstalacao() {
  return unwrap(await api.get(`${INSTALL}/status`))
}

export async function listarGruposInstalacao() {
  return unwrap(await api.get(`${INSTALL}/groups`))
}

export async function listarPlanosInstalacao(groupId) {
  return unwrap(await api.get(`${INSTALL}/plans`, { params: { group_id: groupId } }))
}

export async function listarArquivosInstalacao(groupId) {
  return unwrap(await api.get(`${INSTALL}/files`, { params: { group_id: groupId } }))
}

export async function criarPlanilhaInstalacao(groupId, nome = 'CopilotMemory.xlsx') {
  return unwrap(await api.post(`${INSTALL}/workbook`, null, { params: { group_id: groupId, nome } }))
}

export async function listarConexoesInstalacao(environmentId) {
  // Conexoes Planner/Excel Online sao pessoais do usuario: precisa de um
  // token delegado (via MSAL) para o backend enxerga-las.
  //
  // Ausencia de token continua valida para login demo/sem conta Microsoft e o
  // backend devolve a mensagem funcional correspondente. Erro real de MSAL,
  // consentimento ou escopo NAO pode ser convertido em null, pois isso mascara
  // a causa raiz e faz a descoberta parecer apenas "pendente".
  const token = await acquirePowerPlatformToken()
  const headers = token ? { 'X-Power-Platform-Token': token } : {}
  return unwrap(await api.get(`${INSTALL}/connections`, { params: { environment_id: environmentId }, headers }))
}

export async function validarImplantacao(payload) {
  return unwrap(await api.post(`${INSTALL}/deploy`, { ...payload, confirmar: false }))
}

export async function implantarCopilotMemory(payload) {
  return unwrap(await api.post(`${INSTALL}/deploy`, { ...payload, confirmar: true }))
}

export async function gerarPacoteCopilotMemory() {
  return unwrap(await api.post(`${BASE}/lowcode/package`, {}))
}

export function baixarPacoteGerado(solution) {
  const encoded = solution?.package?.zip_base64
  if (!encoded) throw new Error('Pacote não foi retornado pelo ReqSys.')
  const binary = atob(encoded)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  const blob = new Blob([bytes], { type: 'application/zip' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = solution?.package?.zip_filename || 'CopilotMemoryCorporativo-Pronto.zip'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function isPowerPlatformConsentError(error) {
  const code = String(error?.errorCode || error?.code || '').toLowerCase()
  const message = String(error?.message || '').toLowerCase()
  return [
    'consent_required',
    'invalid_scope',
    'unauthorized_client',
    'access_denied',
    'aadsts65001',
  ].some((marker) => code.includes(marker) || message.includes(marker))
}

export function mensagemErroInstalacao(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail

  if (isPowerPlatformConsentError(error)) {
    return 'O ReqSys não conseguiu obter o token delegado da Power Platform. Verifique no Microsoft Entra se o aplicativo possui a permissão delegada Connectivity.Connections.Read e se o consentimento necessário foi concedido.'
  }
  if (status === 401) return 'Sua sessão expirou. Entre novamente no ReqSys.'
  if (status === 403) return 'Esta instalação exige uma conta administradora autorizada.'
  if (status === 409) return typeof detail === 'string' ? detail : 'O ambiente bloqueou uma etapa da instalação.'
  if (status === 422) return 'Revise as escolhas antes de continuar.'
  return typeof detail === 'string' ? detail : error?.message || 'Não foi possível concluir esta etapa.'
}
