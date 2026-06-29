import { describe, expect, it } from 'vitest'
import {
  calcularMetricasGovbi,
  contarConsultasGovbi,
  criarQueryFiltrosGovbi,
  criarRegistroConsultaGovbi,
  exportarEvidenciaGovbi,
  filtrarConsultasGovbi,
  possuiFiltroAtivo,
} from './filtrosGovbi'

const consultas = [
  criarRegistroConsultaGovbi({
    pergunta: 'Total por unidade',
    statusFluxo: 'CONCLUIDO',
    fonte: 'backend',
    latenciaMs: 320,
    correlationId: 'corr-govbi-1',
    fallback: false,
  }),
  criarRegistroConsultaGovbi({
    pergunta: 'Erro de conexao',
    statusFluxo: 'MODO_DEGRADADO',
    fonte: 'fallback',
    latenciaMs: 15000,
    correlationId: 'corr-govbi-2',
    fallback: true,
    erro: 'timeout',
  }),
]

describe('filtrosGovbi', () => {
  it('filtra consultas por status, fonte e fallback', () => {
    const resultado = filtrarConsultasGovbi(consultas, { status: 'MODO_DEGRADADO', fonte: 'fallback', fallback: 'true' })
    expect(resultado).toHaveLength(1)
    expect(resultado[0].correlationId).toBe('corr-govbi-2')
  })

  it('identifica filtros ativos e gera query', () => {
    expect(possuiFiltroAtivo({})).toBe(false)
    expect(possuiFiltroAtivo({ correlation_id: 'corr' })).toBe(true)
    expect(criarQueryFiltrosGovbi({ status: 'ERRO', fonte: 'invalida', busca: 'timeout' })).toEqual({
      status: 'ERRO',
      busca: 'timeout',
    })
  })

  it('conta consultas por resultado', () => {
    expect(contarConsultasGovbi(consultas)).toEqual({ erros: 1, fallback: 1, sucesso: 1 })
  })

  it('calcula metricas agregadas com latencia media', () => {
    expect(calcularMetricasGovbi(consultas)).toEqual({
      total: 2,
      sucesso: 1,
      erros: 1,
      fallback: 1,
      latenciaMediaMs: 7660,
    })
  })

  it('exporta evidencia filtrada em JSON', () => {
    const payload = JSON.parse(exportarEvidenciaGovbi(consultas, { status: 'MODO_DEGRADADO' }))
    expect(payload.modulo).toBe('govbi-ia')
    expect(payload.consultas).toHaveLength(1)
    expect(payload.metricas.erros).toBe(1)
    expect(payload.filtros.status).toBe('MODO_DEGRADADO')
  })
})
