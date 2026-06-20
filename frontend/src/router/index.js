import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// Rotas com carregamento sob demanda (code-splitting): cada view vira um chunk
// separado, reduzindo o bundle inicial e isolando falhas de uma view do resto da SPA.
const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/DashboardView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/requisitos', component: () => import('../views/RequisitosView.vue'), meta: { recurso: 'requisitos:write' } },
  { path: '/rastreabilidade', component: () => import('../views/RastreabilidadeView.vue'), meta: { recurso: 'rastreabilidade:read' } },
  { path: '/auditoria', component: () => import('../views/AuditoriaView.vue'), meta: { recurso: 'auditoria:read' } },
  { path: '/pipeline', component: () => import('../views/PipelineView.vue'), meta: { recurso: 'requisitos:write' } },
  { path: '/relatorios', component: () => import('../views/RelatoriosView.vue'), meta: { recurso: 'relatorios:read' } },
  { path: '/segredos-status', component: () => import('../views/SegredosStatusView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/qualidade-ia', component: () => import('../views/QualidadeIAView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/recomendacoes-ia', component: () => import('../views/RecomendacoesIAView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/task-console', component: () => import('../views/TaskConsoleView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/specs', component: () => import('../views/SpecsView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/hub-lowcode', component: () => import('../views/HubLowCodeView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/painel-integracao', component: () => import('../views/PainelIntegracaoView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/arquitetura', component: () => import('../views/ArquiteturaView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/governanca', component: () => import('../views/GovernancaEnterpriseView.vue'), meta: { recurso: 'dashboard:read' } },
  { path: '/govbi-ia', component: () => import('../views/GovBIView.vue'), meta: { recurso: 'dashboard:read' } }
]
const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.autenticado) return '/login'
  if (to.meta.recurso && auth.usuario && !auth.pode(to.meta.recurso)) return '/'
})
export default router
