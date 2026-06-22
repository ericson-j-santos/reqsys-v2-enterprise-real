import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AnalyticsRuntimeIntelligenceView from '../AnalyticsRuntimeIntelligenceView.vue'

const mockSnapshot = {
  success: true,
  data: {
    health_score: 92,
    confidence_score: 92,
    ai_governance_score: 89,
    operational_quality_score: 91,
    production_ready: false,
    draft_recomendado: true,
    figma: {
      status: 'aguardando_plano_figma',
      artefato: 'Enterprise Operations Center / Analytics Runtime Intelligence',
      objetivo: 'retorno visual em tela para ARI, Figma e GitHub',
    },
    readiness_matrix: [
      {
        capability: 'Backend ARI',
        estado: 'VALIDADO',
        evidencia: 'Endpoint snapshot e testes backend verdes.',
        gap: 'Conectar adapter real por fonte.',
        cor: 'verde',
        bloqueia_producao: false,
      },
      {
        capability: 'Production Readiness',
        estado: 'BLOQUEIO',
        evidencia: 'Ainda sem runtime staging validado.',
        gap: 'Manter PR em draft ate evidencia operacional.',
        cor: 'vermelho',
        bloqueia_producao: true,
      },
    ],
    production_gaps: ['Validar ARI Center em staging publicado.'],
    runtime_timeline: [
      {
        evento: 'Readiness Layer',
        estado: 'IMPLEMENTADO',
        detalhe: 'Matriz, gaps e timeline em tela.',
        cor: 'verde',
      },
    ],
    validacoes: [
      {
        codigo: 'JOIN_CARDINALITY',
        nome: 'Validar JOINs utilizados',
        categoria: 'Relacionamento',
        status: 'warn',
        score: 87,
        evidencia: 'Explosão cartesiana monitorada.',
        acao_recomendada: 'Conectar baseline real.',
      },
    ],
    guard_rails: [
      {
        regra: 'IA sem fonte ou sem grounding',
        acao: 'BLOCK',
      },
    ],
  },
}

describe('AnalyticsRuntimeIntelligenceView', () => {
  beforeEach(() => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockSnapshot),
      }),
    )
  })

  it('renderiza os indicadores principais do ARI Center e a matriz de readiness', async () => {
    const wrapper = mount(AnalyticsRuntimeIntelligenceView)

    await vi.dynamicImportSettled()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.text()).toContain('Analytics Runtime Intelligence')
    expect(wrapper.text()).toContain('Health Score')
    expect(wrapper.text()).toContain('Confidence')
    expect(wrapper.text()).toContain('IA Governance')
    expect(wrapper.text()).toContain('Operational Quality')
    expect(wrapper.text()).toContain('Operational Readiness Matrix')
    expect(wrapper.text()).toContain('DRAFT MANTIDO')
    expect(wrapper.text()).toContain('Production Readiness')
    expect(wrapper.text()).toContain('Validar ARI Center em staging publicado.')
    expect(wrapper.text()).toContain('aguardando_plano_figma')
    expect(wrapper.text()).toContain('IA sem fonte ou sem grounding')
  })
})
