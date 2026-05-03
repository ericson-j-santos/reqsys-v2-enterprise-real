import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import RequisitosView from '../views/RequisitosView.vue'
import RastreabilidadeView from '../views/RastreabilidadeView.vue'
import AuditoriaView from '../views/AuditoriaView.vue'
import PipelineView from '../views/PipelineView.vue'
import RelatoriosView from '../views/RelatoriosView.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/', component: DashboardView, meta: { recurso: 'dashboard:read' } },
  { path: '/requisitos', component: RequisitosView, meta: { recurso: 'requisitos:write' } },
  { path: '/rastreabilidade', component: RastreabilidadeView, meta: { recurso: 'rastreabilidade:read' } },
  { path: '/auditoria', component: AuditoriaView, meta: { recurso: 'auditoria:read' } },
  { path: '/pipeline', component: PipelineView, meta: { recurso: 'requisitos:write' } },
  { path: '/relatorios', component: RelatoriosView, meta: { recurso: 'relatorios:read' } }
]
const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.autenticado) return '/login'
  if (to.meta.recurso && !auth.pode(to.meta.recurso)) return '/'
})
export default router
