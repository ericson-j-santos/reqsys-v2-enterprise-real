import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMock = {
  get: vi.fn(),
  post: vi.fn(),
}

vi.mock('../api', () => ({ api: apiMock }))

import {
  atualizarMinhaSessao,
  carregarStatusSessoes,
  invalidarTodasSessoes,
  mensagemErroSessao,
} from '../sessionManagement'

describe('sessionManagement', () => {
  beforeEach(() => {
    apiMock.get.mockReset()
    apiMock.post.mockReset()
  })

  it('carrega status sanitizado do gerenciamento de sessões', async () => {
    apiMock.get.mockResolvedValue({ data: { data: { session_epoch: 3, authz_version: 'rbac-abc' } } })
    await expect(carregarStatusSessoes()).resolves.toEqual({ session_epoch: 3, authz_version: 'rbac-abc' })
    expect(apiMock.get).toHaveBeenCalledWith('/v1/auth/sessions/admin/status')
  })

  it('atualiza a própria sessão pelo endpoint governado', async () => {
    apiMock.post.mockResolvedValue({ data: { data: { access_token: 'novo-token' } } })
    await expect(atualizarMinhaSessao()).resolves.toEqual({ access_token: 'novo-token' })
    expect(apiMock.post).toHaveBeenCalledWith('/v1/auth/session/refresh')
  })

  it('invalida todas as sessões enviando confirmação e motivo', async () => {
    apiMock.post.mockResolvedValue({ data: { data: { decision: 'all_human_sessions_invalidated' } } })
    await invalidarTodasSessoes('INVALIDAR-SESSOES-DEV', 'Alteração controlada de RBAC')
    expect(apiMock.post).toHaveBeenCalledWith('/v1/auth/sessions/admin/invalidate-all', {
      confirmacao: 'INVALIDAR-SESSOES-DEV',
      motivo: 'Alteração controlada de RBAC',
    })
  })

  it('traduz sessão revogada sem expor detalhes internos', () => {
    expect(mensagemErroSessao({ response: { status: 401 } })).toContain('Autentique-se novamente')
    expect(mensagemErroSessao({ response: { status: 403 } })).toContain('administradores')
  })
})
