import { describe, expect, it } from 'vitest'
import {
  calcularResumoSemaforo,
  criarQueryFiltrosMonitoramento,
  filtrarItensMonitoramento,
  normalizarFiltrosMonitoramento,
  normalizarSemaforo,
  semaforoGeral,
} from './filtrosMonitoramento'
import { mapearCardsComDrilldown, resolverDrilldownSpa } from './runtimeDrilldown'

const itens = [
  { tipo: 'gate', referencia: 'REQSYS-OPER-001', titulo: 'CI verde', estado: 'verde', severidade: 'baixa' },
  { tipo: 'gate', referencia: 'REQSYS-OPER-002', titulo: 'Integração pendente', estado: 'amarelo', severidade: 'media' },
  { tipo: 'incidente', referencia: 'REQSYS-OPER-003', titulo: 'Falha crítica', estado: 'vermelho', severidade: 'alta' },
]

describe('filtrosMonitoramento', () => {
  it('normaliza semáforo operacional canônico', () => {
    expect(normalizarSemaforo('healthy').key).toBe('verde')
    expect(normalizarSemaforo('runtime_degraded').key).toBe('vermelho')
    expect(normalizarSemaforo('critico').label).toBe('Crítico')
  })

  it('filtra itens por estado e busca', () => {
    const resultado = filtrarItensMonitoramento(itens, { estado: 'vermelho', busca: 'falha' })
    expect(resultado).toHaveLength(1)
    expect(resultado[0].referencia).toBe('REQSYS-OPER-003')
  })

  it('gera query válida e calcula semáforo geral', () => {
    expect(criarQueryFiltrosMonitoramento({ estado: 'amarelo', secao: 'invalida' })).toEqual({ estado: 'amarelo' })
    const resumo = calcularResumoSemaforo(itens)
    expect(semaforoGeral(resumo)).toBe('vermelho')
  })

  it('normaliza filtros com aliases', () => {
    expect(normalizarFiltrosMonitoramento({ correlationId: 'corr-1', q: 'gate' })).toEqual({
      estado: '',
      secao: '',
      severidade: '',
      correlation_id: 'corr-1',
      busca: 'gate',
    })
  })
})

describe('runtimeDrilldown', () => {
  it('resolve drill-down de API para rota SPA', () => {
    expect(resolverDrilldownSpa('/api/runtime/health')).toEqual({
      path: '/monitoramento-operacional',
      query: { secao: 'runtime' },
    })
  })

  it('prioriza spa_drilldown do card', () => {
    expect(resolverDrilldownSpa('/api/runtime/health', {
      spa_drilldown: { path: '/analytics', query: {} },
    })).toEqual({ path: '/analytics', query: {} })
  })

  it('mapeia cards com rota SPA', () => {
    const cards = mapearCardsComDrilldown([
      { id: 'pending-items', drilldown: '/monitoramento-operacional' },
    ])
    expect(cards[0].rotaSpa.query).toEqual({ estado: 'amarelo', secao: 'itens' })
  })
})
