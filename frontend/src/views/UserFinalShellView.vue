<template>
  <section class="user-final-page" data-testid="user-final-shell">
    <div class="user-final-hero">
      <div>
        <div class="eyebrow">ReqSys · usuário final</div>
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
        <v-btn color="amber" variant="flat" prepend-icon="mdi-arrow-right-circle" @click="goTo('/workspace')">
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
    </v-card>

    <v-card class="guided-workspace mt-4" data-testid="user-final-guided-workspace">
      <div class="guided-header">
        <div>
          <div class="eyebrow">Jornada assistida</div>
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
            <v-icon icon="mdi-open-in-new" size="16" />
            Abrir detalhe governado
          </div>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col cols="12" lg="7">
        <v-card class="state-card" data-testid="user-final-states">
          <v-card-title>Estados visuais padrão</v-card-title>
          <v-card-text>
            <div class="state-grid">
              <div v-for="state in uiStates" :key="state.id" class="state-item" :data-testid="`ui-state-${state.id}`">
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
        <v-card class="state-card" data-testid="user-final-next-steps">
          <v-card-title>Próximos passos do usuário</v-card-title>
          <v-card-text>
            <v-list density="compact" class="transparent-list">
              <v-list-item
                v-for="item in nextSteps"
                :key="item.title"
                :prepend-icon="item.icon"
                :title="item.title"
                :subtitle="item.subtitle"
              />
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="technical-footer mt-4" variant="tonal" data-testid="user-final-technical-footer">
      <div>
        <strong>Rodapé técnico</strong>
        <span class="muted">
          {{ versionSummary }}
          <template v-if="apiBuildShaShort"> · build {{ apiBuildShaShort }}</template>
          · ambiente {{ environment.id }}
          · correlation_id {{ correlationId }}
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
        <v-chip size="small" color="green" variant="tonal">sem dado sensível</v-chip>
      </div>
    </v-card>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppVersion } from '../composables/useAppVersion'

const route = useRoute()
const router = useRouter()
const { frontendVersion, apiVersion, apiBuildShaShort, versionsAligned, hasVersionDrift } = useAppVersion()
const correlationId = `ufs-${Date.now().toString(36)}`

const versionSummary = computed(() => {
  if (!apiVersion.value) return `Versão frontend v${frontendVersion}`
  if (versionsAligned.value) return `Versão v${frontendVersion} (frontend e API alinhadas)`
  return `Versão frontend v${frontendVersion} · API v${apiVersion.value}`
})

const shellNavItems = [
  { label: 'Início', route: '/home', icon: 'mdi-home-outline' },
  { label: 'Workspace', route: '/workspace', icon: 'mdi-view-dashboard-edit-outline' },
  { label: 'Analytics', route: '/analytics', icon: 'mdi-chart-box-outline' },
  { label: 'Ajuda', route: '/ajuda', icon: 'mdi-help-circle-outline' },
]

const sections = {
  '/home': { title: 'Início operacional', description: 'Ponto de entrada do usuário final com orientação clara, ambiente visível e acesso às áreas principais.' },
  '/workspace': { title: 'Workspace', description: 'Área de trabalho inicial para acompanhar pendências, requisitos e próximas ações operacionais.' },
  '/analytics': { title: 'Analytics inicial', description: 'Visão executiva de indicadores com preparação para drill-down filtrado e rastreável.' },
  '/ajuda': { title: 'Ajuda e onboarding', description: 'Orientação rápida para começar a usar o ReqSys sem depender de documentação externa.' },
}

const section = computed(() => sections[route.path] || sections['/home'])
const environment = computed(() => {
  const raw = (import.meta.env.VITE_APP_ENVIRONMENT || 'DEV').toUpperCase()
  if (['PRD', 'PROD', 'PRODUCTION', 'PRODUCAO'].includes(raw)) return { id: 'PRD', label: 'Produção', color: 'red' }
  if (['HML', 'HOMOLOG', 'HOMOLOGACAO', 'STAGING'].includes(raw)) return { id: 'HML', label: 'Homologação', color: 'amber' }
  return { id: 'DEV', label: 'Desenvolvimento', color: 'blue' }
})

