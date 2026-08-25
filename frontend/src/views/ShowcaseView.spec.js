import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it } from 'vitest'
import ShowcaseView from './ShowcaseView.vue'

describe('ShowcaseView', () => {
  it('expõe somente conteúdo demonstrativo e os cinco cenários versionados', () => {
    const wrapper = mount(ShowcaseView)

    expect(wrapper.get('[data-testid="demo-banner"]').text()).toContain('AMBIENTE DE DEMONSTRAÇÃO')
    expect(wrapper.text()).toContain('DADOS FICTÍCIOS')
    expect(wrapper.get('[data-testid="scenario-grid"]').findAll('button')).toHaveLength(5)
    expect(wrapper.text()).toContain('Happy Path')
    expect(wrapper.text()).toContain('IA / OCR com revisão governada')
    expect(wrapper.text()).toContain('Ação humana governada')
  })

  it('demonstra falha externa com retry, isolamento e DLQ sem perder a demanda', async () => {
    const wrapper = mount(ShowcaseView)

    await wrapper.get('[data-testid="scenario-outage"]').trigger('click')
    await wrapper.get('[data-testid="run-all"]').trigger('click')
    await nextTick()

    expect(wrapper.get('[data-testid="demo-status"]').text()).toContain('Cenário concluído')
    expect(wrapper.get('[data-testid="evidence-card"]').text()).toContain('HTTP 503 simulado')
    expect(wrapper.get('[data-testid="evidence-card"]').text()).toContain('Quarentena / DLQ')
    expect(wrapper.get('[data-testid="scenario-result"]').text()).toContain('Demanda preservada em quarentena')
  })

  it('revela controles de arquitetura apenas na profundidade técnica', async () => {
    const wrapper = mount(ShowcaseView)
    const audienceButtons = wrapper.get('[data-testid="audience-toggle"]').findAll('button')

    expect(wrapper.find('[data-testid="technical-panel"]').exists()).toBe(false)
    await audienceButtons[2].trigger('click')
    await nextTick()

    expect(wrapper.get('[data-testid="technical-panel"]').text()).toContain('backpressure')
    expect(wrapper.get('[data-testid="technical-panel"]').text()).toContain('DLQ / quarentena')
    expect(wrapper.get('[data-testid="technical-panel"]').text()).toContain('correlation_id')
  })
})
