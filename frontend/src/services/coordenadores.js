import { api } from './api'

function mensagemErro(erro, fallback) {
  return erro?.response?.data?.detail
    || erro?.response?.data?.errors?.[0]?.message
    || erro?.message
    || fallback
}

async function requisitarDados(promessa, fallback) {
  try {
    const resposta = await promessa
    return { ok: true, dados: resposta.data?.data }
  } catch (erro) {
    return { ok: false, erro: mensagemErro(erro, fallback) }
  }
}

export function verificarHealthCoordenacao(basePath) {
  return requisitarDados(api.get(`${basePath}/health`), 'Falha ao verificar saúde da coordenação.')
}

export function listarCoordenadores(basePath) {
  return requisitarDados(api.get(`${basePath}/coordinators`), 'Falha ao carregar coordenadores.')
}

export function classificarDemanda(basePath, payload) {
  return requisitarDados(api.post(`${basePath}/route`, payload), 'Falha ao classificar demanda.')
}

export function carregarAnalyticsResumo(basePath) {
  return requisitarDados(api.get(`${basePath}/analytics/summary`), 'Falha ao carregar resumo analítico.')
}

export function carregarAnalyticsDimensao(basePath, dimensaoEndpoint) {
  return requisitarDados(api.get(`${basePath}/analytics/${dimensaoEndpoint}`), 'Falha ao carregar analítico por dimensão.')
}

export function carregarAnalyticsCoordenadores(basePath) {
  return requisitarDados(api.get(`${basePath}/analytics/coordinators`), 'Falha ao carregar analítico por coordenador.')
}

export function carregarAnalyticsRisco(basePath) {
  return requisitarDados(api.get(`${basePath}/analytics/risk`), 'Falha ao carregar indicadores de risco.')
}
