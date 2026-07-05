/**
 * Catálogo de navegação por tema/tópico de negócio.
 *
 * Diretriz UX real:
 * - as primeiras áreas devem apoiar o trabalho diário do analista/PO;
 * - recursos técnicos ficam em Administração, Governança ou Arquitetura;
 * - o usuário final não deve precisar entender CI, runtime ou infraestrutura para cadastrar e acompanhar uma demanda.
 */
export const NAV_TEMAS = [
  {
    id: 'trabalho',
    title: 'Meu trabalho',
    topic: 'Pendências · jornada diária',
    icon: 'mdi-clipboard-check-outline',
    items: [
      { to: '/', icon: 'mdi-view-dashboard', title: 'Painel do dia', tip: 'Resumo objetivo das pendências, qualidade e próximos passos.' },
      { to: '/requisitos', icon: 'mdi-file-document-edit', title: 'Demandas e requisitos', tip: 'Cadastrar, revisar e acompanhar requisitos de negócio.' },
      { to: '/pipeline', icon: 'mdi-pipe', title: 'Fluxo de aprovação', tip: 'Acompanhar a demanda da entrada até aprovação/publicação.' },
      { to: '/rastreabilidade', icon: 'mdi-vector-link', title: 'Rastreabilidade', tip: 'Ver origem, história, decisão, entrega e evidências.' },
    ],
  },
  {
    id: 'requisitos',
    title: 'Engenharia de requisitos',
    topic: 'Entrada · refinamento · publicação',
    icon: 'mdi-file-document-edit',
    subgroups: [
      {
        id: 'entrada',
        title: 'Entrada',
        topic: 'Captura, triagem e cadastro',
        paths: ['/requisitos'],
      },
      {
        id: 'pipeline',
        title: 'Refinamento e fluxo',
        topic: 'Qualidade, IA, histórias e aprovação',
        paths: ['/pipeline', '/agile-runtime'],
      },
      {
        id: 'publicacao',
        title: 'Publicação',
        topic: 'Rastreio e entrega',
        paths: ['/rastreabilidade'],
      },
    ],
    items: [
      { to: '/requisitos', icon: 'mdi-file-document-edit', title: 'Requisitos', tip: 'Cadastro, listagem e acompanhamento dos requisitos.', subgroupId: 'entrada' },
      { to: '/qualidade-ia', icon: 'mdi-brain', title: 'Qualidade IA', tip: 'Score de completude, clareza e testabilidade dos requisitos.' },
      { to: '/recomendacoes-ia', icon: 'mdi-robot-outline', title: 'Recomendações IA', tip: 'Sugestões governadas para melhorar requisitos e histórias.' },
      { to: '/task-console', icon: 'mdi-clipboard-check-outline', title: 'Preparar tarefas', tip: 'Revisar tarefas antes de enviar para Planner ou ferramenta de entrega.' },
      { to: '/pipeline', icon: 'mdi-pipe', title: 'Pipeline', tip: 'Fluxo operacional do requisito até aprovação e publicação.', subgroupId: 'pipeline' },
      { to: '/agile-runtime', icon: 'mdi-source-branch', title: 'Agile Runtime', tip: 'Work items com branch, PR e ambiente corretos.', subgroupId: 'pipeline' },
      { to: '/rastreabilidade', icon: 'mdi-vector-link', title: 'Rastreabilidade', tip: 'Matriz requisito → história → entrega → evidência.', subgroupId: 'publicacao' },
    ],
  },
  {
    id: 'analise',
    title: 'Análise e indicadores',
    topic: 'Gestão · qualidade · valor',
    icon: 'mdi-chart-timeline-variant',
    items: [
      { to: '/analytics', icon: 'mdi-chart-timeline-variant', title: 'Analytics', tip: 'Indicadores executivos com drill-down.' },
      { to: '/estatisticas', icon: 'mdi-chart-box-outline', title: 'Estatísticas', tip: 'Indicadores auditáveis com fonte, fórmula e analítico.' },
      { to: '/relatorios', icon: 'mdi-file-chart-outline', title: 'Relatórios', tip: 'Catálogo e status de relatórios corporativos.' },
      { to: '/govbi-ia', icon: 'mdi-database-search', title: 'GovBI IA', tip: 'Consultas analíticas em linguagem natural governada.' },
    ],
  },
  {
    id: 'integracoes',
    title: 'Integrações',
    topic: 'Ferramentas · conectores',
    icon: 'mdi-connection',
    items: [
      { to: '/painel-integracao', icon: 'mdi-view-dashboard-outline', title: 'Integrações', tip: 'Planner, Teams, GitHub e histórico de eventos.' },
      { to: '/hub-lowcode', icon: 'mdi-lightning-bolt-circle', title: 'Hub Low-Code', tip: 'Power Automate, Power Apps, bot ReqSysAgent e ALM.' },
      { to: '/figma-github', icon: 'mdi-vector-square', title: 'Figma GitHub', tip: 'Sincronização Figma ↔ GitHub com retorno em tela.' },
    ],
  },
  {
    id: 'administracao',
    title: 'Administração',
    topic: 'Operação técnica · governança',
    icon: 'mdi-shield-check-outline',
    items: [
      { to: '/monitoramento-operacional', icon: 'mdi-monitor-dashboard', title: 'Monitoramento', tip: 'Estado técnico de integrações, gates, runtime e pendências operacionais.' },
      { to: '/auditoria', icon: 'mdi-shield-search', title: 'Auditoria', tip: 'Linha do tempo de eventos e governança operacional.' },
      { to: '/segredos-status', icon: 'mdi-key-chain-variant', title: 'Segredos', tip: 'Diagnóstico da origem dos segredos do backend.' },
      { to: '/specs', icon: 'mdi-file-code-outline', title: 'Specs SDD', tip: 'Especificações técnicas e contratos de features.' },
      { to: '/governanca', icon: 'mdi-shield-check-outline', title: 'Governança', tip: 'Gates, CI/CD, observabilidade, políticas e evidências.' },
      { to: '/codex', icon: 'mdi-code-braces', title: 'Codex', tip: 'Análise de código com LLM local ou mock, governada pelo ReqSys.' },
    ],
  },
  {
    id: 'arquitetura',
    title: 'Arquitetura',
    topic: 'Mapa · ecossistema',
    icon: 'mdi-sitemap',
    items: [
      { to: '/arquitetura', icon: 'mdi-sitemap', title: 'Mapa da Solução', tip: 'Visão completa dos componentes Web, backend, integrações e Low-Code.' },
    ],
  },
]

