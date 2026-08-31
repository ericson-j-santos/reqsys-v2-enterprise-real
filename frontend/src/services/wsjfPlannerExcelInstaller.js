import { api } from './api'
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
  return unwrap(await api.post(`${BASE}/deploy`, { ...payload, confirmar: true }))
}
