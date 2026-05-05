import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/DashboardView.vue'), meta: { permissao: 'dashboard:read' } },
  { path: '/requisitos', component: () => import('../views/RequisitosView.vue'), meta: { permissao: 'requisitos:write' } },
  { path: '/pipeline', component: () => import('../views/PipelineView.vue'), meta: { permissao: 'requisitos:write' } },
  { path: '/qualidade-ia', component: () => import('../views/QualidadeIAView.vue'), meta: { permissao: 'dashboard:read' } },
  { path: '/relatorios', component: () => import('../views/RelatoriosView.vue'), meta: { permissao: 'relatorios:read' } },
  { path: '/segredos-status', component: () => import('../views/SegredosStatusView.vue'), meta: { permissao: 'dashboard:read' } },
  { path: '/rastreabilidade', component: () => import('../views/RastreabilidadeView.vue'), meta: { permissao: 'rastreabilidade:read' } },
  { path: '/auditoria', component: () => import('../views/AuditoriaView.vue'), meta: { permissao: 'auditoria:read' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true
  if (!auth.autenticado) return '/login'
  if (to.meta.permissao && !auth.pode(to.meta.permissao)) return '/'
  return true
})

export default router
