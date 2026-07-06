<template>
  <section class="user-final-page" data-testid="user-final-shell">
    <div class="user-final-hero">
      <div>
        <div class="eyebrow">ReqSys · uso real</div>
        <h1>{{ section.title }}</h1>
        <p class="hero-copy">{{ section.description }}</p>

        <div class="hero-intents" aria-label="Contexto operacional do usuário final">
          <v-chip
            v-for="intent in activeIntents"
            :key="intent.id"
            size="small"
            :color="intent.color"
            variant="tonal"
            :prepend-icon="intent.icon"
            :data-testid="`user-final-intent-${intent.id}`"
          >
            {{ intent.label }}
          </v-chip>
        </div>
      </div>

      <div class="hero-actions" aria-label="Ações principais do shell">
        <v-chip :color="environment.color" variant="flat" class="environment-chip" data-testid="user-final-environment">
          {{ environment.id }} · {{ environment.label }}
        </v-chip>
        <v-btn color="amber" variant="flat" prepend-icon="mdi-plus-circle-outline" @click="goTo('/requisitos?acao=novo')">
          Nova demanda
        </v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-view-dashboard-edit-outline" @click="goTo('/workspace')">
          Abrir workspace
        </v-btn>
      </div>
    </div>

    <v-card class="shell-navigation mt-4" variant="tonal" data-testid="user-final-navigation">
      <v-btn
        v-for="item in shellNavItems"
        :key="item.route"
        :prepend-icon="item.icon"
        :variant="route.path === item.route ? 'flat' : 'text'"
        :color="route.path === item.route ? 'amber' : undefined"
        class="shell-nav-button"
        @click="goTo(item.route)"
      >
        {{ item.label }}
      </v-btn>
      <v-spacer />
      <v-chip size="small" :color="workspaceSourceColor" variant="tonal" data-testid="user-final-workspace-source">
        dados {{ workspaceStatusLabel }}
      </v-chip>
    </v-card>

    <v-row class="mt-4">
      <v-col v-for="metric in realUseMetrics" :key="metric.id" cols="12" sm="6" lg="3">
        <v-card class="metric-card" :data-testid="`real-use-metric-${metric.id}`">
          <div class="metric-header">
            <v-icon :icon="metric.icon" size="22" :color="metric.color" />
            <v-chip size="x-small" :color="metric.color" variant="tonal">{{ metric.status }}</v-chip>
          </div>
          <div class="metric-value">{{ metric.value }}</div>
          <div class="metric-label">{{ metric.label }}</div>
          <p class="muted mb-0">{{ metric.description }}</p>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="guided-workspace mt-4" data-testid="user-final-guided-workspace">
      <div class="guided-header">
        <div>
          <div class="eyebrow">Jornada principal</div>
          <h2>{{ guidedWorkspace.title }}</h2>
          <p class="muted mb-0">{{ guidedWorkspace.description }}</p>
        </div>
        <v-chip color="green" variant="tonal" prepend-icon="mdi-progress-check" data-testid="user-final-progress">
          {{ guidedWorkspace.progress }}% orientado
        </v-chip>
      </div>

      <div class="journey-grid mt-4">
        <div
          v-for="step in guidedWorkspace.steps"
          :key="step.id"
          class="journey-step"
          :class="{ 'journey-step--active': step.active }"
          :data-testid="`user-final-journey-${step.id}`"
        >
          <v-icon :icon="step.icon" size="22" :color="step.active ? 'amber' : 'grey'" />
          <div>
            <strong>{{ step.title }}</strong>
            <p class="muted mb-0">{{ step.description }}</p>
          </div>
        </div>
      </div>
    </v-card>

    <v-row class="mt-4">
      <v-col cols="12" lg="7">
        <v-card class="state-card" data-testid="user-final-action-queue">
          <v-card-title>Fila de trabalho do analista</v-card-title>
          <v-card-subtitle v-if="workspaceSummary.total_requisitos !== null" data-testid="user-final-workspace-summary">
            {{ workspaceSummary.total_requisitos }} requisitos · score médio {{ workspaceSummary.score_medio_prontidao }}% · {{ workspaceSummary.pendencias_operacionais }} pendências
          </v-card-subtitle>
          <v-card-text>
            <div class="work-queue">
              <div v-for="item in actionQueue" :key="item.id" class="queue-item" :data-testid="`user-final-queue-${item.id}`">
                <div class="queue-main">
                  <v-icon :icon="item.icon" size="22" :color="item.color" />
                  <div>
                    <strong>{{ item.title }}</strong>
                    <p class="muted mb-0">{{ item.description }}</p>
                  </div>
                </div>
                <v-chip size="small" :color="item.color" variant="tonal">{{ item.count }}</v-chip>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card class="state-card" data-testid="user-final-next-steps">
          <v-card-title>Próximas ações recomendadas</v-card-title>
          <v-card-text>
            <v-list density="compact" class="transparent-list">
              <v-list-item
                v-for="item in nextSteps"
                :key="item.title"
                :prepend-icon="item.icon"
                :title="item.title"
                :subtitle="item.subtitle"
                @click="item.route ? goTo(item.route) : undefined"
              />
            </v-list>
            <v-alert v-if="workspaceError" type="warning" variant="tonal" density="compact" class="mt-2" data-testid="user-final-workspace-error">
              API indisponível. Mantido fallback seguro para não bloquear a jornada.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col v-for="card in operationalCards" :key="card.id" cols="12" md="4">
        <v-card
          class="operational-card"
          :data-testid="`user-final-card-${card.id}`"
          role="button"
          tabindex="0"
          @click="goTo(card.route)"
          @keyup.enter="goTo(card.route)"
          @keyup.space.prevent="goTo(card.route)"
        >
          <div class="card-header">
            <v-icon :icon="card.icon" size="22" />
            <v-chip size="x-small" :color="card.statusColor" variant="tonal">
              {{ card.status }}
            </v-chip>
          </div>
          <div class="card-title">{{ card.title }}</div>
          <p class="muted card-description">{{ card.description }}</p>
          <div class="drilldown-hint">
            <v-icon icon="mdi-arrow-right" size="16" />
            {{ card.actionLabel }}
          </div>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col cols="12" lg="7">
        <v-card class="state-card" data-testid="user-final-data-quality">
          <v-card-title>Qualidade das informações</v-card-title>
          <v-card-text>
            <div class="state-grid">
              <div v-for="state in dataQualityStates" :key="state.id" class="state-item" :data-testid="`data-quality-${state.id}`">
                <v-icon :icon="state.icon" size="20" :color="state.color" />
                <div>
                  <strong>{{ state.label }}</strong>
                  <p class="muted mb-0">{{ state.message }}</p>
                </div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card class="state-card" data-testid="user-final-hidden-tech">
          <v-card-title>Governança fora da jornada principal</v-card-title>
          <v-card-text>
            <p class="muted">
              Workflows, CI, ambientes, build, correlation_id e evidências técnicas permanecem disponíveis,
              mas não competem com a rotina do analista na tela principal.
            </p>
            <div class="footer-chips">
              <v-chip size="small" color="green" variant="tonal" prepend-icon="mdi-shield-check-outline">auditável</v-chip>
              <v-chip size="small" color="blue" variant="tonal" prepend-icon="mdi-source-branch">CI/CD isolado</v-chip>
              <v-chip size="small" color="amber" variant="tonal" prepend-icon="mdi-eye-outline">evidência sob demanda</v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="technical-footer mt-4" variant="tonal" data-testid="user-final-technical-footer">
      <div>
        <strong>Evidência técnica discreta</strong>
        <span class="muted">
          {{ versionSummary }}
          <template v-if="apiBuildShaShort"> · build {{ apiBuildShaShort }}</template>
          · ambiente {{ environment.id }}
          · correlation_id {{ correlationId }}
        </span>
        <span class="muted" data-testid="user-final-telemetry-summary">
          jornada {{ telemetrySummary.current_state }}
          · eventos {{ telemetrySummary.event_count }}
          <template v-if="telemetrySummary.time_to_primary_action_ms !== null">
            · ação {{ telemetrySummary.time_to_primary_action_ms }}ms
          </template>
          · {{ telemetrySummary.pii_policy }}
        </span>
      </div>
      <div class="footer-chips">
        <v-chip
          v-if="hasVersionDrift"
          size="small"
          color="warning"
          variant="tonal"
          prepend-icon="mdi-alert-outline"
          data-testid="user-final-version-drift-chip"
        >
          Versões divergentes
        </v-chip>
        <v-chip size="small" color="green" variant="tonal" data-testid="user-final-telemetry-chip">
          jornada observada
        </v-chip>
        <v-chip size="small" color="green" variant="tonal">sem dado sensível</v-chip>
      </div>
    </v-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppVersion } from '../composables/useAppVersion'
