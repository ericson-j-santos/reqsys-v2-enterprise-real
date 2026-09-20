import { describe, expect, it, vi } from 'vitest'
import {
  carregarServiceCase,
  executarTransicaoServiceCase,
  validarServiceCaseId,
} from './serviceCases'

const CASE_ID = '3f388722-40fc-4d3d-8b3d-a8f77367f9d1'

function apiForRead(state = 'NEW', allowed = ['CANCELED', 'TRIAGE']) {
  return {
    get: vi.fn()
      .mockResolvedValueOnce({ data: { data: { case_id: CASE_ID, state, version: 1, allowed_transitions: allowed } } })
      .mockResolvedValueOnce({ data: { data: { case_id: CASE_ID, state, version: 1 } } }),
  }
}

describe('serviceCases', () => {
  it('rejeita identidade inválida antes de chamar a API', async () => {
    expect(() => validarServiceCaseId('invalido')).toThrow(/identificador de caso válido/i)
    const api = { get: vi.fn() }
    await expect(carregarServiceCase(api, 'invalido')).rejects.toThrow(/identificador de caso válido/i)
    expect(api.get).not.toHaveBeenCalled()
  })

  it('faz duas leituras independentes e exige a mesma identidade', async () => {
    const api = apiForRead()
    const result = await carregarServiceCase(api, CASE_ID)
    expect(result.caseData.case_id).toBe(CASE_ID)
    expect(result.operations.case_id).toBe(CASE_ID)
    expect(api.get).toHaveBeenNthCalledWith(1, `/v1/service-cases/${CASE_ID}`)
    expect(api.get).toHaveBeenNthCalledWith(2, `/v1/service-cases/${CASE_ID}/operations`)
  })

  it('executa transição e só confirma após releitura persistida', async () => {
    const api = {
      post: vi.fn().mockResolvedValue({ data: { data: { duplicate: false } } }),
      get: vi.fn()
        .mockResolvedValueOnce({ data: { data: { case_id: CASE_ID, state: 'TRIAGE', version: 2, allowed_transitions: [] } } })
        .mockResolvedValueOnce({ data: { data: { case_id: CASE_ID, state: 'TRIAGE', version: 2 } } }),
    }
    const result = await executarTransicaoServiceCase(
      api,
      { case_id: CASE_ID, state: 'NEW', version: 1, allowed_transitions: ['TRIAGE'] },
      'TRIAGE',
    )
    expect(result.caseData.state).toBe('TRIAGE')
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('falha fechado quando o POST não é confirmado pela leitura independente', async () => {
    const api = {
      post: vi.fn().mockResolvedValue({ data: { data: { duplicate: false } } }),
      get: vi.fn()
        .mockResolvedValueOnce({ data: { data: { case_id: CASE_ID, state: 'NEW', version: 1, allowed_transitions: ['TRIAGE'] } } })
        .mockResolvedValueOnce({ data: { data: { case_id: CASE_ID, state: 'NEW', version: 1 } } }),
    }
    await expect(
      executarTransicaoServiceCase(
        api,
        { case_id: CASE_ID, state: 'NEW', version: 1, allowed_transitions: ['TRIAGE'] },
        'TRIAGE',
      ),
    ).rejects.toThrow(/leitura persistida permaneceu/i)
  })

  it('não envia resolução sem evidência objetiva', async () => {
    const api = { post: vi.fn(), get: vi.fn() }
    await expect(
      executarTransicaoServiceCase(
        api,
        { case_id: CASE_ID, state: 'IN_PROGRESS', version: 3, allowed_transitions: ['RESOLVED'] },
        'RESOLVED',
      ),
    ).rejects.toThrow(/exige URI de evidência e SHA-256 válido/i)
    expect(api.post).not.toHaveBeenCalled()
  })
})
