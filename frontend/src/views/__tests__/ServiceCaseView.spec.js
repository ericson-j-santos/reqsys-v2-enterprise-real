import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ServiceCaseView from '../ServiceCaseView.vue'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

vi.mock('../../services/api', () => ({ api: apiMock }))

function payload(overrides = {}) {
  return {
    case_id: 'case-123',
    case_type: 'REQUEST',
    service_id: 'service-1',
    requester: 'eri',
    impact: 'MEDIUM',
    urgency: 'HIGH',
    priority: 'P2',
    state: 'NEW',
    correlation_id: 'corr-rsm-05',
    version: 1,
    allowed_transitions: ['CANCELED', 'TRIAGE'],
    events: [
      {
        event_id: 'event-1',
        event_type: 'CASE_CREATED',
        from_state: null,
        to_state: 'NEW',
        correlation_id: 'corr-rsm-05',
      },
    ],
    ...overrides,
  }
}

async function montar(caseId = 'case-123') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/service-cases/:caseId?', component: ServiceCaseView },
    ],
  })
  await router.push(`/service-cases/${caseId}`)
  await router.isReady()
  const wrapper = mount(ServiceCaseView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('ServiceCaseView', () => {
  beforeEach(() => {
    apiMock.get.mockReset()
    apiMock.post.mockReset()
  })

  it('renderiza somente transições autorizadas pelo backend e relê o estado após mutação', async () => {
    apiMock.get
      .mockResolvedValueOnce({ data: { data: payload() } })
      .mockResolvedValueOnce({
        data: {
          data: payload({
            state: 'TRIAGE',
            version: 2,
            allowed_transitions: ['CANCELED', 'IN_PROGRESS', 'PENDING_APPROVAL'],
          }),
        },
      })
    apiMock.post.mockResolvedValue({ data: { data: { case: payload({ state: 'TRIAGE', version: 2 }) } } })

    const wrapper = await montar()

    expect(wrapper.find('[data-testid="transition-TRIAGE"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="transition-CANCELED"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="transition-CLOSED"]').exists()).toBe(false)

    await wrapper.get('[data-testid="transition-TRIAGE"]').trigger('click')
    await flushPromises()

    expect(apiMock.post).toHaveBeenCalledTimes(1)
    expect(apiMock.post.mock.calls[0][0]).toBe('/v1/service-cases/case-123/transitions')
    expect(apiMock.post.mock.calls[0][1]).toEqual(expect.objectContaining({
      target_state: 'TRIAGE',
      expected_version: 1,
    }))
    expect(apiMock.get).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="service-case-state"]').text()).toContain('Triagem')
    expect(wrapper.get('[data-testid="service-case-success"]').text()).toContain('Estado persistido confirmado')
  })

  it('mostra rejeição do backend e mantém o estado obtido por releitura independente', async () => {
    const pending = payload({
      state: 'PENDING_APPROVAL',
      version: 3,
      allowed_transitions: ['IN_PROGRESS'],
    })
    apiMock.get
      .mockResolvedValueOnce({ data: { data: pending } })
      .mockResolvedValueOnce({ data: { data: pending } })
    apiMock.post.mockRejectedValue({
      response: { status: 409, data: { detail: 'aprovação obrigatória não satisfeita' } },
    })

    const wrapper = await montar()

    await wrapper.get('[data-testid="transition-IN_PROGRESS"]').trigger('click')
    await flushPromises()

    expect(apiMock.get).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="service-case-error"]').text()).toContain('aprovação obrigatória')
    expect(wrapper.get('[data-testid="service-case-state"]').text()).toContain('Aguardando aprovação')
    expect(wrapper.find('[data-testid="service-case-success"]').exists()).toBe(false)
  })
})
