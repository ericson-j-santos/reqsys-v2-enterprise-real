import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick, reactive } from 'vue'
import { mount } from '@vue/test-utils'
import { useUserJourneyTelemetry, __userJourneyTelemetryInternals } from '../useUserJourneyTelemetry'

function mountComposable(route) {
  let exposed
  const wrapper = mount({
    template: '<div />',
    setup() {
      exposed = useUserJourneyTelemetry(route)
      return {}
    },
  })
  return { wrapper, exposed }
}

describe('useUserJourneyTelemetry', () => {
  beforeEach(() => {
    vi.spyOn(performance, 'now').mockReturnValue(1000)
  })

  it('sanitiza query string mantendo apenas chaves seguras', () => {
    const sanitized = __userJourneyTelemetryInternals.sanitizeQuery({
      status: 'pendente',
      token: 'segredo',
      cpf: '12345678901',
      tab: 'resumo',
    })

    expect(sanitized).toEqual({ status: 'pendente', tab: 'resumo' })
  })

  it('registra montagem e estado disponível sem expor dados sensíveis', async () => {
    const route = reactive({ path: '/home', fullPath: '/home', query: { status: 'pendente', cpf: '123' } })
    const { wrapper, exposed } = mountComposable(route)

    await nextTick()

    expect(exposed.eventCount.value).toBe(2)
    expect(exposed.telemetrySummary.value.current_state).toBe('success')
    expect(exposed.events.value[0].query).toEqual({ status: 'pendente' })

    wrapper.unmount()
  })

  it('mede tempo até a primeira ação primária', async () => {
    const route = reactive({ path: '/workspace', fullPath: '/workspace', query: {} })
    const { wrapper, exposed } = mountComposable(route)

    vi.mocked(performance.now).mockReturnValue(1450)
    exposed.markPrimaryAction('/requisitos')

    expect(exposed.timeToPrimaryActionMs.value).toBe(450)
    expect(exposed.latestEvent.value.type).toBe('primary_action')
    expect(exposed.latestEvent.value.details.target).toBe('/requisitos')

    wrapper.unmount()
  })

  it('registra navegação governada quando a rota muda', async () => {
    const route = reactive({ path: '/home', fullPath: '/home', query: {} })
    const { wrapper, exposed } = mountComposable(route)

    route.path = '/analytics'
    route.fullPath = '/analytics'
    await nextTick()

    expect(exposed.latestEvent.value.type).toBe('navigation')
    expect(exposed.telemetrySummary.value.latest_path).toBe('/analytics')

    wrapper.unmount()
  })
})
