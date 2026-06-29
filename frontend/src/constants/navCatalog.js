/**
 * Catálogo de navegação por tema/tópico de negócio.
 * Referência: Mapa da Solução (ArquiteturaView) e Trilha C · UX Operacional.
 */
export const NAV_TEMAS = [
  {
    id: 'operacao',
    title: 'Operação',
    topic: 'Trilha C · visão executiva',
    icon: 'mdi-view-dashboard',
    items: [
      { to: '/', icon: 'mdi-view-dashboard', title: 'Dashboard', tip: 'Visão consolidada das métricas e acessos rápidos.' },
      { to: '/monitoramento-operacional', icon: 'mdi-monitor-dashboard', title: 'Monitoramento', tip: 'Estado operacional de PRs, gates, integrações e pendências.' },
      { to: '/analytics', icon: 'mdi-chart-timeline-variant', title: 'Analytics', tip: 'Hub navegável com semáforo operacional e drill-down filtrado.' },
      { to: '/estatisticas', icon: 'mdi-chart-box-outline', title: 'Estatísticas', tip: 'Indicadores auditáveis com fonte, fórmula e analítico.' },
    ],
  },
  {
    id: 'requisitos',
    title: 'Requisitos',
    topic: 'Demanda · entrega',
    icon: 'mdi-file-document-edit',
    items: [
      { to: '/requisitos', icon: 'mdi-file-document-edit', title: 'Requisitos', tip: 'Cadastro, listagem e acompanhamento dos requisitos.' },
      { to: '/pipeline', icon: 'mdi-pipe', title: 'Pipeline', tip: 'Fluxo operacional do requisito até a publicação.' },
      { to: '/task-console', icon: 'mdi-clipboard-check-outline', title: 'Task Console', tip: 'Revisar tarefas e preparar envio ao Planner.' },
      { to: '/agile-runtime', icon: 'mdi-source-branch', title: 'Agile Runtime', tip: 'Work items no GitHub com branch e ambiente corretos.' },
      { to: '/rastreabilidade', icon: 'mdi-vector-link', title: 'Rastreabilidade', tip: 'Matriz requisito → história → entrega.' },
    ],
  },
  {
    id: 'inteligencia',
    title: 'Inteligência',
    topic: 'IA · qualidade',
    icon: 'mdi-brain',
    items: [
      { to: '/qualidade-ia', icon: 'mdi-brain', title: 'Qualidade IA', tip: 'Score e tendência de qualidade do módulo de IA.' },
      { to: '/recomendacoes-ia', icon: 'mdi-robot-outline', title: 'Recomendações IA', tip: 'Recomendações geradas por IA com decisão e outcome.' },
      { to: '/govbi-ia', icon: 'mdi-database-search', title: 'GovBI IA', tip: 'Consultas analíticas em linguagem natural governada.' },
    ],
  },
  {
    id: 'integracoes',
    title: 'Integrações',
    topic: 'Low-code · conectores',
    icon: 'mdi-connection',
    items: [
      { to: '/painel-integracao', icon: 'mdi-view-dashboard-outline', title: 'Integrações', tip: 'Planner, Teams e histórico de eventos.' },
      { to: '/hub-lowcode', icon: 'mdi-lightning-bolt-circle', title: 'Hub Low-Code', tip: 'Pacotes IA, Power Automate, bot ReqSysAgent e ALM.' },
      { to: '/figma-github', icon: 'mdi-vector-square', title: 'Figma GitHub', tip: 'Sincronização Figma ↔ GitHub com retorno em tela.' },
    ],
  },
  {
    id: 'governanca',
    title: 'Governança',
    topic: 'Conformidade · auditoria',
    icon: 'mdi-shield-check-outline',
    items: [
      { to: '/auditoria', icon: 'mdi-shield-search', title: 'Auditoria', tip: 'Linha do tempo de eventos e governança operacional.' },
      { to: '/segredos-status', icon: 'mdi-key-chain-variant', title: 'Segredos', tip: 'Diagnóstico da origem dos segredos do backend.' },
      { to: '/relatorios', icon: 'mdi-file-chart-outline', title: 'Relatórios SSRS', tip: 'Catálogo e status dos relatórios SSRS.' },
      { to: '/specs', icon: 'mdi-file-code-outline', title: 'Specs SDD', tip: 'Especificações de features do my-first-spec-project.' },
      { to: '/governanca', icon: 'mdi-shield-check-outline', title: 'Governança', tip: 'Padrão Ouro Enterprise: gates, CI/CD e observabilidade.' },
    ],
  },
  {
    id: 'arquitetura',
    title: 'Arquitetura',
    topic: 'Mapa · ecossistema',
    icon: 'mdi-sitemap',
    items: [
      { to: '/arquitetura', icon: 'mdi-sitemap', title: 'Mapa da Solução', tip: 'Visão completa dos componentes Web e Low-Code.' },
    ],
  },
]

/** Lista plana (compatibilidade com testes e buscas). */
export const NAV_ITEMS_FLAT = NAV_TEMAS.flatMap((tema) =>
  tema.items.map((item) => ({ ...item, temaId: tema.id, temaTitle: tema.title })),
)

export function temaIdPorRota(path) {
  const normalizado = path === '/' ? '/' : path.replace(/\/$/, '')
  const tema = NAV_TEMAS.find((grupo) =>
    grupo.items.some((item) => item.to === normalizado || (normalizado !== '/' && normalizado.startsWith(item.to + '/'))),
  )
  return tema?.id ?? NAV_TEMAS[0].id
}

export function temaPorId(id) {
  return NAV_TEMAS.find((tema) => tema.id === id) ?? NAV_TEMAS[0]
}

export function itemPorRota(path) {
  const normalizado = path === '/' ? '/' : path.replace(/\/$/, '')
  return NAV_ITEMS_FLAT.find((item) => item.to === normalizado)
}
