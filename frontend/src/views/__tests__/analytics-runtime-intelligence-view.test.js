import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AnalyticsRuntimeIntelligenceView from '../AnalyticsRuntimeIntelligenceView.vue'

const mockPayload = {
  success: true,
  data: {
    evidence_scope: 'repository_contract',
    correlation_id: 'corr-ari-ui',
    health_score: 78,
    production_ready: false,
    draft_recomendado: true,
    runtime_sql_validation: { runtime_sql_ready: true, production_evidence: false },
    staging_validation: { staging_ready: false },
    readiness_matrix: [
      {
        capability: 'Staging Validation',
        estado: 'EVIDENCIA_AUSENTE',
        evidencia: 'Sem conjunto completo de evidências.',
        gap: 'Executar staging externo governado.',
        bloqueia_producao: true,
      },
    ],
    validacoes: [
      {
        codigo: 'AI_GROUNDING',
        nome: 'IA governada com fonte e lineage',
        status: 'block',
        score: 55,
        evidencia: 'Sem grounding externo.',
        acao_recomendada: 'Bloquear promoção.',
      },
    ],
    production_gaps: ['Executar staging externo governado.'],
    figma: { status: 'evidence_pending', ready: false, evidence: 'Sem artefato Figma atual.' },
  },
}

describe('AnalyticsRuntimeIntelligenceView', () => {
  beforeEach(() => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockPayload),
      }),
    )
  })

  it('mantem production readiness bloqueado sem evidencia externa', async () => {
    const wrapper = mount(AnalyticsRuntimeIntelligenceView)

    await vi.dynamicImportSettled()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.get('#titulo-ari').text()).toBe('Inteligência operacional de indicadores')
    expect(wrapper.text()).toContain('Evidência externa pendente')
    expect(wrapper.text()).toContain('Bloqueado')
    expect(wrapper.text()).toContain('EVIDENCIA_AUSENTE')
    expect(wrapper.text()).toContain('Sem artefato Figma atual')
  })
})
