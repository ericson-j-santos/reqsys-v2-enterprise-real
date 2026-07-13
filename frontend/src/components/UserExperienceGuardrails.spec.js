import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import UserExperienceGuardrails from './UserExperienceGuardrails.vue'

const route = reactive({
  fullPath: '/dashboard',
  name: 'Dashboard',
  meta: { title: 'Painel executivo' },
})

vi.mock('vue-router', () => ({
  useRoute: () => route,
}))

describe('UserExperienceGuardrails', () => {
  beforeEach(() => {
    document.body.innerHTML = '<main class="req-main"></main>'
    Object.defineProperty(window.navigator, 'onLine', {
      configurable: true,
      value: true,
    })
    route.fullPath = '/dashboard'
    route.name = 'Dashboard'
    route.meta = { title: 'Painel executivo' }
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('prepara o conteúdo principal e anuncia a tela atual', () => {
    const wrapper = mount(UserExperienceGuardrails)
    const main = document.querySelector('.req-main')

    expect(wrapper.get('.req-skip-link').attributes('href')).toBe('#reqsys-main-content')
    expect(main.id).toBe('reqsys-main-content')
    expect(main.getAttribute('tabindex')).toBe('-1')
    expect(main.getAttribute('aria-label')).toBe('Conteúdo principal')
    expect(wrapper.get('[data-testid="route-announcement"]').text()).toContain('Painel executivo')
  })

  it('move o foco para o conteúdo após mudança de rota', async () => {
    const main = document.querySelector('.req-main')
    const focusSpy = vi.spyOn(main, 'focus')
    mount(UserExperienceGuardrails)

    route.fullPath = '/requisitos'
    route.meta = { title: 'Requisitos' }
    await nextTick()
    await nextTick()

    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true })
  })

  it('informa perda e recuperação de conectividade', async () => {
    const wrapper = mount(UserExperienceGuardrails)

    Object.defineProperty(window.navigator, 'onLine', {
      configurable: true,
      value: false,
    })
    window.dispatchEvent(new Event('offline'))
    await nextTick()
    expect(wrapper.get('[data-testid="offline-alert"]').text()).toContain('Conexão indisponível')

    Object.defineProperty(window.navigator, 'onLine', {
      configurable: true,
      value: true,
    })
    window.dispatchEvent(new Event('online'))
    await nextTick()
    expect(wrapper.find('[data-testid="offline-alert"]').exists()).toBe(false)
  })
})
