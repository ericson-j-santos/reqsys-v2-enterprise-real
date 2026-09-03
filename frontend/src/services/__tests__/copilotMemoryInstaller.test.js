import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { acquirePowerPlatformToken } from '../../auth/msal'
import { listarConexoesInstalacao, mensagemErroInstalacao } from '../copilotMemoryInstaller'

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

  it('propaga erro de aquisicao do token e nao chama o backend sem header', async () => {
    const error = Object.assign(new Error('consent required'), { errorCode: 'consent_required' })
    acquirePowerPlatformToken.mockRejectedValue(error)

    await expect(listarConexoesInstalacao('env-1')).rejects.toBe(error)
    expect(api.get).not.toHaveBeenCalled()
  })
})

describe('mensagemErroInstalacao', () => {
  it.each([
    { errorCode: 'consent_required', message: 'consent required' },
    { errorCode: 'invalid_scope', message: 'invalid scope' },
    { errorCode: 'unauthorized_client', message: 'unauthorized client' },
    { errorCode: 'access_denied', message: 'access denied' },
    { errorCode: '', message: 'AADSTS65001: consent required' },
  ])('explica a verificacao do Entra para erro de permissao/token: $errorCode', (data) => {
    const error = Object.assign(new Error(data.message), { errorCode: data.errorCode })

    expect(mensagemErroInstalacao(error)).toContain('Connectivity.Connections.Read')
    expect(mensagemErroInstalacao(error)).toContain('Microsoft Entra')
  })

  it('preserva mensagem de erro desconhecido', () => {
    expect(mensagemErroInstalacao(new Error('falha de rede'))).toBe('falha de rede')
  })
})
