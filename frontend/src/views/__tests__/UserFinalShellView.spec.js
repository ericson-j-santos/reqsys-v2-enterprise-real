import { describe, it, expect, vi } from 'vitest'
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

  return mount(UserFinalShellView, {
    global: {
      plugins: [router],
      config: { warnHandler: () => {} },
    },
  })
}

describe('UserFinalShellView', () => {
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

  it('contextualiza workspace filtrado sem perder orientação de UX', async () => {
    const wrapper = await montar('/workspace?status=pendente')

    expect(wrapper.find('[data-testid="user-final-intent-filtered-context"]').text()).toContain('pendente')
    expect(wrapper.find('[data-testid="user-final-progress"]').text()).toContain('40%')
    expect(wrapper.text()).toContain('Filtrar pendências')
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
