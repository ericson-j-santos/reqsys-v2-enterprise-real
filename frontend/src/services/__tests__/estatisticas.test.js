import { describe, expect, it, vi } from 'vitest'
import {
  calcularResumoEstatisticas,
  carregarEstatisticas,
  criarDrilldownIndicador,
  estatisticasExternasIniciais,
  estatisticasInternasIniciais,
  validarIndicador
} from '../estatisticas'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    get: vi.fn()
  }
}))

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

  it('cria drill-down navegavel preservando fonte, evidencias e proxima acao', () => {
    const indicador = estatisticasExternasIniciais[0]
    const drilldown = criarDrilldownIndicador(indicador)

    expect(drilldown.id).toBe(indicador.id)
    expect(drilldown.fonte.id).toBe(indicador.fonte.id)
    expect(drilldown.evidencias).toEqual(indicador.evidencias)
    expect(drilldown.pendencias).toEqual(indicador.pendencias)
    expect(drilldown.guardRails).toEqual([])
    expect(drilldown.statusNavegavel).toBe('acao_requerida')
    expect(drilldown.proximaAcao).toBe(indicador.pendencias[0])
    expect(drilldown.trilhaAuditoria).toContain(`indicador:${indicador.id}`)
  })

  it('bloqueia drill-down sem contrato minimo antes de promover estado operacional', () => {
    const drilldown = criarDrilldownIndicador({
      id: 'ux-invalido',
      nome: 'UX inválido',
      estadoAtual: 'avancado',
      estadoAlvo: 'avancado',
      tendencia: 'subindo',
      evidencias: ['uma evidencia']
    })

    expect(drilldown.statusNavegavel).toBe('acao_requerida')
    expect(drilldown.guardRails).toContain('Indicador sem fórmula documentada.')
    expect(drilldown.guardRails).toContain('Indicador sem fonte.')
    expect(drilldown.proximaAcao).toBe('Corrigir contrato do indicador antes de promover o estado operacional.')
  })

  it('carrega indicadores reais via API quando disponiveis', async () => {
    const indicadorApi = {
      id: 'total-requisitos',
      nome: 'Total de requisitos',
      descricao: 'Total real',
      categoria: 'Requisitos',
      valorAtual: 10,
      unidade: 'itens',
      tendencia: 'indefinida',
      estadoAtual: 'adequado',
      estadoAlvo: 'avancado',
      formula: 'count(requisitos.id)',
      fonte: {
        id: 'reqsys-db-requisitos',
        tipo: 'interna',
        nome: 'Banco operacional ReqSys',
        origem: 'backend-db:requisitos',
        coletadoEm: new Date().toISOString(),
        confiabilidade: 'alta'
      },
      evidencias: ['endpoint backend /v1/estatisticas'],
      pendencias: []
    }
    api.get.mockResolvedValueOnce({ data: { data: { indicadores: [indicadorApi] } } })

    const indicadores = await carregarEstatisticas()

    expect(api.get).toHaveBeenCalledWith('/v1/estatisticas')
    expect(indicadores).toEqual([indicadorApi])
  })

  it('usa fallback controlado quando API falha', async () => {
    api.get.mockRejectedValueOnce(new Error('api indisponivel'))

    const indicadores = await carregarEstatisticas()

    expect(indicadores.length).toBe(4)
    expect(indicadores.some((item) => item.fonte.origem === 'frontend-runtime-fallback')).toBe(true)
  })
})
