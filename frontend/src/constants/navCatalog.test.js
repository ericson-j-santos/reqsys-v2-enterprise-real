import { describe, expect, it } from 'vitest'
import { calcularPendenciasPorTema } from '../composables/navPendencias'
import {
  lerSubgrupoRequisitosPersistido,
  lerTemaPersistido,
  salvarSubgrupoRequisitosPersistido,
  salvarTemaPersistido,
} from '../composables/navTemaPersist'
import {
  NAV_TEMAS,
  itensDoSubgrupo,
  subgrupoIdPorRota,
  temaIdPorRota,
} from './navCatalog'

describe('navPendencias', () => {
  it('marca integrações em vermelho quando há erros', () => {
    const badges = calcularPendenciasPorTema({ integracaoErros: 3 })
    expect(badges.integracoes).toEqual({ count: 3, level: 'vermelho' })
  })

  it('marca requisitos em amarelo com pendências', () => {
    const badges = calcularPendenciasPorTema({
      metricas: { pendentes: 5, em_analise: 2 },
    })
    expect(badges.requisitos.count).toBe(7)
    expect(badges.requisitos.level).toBe('amarelo')
  })

  it('marca inteligência em vermelho com score baixo', () => {
    const badges = calcularPendenciasPorTema({ scoreIA: 58 })
    expect(badges.inteligencia).toEqual({ count: 1, level: 'vermelho' })
  })
})

describe('navTemaPersist', () => {
  it('persiste tema e subgrupo no sessionStorage', () => {
    salvarTemaPersistido('integracoes')
    salvarSubgrupoRequisitosPersistido('pipeline')
    expect(lerTemaPersistido()).toBe('integracoes')
    expect(lerSubgrupoRequisitosPersistido()).toBe('pipeline')
  })
})

describe('navCatalog subgrupos', () => {
  it('define subgrupos para Requisitos e Administração', () => {
    const requisitos = NAV_TEMAS.find((t) => t.id === 'requisitos')
    const administracao = NAV_TEMAS.find((t) => t.id === 'administracao')
    expect(requisitos.subgroups?.map((s) => s.id)).toEqual(['entrada', 'pipeline', 'publicacao'])
    expect(administracao.subgroups?.map((s) => s.id)).toEqual(['operacao', 'seguranca-governanca', 'engenharia-ia'])
  })

  it('resolve subgrupo pela rota', () => {
    expect(subgrupoIdPorRota('/pipeline')).toBe('pipeline')
    expect(subgrupoIdPorRota('/qualidade-ia')).toBe('pipeline')
    expect(subgrupoIdPorRota('/recomendacoes-ia')).toBe('pipeline')
    expect(subgrupoIdPorRota('/task-console')).toBe('pipeline')
    expect(subgrupoIdPorRota('/requisitos')).toBe('entrada')
    expect(subgrupoIdPorRota('/rastreabilidade')).toBe('publicacao')
    expect(subgrupoIdPorRota('/monitoramento-operacional')).toBe('operacao')
    expect(subgrupoIdPorRota('/admin/session-management')).toBe('seguranca-governanca')
    expect(subgrupoIdPorRota('/orquestrador-ia')).toBe('engenharia-ia')
  })

  it('lista todos os itens do subgrupo de refinamento', () => {
    const itens = itensDoSubgrupo('requisitos', 'pipeline')
    expect(itens.map((i) => i.to)).toEqual([
      '/qualidade-ia',
      '/recomendacoes-ia',
      '/task-console',
      '/pipeline',
      '/agile-runtime',
    ])
  })

  it('divide Administração em grupos com no máximo cinco opções', () => {
    const administracao = NAV_TEMAS.find((t) => t.id === 'administracao')
    for (const subgrupo of administracao.subgroups) {
      expect(itensDoSubgrupo('administracao', subgrupo.id).length).toBeLessThanOrEqual(5)
    }
  })

  it('garante que todo item de tema com subgrupos seja alcançável', () => {
    for (const tema of NAV_TEMAS.filter((item) => item.subgroups?.length)) {
      const paths = new Set(tema.subgroups.flatMap((subgrupo) => subgrupo.paths))
      for (const item of tema.items) {
        expect(paths.has(item.to), `${tema.id}:${item.to} deve pertencer a um subgrupo`).toBe(true)
      }
    }
  })

  it('mantém tema correto para rotas dos subgrupos', () => {
    expect(temaIdPorRota('/agile-runtime')).toBe('requisitos')
    expect(temaIdPorRota('/qualidade-ia')).toBe('requisitos')
    expect(temaIdPorRota('/admin/github-merge')).toBe('administracao')
  })
})
