import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import GuidedEmptyState from './GuidedEmptyState.vue'
import GovBIEmptyState from './GovBIEmptyState.vue'
import OperationalDashboardEmptyState from './OperationalDashboardEmptyState.vue'
import { readEmptyStateTelemetry } from '../services/emptyStateTelemetry'

const global = {
  stubs: {
    VIcon: { template: '<span />' },
    VBtn: { template: '<button><slot/></button>' },
  },
}

describe('GuidedEmptyState', () => {
  beforeEach(() => sessionStorage.clear())

  it('explica ausência de dados, oferece ação e registra visualização', async () => {
    const wrapper = mount(GuidedEmptyState, {
      global,
      props: {
        context: 'test-context',
        title: 'Sem dados',
        description: 'Não há registros disponíveis.',
        reason: 'Filtros restritivos.',
        actionLabel: 'Atualizar',
      },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Sem dados')
    expect(wrapper.text()).toContain('Filtros restritivos')
    expect(readEmptyStateTelemetry()).toEqual(expect.arrayContaining([
      expect.objectContaining({ context: 'test-context', event: 'view' }),
    ]))
  })

  it('emite ação principal e registra telemetria', async () => {
    const wrapper = mount(GuidedEmptyState, {
      global,
      props: {
        context: 'test-action',
        title: 'Sem dados',
        description: 'Descrição',
        actionLabel: 'Continuar',
      },
    })
    await wrapper.find('[data-testid="guided-empty-state-primary-action"]').trigger('click')
    expect(wrapper.emitted('activate')).toHaveLength(1)
    expect(readEmptyStateTelemetry()).toEqual(expect.arrayContaining([
      expect.objectContaining({ context: 'test-action', event: 'primary_action' }),
    ]))
  })

  it('especializa ações do GovBI IA', async () => {
    const wrapper = mount(GovBIEmptyState, { global })
    expect(wrapper.text()).toContain('Reformular pergunta')
    expect(wrapper.text()).toContain('Executar novamente')
  })

  it('especializa ações dos dashboards operacionais', async () => {
    const wrapper = mount(OperationalDashboardEmptyState, { global })
    expect(wrapper.text()).toContain('Atualizar dados')
    expect(wrapper.text()).toContain('Limpar filtros')
  })
})
