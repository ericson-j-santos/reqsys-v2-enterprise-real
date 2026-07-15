const EVENT_NAME = 'reqsys:user-journey-feedback'

function emit(detail) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail }))
}

export function showJourneyLoading(message = 'Carregando informações…') {
  emit({ type: 'loading', message, persistent: true })
}

export function showJourneySuccess(message = 'Operação concluída com sucesso.') {
  emit({ type: 'success', message })
}

export function showJourneyError(message, retry) {
  emit({ type: 'error', message: message || 'Não foi possível concluir a operação.', retry })
}

export function clearJourneyFeedback() {
  emit({ type: 'clear' })
}

export { EVENT_NAME }
