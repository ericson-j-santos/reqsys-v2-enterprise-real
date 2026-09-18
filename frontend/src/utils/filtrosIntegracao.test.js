import { describe, expect, it } from 'vitest'
import {
  contarIntegracoesPorStatus,
  criarQueryFiltrosIntegracao,
  filtrarIntegracoes,
  normalizarFiltrosIntegracao,
  possuiFiltroAtivo,
} from './filtrosIntegracao'

const itens = [
  {
    id: 1,
    tipo: 'planner',
    status: 'sucesso',
    autor: 'ana.silva',
    correlation_id: 'corr-001',
    criado_em: '2026-06-20T10:00:00Z',
    titulo: 'Envio planner',
    mensagem: 'ok',
  },
  {
    id: 2,
    tipo: 'teams',
    status: 'erro',
    autor: 'joao.santos',
    correlation_id: 'corr-002',
    criado_em: '2026-06-21T15:30:00Z',
    titulo: 'Notificacao teams',
    mensagem: 'webhook invalido',
  },
]

describe('filtrosIntegracao', () => {
  it('normaliza query com aliases de origem e correlationId', () => {
    expect(normalizarFiltrosIntegracao({ origem: 'planner', correlationId: 'corr-001', dia: '2026-06-20' })).toEqual({
      tipo: 'planner',
      status: '',
      autor: '',
      correlation_id: 'corr-001',
      data: '2026-06-20',
      busca: '',
    })
  })

  it('filtra integracoes por status, origem, data e correlation_id', () => {
    const resultado = filtrarIntegracoes(itens, {
      status: 'erro',
      tipo: 'teams',
      data: '2026-06-21',
      correlation_id: 'corr-002',
    })
    expect(resultado).toHaveLength(1)
    expect(resultado[0].id).toBe(2)
  })

  it('identifica filtros ativos e gera query valida', () => {
    expect(possuiFiltroAtivo({})).toBe(false)
    expect(possuiFiltroAtivo({ status: 'erro' })).toBe(true)
    expect(criarQueryFiltrosIntegracao({ status: 'erro', tipo: 'invalido', busca: 'webhook' })).toEqual({
      status: 'erro',
      busca: 'webhook',
    })
  })

  it('conta integracoes por status', () => {
    expect(contarIntegracoesPorStatus(itens)).toEqual({ erros: 1, sucessos: 1 })
  })
})
