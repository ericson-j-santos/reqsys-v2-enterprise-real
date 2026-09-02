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
  // token delegado (via MSAL) para o backend enxerga-las. Se a aquisicao
  // falhar (ex.: login demo, sem conta Microsoft), segue sem o header — o
  // backend responde com uma mensagem clara em vez de lista vazia muda.
  let token = null
  try {
    token = await acquirePowerPlatformToken()
  } catch {
    token = null
  }
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

export function mensagemErroInstalacao(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  if (status === 401) return 'Sua sessão expirou. Entre novamente no ReqSys.'
  if (status === 403) return 'Esta instalação exige uma conta administradora autorizada.'
  if (status === 409) return typeof detail === 'string' ? detail : 'O ambiente bloqueou uma etapa da instalação.'
  if (status === 422) return 'Revise as escolhas antes de continuar.'
  return typeof detail === 'string' ? detail : error?.message || 'Não foi possível concluir esta etapa.'
}
