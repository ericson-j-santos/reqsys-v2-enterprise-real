import { describe, expect, it } from 'vitest'
import { criarQueryFiltrosRequisitos, filtrarRequisitos, possuiFiltroAtivo } from './filtrosRequisitos'

const itens = [
  { codigo: 'REQ-001', titulo: 'Item A', status: 'em_analise', urgencia: 'alta', area: 'TI' },
  { codigo: 'REQ-002', titulo: 'Item B', status: 'aprovado', urgencia: 'media', area: 'Negocio' },
]

describe('filtrosRequisitos', () => {
  it('filtra requisitos por status e urgencia', () => {
    const resultado = filtrarRequisitos(itens, { status: 'em_analise', urgencia: 'alta' })
    expect(resultado).toHaveLength(1)
    expect(resultado[0].codigo).toBe('REQ-001')
  })

  it('identifica filtros ativos', () => {
    expect(possuiFiltroAtivo({})).toBe(false)
    expect(possuiFiltroAtivo({ status: 'aprovado' })).toBe(true)
  })

  it('gera query somente com filtros validos', () => {
    expect(criarQueryFiltrosRequisitos({ status: 'aprovado', urgencia: 'invalida', area: 'Negocio' })).toEqual({
      status: 'aprovado',
      area: 'Negocio',
    })
  })
})
