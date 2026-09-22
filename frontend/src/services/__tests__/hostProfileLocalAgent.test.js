import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import { api } from '../api'
import {
  alterarPerfilNoteri,
  obterPerfilNoteri,
  __hostProfileLocalAgentInternals,
} from '../hostProfileLocalAgent'

afterEach(() => {
  vi.clearAllMocks()
})

function envelope(data) {
  return {
    data: {
      success: true,
      data,
      errors: [],
      meta: { correlation_id: 'corr-test-001' },
    },
  }
}

describe('hostProfileLocalAgent via same-origin API', () => {
  it('lê o perfil real do Noteri pela API ReqSys', async () => {
    api.get.mockResolvedValue(envelope({
      host: 'Noteri',
      profile: 'NORMAL',
      accepts_new_development: true,
    }))

    await expect(obterPerfilNoteri()).resolves.toMatchObject({
      profile: 'NORMAL',
      accepts_new_development: true,
    })
    expect(api.get).toHaveBeenCalledWith('/v1/noteri/profile', expect.any(Object))
  })

  it('altera para ESTUDO e exige leitura independente coerente', async () => {
    api.post.mockResolvedValue(envelope({
      host: 'Noteri',
      profile: 'ESTUDO',
      accepts_new_development: false,
      changed: true,
      request_correlation_id: 'corr-estudo-001',
    }))
    api.get.mockResolvedValue(envelope({
      host: 'Noteri',
      profile: 'ESTUDO',
      accepts_new_development: false,
    }))

    const result = await alterarPerfilNoteri('ESTUDO', 'corr-estudo-001')
    expect(result).toMatchObject({
      profile: 'ESTUDO',
      accepts_new_development: false,
      changed: true,
    })
    expect(api.post).toHaveBeenCalledWith('/v1/noteri/profile', {
      profile: 'ESTUDO',
      correlation_id: 'corr-estudo-001',
    })
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('preserva idempotência informada pelo backend', async () => {
    api.post.mockResolvedValue(envelope({
      host: 'Noteri',
      profile: 'ESTUDO',
      accepts_new_development: false,
      changed: false,
      request_correlation_id: 'corr-estudo-idempotente',
    }))
    api.get.mockResolvedValue(envelope({
      host: 'Noteri',
      profile: 'ESTUDO',
      accepts_new_development: false,
    }))

    await expect(alterarPerfilNoteri('ESTUDO', 'corr-estudo-idempotente'))
      .resolves.toMatchObject({ changed: false, profile: 'ESTUDO' })
  })

  it('falha quando a leitura independente não confirma o perfil', async () => {
    api.post.mockResolvedValue(envelope({
      host: 'Noteri',
      profile: 'ESTUDO',
      accepts_new_development: false,
      changed: true,
    }))
    api.get.mockResolvedValue(envelope({
      host: 'Noteri',
      profile: 'NORMAL',
      accepts_new_development: true,
    }))

    await expect(alterarPerfilNoteri('ESTUDO', 'corr-divergencia-001'))
      .rejects.toThrow('Leitura independente divergiu')
  })

  it('falha fechado quando o estado pertence a outro host', async () => {
    api.get.mockResolvedValue(envelope({
      host: 'DESKTOP-PDQK954',
      profile: 'NORMAL',
      accepts_new_development: true,
    }))

    await expect(obterPerfilNoteri()).rejects.toThrow('não ao Noteri')
  })

  it('propaga indisponibilidade do backend sem simular sucesso', async () => {
    api.get.mockRejectedValue({
      response: { data: { detail: 'diretório do perfil não montado' } },
    })

    await expect(obterPerfilNoteri()).rejects.toThrow('diretório do perfil não montado')
  })

  it('não expõe configuração de agente loopback ao navegador', () => {
    expect(__hostProfileLocalAgentInternals.DEFAULT_AGENT_URL).toBeUndefined()
    expect(Object.keys(__hostProfileLocalAgentInternals)).toEqual(['VALID_PROFILES'])
  })
})
