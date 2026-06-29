import { contarIntegracoesPorStatus } from '../utils/filtrosIntegracao'
import { carregarHistoricoGovbi, contarConsultasGovbi } from '../utils/filtrosGovbi'
import { achatarHistoricoPipeline, carregarHistoricoPipeline, contarEtapasPipeline } from '../utils/filtrosPipeline'

/**
 * Calcula badge de pendência por tema de navegação.
 * @returns {Record<string, { count: number, level: 'vermelho'|'amarelo'|null }>}
 */
export function calcularPendenciasPorTema({
  metricas = {},
  scoreIA = 100,
  integracaoErros = 0,
  govbiErros = 0,
  pipelineErros = 0,
} = {}) {
  const pendentes = Number(metricas.pendentes ?? 0)
  const emAnalise = Number(metricas.em_analise ?? 0)
  const requisitosTotal = pendentes + emAnalise

  const operacaoCritico = pipelineErros + integracaoErros
  const operacaoCount = operacaoCritico > 0 ? operacaoCritico : emAnalise

  const inteligenciaCount =
    scoreIA < 70 ? 1 : scoreIA < 90 ? 1 : govbiErros > 0 ? govbiErros : 0
  const inteligenciaVermelho = scoreIA < 70 || govbiErros > 0

  return {
    operacao: badge(operacaoCount, operacaoCritico > 0 || pipelineErros > 0),
    requisitos: badge(requisitosTotal, pendentes > 30 || emAnalise > 10),
    inteligencia: badge(inteligenciaCount, inteligenciaVermelho),
    integracoes: badge(integracaoErros, integracaoErros > 0),
    governanca: badge(0, false),
    arquitetura: badge(0, false),
  }
}

function badge(count, vermelho) {
  const n = Number(count) || 0
  if (n <= 0) return { count: 0, level: null }
  return { count: n, level: vermelho ? 'vermelho' : 'amarelo' }
}

export async function carregarDadosPendenciasNav(api) {
  const metricas = {}
  let scoreIA = 100
  let integracaoErros = 0

  try {
    const { data } = await api.get('/v1/dashboard/requisitos')
    Object.assign(metricas, data?.data ?? {})
  } catch {
    /* fallback local */
  }

  try {
    const { data } = await api.get('/v1/qualidade-ia/resumo')
    scoreIA = Math.round(data?.data?.score_geral ?? 100)
  } catch {
    /* silencioso */
  }

  try {
    const resp = await api.get('/v1/hub-lowcode/integracoes/historico?limit=100')
    const eventos = resp.data?.data?.eventos || []
    integracaoErros = contarIntegracoesPorStatus(eventos).erros
  } catch {
    integracaoErros = 0
  }

  const consultasGovbi = carregarHistoricoGovbi()
  const govbiErros = contarConsultasGovbi(consultasGovbi).erros
  const etapasPipeline = achatarHistoricoPipeline(carregarHistoricoPipeline())
  const pipelineErros = contarEtapasPipeline(etapasPipeline).erros

  return calcularPendenciasPorTema({
    metricas,
    scoreIA,
    integracaoErros,
    govbiErros,
    pipelineErros,
  })
}
