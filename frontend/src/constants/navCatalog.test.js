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
  it('define subgrupos para o tema Requisitos', () => {
    const requisitos = NAV_TEMAS.find((t) => t.id === 'requisitos')
    expect(requisitos.subgroups?.length).toBe(3)
    expect(requisitos.subgroups.map((s) => s.id)).toEqual(['entrada', 'pipeline', 'publicacao'])
  })

  it('resolve subgrupo pela rota', () => {
    expect(subgrupoIdPorRota('/pipeline')).toBe('pipeline')
    expect(subgrupoIdPorRota('/requisitos')).toBe('entrada')
    expect(subgrupoIdPorRota('/rastreabilidade')).toBe('publicacao')
    expect(subgrupoIdPorRota('/qualidade-ia')).toBe('pipeline')
    expect(subgrupoIdPorRota('/recomendacoes-ia')).toBe('pipeline')
    expect(subgrupoIdPorRota('/task-console')).toBe('pipeline')
  })

  it('lista todos os itens de refinamento e fluxo', () => {
    const itens = itensDoSubgrupo('requisitos', 'pipeline')
    expect(itens.map((i) => i.to)).toEqual([
      '/qualidade-ia',
      '/recomendacoes-ia',
      '/task-console',
      '/pipeline',
      '/agile-runtime',
    ])
  })

  it('mantém tema requisitos para rotas do subgrupo', () => {
    expect(temaIdPorRota('/agile-runtime')).toBe('requisitos')
    expect(temaIdPorRota('/qualidade-ia')).toBe('requisitos')
  })

  it('garante que todo item de tema com subgrupos seja alcançável em pelo menos um subgrupo', () => {
    for (const tema of NAV_TEMAS.filter((item) => item.subgroups?.length)) {
      const rotasVisiveis = new Set(
        tema.subgroups.flatMap((subgrupo) => itensDoSubgrupo(tema.id, subgrupo.id).map((item) => item.to)),
      )
      expect([...tema.items.map((item) => item.to).filter((rota) => !rotasVisiveis.has(rota))]).toEqual([])
    }
  })
})

describe('navCatalog Administração', () => {
  it('define subgrupos operacionais sem ocultar funções', () => {
    const administracao = NAV_TEMAS.find((t) => t.id === 'administracao')
    expect(administracao.subgroups?.map((s) => s.id)).toEqual(['operacao', 'seguranca-governanca', 'engenharia-ia'])
    for (const subgrupo of administracao.subgroups) {
      expect(itensDoSubgrupo('administracao', subgrupo.id).length).toBeLessThanOrEqual(5)
    }
  })

  it('resolve rotas administrativas para o subgrupo e tema corretos', () => {
    expect(subgrupoIdPorRota('/monitoramento-operacional')).toBe('operacao')
    expect(subgrupoIdPorRota('/admin/session-management')).toBe('seguranca-governanca')
    expect(subgrupoIdPorRota('/orquestrador-ia')).toBe('engenharia-ia')
    expect(temaIdPorRota('/admin/github-merge')).toBe('administracao')
  })
})