const operationalCards = [
  { id: 'requisitos', title: 'Requisitos', description: 'Consultar e acompanhar o catálogo de requisitos e demandas.', icon: 'mdi-file-document-edit-outline', status: 'MVP', statusColor: 'blue', route: '/requisitos' },
  { id: 'pendencias', title: 'Pendências operacionais', description: 'Acessar a área de trabalho com filtros preparados para itens pendentes.', icon: 'mdi-clipboard-alert-outline', status: 'Inicial', statusColor: 'amber', route: '/workspace?status=pendente' },
  { id: 'governanca', title: 'Governança', description: 'Visualizar gates, evidências e trilhas de auditoria em alto nível.', icon: 'mdi-shield-check-outline', status: 'Auditável', statusColor: 'green', route: '/governanca' },
]

const uiStates = [
  { id: 'loading', label: 'Carregando', message: 'Exibir feedback não bloqueante enquanto dados operacionais são carregados.', icon: 'mdi-loading', color: 'blue' },
  { id: 'empty', label: 'Sem dados', message: 'Explicar o próximo passo quando não houver informações disponíveis.', icon: 'mdi-inbox-outline', color: 'grey' },
  { id: 'error', label: 'Erro operacional', message: 'Mostrar mensagem segura e caminho de recuperação sem expor detalhe sensível.', icon: 'mdi-alert-circle-outline', color: 'red' },
  { id: 'success', label: 'Disponível', message: 'Exibir conteúdo e ações primárias quando a área estiver pronta.', icon: 'mdi-check-circle-outline', color: 'green' },
  { id: 'unauthorized', label: 'Acesso restrito', message: 'Orientar login ou permissão necessária sem vazar regra interna.', icon: 'mdi-lock-outline', color: 'amber' },
]

const baseNextSteps = [
  { title: 'Abrir workspace', subtitle: 'Entender pendências e itens em andamento.', icon: 'mdi-view-dashboard-outline' },
  { title: 'Consultar requisitos', subtitle: 'Acompanhar demanda, status e rastreabilidade.', icon: 'mdi-file-search-outline' },
  { title: 'Ver governança', subtitle: 'Conferir gates, evidências e segurança operacional.', icon: 'mdi-shield-search' },
]

const contextualNextSteps = {
  '/workspace': [
    { title: 'Filtrar pendências', subtitle: 'Use status, prioridade e responsável para reduzir ruído operacional.', icon: 'mdi-filter-check-outline' },
    { title: 'Abrir item crítico', subtitle: 'Priorize requisitos bloqueados ou sem evidência recente.', icon: 'mdi-alert-decagram-outline' },
    { title: 'Registrar decisão', subtitle: 'Mantenha rastreabilidade antes de avançar fluxo.', icon: 'mdi-text-box-check-outline' },
  ],
  '/analytics': [
    { title: 'Revisar indicadores', subtitle: 'Compare maturidade, risco e estabilidade por domínio.', icon: 'mdi-chart-timeline-variant' },
    { title: 'Abrir detalhe', subtitle: 'Faça drill-down apenas quando houver desvio relevante.', icon: 'mdi-magnify-expand' },
    { title: 'Exportar evidência', subtitle: 'Use artefatos para governança e prestação de contas.', icon: 'mdi-file-export-outline' },
  ],
  '/ajuda': [
    { title: 'Seguir onboarding', subtitle: 'Comece por workspace, requisito e governança.', icon: 'mdi-map-marker-path' },
    { title: 'Entender estados visuais', subtitle: 'Verifique como interpretar sucesso, vazio, erro e restrição.', icon: 'mdi-palette-swatch-outline' },
    { title: 'Acionar suporte interno', subtitle: 'Informe ambiente e correlation_id sem expor dado sensível.', icon: 'mdi-lifebuoy' },
  ],
}

const nextSteps = computed(() => contextualNextSteps[route.path] || baseNextSteps)

const activeIntents = computed(() => {
  const status = route.query.status ? String(route.query.status) : null
  const intents = [
    { id: 'low-cognitive-load', label: 'baixo esforço cognitivo', icon: 'mdi-brain', color: 'blue' },
    { id: 'auditable', label: 'auditável', icon: 'mdi-shield-check-outline', color: 'green' },
  ]

  if (status) {
    intents.push({ id: 'filtered-context', label: `filtro: ${status}`, icon: 'mdi-filter-outline', color: 'amber' })
  }

  return intents
})

