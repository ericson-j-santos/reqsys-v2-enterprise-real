import { describe, expect, it } from 'vitest'
import { calcularResumoEstatisticas, estatisticasExternasIniciais, estatisticasInternasIniciais, validarIndicador } from '../estatisticas'

describe('estatisticas', () => {
  it('mantem indicadores iniciais com contrato valido', () => {
    const indicadores = [...estatisticasInternasIniciais, ...estatisticasExternasIniciais]

    expect(indicadores.length).toBeGreaterThan(0)
    expect(indicadores.flatMap((indicador) => validarIndicador(indicador))).toEqual([])
  })

  it('bloqueia indicador sem fonte e formula', () => {
    const erros = validarIndicador({
      id: 'indicador-invalido',
      nome: 'Indicador inválido',
      estadoAtual: 'avancado',
      estadoAlvo: 'avancado',
      tendencia: 'subindo',
      evidencias: ['uma evidencia']
    })

    expect(erros).toContain('Indicador sem fórmula documentada.')
    expect(erros).toContain('Indicador sem fonte.')
    expect(erros).toContain('Estado avançado exige pelo menos duas evidências.')
  })

  it('calcula resumo consolidado sem promover estado alvo como atual', () => {
    const resumo = calcularResumoEstatisticas([...estatisticasInternasIniciais, ...estatisticasExternasIniciais])

    expect(resumo.total).toBe(4)
    expect(resumo.externos).toBe(1)
    expect(resumo.invalidos).toBe(0)
    expect(resumo.atencao).toBeGreaterThanOrEqual(1)
  })
})
