import { describe, expect, it } from 'vitest'
import { buildPulsoPortfolio, projectHealth } from '../painelProjetos'

describe('portfolio do Pulso no ReqSys', () => {
  it('agrupa execução pelo projeto atual e vincula seus requisitos e entregas', () => {
    const result = buildPulsoPortfolio(
      [{ id: 7, codigo: 'REQ-007', titulo: 'Portal', descricao: 'Evolução', solicitante: 'Ana', sistema: 'Portal', status: 'aprovado' }],
      [
        { requisito_id: 7, repositorio: 'acme/portal', status: 'em_ci', owner_ai: 'Time Portal', ci_status: 'running', ci_url: 'https://evidence.example/run', ambiente_deploy: 'dev', atualizado_em: '2026-10-03T10:00:00Z', change_id: '42', branch: 'feat/portal' },
        { requisito_id: 7, repositorio: 'ACME/PORTAL', status: 'em_execucao', ci_status: 'unknown', ambiente_deploy: 'none', atualizado_em: '2026-10-02T10:00:00Z' },
      ],
      [{ requisito: 'REQ-007', repositorio: 'acme/portal', planner: 'planner-7', entrega: 'PR #42', entrega_url: 'https://evidence.example/pr', ambiente: 'dev' }],
      'DEV',
    )

    expect(result.projects).toHaveLength(1)
    expect(result.projects[0]).toMatchObject({
      code: 'acme/portal', name: 'portal', progress: 72, environment: 'DEV',
      plannerTaskId: 'planner-7', evidenceUrl: 'https://evidence.example/run',
      origin: 'Agile Execução · projeto atual', workItems: 2, requirements: 1,
      changeId: '42', branch: 'feat/portal',
    })
    expect(result.solutions[0]).toMatchObject({ name: 'Portal', projects: 1, progress: 72 })
  })

  it('não transforma requisito ou item sem repositório em projeto', () => {
    const result = buildPulsoPortfolio(
      [{ id: 8, codigo: 'REQ-008', titulo: 'Ideia sem projeto' }],
      [{ requisito_id: 8, repositorio: null, status: 'novo' }],
    )

    expect(result.projects).toEqual([])
    expect(result.unlinkedWorkItems).toBe(1)
  })

  it('consolida bloqueio e falha de CI no nível do projeto', () => {
    const result = buildPulsoPortfolio([], [
      { repositorio: 'acme/api', status: 'em_execucao', ci_status: 'success' },
      { repositorio: 'acme/api', status: 'em_ci', ci_status: 'failed' },
    ])

    expect(result.projects[0]).toMatchObject({ status: 'bloqueado', health: 'Atrasado', nextMilestone: 'Remover impedimento' })
    expect(projectHealth('em_ci', 'failed')).toBe('Atrasado')
  })
})
