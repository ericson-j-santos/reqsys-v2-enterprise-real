import { describe, expect, it, vi } from 'vitest'
import {
  consolidarResultadosFuncionamento,
  executarFuncionamentoGovbi,
  executarTestesApiGovbi,
  executarTestesLocaisGovbi,
  statusGovbiComprovaExecucao,
} from './govbiFuncionamento'

describe('govbiFuncionamento', () => {
  it.each(['ERRO', 'BLOQUEADA', 'PENDENTE_APROVACAO', 'MODO_DEGRADADO', null, undefined, '', 'DESCONHECIDO'])(
    'não promove status externo não conclusivo: %s',
    (statusFluxo) => {
      expect(statusGovbiComprovaExecucao(statusFluxo)).toBe(false)
    },
  )

  it.each(['EXECUTADA', 'CONCLUIDO'])(
    'aceita apenas status positivo conhecido: %s',
    (statusFluxo) => {
      expect(statusGovbiComprovaExecucao(statusFluxo)).toBe(true)
    },
  )

  it('executa testes locais com 100% de aprovação', () => {
    const resultados = executarTestesLocaisGovbi()
    const consolidado = consolidarResultadosFuncionamento(resultados)

    expect(resultados.length).toBeGreaterThanOrEqual(10)
    expect(consolidado.aprovados).toBe(consolidado.total)
    expect(consolidado.percentual).toBe(100)
    expect(consolidado.completo).toBe(true)
  })

  it('consolida reprovações corretamente', () => {
    const consolidado = consolidarResultadosFuncionamento([
      { id: 'a', nome: 'A', ok: true, detalhe: 'OK', categoria: 'local' },
      { id: 'b', nome: 'B', ok: false, detalhe: 'Falha', categoria: 'api' },
    ])

    expect(consolidado.total).toBe(2)
    expect(consolidado.aprovados).toBe(1)
    expect(consolidado.reprovados).toBe(1)
    expect(consolidado.percentual).toBe(50)
    expect(consolidado.completo).toBe(false)
  })

  it('não promove fallback degradado mesmo com configuração e contrato local válidos', async () => {
    const client = {
      get: vi.fn(async (url) => {
        if (url === '/govbi/health') {
          return { data: { data: { service: 'govbi-proxy', status: 'configurado', configuration_status: 'valida', local_contract_status: 'valido', external_health_status: 'nao_verificada', timeout_seconds: 15 } } }
        }
        if (url === '/govbi/funcionamento') {
          return {
            data: {
              data: {
                completo: true,
                percentual: 100,
                aprovados: 5,
                total: 5,
              },
            },
          }
        }
        throw new Error(`GET inesperado: ${url}`)
      }),
      post: vi.fn(async (url, body) => {
        if (url === '/govbi/perguntas' && body?.pergunta === 'oi') {
          const error = new Error('validation')
          error.response = { status: 422 }
          throw error
        }
        if (url === '/govbi/perguntas') {
          return {
            data: {
              statusFluxo: 'MODO_DEGRADADO',
              correlationId: 'corr-mock',
              resultado: { colunas: [], linhas: [] },
              explicacao: 'mock',
              mascaramentoAplicado: true,
            },
          }
        }
        throw new Error(`POST inesperado: ${url}`)
      }),
    }

    const api = await executarTestesApiGovbi(client)
    const consolidado = consolidarResultadosFuncionamento(api)

    const resultadoExterno = api.find((item) => item.id === 'api-contrato-perguntas')

    expect(api).toHaveLength(4)
    expect(resultadoExterno.ok).toBe(false)
    expect(resultadoExterno.detalhe).toContain('degradado e não comprovado')
    expect(consolidado.percentual).toBeLessThan(100)
    expect(consolidado.completo).toBe(false)
  })


  it('não confunde status legado ok com saúde externa comprovada', async () => {
    const client = {
      get: vi.fn(async (url) => {
        if (url === '/govbi/health') {
          return { data: { data: { service: 'govbi-proxy', status: 'ok', timeout_seconds: 15 } } }
        }
        return { data: { data: { completo: true, percentual: 100, aprovados: 5, total: 5 } } }
      }),
      post: vi.fn(async (url, body) => {
        if (body?.pergunta === 'oi') {
          const error = new Error('validation')
          error.response = { status: 422 }
          throw error
        }
        return {
          data: {
            statusFluxo: 'MODO_DEGRADADO',
            correlationId: 'corr',
            resultado: { colunas: [], linhas: [] },
            explicacao: 'fallback governado; não comprova integração externa',
            mascaramentoAplicado: true,
          },
        }
      }),
    }

    const resultados = await executarTestesApiGovbi(client)
    const health = resultados.find((item) => item.id === 'api-health')

    expect(health.ok).toBe(false)
    expect(health.detalhe).toBe('Resposta fora do contrato local')
  })

  it('agrega local + API no funcionamento completo', async () => {
    const client = {
      get: vi.fn(async (url) => {
        if (url === '/govbi/health') {
          return { data: { data: { service: 'govbi-proxy', status: 'configurado', configuration_status: 'valida', local_contract_status: 'valido', external_health_status: 'nao_verificada', timeout_seconds: 15 } } }
        }
        return {
          data: {
            data: { completo: true, percentual: 100, aprovados: 5, total: 5 },
          },
        }
      }),
      post: vi.fn(async (url, body) => {
        if (body?.pergunta === 'oi') {
          const error = new Error('validation')
          error.response = { status: 422 }
          throw error
        }
        return {
          data: {
            statusFluxo: 'CONCLUIDO',
            correlationId: 'corr',
            resultado: { colunas: ['a'], linhas: [] },
            explicacao: 'ok',
            mascaramentoAplicado: true,
          },
        }
      }),
    }

    const consolidado = await executarFuncionamentoGovbi(client)
    expect(consolidado.total).toBeGreaterThanOrEqual(14)
    expect(consolidado.completo).toBe(true)
    expect(consolidado.percentual).toBe(100)
  })
})
