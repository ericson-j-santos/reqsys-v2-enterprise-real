import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('../../services/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

import { api } from '../../services/api'
import { useRequisitosStore } from '../requisitos'

describe('stores/requisitos', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('listar() popula itens e zera o estado de carregamento', async () => {
    api.get.mockResolvedValueOnce({ data: { data: [{ id: 1, titulo: 'A' }] } })
    const store = useRequisitosStore()
    await store.listar()
    expect(api.get).toHaveBeenCalledWith('/v1/requisitos')
    expect(store.itens).toHaveLength(1)
    expect(store.carregando).toBe(false)
  })

  it('listar() captura erro em this.erro', async () => {
    api.get.mockRejectedValueOnce(new Error('falha de rede'))
    const store = useRequisitosStore()
    await store.listar()
    expect(store.erro).toBe('falha de rede')
    expect(store.carregando).toBe(false)
  })

  it('criar() faz POST e insere o novo item no topo da lista', async () => {
    const novo = { id: 9, titulo: 'Novo', codigo: 'REQ-9' }
    api.post.mockResolvedValueOnce({ data: { data: novo } })
    const store = useRequisitosStore()
    store.itens = [{ id: 1, titulo: 'Existente' }]
    const retorno = await store.criar({ titulo: 'Novo' })
    expect(api.post).toHaveBeenCalledWith('/v1/requisitos', { titulo: 'Novo' })
    expect(store.itens[0]).toEqual(novo)
    expect(retorno).toEqual(novo)
  })

  it('carregarMetricas() popula metricas a partir do dashboard', async () => {
    api.get.mockResolvedValueOnce({ data: { data: { total: 10, aprovados: 3 } } })
    const store = useRequisitosStore()
    await store.carregarMetricas()
    expect(api.get).toHaveBeenCalledWith('/v1/dashboard/requisitos')
    expect(store.metricas).toEqual({ total: 10, aprovados: 3 })
  })

  it('carregarQualidadeIA() popula o resumo de qualidade', async () => {
    api.get.mockResolvedValueOnce({ data: { data: { score: 58 } } })
    const store = useRequisitosStore()
    await store.carregarQualidadeIA()
    expect(api.get).toHaveBeenCalledWith('/v1/qualidade-ia/resumo')
    expect(store.qualidadeIAResumo).toEqual({ score: 58 })
  })
})
