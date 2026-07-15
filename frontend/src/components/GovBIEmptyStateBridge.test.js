import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import GovBIEmptyStateBridge, { GOVBI_EMPTY_EVENT } from './GovBIEmptyStateBridge.vue'

const global = {
  stubs: {
    VDialog: {
      props: ['modelValue'],
      template: '<div v-if="modelValue" data-testid="govbi-empty-state-dialog"><slot /></div>',
    },
    VCard: { template: '<div><slot /></div>' },
    VCardText: { template: '<div><slot /></div>' },
    VCardActions: { template: '<div><slot /></div>' },
    VBtn: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
    GovBIEmptyState: {
      emits: ['reformulate', 'retry'],
      template: '<div><button data-testid="reformulate" @click="$emit(\'reformulate\')">Reformular</button><button data-testid="retry" @click="$emit(\'retry\')">Repetir</button></div>',
    },
  },
}

describe('GovBIEmptyStateBridge', () => {
  it('exibe orientação quando a API informa resultado vazio', async () => {
    const wrapper = mount(GovBIEmptyStateBridge, { global })
    window.dispatchEvent(new CustomEvent(GOVBI_EMPTY_EVENT, { detail: { reason: 'Sem linhas.' } }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="govbi-empty-state-dialog"]').exists()).toBe(true)
  })

  it('executa novamente sem persistir payload da consulta', async () => {
    const retry = vi.fn()
    const wrapper = mount(GovBIEmptyStateBridge, { global })
    window.dispatchEvent(new CustomEvent(GOVBI_EMPTY_EVENT, { detail: { retry } }))
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-testid="retry"]').trigger('click')
    expect(retry).toHaveBeenCalledOnce()
  })
})