import { useUserJourneyTelemetry } from '../composables/useUserJourneyTelemetry'

const route = useRoute()
const router = useRouter()
const { frontendVersion, apiVersion, apiBuildShaShort, versionsAligned, hasVersionDrift } = useAppVersion()
const { telemetrySummary, markPrimaryAction } = useUserJourneyTelemetry(route)
const correlationId = `ufs-${Date.now().toString(36)}`
const workspaceStatus = ref('fallback')
const workspaceError = ref(null)
const workspaceSummary = ref({ total_requisitos: null, score_medio_prontidao: 0, pendencias_operacionais: 0 })

const fallbackMetrics = [
  { id: 'prontas', value: '86%', label: 'prontidão funcional', description: 'Jornada principal orientada para trabalho real.', icon: 'mdi-account-check-outline', color: 'green', status: 'fallback' },
  { id: 'dados', value: '74%', label: 'qualidade dos dados', description: 'Campos críticos e rastreabilidade ainda exigem saneamento progressivo.', icon: 'mdi-database-check-outline', color: 'amber', status: 'fallback' },
  { id: 'fluxo', value: '6 etapas', label: 'workflow de requisito', description: 'Fluxo canônico definido da entrada até a evidência.', icon: 'mdi-source-branch-sync', color: 'blue', status: 'guiado' },
  { id: 'pendencias', value: '34', label: 'pendências operacionais', description: 'Itens pendentes por baixa prontidão ou etapa incompleta.', icon: 'mdi-clipboard-alert-outline', color: 'amber', status: 'fallback' },
]

