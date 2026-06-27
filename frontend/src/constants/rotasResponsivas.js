/**
 * Rotas canônicas do incremento padrão ouro de responsividade (16 telas operacionais).
 * Referência: docs/varreduras/REQSYS_VARREDURA_PADRAO_OURO_2026-06-20.md
 */
export const ROTAS_RESPONSIVAS = [
  { path: '/login', testId: 'route-login', titulo: 'Login' },
  { path: '/', testId: 'route-dashboard', titulo: 'Dashboard' },
  { path: '/requisitos', testId: 'route-requisitos', titulo: 'Requisitos' },
  { path: '/rastreabilidade', testId: 'route-rastreabilidade', titulo: 'Rastreabilidade' },
  { path: '/auditoria', testId: 'route-auditoria', titulo: 'Auditoria' },
  { path: '/pipeline', testId: 'route-pipeline', titulo: 'Pipeline' },
  { path: '/relatorios', testId: 'route-relatorios', titulo: 'Relatórios' },
  { path: '/segredos-status', testId: 'route-segredos-status', titulo: 'Segredos' },
  { path: '/qualidade-ia', testId: 'route-qualidade-ia', titulo: 'Qualidade IA' },
  { path: '/recomendacoes-ia', testId: 'route-recomendacoes-ia', titulo: 'Recomendações IA' },
  { path: '/task-console', testId: 'route-task-console', titulo: 'Task Console' },
  { path: '/specs', testId: 'route-specs', titulo: 'Specs' },
  { path: '/hub-lowcode', testId: 'route-hub-lowcode', titulo: 'Hub Low-Code' },
  { path: '/painel-integracao', testId: 'route-painel-integracao', titulo: 'Painel de Integração' },
  { path: '/arquitetura', testId: 'route-arquitetura', titulo: 'Arquitetura' },
  { path: '/govbi-ia', testId: 'route-govbi-ia', titulo: 'GovBI IA' },
]
