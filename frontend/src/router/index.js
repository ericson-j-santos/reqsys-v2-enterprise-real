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
import RecomendacoesIAView from '../views/RecomendacoesIAView.vue'
import SpecsView from '../views/SpecsView.vue'
import TaskConsoleView from '../views/TaskConsoleView.vue'
import ArquiteturaView from '../views/ArquiteturaView.vue'
import GovernancaEnterpriseView from '../views/GovernancaEnterpriseView.vue'
import HubLowCodeView from '../views/HubLowCodeView.vue'
import GovBIView from '../views/GovBIView.vue'
import PainelIntegracaoView from '../views/PainelIntegracaoView.vue'
import MonitoramentoOperacionalView from '../views/MonitoramentoOperacionalView.vue'
import RuntimeValidatorView from '../views/RuntimeValidatorView.vue'
import FigmaGithubView from '../views/FigmaGithubView.vue'
import EstatisticasView from '../views/EstatisticasView.vue'
import UserFinalShellView from '../views/UserFinalShellView.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/', component: DashboardView, meta: { recurso: 'dashboard:read' } },
  { path: '/home', component: UserFinalShellView, meta: { recurso: 'dashboard:read', userFinalShell: true } },
  { path: '/workspace', component: UserFinalShellView, meta: { recurso: 'dashboard:read', userFinalShell: true } },
  { path: '/analytics', component: UserFinalShellView, meta: { recurso: 'dashboard:read', userFinalShell: true } },
  { path: '/ajuda', component: UserFinalShellView, meta: { recurso: 'dashboard:read', userFinalShell: true } },
  { path: '/requisitos', component: RequisitosView, meta: { recurso: 'requisitos:write' } },
  { path: '/rastreabilidade', component: RastreabilidadeView, meta: { recurso: 'rastreabilidade:read' } },
  { path: '/auditoria', component: AuditoriaView, meta: { recurso: 'auditoria:read' } },
  { path: '/pipeline', component: PipelineView, meta: { recurso: 'requisitos:write' } },
  { path: '/relatorios', component: RelatoriosView, meta: { recurso: 'relatorios:read' } },
  { path: '/segredos-status', component: SegredosStatusView, meta: { recurso: 'dashboard:read' } },
  { path: '/qualidade-ia', component: QualidadeIAView, meta: { recurso: 'dashboard:read' } },
  { path: '/recomendacoes-ia', component: RecomendacoesIAView, meta: { recurso: 'dashboard:read' } },
  { path: '/task-console', component: TaskConsoleView, meta: { recurso: 'dashboard:read' } },
  { path: '/specs',        component: SpecsView,       meta: { recurso: 'dashboard:read' } },
  { path: '/hub-lowcode', component: HubLowCodeView,  meta: { recurso: 'dashboard:read' } },
  { path: '/painel-integracao', component: PainelIntegracaoView, meta: { recurso: 'dashboard:read' } },
  { path: '/figma-github', component: FigmaGithubView, meta: { recurso: 'dashboard:read' } },
  { path: '/estatisticas', component: EstatisticasView, meta: { recurso: 'dashboard:read' } },
  { path: '/arquitetura', component: ArquiteturaView, meta: { recurso: 'dashboard:read' } },
  { path: '/governanca', component: GovernancaEnterpriseView, meta: { recurso: 'dashboard:read' } },
  { path: '/monitoramento-operacional', component: MonitoramentoOperacionalView, meta: { recurso: 'dashboard:read' } },
  { path: '/runtime-validator', component: RuntimeValidatorView, meta: { recurso: 'dashboard:read' } },
  { path: '/govbi-ia', alias: '/govbi', component: GovBIView, meta: { recurso: 'dashboard:read' } }
]
const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.autenticado) return '/login'
  if (to.meta.recurso && auth.usuario && !auth.pode(to.meta.recurso)) return '/'
})
export default router