const fallbackActionQueue = [
  { id: 'sem-aceite', title: 'Histórias sem critério de aceite', description: 'Requisitos que ainda não estão prontos para desenvolvimento.', count: '12', icon: 'mdi-format-list-checks', color: 'red' },
  { id: 'baixa-qualidade', title: 'Requisitos com baixa qualidade', description: 'Itens que precisam de refinamento, ambiguidade removida ou exemplo BDD.', count: '8', icon: 'mdi-auto-fix', color: 'amber' },
  { id: 'sem-rastro', title: 'Itens sem rastreabilidade', description: 'Demandas sem origem, decisão, vínculo técnico ou evidência de aprovação.', count: '5', icon: 'mdi-link-variant-off', color: 'amber' },
  { id: 'aprovacao', title: 'Aguardando aprovação', description: 'Itens já refinados que dependem de aceite do responsável.', count: '9', icon: 'mdi-account-clock-outline', color: 'blue' },
]

const realUseMetrics = ref([...fallbackMetrics])
const actionQueue = ref([...fallbackActionQueue])

const versionSummary = computed(() => {
  if (!apiVersion.value) return `Versão frontend v${frontendVersion}`
  if (versionsAligned.value) return `Versão v${frontendVersion} (frontend e API alinhadas)`
  return `Versão frontend v${frontendVersion} · API v${apiVersion.value}`
})

const workspaceStatusLabel = computed(() => {
  if (workspaceStatus.value === 'api') return 'reais'
  if (workspaceStatus.value === 'loading') return 'carregando'
  return 'fallback'
})
const workspaceSourceColor = computed(() => (workspaceStatus.value === 'api' ? 'green' : workspaceStatus.value === 'loading' ? 'blue' : 'amber'))

const shellNavItems = [
  { label: 'Início', route: '/home', icon: 'mdi-home-outline' },
  { label: 'Workspace', route: '/workspace', icon: 'mdi-view-dashboard-edit-outline' },
  { label: 'Analytics', route: '/analytics', icon: 'mdi-chart-box-outline' },
  { label: 'Ajuda', route: '/ajuda', icon: 'mdi-help-circle-outline' },
]

const sections = {
  '/home': {
    title: 'Painel de uso real do ReqSys',
    description: 'Entrada objetiva para registrar demandas, refinar requisitos, acompanhar pendências e evidenciar decisões sem ruído técnico.',
  },
  '/workspace': {
    title: 'Workspace operacional',
    description: 'Fila de trabalho para tratar demandas incompletas, requisitos em análise, aprovações e itens sem rastreabilidade.',
  },
  '/analytics': {
    title: 'Analytics executivo',
    description: 'Indicadores de prontidão, qualidade da informação, risco e valor gerado para apoiar decisão e priorização.',
  },
  '/ajuda': {
    title: 'Onboarding do analista',
    description: 'Guia direto para usar o ReqSys: cadastrar demanda, refinar, aprovar, rastrear e exportar evidências.',
  },
}

