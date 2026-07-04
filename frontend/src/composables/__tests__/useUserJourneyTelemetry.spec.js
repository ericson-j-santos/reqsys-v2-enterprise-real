import { describe, it, expect } from 'vitest'
import { nextTick, reactive } from 'vue'
import { mount } from '@vue/test-utils'
import { useUserJourneyTelemetry, __userJourneyTelemetryInternals } from '../useUserJourneyTelemetry'

async function mountComposable(route, options = {}) {
  let exposed
  const wrapper = mount({
    template: '<div />',
    setup() {
      exposed = useUserJourneyTelemetry(route, options)
      return {}
    },
  })

  // Garante que os hooks de montagem e watchers iniciais do Vue sejam drenados
  // antes das asserções. Isso evita corrida entre o runner CI e o lifecycle.
  await nextTick()
  await nextTick()

  return { wrapper, exposed }
}

describe('useUserJourneyTelemetry', () => {
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
    const { wrapper, exposed } = await mountComposable(route, { nowMs: () => 1000 })

    expect(exposed.eventCount.value).toBe(2)
    expect(exposed.telemetrySummary.value.current_state).toBe('success')
    expect(exposed.events.value[0].query).toEqual({ status: 'pendente' })

    wrapper.unmount()
  })

  it('mede tempo até a primeira ação primária', async () => {
    const route = reactive({ path: '/workspace', fullPath: '/workspace', query: {} })
    let currentNowMs = 1000
    const { wrapper, exposed } = await mountComposable(route, { nowMs: () => currentNowMs })

    currentNowMs = 1450
    exposed.markPrimaryAction('/requisitos')

    expect(exposed.timeToPrimaryActionMs.value).toBe(450)
    expect(exposed.latestEvent.value.type).toBe('primary_action')
    expect(exposed.latestEvent.value.details.target).toBe('/requisitos')

    wrapper.unmount()
  })

  it('registra navegação governada quando a rota muda', async () => {
    const route = reactive({ path: '/home', fullPath: '/home', query: {} })
    const { wrapper, exposed } = await mountComposable(route, { nowMs: () => 1000 })

    route.path = '/analytics'
    route.fullPath = '/analytics'
    await nextTick()
    await nextTick()

    expect(exposed.latestEvent.value.type).toBe('navigation')
    expect(exposed.telemetrySummary.value.latest_path).toBe('/analytics')

    wrapper.unmount()
  })
})
