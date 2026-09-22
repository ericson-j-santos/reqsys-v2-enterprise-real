import { describe, expect, it, vi } from 'vitest'
import { atualizarCdi, carregarCdiAtual, formatarPercentual } from '../financeiro'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('financeiro', () => {
  it('carrega a taxa CDI atual via API quando disponivel', async () => {
    api.get.mockResolvedValueOnce({
      data: { data: { reference_date: '2026-07-02', daily_rate_percent: 0.052531, stale: false } },
    })

    const resultado = await carregarCdiAtual()

    expect(api.get).toHaveBeenCalledWith('/v1/financeiro/cdi/latest')
    expect(resultado.modoOffline).toBe(false)
    expect(resultado.cdi.reference_date).toBe('2026-07-02')
  })

  it('trata 404 como cache vazio, sem ativar modo offline', async () => {
    api.get.mockRejectedValueOnce({ response: { status: 404 } })

    const resultado = await carregarCdiAtual()

    expect(resultado.modoOffline).toBe(false)
    expect(resultado.cdi).toBeNull()
    expect(resultado.mensagem).toMatch(/ainda não foi carregada/i)
  })

  it('ativa modo offline quando a API falha por outro motivo', async () => {
    api.get.mockRejectedValueOnce(new Error('network error'))

    const resultado = await carregarCdiAtual()

    expect(resultado.modoOffline).toBe(true)
    expect(resultado.cdi).toBeNull()
    expect(resultado.mensagem).toMatch(/indisponível/i)
  })

  it('atualiza a taxa CDI chamando o endpoint de refresh', async () => {
    api.post.mockResolvedValueOnce({ data: { data: { reference_date: '2026-07-03' }, meta: {} } })

    const resultado = await atualizarCdi()

    expect(api.post).toHaveBeenCalledWith('/v1/financeiro/cdi/refresh')
    expect(resultado.data.reference_date).toBe('2026-07-03')
  })

  it('formata percentual com casas decimais padrao', () => {
    expect(formatarPercentual(0.052531)).toBe('0.052531%')
    expect(formatarPercentual(undefined)).toBe('-')
  })
})