const section = computed(() => sections[route.path] || sections['/home'])
const environment = computed(() => {
  const raw = (import.meta.env.VITE_APP_ENVIRONMENT || 'DEV').toUpperCase()
  if (['PRD', 'PROD', 'PRODUCTION', 'PRODUCAO'].includes(raw)) return { id: 'PRD', label: 'Produção', color: 'red' }
  if (['HML', 'HOMOLOG', 'HOMOLOGACAO', 'STAGING'].includes(raw)) return { id: 'HML', label: 'Homologação', color: 'amber' }
  return { id: 'DEV', label: 'Desenvolvimento', color: 'blue' }
})

const operationalCards = [
  { id: 'requisitos', title: 'Requisitos', description: 'Criar, consultar e acompanhar demandas com foco em clareza, aceite e rastreabilidade.', icon: 'mdi-file-document-edit-outline', status: 'Ação principal', statusColor: 'green', route: '/requisitos', actionLabel: 'Abrir requisitos' },
  { id: 'pendencias', title: 'Pendências operacionais', description: 'Tratar itens sem dono, sem aceite, com baixa qualidade ou bloqueados por aprovação.', icon: 'mdi-clipboard-alert-outline', status: 'Fila diária', statusColor: 'amber', route: '/workspace?status=pendente', actionLabel: 'Abrir fila' },
  { id: 'governanca', title: 'Evidências e governança', description: 'Consultar gates, trilhas e observabilidade apenas quando a decisão exigir comprovação.', icon: 'mdi-shield-check-outline', status: 'Sob demanda', statusColor: 'blue', route: '/governanca', actionLabel: 'Ver evidência' },
]

const dataQualityStates = [
  { id: 'entrada', label: 'Entrada mínima obrigatória', message: 'Título, área, objetivo, impacto, solicitante e urgência devem ser claros antes do refinamento.', icon: 'mdi-form-textbox', color: 'green' },
  { id: 'bdd', label: 'Critérios testáveis', message: 'Cada história deve ter aceite verificável e, quando aplicável, cenário BDD.', icon: 'mdi-test-tube', color: 'blue' },
  { id: 'rastreabilidade', label: 'Rastreabilidade completa', message: 'Origem, decisão, responsável, status e evidência precisam acompanhar a demanda.', icon: 'mdi-link-variant', color: 'amber' },
  { id: 'limpeza', label: 'Menos tópicos dispersos', message: 'Conteúdos técnicos, ambientes e CI deixam de ocupar a jornada principal do usuário.', icon: 'mdi-filter-remove-outline', color: 'green' },
]

const baseNextSteps = [
  { title: 'Cadastrar nova demanda', subtitle: 'Registrar necessidade de negócio com dados mínimos.', icon: 'mdi-plus-circle-outline', route: '/requisitos?acao=novo' },
  { title: 'Tratar pendências', subtitle: 'Resolver itens sem aceite, dono, qualidade ou rastreabilidade.', icon: 'mdi-clipboard-alert-outline', route: '/workspace?status=pendente' },
  { title: 'Consultar evidências', subtitle: 'Abrir governança apenas quando precisar comprovar decisão ou estabilidade.', icon: 'mdi-shield-search', route: '/governanca' },
]

