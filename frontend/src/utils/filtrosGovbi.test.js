import { describe, expect, it } from 'vitest'
import {
  contarConsultasGovbi,
  criarQueryFiltrosGovbi,
  criarRegistroConsultaGovbi,
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
})
