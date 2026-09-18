import { api } from './api'
import { acquireFlowManagementToken } from '../auth/msal'
import {
  carregarStatusInstalacao,
  listarArquivosInstalacao,
  listarConexoesInstalacao,
  listarGruposInstalacao,
  listarPlanosInstalacao,
  mensagemErroInstalacao,
} from './copilotMemoryInstaller'

const BASE = '/v1/hub-lowcode/wsjf/planner-excel'
const unwrap = (response) => response.data?.data || {}

export {
  carregarStatusInstalacao,
  listarArquivosInstalacao,
  listarConexoesInstalacao,
  listarGruposInstalacao,
  listarPlanosInstalacao,
  mensagemErroInstalacao,
}

export function somenteArquivoWsjf(arquivos = []) {
  return arquivos.filter((arquivo) => String(arquivo?.nome || '').trim().toLowerCase() === 'wsjf.xlsx')
}

export function somenteAmbientesDev(ambientes = []) {
  return ambientes.filter((ambiente) => {
    const texto = [ambiente?.nome, ambiente?.tipo, ambiente?.id, ambiente?.url]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return /(^|[^a-z])dev([^a-z]|$)|development|desenvolvimento/.test(texto)
  })
}

export async function carregarContratoWsjf() {
  return unwrap(await api.get(`${BASE}/contract`))
}

export async function validarWsjfPlannerExcel(payload) {
  return unwrap(await api.post(`${BASE}/validate`, { ...payload, confirmar: false }))
}

export async function instalarWsjfPlannerExcel(payload) {
  // Criar/atualizar o fluxo de verdade exige token delegado (via MSAL): a
  // API de gerenciamento de fluxos do Power Automate não aceita credencial
  // app-only. Diferente da leitura de conexões, aqui deixamos o erro de
  // aquisição propagar — é uma instalação real, não deve seguir silenciosa.
  const token = await acquireFlowManagementToken()
  const headers = token ? { 'X-Power-Automate-Token': token } : {}
  return unwrap(await api.post(`${BASE}/deploy`, { ...payload, confirmar: true }, { headers }))
}

export async function diagnosticarWorkbookWsjf({ excel_drive, excel_file }) {
  return unwrap(await api.post(`${BASE}/excel/diagnostico`, { excel_drive, excel_file }))
}

export async function regenerarWorkbookWsjf({ excel_drive, excel_file }) {
  // Substitui o arquivo do tenant: exige confirmação explícita no backend.
  return unwrap(await api.post(`${BASE}/excel/reparar`, { excel_drive, excel_file, confirmar: true }))
}