const contextualNextSteps = {
  '/workspace': [
    { title: 'Filtrar pendências críticas', subtitle: 'Priorize baixa qualidade, falta de aceite e ausência de rastreabilidade.', icon: 'mdi-filter-check-outline', route: '/workspace?status=critico' },
    { title: 'Abrir item bloqueado', subtitle: 'Trate requisitos parados antes de criar novos tópicos.', icon: 'mdi-alert-decagram-outline', route: '/requisitos?status=bloqueado' },
    { title: 'Registrar decisão', subtitle: 'Mantenha histórico e responsável antes de avançar o fluxo.', icon: 'mdi-text-box-check-outline', route: '/auditoria' },
  ],
  '/analytics': [
    { title: 'Revisar prontidão', subtitle: 'Compare qualidade, rastreabilidade e pendências por domínio.', icon: 'mdi-chart-timeline-variant', route: '/analytics' },
    { title: 'Investigar desvio', subtitle: 'Faça drill-down apenas quando houver risco, queda ou fila acumulada.', icon: 'mdi-magnify-expand', route: '/estatisticas' },
    { title: 'Exportar evidência', subtitle: 'Use relatórios para prestação de contas e governança.', icon: 'mdi-file-export-outline', route: '/relatorios' },
  ],
  '/ajuda': [
    { title: 'Seguir fluxo recomendado', subtitle: 'Cadastrar, refinar, aprovar, rastrear e exportar.', icon: 'mdi-map-marker-path', route: '/requisitos?acao=novo' },
    { title: 'Entender qualidade', subtitle: 'Verifique dados mínimos, aceite, BDD e rastreabilidade.', icon: 'mdi-palette-swatch-outline', route: '/home' },
    { title: 'Acionar suporte interno', subtitle: 'Informe ambiente e correlation_id sem expor dado sensível.', icon: 'mdi-lifebuoy' },
  ],
}

const nextSteps = computed(() => contextualNextSteps[route.path] || baseNextSteps)

const activeIntents = computed(() => {
  const status = route.query.status ? String(route.query.status) : null
  const intents = [
    { id: 'low-cognitive-load', label: 'baixo esforço cognitivo', icon: 'mdi-brain', color: 'blue' },
    { id: 'real-use', label: 'uso real primeiro', icon: 'mdi-account-check-outline', color: 'green' },
    { id: 'auditable', label: 'auditável sem poluir a jornada', icon: 'mdi-shield-check-outline', color: 'green' },
  ]

  if (status) {
    intents.push({ id: 'filtered-context', label: `filtro: ${status}`, icon: 'mdi-filter-outline', color: 'amber' })
  }

  return intents
})

const guidedWorkspace = computed(() => {
  const steps = [
    { id: 'entrada', title: 'Entrada', description: 'Registrar demanda com objetivo, área, impacto, urgência e solicitante.', icon: 'mdi-inbox-arrow-down-outline', active: route.path === '/home' || route.path === '/ajuda' },
    { id: 'refinar', title: 'Refinar', description: 'Transformar texto bruto em requisito claro, testável e sem ambiguidade.', icon: 'mdi-auto-fix', active: route.path === '/workspace' },
    { id: 'aceitar', title: 'Aceitar', description: 'Gerar histórias e critérios BDD antes de liberar para execução.', icon: 'mdi-check-decagram-outline', active: route.path === '/requisitos' },
    { id: 'rastrear', title: 'Rastrear', description: 'Manter origem, decisão, responsável, vínculo técnico e evidência.', icon: 'mdi-link-variant', active: route.path === '/analytics' },
    { id: 'exportar', title: 'Exportar', description: 'Enviar para relatório, Redmine, GitHub ou governança conforme necessidade.', icon: 'mdi-export-variant', active: false },
  ]
  const activeIndex = Math.max(steps.findIndex((step) => step.active), 0)
  const progress = Math.round(((activeIndex + 1) / steps.length) * 100)

  return {
    title: 'Fluxo canônico de requisito pronto para operação',
    description: 'A tela principal passa a guiar o trabalho real: entrada, refinamento, aceite, rastreabilidade e evidência.',
    progress,
    steps,
  }
})

function getApiBaseUrl() {
  return (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
}

function getPersistedFilters() {
  if (typeof localStorage === 'undefined') return {}
  try {
    return JSON.parse(localStorage.getItem('reqsys.workspace.filters') || '{}')
  } catch {
    return {}
  }
}

function persistFilters(filters) {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem('reqsys.workspace.filters', JSON.stringify(filters))
}

function buildWorkspaceQuery() {
  const persisted = getPersistedFilters()
  const filters = {
    status: route.query.status ? String(route.query.status) : persisted.status,
    area: route.query.area ? String(route.query.area) : persisted.area,
    responsavel: route.query.responsavel ? String(route.query.responsavel) : persisted.responsavel,
  }
  persistFilters(filters)

  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })
  return params.toString()
}

