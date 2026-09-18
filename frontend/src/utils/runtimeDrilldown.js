const DRILLDOWN_SPA_MAP = {
  '/monitoramento-operacional': (card) => ({
    path: '/monitoramento-operacional',
    query: card?.id === 'pending-items' ? { estado: 'amarelo', secao: 'itens' } : {},
  }),
  '/api/runtime/health': () => ({ path: '/monitoramento-operacional', query: { secao: 'runtime' } }),
  '/api/runtime/metrics': () => ({ path: '/monitoramento-operacional', query: { secao: 'metrics' } }),
  '/api/runtime/readiness': () => ({ path: '/monitoramento-operacional', query: { secao: 'runtime', estado: 'amarelo' } }),
  '/api/runtime/liveness': () => ({ path: '/monitoramento-operacional', query: { secao: 'runtime' } }),
  '/api/runtime/contracts': () => ({ path: '/monitoramento-operacional', query: { secao: 'runtime' } }),
  '/api/runtime/analytics': () => ({ path: '/monitoramento-operacional', query: { secao: 'timeline' } }),
  '/api/runtime/dashboard': () => ({ path: '/analytics', query: {} }),
  '/estatisticas': () => ({ path: '/estatisticas', query: {} }),
  '/painel-integracao': () => ({ path: '/painel-integracao', query: {} }),
  '/': () => ({ path: '/', query: {} }),
}

export function resolverDrilldownSpa(drilldown, card = {}) {
  if (!drilldown) return null

  if (card.spa_drilldown?.path) {
    return {
      path: card.spa_drilldown.path,
      query: card.spa_drilldown.query || {},
    }
  }

  const resolver = DRILLDOWN_SPA_MAP[drilldown]
  if (resolver) return resolver(card)

  if (drilldown.startsWith('/') && !drilldown.startsWith('/api')) {
    return { path: drilldown, query: {} }
  }

  return { path: '/monitoramento-operacional', query: { secao: 'runtime' } }
}

export function mapearCardsComDrilldown(cards = []) {
  return cards.map((card) => ({
    ...card,
    rotaSpa: resolverDrilldownSpa(card.spa_drilldown?.path || card.drilldown, card),
  }))
}
