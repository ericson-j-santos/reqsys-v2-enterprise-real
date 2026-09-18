import { computed, onMounted, ref, watch } from 'vue'

const SAFE_ROUTE_QUERY_KEYS = ['status', 'view', 'tab']
const MAX_EVENTS = 25

function nowMs() {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return Math.round(performance.now())
  }
  return Date.now()
}

function sanitizeQuery(query = {}) {
  return Object.fromEntries(
    Object.entries(query)
      .filter(([key]) => SAFE_ROUTE_QUERY_KEYS.includes(key))
      .map(([key, value]) => [key, String(value).slice(0, 48)]),
  )
}

function createEvent(type, route, details = {}, getNowMs = nowMs) {
  return {
    type,
    path: route?.path || '/',
    query: sanitizeQuery(route?.query),
    timestamp_ms: getNowMs(),
    details,
  }
}

export function useUserJourneyTelemetry(route, options = {}) {
  const maxEvents = options.maxEvents || MAX_EVENTS
  const getNowMs = typeof options.nowMs === 'function' ? options.nowMs : nowMs
  const startedAtMs = getNowMs()
  const events = ref([])
  const primaryActionAtMs = ref(null)
  const currentState = ref('loading')

  function pushEvent(type, details = {}) {
    const event = createEvent(type, route, details, getNowMs)
    events.value = [...events.value.slice(-(maxEvents - 1)), event]
    return event
  }

  function markState(state, details = {}) {
    currentState.value = state
    return pushEvent('state_change', { state, ...details })
  }

  function markPrimaryAction(target) {
    if (!primaryActionAtMs.value) {
      primaryActionAtMs.value = getNowMs()
    }
    return pushEvent('primary_action', {
      target: String(target || '').slice(0, 96),
      time_to_action_ms: timeToPrimaryActionMs.value,
    })
  }

  const timeOnJourneyMs = computed(() => Math.max(getNowMs() - startedAtMs, 0))
  const timeToPrimaryActionMs = computed(() => {
    if (!primaryActionAtMs.value) return null
    return Math.max(primaryActionAtMs.value - startedAtMs, 0)
  })
  const latestEvent = computed(() => events.value.at(-1) || null)
  const eventCount = computed(() => events.value.length)
  const telemetrySummary = computed(() => ({
    current_state: currentState.value,
    event_count: eventCount.value,
    latest_event_type: latestEvent.value?.type || null,
    latest_path: latestEvent.value?.path || route?.path || '/',
    time_on_journey_ms: timeOnJourneyMs.value,
    time_to_primary_action_ms: timeToPrimaryActionMs.value,
    pii_policy: 'sanitized_route_only',
  }))

  onMounted(() => {
    pushEvent('journey_mount', { state: currentState.value })
    markState('success')
  })

  watch(
    () => route.fullPath,
    (to, from) => {
      if (!from || to === from) return
      pushEvent('navigation', { from: String(from).slice(0, 96), to: String(to).slice(0, 96) })
    },
  )

  return {
    events,
    currentState,
    latestEvent,
    eventCount,
    telemetrySummary,
    timeOnJourneyMs,
    timeToPrimaryActionMs,
    pushEvent,
    markState,
    markPrimaryAction,
  }
}

export const __userJourneyTelemetryInternals = {
  sanitizeQuery,
  createEvent,
}