const guidedWorkspace = computed(() => {
  const steps = [
    { id: 'orientar', title: 'Entender contexto', description: 'Identifique ambiente, seção atual e objetivo operacional.', icon: 'mdi-compass-outline', active: route.path === '/home' || route.path === '/ajuda' },
    { id: 'executar', title: 'Executar tarefa', description: 'Abra workspace ou requisitos com ação primária explícita.', icon: 'mdi-play-circle-outline', active: route.path === '/workspace' },
    { id: 'evidenciar', title: 'Validar evidência', description: 'Confirme governança, analytics e rastreabilidade antes de concluir.', icon: 'mdi-clipboard-check-outline', active: route.path === '/analytics' },
  ]
  const activeIndex = Math.max(steps.findIndex((step) => step.active), 0)
  const progress = Math.round(((activeIndex + 1) / steps.length) * 100)

  return {
    title: 'Fluxo guiado para usuário final',
    description: 'Reduz navegação dispersa e transforma o shell em uma jornada operacional com contexto, ação e evidência.',
    progress,
    steps,
  }
})

function goTo(target) {
  if (!target) return
  router.push(target)
}
</script>

<style scoped>
.user-final-page { padding: 20px; }
.user-final-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 24px; border-radius: 18px; background: linear-gradient(135deg, rgba(0, 83, 160, 0.12), rgba(243, 146, 0, 0.14)); border: 1px solid rgba(0, 0, 0, 0.08); }
.eyebrow { text-transform: uppercase; font-size: 12px; letter-spacing: 0.08em; font-weight: 800; color: var(--accent); margin-bottom: 6px; }
.user-final-hero h1 { margin: 0; font-size: clamp(28px, 4vw, 42px); line-height: 1.05; }
.hero-copy { max-width: 68ch; margin-top: 10px; margin-bottom: 0; color: rgba(0, 0, 0, 0.7); }
.hero-intents { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.hero-actions, .shell-navigation { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.shell-navigation { align-items: center; justify-content: flex-start; padding: 10px; border-radius: 14px; }
.shell-nav-button { min-width: 132px; }
.environment-chip { font-weight: 800; }
.guided-workspace { padding: 18px; border-radius: 16px; }
.guided-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.guided-header h2 { margin: 0; font-size: clamp(20px, 3vw, 28px); }
.journey-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.journey-step { display: flex; align-items: flex-start; gap: 12px; min-height: 110px; padding: 14px; border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 14px; background: rgba(0, 0, 0, 0.025); }
.journey-step--active { background: rgba(243, 146, 0, 0.12); border-color: rgba(243, 146, 0, 0.38); }
.operational-card { height: 100%; padding: 18px; cursor: pointer; transition: transform 0.16s ease, box-shadow 0.16s ease; }
.operational-card:hover, .operational-card:focus-visible { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(0, 0, 0, 0.14); }
.card-header, .technical-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-title { font-weight: 800; font-size: 18px; margin-top: 14px; }
.card-description { margin-top: 6px; min-height: 48px; }
.drilldown-hint { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; color: var(--accent); }
.state-card { height: 100%; }
.state-grid { display: grid; gap: 12px; }
.state-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px; border-radius: 12px; background: rgba(0, 0, 0, 0.035); }
.transparent-list { background: transparent; }
.technical-footer { padding: 14px 18px; flex-wrap: wrap; }
.technical-footer span { display: block; margin-top: 2px; }
.footer-chips { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
@media (max-width: 960px) {
  .journey-grid { grid-template-columns: 1fr; }
  .journey-step { min-height: auto; }
}
@media (max-width: 760px) {
  .user-final-page { padding: 12px; }
  .user-final-hero { flex-direction: column; padding: 18px; }
  .hero-actions, .shell-navigation { align-items: stretch; justify-content: flex-start; width: 100%; }
  .hero-actions :deep(.v-btn), .shell-nav-button { width: 100%; }
}
</style>
