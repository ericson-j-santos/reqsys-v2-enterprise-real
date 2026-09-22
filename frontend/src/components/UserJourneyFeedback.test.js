import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import UserJourneyFeedback from './UserJourneyFeedback.vue'
import { clearJourneyFeedback, showJourneyError, showJourneyLoading, showJourneySuccess } from '../services/userJourneyFeedback'

const global = {
  stubs: {
    VProgressLinear: { template: '<div data-testid="journey-loading" />' },
    VSnackbar: {
      props: ['modelValue'],
      template: '<div v-if="modelValue" data-testid="journey-feedback"><slot/><slot name="actions"/></div>',
    },
    VIcon: { template: '<span />' },
    VBtn: { template: '<button @click="$emit(\'click\')"><slot/></button>' },
  },
}

describe('UserJourneyFeedback', () => {
  it('exibe carregamento e permite limpar o estado', async () => {
    const wrapper = mount(UserJourneyFeedback, { global })
    showJourneyLoading('Carregando painel')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Carregando painel')
    expect(wrapper.find('[data-testid="journey-loading"]').exists()).toBe(true)

    clearJourneyFeedback()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="journey-feedback"]').exists()).toBe(false)
  })

  it('exibe sucesso acessível', async () => {
    const wrapper = mount(UserJourneyFeedback, { global })
    showJourneySuccess('Dados atualizados')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Dados atualizados')
  })

  it('oferece recuperação para erros acionáveis', async () => {
    const retry = vi.fn()
    const wrapper = mount(UserJourneyFeedback, { global })
    showJourneyError('Falha ao carregar', retry)
    await wrapper.vm.$nextTick()

    const button = wrapper.find('[data-testid="journey-retry"]')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    expect(retry).toHaveBeenCalledOnce()
  })
})
