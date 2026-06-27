import { describe, expect, it, vi } from 'vitest'

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('../api', () => ({
  api: { get, post },
}))

const { carregarRuntimeDashboard, solicitarRemediacao, validarWorkflow } = await import('../runtimeValidator')

describe('services/runtimeValidator', () => {
  it('carrega dashboard pelo endpoint operacional versionado', async () => {
    get.mockResolvedValueOnce({ data: { data: { stability_score: 85 } } })

    await expect(carregarRuntimeDashboard()).resolves.toEqual({ stability_score: 85 })
    expect(get).toHaveBeenCalledWith('/runtime-validator/dashboard')
  })

  it('envia payload de validação de workflow sem mutar o contrato', async () => {
    const payload = { workflow_name: 'ci', required_jobs: ['backend'] }
    post.mockResolvedValueOnce({ data: { data: { valid: true } } })

    await expect(validarWorkflow(payload)).resolves.toEqual({ valid: true })
    expect(post).toHaveBeenCalledWith('/runtime-validator/workflows/validate', payload)
  })

  it('envia remediação em dry-run para o endpoint governado', async () => {
    const payload = { target: 'ci', action: 'rerun_workflow', mode: 'dry_run' }
    post.mockResolvedValueOnce({ data: { data: { accepted: true } } })

    await expect(solicitarRemediacao(payload)).resolves.toEqual({ accepted: true })
    expect(post).toHaveBeenCalledWith('/runtime-validator/remediations', payload)
  })
})
