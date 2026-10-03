import { beforeEach, describe, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import DashboardView from '../DashboardView.vue'

const { push, store } = vi.hoisted(() => ({
  push: vi.fn(),
  store: {
    metricas: {},
    metricasColeta: {},
    dashboardInfo: {},
    qualidadeIAResumo: {},
    carregarMetricas: vi.fn().mockResolvedValue(),
    carregarMetricasColeta: vi.fn().mockResolvedValue(),
    carregarDashboardInfo: vi.fn().mockResolvedValue(),
    carregarQualidadeIA: vi.fn().mockResolvedValue(),
  },
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('../../stores/requisitos', () => ({ useRequisitosStore: () => store }))

describe('DashboardView: acesso visivel ao Painel de projetos', () => {
  beforeEach(() => push.mockReset())

  it('oferece atalho no topo e abre a rota canonica', async () => {
    const wrapper = shallowMount(DashboardView, {
      global: {
        stubs: { VBtn: { template: '<button><slot /></button>' } },
      },
    })
    const shortcut = wrapper.get('[data-testid="dashboard-abrir-painel-projetos"]')

    expect(shortcut.text()).toContain('Abrir Painel de projetos')
    await shortcut.trigger('click')

    expect(push).toHaveBeenCalledWith({ path: '/painel-projetos' })
  })
})
