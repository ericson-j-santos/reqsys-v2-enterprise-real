import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  alterarPerfilNoteri,
  obterPerfilNoteri,
} from '../hostProfileLocalAgent'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function response(payload, ok = true, status = 200) {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  }
}

describe('hostProfileLocalAgent', () => {
  it('lê o perfil real do Noteri', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ok: true,
      host: 'Noteri',
      profile: 'NORMAL',
      accepts_new_development: true,
    })))

    await expect(obterPerfilNoteri()).resolves.toMatchObject({
      profile: 'NORMAL',
      accepts_new_development: true,
    })
  })

  it('altera para ESTUDO e exige leitura independente coerente', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({
        ok: true,
        host: 'Noteri',
        profile: 'ESTUDO',
        accepts_new_development: false,
        changed: true,
        request_correlation_id: 'corr-estudo-001',
      }))
      .mockResolvedValueOnce(response({
        ok: true,
        host: 'Noteri',
        profile: 'ESTUDO',
        accepts_new_development: false,
      }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await alterarPerfilNoteri('ESTUDO', 'corr-estudo-001')
    expect(result).toMatchObject({
      profile: 'ESTUDO',
      accepts_new_development: false,
      changed: true,
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('falha quando a leitura independente não confirma o perfil', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(response({
        ok: true,
        host: 'Noteri',
        profile: 'ESTUDO',
        accepts_new_development: false,
        changed: true,
      }))
      .mockResolvedValueOnce(response({
        ok: true,
        host: 'Noteri',
        profile: 'NORMAL',
        accepts_new_development: true,
      })))

    await expect(alterarPerfilNoteri('ESTUDO', 'corr-divergencia-001'))
      .rejects.toThrow('Leitura independente divergiu')
  })

  it('falha fechado quando o agente responde de outro host', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ok: true,
      host: 'DESKTOP-PDQK954',
      profile: 'NORMAL',
      accepts_new_development: true,
    })))

    await expect(obterPerfilNoteri()).rejects.toThrow('não ao Noteri')
  })

  it('propaga indisponibilidade sem simular sucesso', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ok: false,
      error: 'origin_not_allowed',
    }, false, 403)))

    await expect(obterPerfilNoteri()).rejects.toThrow('origin_not_allowed')
  })
})
