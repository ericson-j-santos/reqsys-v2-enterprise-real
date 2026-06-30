import { describe, expect, it } from 'vitest'
import {
  calcularMetricasGovbi,
  carregarHistoricoGovbi,
  contarConsultasGovbi,
  criarQueryFiltrosGovbi,
  criarRegistroConsultaGovbi,
  exportarEvidenciaGovbi,
  filtrarConsultasGovbi,
  GOVBI_HISTORICO_KEY,
  normalizarFiltrosGovbi,
  possuiFiltroAtivo,
  salvarHistoricoGovbi,
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

  it('aceita fonte transporte para erros de conectividade', () => {
    const transporte = criarRegistroConsultaGovbi({
      pergunta: 'Timeout backend',
      statusFluxo: 'ERRO',
      fonte: 'transporte',
      latenciaMs: 15000,
      correlationId: 'corr-govbi-transporte',
      fallback: true,
      erro: 'sem resposta do backend',
    })
    const resultado = filtrarConsultasGovbi([transporte], { status: 'ERRO', fonte: 'transporte' })
    expect(resultado).toHaveLength(1)
    expect(resultado[0].statusFluxo).toBe('ERRO')
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

  it('normaliza filtros por data e fallback', () => {
    expect(normalizarFiltrosGovbi({ data: '2026-06-29', fallback: 'true' })).toEqual({
      status: '',
      fonte: '',
      correlation_id: '',
      data: '2026-06-29',
      busca: '',
      fallback: 'true',
    })
  })

  it('persiste e carrega historico no storage da sessao', () => {
    const storage = {
      store: {},
      getItem(key) { return this.store[key] ?? null },
      setItem(key, value) { this.store[key] = value },
    }
    salvarHistoricoGovbi(consultas, storage, 10)
    expect(carregarHistoricoGovbi(storage)).toHaveLength(2)
    expect(storage.store[GOVBI_HISTORICO_KEY]).toBeTruthy()
  })
})
