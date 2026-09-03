import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { acquirePowerPlatformToken } from '../../auth/msal'
import { listarConexoesInstalacao } from '../copilotMemoryInstaller'

vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

vi.mock('../../auth/msal', () => ({
  acquirePowerPlatformToken: vi.fn(),
}))

describe('listarConexoesInstalacao', () => {
  beforeEach(() => vi.clearAllMocks())

  it('envia o token delegado no header quando a aquisicao via MSAL funciona', async () => {
    acquirePowerPlatformToken.mockResolvedValue('token-delegado-123')
    api.get.mockResolvedValue({ data: { data: { planner: [], excel: [] } } })

    await listarConexoesInstalacao('env-1')

    expect(api.get).toHaveBeenCalledWith(
      '/v1/hub-lowcode/copilot-memory/install/connections',
      expect.objectContaining({
        params: { environment_id: 'env-1' },
        headers: { 'X-Power-Platform-Token': 'token-delegado-123' },
      })
    )
  })

  it('segue sem o header quando nao ha token (ex.: login demo)', async () => {
    acquirePowerPlatformToken.mockResolvedValue(null)
    api.get.mockResolvedValue({ data: { data: { planner: [], excel: [] } } })

    await listarConexoesInstalacao('env-1')

    expect(api.get).toHaveBeenCalledWith(
      '/v1/hub-lowcode/copilot-memory/install/connections',
      expect.objectContaining({
        params: { environment_id: 'env-1' },
        headers: {},
      })
    )
  })

  it('propaga falha real de aquisicao do token e nao consulta conexoes sem credencial', async () => {
    const erro = new Error('consent_required')
    acquirePowerPlatformToken.mockRejectedValue(erro)

    await expect(listarConexoesInstalacao('env-1')).rejects.toBe(erro)

    expect(api.get).not.toHaveBeenCalled()
  })
})
