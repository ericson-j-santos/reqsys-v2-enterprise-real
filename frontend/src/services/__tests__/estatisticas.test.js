import { describe, expect, it, vi } from 'vitest'
import {
  calcularResumoEstatisticas,
  carregarEstatisticas,
  indicadoresExemploValidacao,
  validarIndicador
} from '../estatisticas'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    get: vi.fn()
  }
}))

describe('estatisticas', () => {
  it('mantem indicadores de exemplo com contrato valido', () => {
    expect(indicadoresExemploValidacao.length).toBeGreaterThan(0)
    expect(indicadoresExemploValidacao.flatMap((indicador) => validarIndicador(indicador))).toEqual([])
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
    const resumo = calcularResumoEstatisticas(indicadoresExemploValidacao)

    expect(resumo.total).toBe(4)
    expect(resumo.externos).toBe(1)
    expect(resumo.invalidos).toBe(0)
    expect(resumo.atencao).toBeGreaterThanOrEqual(1)
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

    const resultado = await carregarEstatisticas()

    expect(api.get).toHaveBeenCalledWith('/v1/estatisticas')
    expect(resultado.modoOffline).toBe(false)
    expect(resultado.indicadores).toEqual([indicadorApi])
  })

  it('ativa modo offline sem KPIs inventados quando API falha', async () => {
    api.get.mockRejectedValueOnce(new Error('api indisponivel'))

    const resultado = await carregarEstatisticas()

    expect(resultado.modoOffline).toBe(true)
    expect(resultado.indicadores).toEqual([])
    expect(resultado.mensagem).toMatch(/indisponível/i)
  })
})