/** Lista plana (compatibilidade com testes e buscas). */
export const NAV_ITEMS_FLAT = NAV_TEMAS.flatMap((tema) =>
  tema.items.map((item) => ({ ...item, temaId: tema.id, temaTitle: tema.title })),
)

function normalizarRota(path) {
  return path === '/' ? '/' : path.replace(/\/$/, '')
}

function rotaCorresponde(pathAtual, rotaCatalogo) {
  return pathAtual === rotaCatalogo || (pathAtual !== '/' && pathAtual.startsWith(rotaCatalogo + '/'))
}

function resolverSubgrupoCanonico(path) {
  const normalizado = normalizarRota(path)
  for (const tema of NAV_TEMAS) {
    const subgrupo = tema.subgroups?.find((sub) =>
      sub.paths.some((rota) => rotaCorresponde(normalizado, rota)),
    )
    if (subgrupo) return { tema, subgrupo }
  }
  return null
}

export function temaIdPorRota(path) {
  const subgrupoCanonico = resolverSubgrupoCanonico(path)
  if (subgrupoCanonico) return subgrupoCanonico.tema.id

  const normalizado = normalizarRota(path)
  const tema = NAV_TEMAS.find((grupo) =>
    grupo.items.some((item) => rotaCorresponde(normalizado, item.to)),
  )
  return tema?.id ?? NAV_TEMAS[0].id
}

export function temaPorId(id) {
  return NAV_TEMAS.find((tema) => tema.id === id) ?? NAV_TEMAS[0]
}

export function itemPorRota(path) {
  const normalizado = normalizarRota(path)
  return NAV_ITEMS_FLAT.find((item) => item.to === normalizado)
}

export function subgrupoIdPorRota(path) {
  const subgrupoCanonico = resolverSubgrupoCanonico(path)
  if (subgrupoCanonico) return subgrupoCanonico.subgrupo.id

  const item = itemPorRota(path)
  if (item?.subgroupId) return item.subgroupId
  const tema = temaPorId(temaIdPorRota(path))
  return tema.subgroups?.[0]?.id ?? null
}

export function itensDoSubgrupo(temaId, subgrupoId) {
  const tema = temaPorId(temaId)
  if (!tema.subgroups?.length) return tema.items
  const sub = tema.subgroups.find((s) => s.id === subgrupoId) ?? tema.subgroups[0]
  const paths = new Set(sub.paths)
  return tema.items.filter((item) => paths.has(item.to))
}

export function subgrupoAtual(temaId, subgrupoId) {
  const tema = temaPorId(temaId)
  return tema.subgroups?.find((s) => s.id === subgrupoId) ?? tema.subgroups?.[0] ?? null
}

export function temaTemSubgrupos(temaId) {
  return Boolean(temaPorId(temaId).subgroups?.length)
}
