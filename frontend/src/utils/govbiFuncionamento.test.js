import { describe, expect, it, vi } from 'vitest'
import {
  consolidarResultadosFuncionamento,
  executarFuncionamentoGovbi,
  executarTestesApiGovbi,
  executarTestesLocaisGovbi,
} from './govbiFuncionamento'

describe('govbiFuncionamento', () => {
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

  it('executa testes de API com cliente mockado', async () => {
    const client = {
      get: vi.fn(async (url) => {
        if (url === '/api/govbi/health') {
          return { data: { data: { service: 'govbi-proxy', status: 'ok', timeout_seconds: 15 } } }
        }
        if (url === '/api/govbi/funcionamento') {
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
        if (url === '/api/govbi/perguntas' && body?.pergunta === 'oi') {
          const error = new Error('validation')
          error.response = { status: 422 }
          throw error
        }
        if (url === '/api/govbi/perguntas') {
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

    expect(api).toHaveLength(4)
    expect(consolidado.percentual).toBe(100)
    expect(consolidado.completo).toBe(true)
  })

  it('agrega local + API no funcionamento completo', async () => {
    const client = {
      get: vi.fn(async (url) => {
        if (url === '/api/govbi/health') {
          return { data: { data: { service: 'govbi-proxy', status: 'ok', timeout_seconds: 15 } } }
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
