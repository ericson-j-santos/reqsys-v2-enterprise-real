import { describe, expect, it } from 'vitest'
import { buildPulsoPortfolio, projectHealth } from '../painelProjetos'

describe('portfolio do Pulso no ReqSys', () => {
  it('vincula requisito e runtime pelo requisito_id sem inventar associação', () => {
    const result = buildPulsoPortfolio(
      [{ id: 7, codigo: 'REQ-007', titulo: 'Portal', descricao: 'Evolução', solicitante: 'Ana', sistema: 'Portal', status: 'aprovado' }],
      [{ requisito_id: 7, status: 'em_ci', owner_ai: 'Time Portal', ci_status: 'running', ci_url: 'https://evidence.example/run', ambiente_deploy: 'dev', atualizado_em: '2026-10-03T10:00:00Z' }],
      [{ requisito_id: 7, planner_task_id: 'planner-7', correlation_id: 'corr-7' }],
      'DEV',
    )

    expect(result.projects[0]).toMatchObject({
      code: 'REQ-007', progress: 78, environment: 'DEV', plannerTaskId: 'planner-7',
      correlationId: 'corr-7', evidenceUrl: 'https://evidence.example/run', origin: 'ReqSys + Agile Execução',
    })
    expect(result.solutions[0]).toMatchObject({ name: 'Portal', projects: 1, progress: 78 })
  })

  it('classifica bloqueio e falha de CI como atraso', () => {
    expect(projectHealth('bloqueado', 'unknown')).toBe('Atrasado')
    expect(projectHealth('em_ci', 'failed')).toBe('Atrasado')
  })
})
