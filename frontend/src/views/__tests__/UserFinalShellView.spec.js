import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { ref, computed } from 'vue'
import UserFinalShellView from '../UserFinalShellView.vue'

vi.mock('../../composables/useAppVersion', () => ({
  useAppVersion: () => ({
    frontendVersion: '3.1.0',
    apiVersion: ref('3.1.0'),
    apiBuildShaShort: ref('abc1234'),
    versionsAligned: computed(() => true),
    hasVersionDrift: computed(() => false),
  }),
}))

const workspacePayload = {
  data: {
    metrics: [
      { id: 'prontas', value: '50%', label: 'prontidão funcional', description: 'Dados reais da API.', icon: 'mdi-account-check-outline', color: 'amber', status: 'real' },
      { id: 'dados', value: '72%', label: 'qualidade dos dados', description: 'Score real calculado.', icon: 'mdi-database-check-outline', color: 'amber', status: 'real' },
      { id: 'fluxo', value: '6 etapas', label: 'workflow de requisito', description: 'Fluxo canônico.', icon: 'mdi-source-branch-sync', color: 'blue', status: 'guiado' },
      { id: 'pendencias', value: '4', label: 'pendências operacionais', description: 'Pendências reais.', icon: 'mdi-clipboard-alert-outline', color: 'amber', status: 'real' },
    ],
    action_queue: [
      { id: 'sem-aceite', title: 'Histórias sem critério de aceite', description: 'Sem aceite.', count: '2', icon: 'mdi-format-list-checks', color: 'red' },
      { id: 'baixa-qualidade', title: 'Requisitos com baixa qualidade', description: 'Baixa qualidade.', count: '1', icon: 'mdi-auto-fix', color: 'amber' },
      { id: 'sem-rastro', title: 'Itens sem rastreabilidade', description: 'Sem rastreabilidade.', count: '1', icon: 'mdi-link-variant-off', color: 'amber' },
      { id: 'aprovacao', title: 'Aguardando aprovação', description: 'Aprovação.', count: '0', icon: 'mdi-account-clock-outline', color: 'green' },
    ],
    summary: {
      total_requisitos: 4,
      score_medio_prontidao: 72,
      pendencias_operacionais: 4,
    },
  },
}

function criarRouter(initialPath = '/home') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/home', component: UserFinalShellView },
      { path: '/workspace', component: UserFinalShellView },
      { path: '/analytics', component: UserFinalShellView },
      { path: '/ajuda', component: UserFinalShellView },
    ],
  })
  router.push(initialPath)
  return router
}

async function montar(initialPath) {
  const router = criarRouter(initialPath)
  await router.isReady()

  const wrapper = mount(UserFinalShellView, {
    global: {
      plugins: [router],
      config: { warnHandler: () => {} },
    },
  })
  await Promise.resolve()
  await Promise.resolve()
  return wrapper
}

describe('UserFinalShellView', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(workspacePayload),
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('renderiza a jornada assistida do usuário final com evidência operacional', async () => {
    const wrapper = await montar('/home')

    expect(wrapper.find('[data-testid="user-final-shell"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="user-final-guided-workspace"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="user-final-progress"]').text()).toContain('20%')
    expect(wrapper.find('[data-testid="user-final-intent-low-cognitive-load"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="user-final-intent-auditable"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="real-use-metric-prontas"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="user-final-action-queue"]').exists()).toBe(true)
  })

  it('consome workspace operacional real da API com fallback governado', async () => {
    const wrapper = await montar('/home')

    expect(fetch).toHaveBeenCalledWith(
      '/api/requisitos/workspace',
      expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }),
    )
    expect(wrapper.find('[data-testid="user-final-workspace-source"]').text()).toContain('dados reais')
    expect(wrapper.find('[data-testid="user-final-workspace-summary"]').text()).toContain('4 requisitos')
    expect(wrapper.find('[data-testid="real-use-metric-dados"]').text()).toContain('72%')
  })

  it('contextualiza workspace filtrado sem perder orientação de UX', async () => {
    const wrapper = await montar('/workspace?status=pendente')

    expect(wrapper.find('[data-testid="user-final-intent-filtered-context"]').text()).toContain('pendente')
    expect(wrapper.find('[data-testid="user-final-progress"]').text()).toContain('40%')
    expect(wrapper.text()).toContain('Filtrar pendências')
    expect(fetch).toHaveBeenCalledWith(
      '/api/requisitos/workspace?status=pendente',
      expect.any(Object),
    )
  })

  it('destaca etapa de evidência na visão de analytics', async () => {
    const wrapper = await montar('/analytics')

    expect(wrapper.find('[data-testid="user-final-progress"]').text()).toContain('80%')
    expect(wrapper.text()).toContain('Exportar evidência')
  })

  it('expõe resumo técnico de telemetria sanitizada da jornada', async () => {
    const wrapper = await montar('/home')

    expect(wrapper.find('[data-testid="user-final-telemetry-chip"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="user-final-telemetry-summary"]').text()).toContain('jornada')
    expect(wrapper.find('[data-testid="user-final-telemetry-summary"]').text()).toContain('eventos')
    expect(wrapper.find('[data-testid="user-final-telemetry-summary"]').text()).toContain('sanitized_route_only')
  })
})
