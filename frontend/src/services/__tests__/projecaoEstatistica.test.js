import { describe, expect, it } from 'vitest'
import {
  calcularResumoProjecao,
  listarPrincipaisGaps,
  listarRiscosPriorizados,
  montarCenariosComparativos
} from '../projecaoEstatistica'

describe('projecaoEstatistica', () => {
  it('resume a projecao executiva com medias coerentes', () => {
    const resumo = calcularResumoProjecao()

    expect(resumo.consolidacaoMedia).toBe(63)
    expect(resumo.maturidadeEcossistema).toBe(71)
    expect(resumo.capacidadeSemanalPrs).toBe(65)
    expect(resumo.capacidadeSemanalMerges).toBe(50)
    expect(resumo.leadTimeMedioMinutos).toBe(54)
    expect(resumo.estabilizacaoCi).toBe(83)
  })

  it('prioriza gaps residuais mais relevantes', () => {
    const gaps = listarPrincipaisGaps(3)

    expect(gaps).toHaveLength(3)
    expect(gaps[0]).toMatchObject({ id: 'sincronizacao-ambientes', gap: 39 })
    expect(gaps[1]).toMatchObject({ id: 'operacao-autonoma', gap: 31 })
    expect(gaps[2]).toMatchObject({ id: 'analytics-drilldown', gap: 27 })
  })

  it('ordena os riscos pelo nivel de exposicao', () => {
    const riscos = listarRiscosPriorizados()

    expect(riscos[0].nivel).toBe('Medio')
    expect(riscos.at(-1).nivel).toBe('Baixo')
  })

  it('calcula ganho medio entre cenarios conservador e acelerado', () => {
    const cenarios = montarCenariosComparativos()
    const consolidacao = cenarios.find((item) => item.id === 'consolidacao-enterprise')

    expect(consolidacao).toMatchObject({
      conservadorFaixa: '21-35 dias',
      aceleradoFaixa: '14-24 dias',
      ganhoEstimadoDias: 9
    })
  })
})
