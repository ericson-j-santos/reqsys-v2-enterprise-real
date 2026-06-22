</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { useAuthStore } from '../stores/auth'

const { mobile } = useDisplay()
const auth = useAuthStore()
const router = useRouter()
const drawer = ref(!mobile.value)

watch(mobile, (isMobile) => {
  drawer.value = !isMobile
})

const navItems = [
  { to: '/',                icon: 'mdi-view-dashboard',     title: 'Dashboard',       tip: 'Visão consolidada das métricas e acessos rápidos.' },
  { to: '/runtime-center', icon: 'mdi-monitor-dashboard', title: 'Runtime Center', tip: 'Cockpit vivo de health, ambiente, timeline e self-healing governado.' },
  { to: '/monitoramento-operacional', icon: 'mdi-monitor-eye', title: 'Monitoramento', tip: 'Estado operacional de PRs, gates, integrações e pendências.' },
  { to: '/requisitos',      icon: 'mdi-file-document-edit', title: 'Requisitos',      tip: 'Cadastro, listagem e acompanhamento dos requisitos.' },
  { to: '/pipeline',        icon: 'mdi-pipe',               title: 'Pipeline',        tip: 'Fluxo operacional detalhado do requisito até a publicação.' },
  { to: '/task-console',    icon: 'mdi-clipboard-check-outline', title: 'Task Console', tip: 'Console web para revisar tarefas e preparar envio ao Planner.' },
  { to: '/qualidade-ia',    icon: 'mdi-brain',              title: 'Qualidade IA',    tip: 'Monitoramento contínuo de score e tendência de qualidade de IA.' },
  { to: '/recomendacoes-ia', icon: 'mdi-robot-outline',     title: 'Recomendações IA', tip: 'Criação, decisão e outcome de recomendações geradas por IA.' },
  { to: '/relatorios',      icon: 'mdi-file-chart-outline', title: 'Relatórios SSRS', tip: 'Catálogo e status dos relatórios SSRS publicados.' },
  { to: '/segredos-status', icon: 'mdi-key-chain-variant',  title: 'Segredos',        tip: 'Diagnóstico da origem dos segredos do backend.' },
  { to: '/rastreabilidade', icon: 'mdi-vector-link',        title: 'Rastreabilidade', tip: 'Matriz de vínculo entre requisito, história e entrega.' },
  { to: '/specs',            icon: 'mdi-file-code-outline',  title: 'Specs SDD',       tip: 'Especificações de features do my-first-spec-project.' },
  { to: '/auditoria',       icon: 'mdi-shield-search',      title: 'Auditoria',       tip: 'Linha do tempo de eventos e governança operacional.' },
  { to: '/hub-lowcode',       icon: 'mdi-lightning-bolt-circle',    title: 'Hub Low-Code',   tip: 'Pacotes IA, flows Power Automate, bot ReqSysAgent e pipeline GitHub ALM.' },
  { to: '/painel-integracao', icon: 'mdi-view-dashboard-outline',  title: 'Integrações',    tip: 'Painel de acompanhamento: Planner, Teams e histórico de eventos.' },
  { to: '/figma-github',      icon: 'mdi-vector-square',           title: 'Figma GitHub',   tip: 'Sincronização e retorno em tela entre Figma e GitHub.' },
  { to: '/arquitetura',       icon: 'mdi-sitemap',                  title: 'Mapa da Solução', tip: 'Visão completa de todos os componentes Web e Low-Code.' },
  { to: '/governanca',        icon: 'mdi-shield-check-outline',     title: 'Governança',     tip: 'Padrão Ouro Enterprise: gates, CI/CD, observabilidade, analytics e IA auditável.' },
  { to: '/govbi-ia',      icon: 'mdi-database-search',    title: 'GovBI IA',        tip: 'Consultas analíticas em linguagem natural com IA governada.' },
]

function initials(u) {
  return (u.nome || u.email || '?')[0].toUpperCase()
}

function sair() {
  auth.sair()
  router.push('/login')
}