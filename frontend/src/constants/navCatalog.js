/**
 * Catálogo de navegação por tema e tópico de negócio.
 *
 * Diretriz de experiência:
 * - as primeiras áreas devem apoiar o trabalho diário do analista e do responsável pelo produto;
 * - recursos técnicos ficam em Administração, Governança ou Arquitetura;
 * - o usuário final não deve precisar conhecer termos internos de integração, execução ou infraestrutura para cadastrar e acompanhar uma demanda.
 *
 * Compatibilidade com a linha principal:
 * - preserva rotas e identificadores internos para não quebrar contratos;
 * - altera apenas os textos apresentados às pessoas.
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
      { to: '/pipeline', icon: 'mdi-pipe', title: 'Fluxo de aprovação', tip: 'Acompanhar a demanda da entrada até a aprovação e publicação.' },
      { to: '/rastreabilidade', icon: 'mdi-vector-link', title: 'Rastreabilidade', tip: 'Ver origem, história, decisão, entrega e evidências.' },
    ],
  },
  {
    id: 'requisitos',
    title: 'Engenharia de requisitos',
    topic: 'Entrada · refinamento · publicação',
    icon: 'mdi-file-document-edit',
    subgroups: [
      { id: 'entrada', title: 'Entrada', topic: 'Captura, triagem e cadastro', paths: ['/requisitos'] },
      { id: 'pipeline', title: 'Refinamento e fluxo', topic: 'Qualidade, IA, histórias e aprovação', paths: ['/pipeline', '/agile-runtime'] },
      { id: 'publicacao', title: 'Publicação', topic: 'Rastreio e entrega', paths: ['/rastreabilidade'] },
    ],
    items: [
      { to: '/requisitos', icon: 'mdi-file-document-edit', title: 'Requisitos', tip: 'Cadastro, listagem e acompanhamento dos requisitos.', subgroupId: 'entrada' },
      { to: '/qualidade-ia', icon: 'mdi-brain', title: 'Qualidade IA', tip: 'Nota de completude, clareza e possibilidade de validação dos requisitos.' },
      { to: '/recomendacoes-ia', icon: 'mdi-robot-outline', title: 'Recomendações IA', tip: 'Sugestões controladas para melhorar requisitos e histórias.' },
      { to: '/task-console', icon: 'mdi-clipboard-check-outline', title: 'Preparar tarefas', tip: 'Revisar tarefas antes de enviar para Planner ou outra ferramenta de entrega.' },
      { to: '/pipeline', icon: 'mdi-pipe', title: 'Fluxo', tip: 'Fluxo do requisito até a aprovação e publicação.', subgroupId: 'pipeline' },
      { to: '/agile-runtime', icon: 'mdi-source-branch', title: 'Acompanhamento da entrega', tip: 'Itens de trabalho com versão de código, solicitação de integração e ambiente corretos.', subgroupId: 'pipeline' },
      { to: '/rastreabilidade', icon: 'mdi-vector-link', title: 'Rastreabilidade', tip: 'Matriz requisito → história → entrega → evidência.', subgroupId: 'publicacao' },
    ],
  },
  {
    id: 'analise',
    title: 'Análise e indicadores',
    topic: 'Gestão · qualidade · valor',
    icon: 'mdi-chart-timeline-variant',
    items: [
      { to: '/analytics', icon: 'mdi-chart-timeline-variant', title: 'Indicadores', tip: 'Indicadores executivos com detalhamento.' },
      { to: '/estatisticas', icon: 'mdi-chart-box-outline', title: 'Estatísticas', tip: 'Indicadores verificáveis com fonte, fórmula e detalhamento.' },
      { to: '/financeiro', icon: 'mdi-cash-multiple', title: 'Financeiro', tip: 'Taxa CDI diária com armazenamento temporário interno e fonte no Banco Central.' },
      { to: '/relatorios', icon: 'mdi-file-chart-outline', title: 'Relatórios', tip: 'Catálogo e situação dos relatórios corporativos.' },
      { to: '/govbi-ia', icon: 'mdi-database-search', title: 'GovBI IA', tip: 'Consultas analíticas em linguagem natural com controles do ReqSys.' },
    ],
  },
  {
    id: 'integracoes',
    title: 'Integrações',
    topic: 'Ferramentas · conectores',
    icon: 'mdi-connection',
    items: [
      { to: '/painel-integracao', icon: 'mdi-view-dashboard-outline', title: 'Integrações', tip: 'Planner, Teams, GitHub e histórico de eventos.' },
      { to: '/integracoes/pentaho', icon: 'mdi-database-sync-outline', title: 'Pentaho', tip: 'Acompanhar lotes, processamento, quarentena e reprocessamento das cargas Pentaho.' },
      { to: '/hub-lowcode', icon: 'mdi-lightning-bolt-circle', title: 'Central de automações', tip: 'Power Automate, Power Apps, ReqSysAgent e administração do ciclo de entrega.' },
      { to: '/hub-lowcode/copilot-memory/instalar', icon: 'mdi-memory', title: 'Instalar memória do Copilot', tip: 'Instalar a memória do Copilot escolhendo ambiente, Planner, planilha e conexões.' },
      { to: '/hub-lowcode/wsjf/planner-excel/instalar', icon: 'mdi-microsoft-excel', title: 'Instalar Planner → Excel WSJF', tip: 'Escolher DEV, Planner, WSJF.xlsx e conexões sem copiar identificadores técnicos.' },
      { to: '/figma-github', icon: 'mdi-vector-square', title: 'Figma e GitHub', tip: 'Sincronização entre Figma e GitHub com retorno em tela.' },
    ],
  },
  {
    id: 'administracao',
    title: 'Administração',
    topic: 'Operação técnica · governança',
    icon: 'mdi-shield-check-outline',
    items: [
      { to: '/monitoramento-operacional', icon: 'mdi-monitor-dashboard', title: 'Monitoramento', tip: 'Situação técnica das integrações, verificações obrigatórias, execução e pendências operacionais.' },
      { to: '/auditoria', icon: 'mdi-shield-search', title: 'Auditoria', tip: 'Linha do tempo de eventos e controles operacionais.' },
      { to: '/segredos-status', icon: 'mdi-key-chain-variant', title: 'Segredos', tip: 'Diagnóstico da origem dos segredos do serviço.' },
      { to: '/specs', icon: 'mdi-file-code-outline', title: 'Especificações', tip: 'Especificações técnicas e contratos das funcionalidades.' },
      { to: '/governanca', icon: 'mdi-shield-check-outline', title: 'Governança', tip: 'Verificações obrigatórias, automação de integração e publicação, monitoramento, políticas e evidências.' },
      { to: '/codex', icon: 'mdi-code-braces', title: 'Codex', tip: 'Análise de código com modelo de IA local ou simulação, controlada pelo ReqSys.' },
      { to: '/admin/ocr-review', icon: 'mdi-text-box-search-outline', title: 'Revisão de leitura de documentos', tip: 'Revisar resultados de leitura automática abaixo do limite definido, com dados pessoais protegidos e decisão verificável.' },
      { to: '/admin/operational-deploy', icon: 'mdi-rocket-launch-outline', title: 'Central operacional', tip: 'Publicar serviço e aplicação no ambiente de desenvolvimento com confirmação, evidência e sem expor credenciais.' },
      { to: '/admin/session-management', icon: 'mdi-account-lock-outline', title: 'Sessões', tip: 'Atualizar permissões e invalidar sessões humanas com controle e registro.' },
      { to: '/admin/github-merge', icon: 'mdi-source-merge', title: 'Integração GitHub', tip: 'Executar e acompanhar a integração controlada de alterações empilhadas.' },
      { to: '/admin/teams-recipient-policies', icon: 'mdi-account-group-outline', title: 'Políticas Teams', tip: 'Administrar aprovadores e operadores Teams com verificação de prontidão em simulação e identidades mascaradas.' },
      { to: '/orquestrador-ia', icon: 'mdi-sitemap-outline', title: 'Orquestrador IA', tip: 'Classifica demandas por tema e aciona o coordenador de IA correspondente.' },
    ],
  },
  {
    id: 'arquitetura',
    title: 'Arquitetura',
    topic: 'Mapa · ecossistema',
    icon: 'mdi-sitemap',
    items: [
      { to: '/arquitetura', icon: 'mdi-sitemap', title: 'Mapa da solução', tip: 'Visão completa da aplicação, serviços, integrações e automações.' },
      { to: '/coordenacao-adr', icon: 'mdi-book-open-variant', title: 'Coordenação de decisões de arquitetura', tip: 'Coordenação geral que classifica demandas pelas decisões de arquitetura e aponta violações das verificações obrigatórias.' },
    ],
  },
]

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
