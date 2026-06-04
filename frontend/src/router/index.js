import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import RequisitosView from '../views/RequisitosView.vue'
import RastreabilidadeView from '../views/RastreabilidadeView.vue'
import AuditoriaView from '../views/AuditoriaView.vue'
import PipelineView from '../views/PipelineView.vue'
import RelatoriosView from '../views/RelatoriosView.vue'
import SegredosStatusView from '../views/SegredosStatusView.vue'
import QualidadeIAView from '../views/QualidadeIAView.vue'
import SpecsView from '../views/SpecsView.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/', component: DashboardView, meta: { recurso: 'dashboard:read' } },
  { path: '/requisitos', component: RequisitosView, meta: { recurso: 'requisitos:write' } },
  { path: '/rastreabilidade', component: RastreabilidadeView, meta: { recurso: 'rastreabilidade:read' } },
  { path: '/auditoria', component: AuditoriaView, meta: { recurso: 'auditoria:read' } },
  { path: '/pipeline', component: PipelineView, meta: { recurso: 'requisitos:write' } },
  { path: '/relatorios', component: RelatoriosView, meta: { recurso: 'relatorios:read' } },
  { path: '/segredos-status', component: SegredosStatusView, meta: { recurso: 'dashboard:read' } },
  { path: '/qualidade-ia', component: QualidadeIAView, meta: { recurso: 'dashboard:read' } },
  { path: '/specs',        component: SpecsView,       meta: { recurso: 'dashboard:read' } }
]
const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.autenticado) return '/login'
  if (to.meta.recurso && auth.usuario && !auth.pode(to.meta.recurso)) return '/'
})
export default router