async function carregarWorkspaceOperacional() {
  if (typeof fetch !== 'function') return
  workspaceStatus.value = 'loading'
  workspaceError.value = null

  try {
    const query = buildWorkspaceQuery()
    const endpoint = `${getApiBaseUrl()}/api/requisitos/workspace${query ? `?${query}` : ''}`
    const response = await fetch(endpoint, {
      headers: {
        Accept: 'application/json',
        'X-Correlation-Id': correlationId,
      },
    })
    if (!response.ok) throw new Error(`workspace_operacional_http_${response.status}`)
    const envelope = await response.json()
    const payload = envelope?.data
    if (!payload?.metrics || !payload?.action_queue) throw new Error('workspace_operacional_payload_invalido')

    realUseMetrics.value = payload.metrics
    actionQueue.value = payload.action_queue
    workspaceSummary.value = payload.summary || workspaceSummary.value
    workspaceStatus.value = 'api'
  } catch (error) {
    workspaceError.value = error
    workspaceStatus.value = 'fallback'
    realUseMetrics.value = [...fallbackMetrics]
    actionQueue.value = [...fallbackActionQueue]
  }
}

function goTo(target) {
  if (!target) return
  markPrimaryAction(target)
  router.push(target)
}

onMounted(carregarWorkspaceOperacional)
watch(() => route.fullPath, carregarWorkspaceOperacional)
</script>

<style scoped>
.user-final-page { padding: 20px; }
.user-final-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 24px; border-radius: 18px; background: linear-gradient(135deg, rgba(0, 83, 160, 0.12), rgba(243, 146, 0, 0.14)); border: 1px solid rgba(0, 0, 0, 0.08); }
.eyebrow { text-transform: uppercase; font-size: 12px; letter-spacing: 0.08em; font-weight: 800; color: var(--accent); margin-bottom: 6px; }
.user-final-hero h1 { margin: 0; font-size: clamp(28px, 4vw, 42px); line-height: 1.05; }
.hero-copy { max-width: 72ch; margin-top: 10px; margin-bottom: 0; color: rgba(0, 0, 0, 0.7); }
.hero-intents { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.hero-actions, .shell-navigation { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.shell-navigation { align-items: center; justify-content: flex-start; padding: 10px; border-radius: 14px; }
.shell-nav-button { min-width: 132px; }
.environment-chip { font-weight: 800; }
.metric-card { height: 100%; padding: 16px; border-radius: 16px; }
.metric-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.metric-value { font-size: 28px; line-height: 1; font-weight: 900; margin-top: 16px; }
.metric-label { font-size: 14px; font-weight: 800; margin: 6px 0; text-transform: uppercase; letter-spacing: 0.03em; }
.guided-workspace { padding: 18px; border-radius: 16px; }
.guided-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.guided-header h2 { margin: 0; font-size: clamp(20px, 3vw, 28px); }
.journey-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.journey-step { display: flex; align-items: flex-start; gap: 12px; min-height: 128px; padding: 14px; border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 14px; background: rgba(0, 0, 0, 0.025); }
.journey-step--active { background: rgba(243, 146, 0, 0.12); border-color: rgba(243, 146, 0, 0.38); }
.operational-card { height: 100%; padding: 18px; cursor: pointer; transition: transform 0.16s ease, box-shadow 0.16s ease; }
.operational-card:hover, .operational-card:focus-visible { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(0, 0, 0, 0.14); }
.card-header, .technical-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-title { font-weight: 800; font-size: 18px; margin-top: 14px; }
.card-description { margin-top: 6px; min-height: 48px; }
.drilldown-hint { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; color: var(--accent); }
.state-card { height: 100%; }
.work-queue { display: grid; gap: 12px; }
.queue-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; border-radius: 12px; background: rgba(0, 0, 0, 0.035); }
.queue-main { display: flex; align-items: flex-start; gap: 12px; }
.state-grid { display: grid; gap: 12px; }
.state-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px; border-radius: 12px; background: rgba(0, 0, 0, 0.035); }
.transparent-list { background: transparent; }
.technical-footer { padding: 14px 18px; flex-wrap: wrap; opacity: 0.82; }
.technical-footer span { display: block; margin-top: 2px; }
.footer-chips { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
@media (max-width: 1280px) {
  .journey-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 960px) {
  .journey-grid { grid-template-columns: 1fr; }
  .journey-step { min-height: auto; }
}
@media (max-width: 760px) {
  .user-final-page { padding: 12px; }
  .user-final-hero { flex-direction: column; padding: 18px; }
  .hero-actions, .shell-navigation { align-items: stretch; justify-content: flex-start; width: 100%; }
  .hero-actions :deep(.v-btn), .shell-nav-button { width: 100%; }
  .queue-item { align-items: flex-start; flex-direction: column; }
}
</style>
