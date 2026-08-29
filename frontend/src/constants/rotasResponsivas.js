/**
 * Rotas canônicas do incremento padrão ouro de responsividade (36 telas operacionais).
 * Referência: docs/varreduras/REQSYS_VARREDURA_PADRAO_OURO_2026-06-20.md
 *
 * Os caminhos e identificadores técnicos permanecem estáveis; apenas os títulos apresentados
 * às pessoas usam português claro e direto.
 */
export const ROTAS_RESPONSIVAS = [
  { path: '/login', testId: 'route-login', titulo: 'Entrar' },
  { path: '/', testId: 'route-dashboard', titulo: 'Painel' },
  { path: '/home', testId: 'user-final-shell', titulo: 'Início' },
  { path: '/workspace', testId: 'user-final-shell', titulo: 'Área de trabalho' },
  { path: '/analytics', testId: 'route-analytics', titulo: 'Indicadores' },
  { path: '/ajuda', testId: 'user-final-shell', titulo: 'Ajuda' },
  { path: '/requisitos', testId: 'route-requisitos', titulo: 'Requisitos' },
  { path: '/rastreabilidade', testId: 'route-rastreabilidade', titulo: 'Rastreabilidade' },
  { path: '/auditoria', testId: 'route-auditoria', titulo: 'Auditoria' },
  { path: '/pipeline', testId: 'route-pipeline', titulo: 'Fluxo' },
  { path: '/relatorios', testId: 'route-relatorios', titulo: 'Relatórios' },
  { path: '/segredos-status', testId: 'route-segredos-status', titulo: 'Segredos' },
  { path: '/qualidade-ia', testId: 'route-qualidade-ia', titulo: 'Qualidade IA' },
  { path: '/recomendacoes-ia', testId: 'route-recomendacoes-ia', titulo: 'Recomendações IA' },
  { path: '/task-console', testId: 'route-task-console', titulo: 'Preparar tarefas' },
  { path: '/agile-runtime', testId: 'route-agile-runtime', titulo: 'Acompanhamento da entrega' },
  { path: '/specs', testId: 'route-specs', titulo: 'Especificações' },
  { path: '/hub-lowcode', testId: 'route-hub-lowcode', titulo: 'Central de automações' },
  { path: '/hub-lowcode/copilot-memory/instalar', testId: 'route-copilot-memory-installer', titulo: 'Instalar memória do Copilot' },
  { path: '/painel-integracao', testId: 'route-painel-integracao', titulo: 'Painel de integração' },
  { path: '/arquitetura', testId: 'route-arquitetura', titulo: 'Arquitetura' },
  { path: '/govbi-ia', testId: 'route-govbi-ia', titulo: 'GovBI IA' },
  { path: '/codex', testId: 'route-codex', titulo: 'Codex controlado' },
  { path: '/monitoramento-operacional', testId: 'route-monitoramento-operacional', titulo: 'Monitoramento operacional' },
  { path: '/estatisticas', testId: 'route-estatisticas', titulo: 'Estatísticas' },
  { path: '/estatisticas/:indicadorId', testId: 'route-estatistica-detalhe', titulo: 'Detalhe estatístico' },
  { path: '/figma-github', testId: 'route-figma-github', titulo: 'Figma e GitHub' },
  { path: '/governanca', testId: 'route-governanca', titulo: 'Governança' },
  { path: '/financeiro', testId: 'route-financeiro', titulo: 'Financeiro' },
  { path: '/orquestrador-ia', testId: 'route-orquestrador-ia', titulo: 'Orquestrador IA' },
  { path: '/coordenacao-adr', testId: 'route-coordenacao-adr', titulo: 'Coordenação de decisões de arquitetura' },
  { path: '/admin/github-merge', testId: 'route-github-merge', titulo: 'Integração controlada do GitHub' },
  { path: '/admin/teams-recipient-policies', testId: 'route-teams-recipient-policies', titulo: 'Políticas de destinatários do Teams' },
  { path: '/admin/operational-deploy', testId: 'route-operational-deploy', titulo: 'Central de administração operacional' },
  { path: '/admin/session-management', testId: 'route-session-management', titulo: 'Gerenciamento de sessões' },
  { path: '/admin/ocr-review', testId: 'route-ocr-review', titulo: 'Revisão humana de leitura de documentos' },
]
