<template>
  <section class="user-final-page" data-testid="user-final-shell">
    <div class="user-final-hero">
      <div>
        <div class="eyebrow">ReqSys · usuário final</div>
        <h1>{{ section.title }}</h1>
        <p class="hero-copy">{{ section.description }}</p>
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

    <div v-if="isAnalyticsRoute" class="analytics-meta mt-4" data-testid="analytics-meta">
      <v-chip color="primary" variant="tonal" size="small">Ref. {{ referenciaTemporal }}</v-chip>
      <v-chip color="success" variant="tonal" size="small">{{ resumoProjecao.consolidacaoMedia }}% consolidado</v-chip>
      <v-chip color="amber" variant="tonal" size="small">{{ resumoProjecao.estabilizacaoCi }}% CI estabilizado</v-chip>
      <v-chip color="info" variant="tonal" size="small">{{ resumoProjecao.probabilidadeMedia }}% probabilidade media</v-chip>
    </div>

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

    <template v-if="isAnalyticsRoute">
      <v-row class="mt-1" dense>
        <v-col v-for="card in analyticsSummaryCards" :key="card.id" cols="12" sm="6" xl="3">
          <v-card class="metric-card analytics-summary-card" elevation="0" :data-testid="`analytics-summary-card-${card.id}`">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.helper }}</small>
          </v-card>
        </v-col>
      </v-row>

      <v-row class="mt-1" dense>
        <v-col cols="12" lg="7">
          <v-card class="state-card analytics-panel" data-testid="analytics-dimensions">
            <v-card-title>Estado atual consolidado</v-card-title>
            <v-card-text class="analytics-stack">
              <div v-for="item in estadoAtualConsolidado" :key="item.id" class="dimension-row">
                <div class="dimension-header">
                  <div>
                    <strong>{{ item.nome }}</strong>
                    <p class="muted mb-0">Maturidade {{ item.maturidade }}</p>
                  </div>
                  <span class="dimension-value">{{ item.percentual }}%</span>
                </div>
                <v-progress-linear :model-value="item.percentual" color="primary" height="8" rounded />
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" lg="5">
          <v-card class="state-card analytics-panel" data-testid="analytics-gaps">
            <v-card-title>Gaps prioritarios</v-card-title>
            <v-card-text class="analytics-stack">
              <div v-for="gap in principaisGaps" :key="gap.id" class="gap-row">
                <div class="dimension-header">
                  <strong>{{ gap.nome }}</strong>
                  <span class="dimension-value gap-value">{{ gap.gap }}%</span>
                </div>
                <v-progress-linear :model-value="gap.gap" color="amber" height="8" rounded />
              </div>
              <v-alert type="info" variant="tonal" density="comfortable" class="mt-2">
                Principal gargalo atual: <strong>{{ resumoProjecao.principalGargalo }}</strong>.
              </v-alert>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row class="mt-1" dense>
        <v-col cols="12" lg="7">
          <v-card class="state-card analytics-panel" data-testid="analytics-scenarios">
            <v-card-title>Janela de conclusao</v-card-title>
            <v-card-text>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>Marco</th>
                    <th>Conservador</th>
                    <th>Acelerado</th>
                    <th>Ganho medio</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="cenario in cenariosComparativos" :key="cenario.id">
                    <td>{{ cenario.nome }}</td>
                    <td>{{ cenario.conservadorFaixa }}</td>
                    <td>{{ cenario.aceleradoFaixa }}</td>
                    <td>{{ cenario.ganhoEstimadoDias }} dias</td>
                  </tr>
                </tbody>
              </v-table>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" lg="5">
          <v-card class="state-card analytics-panel" data-testid="analytics-probabilities">
            <v-card-title>Probabilidade estatistica</v-card-title>
            <v-card-text class="analytics-stack">
              <div v-for="item in probabilidades" :key="item.id" class="dimension-row">
                <div class="dimension-header">
                  <strong>{{ item.nome }}</strong>
                  <span class="dimension-value">{{ item.percentual }}%</span>
                </div>
                <v-progress-linear :model-value="item.percentual" color="green" height="8" rounded />
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row class="mt-1" dense>
        <v-col cols="12" lg="6">
          <v-card class="state-card analytics-panel" data-testid="analytics-risks">
            <v-card-title>Riscos priorizados</v-card-title>
            <v-card-text>
              <v-list density="compact" class="transparent-list">
                <v-list-item
                  v-for="item in riscosPriorizados"
                  :key="item.id"
                  :title="item.nome"
                >
                  <template #append>
                    <v-chip size="small" :color="riskColor(item.nivel)" variant="tonal">{{ item.nivel }}</v-chip>
                  </template>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" lg="6">
          <v-card class="state-card analytics-panel" data-testid="analytics-accelerators">
            <v-card-title>Alavancas com maior ganho marginal</v-card-title>
            <v-card-text>
              <v-list density="compact" class="transparent-list">
                <v-list-item
                  v-for="item in aceleradoresPriorizados"
                  :key="item"
                  prepend-icon="mdi-lightning-bolt-outline"
                  :title="item"
                />
              </v-list>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row class="mt-1" dense>
        <v-col cols="12" lg="7">
          <v-card class="state-card analytics-panel" data-testid="analytics-completion">
            <v-card-title>Percentual real de conclusao</v-card-title>
            <v-card-text class="analytics-stack">
              <div v-for="item in percentualConclusao" :key="item.id" class="dimension-row">
                <div class="dimension-header">
                  <strong>{{ item.nome }}</strong>
                  <span class="dimension-value">{{ item.percentual }}%</span>
                </div>
                <v-progress-linear :model-value="item.percentual" color="info" height="8" rounded />
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" lg="5">
          <v-card class="state-card analytics-panel" data-testid="analytics-trends">
            <v-card-title>Tendencia atual</v-card-title>
            <v-card-text class="analytics-stack">
              <div v-for="item in tendenciasAtuais" :key="item.id" class="trend-row">
                <div>
                  <strong>{{ item.nome }}</strong>
                  <p class="muted mb-0">{{ item.valor }}</p>
                </div>
                <v-chip size="small" :color="trendColor(item.tendencia)" variant="tonal">{{ item.tendencia }}</v-chip>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-alert class="mt-4" type="success" variant="tonal" data-testid="analytics-executive-summary">
        {{ leituraExecutiva }}
      </v-alert>
    </template>

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
        <span class="muted">Versão frontend {{ frontendVersion }} · ambiente {{ environment.id }} · correlation_id {{ correlationId }}</span>
      </div>
      <v-chip size="small" color="green" variant="tonal">sem dado sensível</v-chip>
    </v-card>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  aceleradores,
  calcularResumoProjecao,
  estadoAtualConsolidado,
  gargalosPrincipais,
  listarPrincipaisGaps,
  listarRiscosPriorizados,
  leituraExecutiva,
  montarCenariosComparativos,
  percentualConclusao,
  probabilidades,
  referenciaTemporal,
  tendenciasAtuais
} from '../services/projecaoEstatistica'

const route = useRoute()
const router = useRouter()
const frontendVersion = '3.1.0'
const correlationId = `ufs-${Date.now().toString(36)}`
const isAnalyticsRoute = computed(() => route.path === '/analytics')
const resumoProjecao = computed(() => calcularResumoProjecao())
const principaisGaps = computed(() => listarPrincipaisGaps(4))
const riscosPriorizados = computed(() => listarRiscosPriorizados())
const cenariosComparativos = computed(() => montarCenariosComparativos())
const aceleradoresPriorizados = computed(() => aceleradores.slice(0, 4))

const shellNavItems = [
  { label: 'Início', route: '/home', icon: 'mdi-home-outline' },
  { label: 'Workspace', route: '/workspace', icon: 'mdi-view-dashboard-edit-outline' },
  { label: 'Analytics', route: '/analytics', icon: 'mdi-chart-box-outline' },
  { label: 'Ajuda', route: '/ajuda', icon: 'mdi-help-circle-outline' },
]

const sections = {
  '/home': { title: 'Início operacional', description: 'Ponto de entrada do usuário final com orientação clara, ambiente visível e acesso às áreas principais.' },
  '/workspace': { title: 'Workspace', description: 'Área de trabalho inicial para acompanhar pendências, requisitos e próximas ações operacionais.' },
  '/analytics': { title: 'Projeção estatística de conclusão', description: 'Visão executiva aplicada com ritmo recente, gaps, cenários, riscos e aceleradores para consolidar o padrão ouro.' },
  '/ajuda': { title: 'Ajuda e onboarding', description: 'Orientação rápida para começar a usar o ReqSys sem depender de documentação externa.' },
}

const section = computed(() => sections[route.path] || sections['/home'])
const environment = computed(() => {
  const raw = (import.meta.env.VITE_APP_ENVIRONMENT || 'DEV').toUpperCase()
  if (['PRD', 'PROD', 'PRODUCTION', 'PRODUCAO'].includes(raw)) return { id: 'PRD', label: 'Produção', color: 'red' }
  if (['HML', 'HOMOLOG', 'HOMOLOGACAO', 'STAGING'].includes(raw)) return { id: 'HML', label: 'Homologação', color: 'amber' }
  return { id: 'DEV', label: 'Desenvolvimento', color: 'blue' }
})

const operationalCards = computed(() => {
  if (isAnalyticsRoute.value) {
    return [
      { id: 'estatisticas', title: 'Indicadores auditaveis', description: 'Abrir a base detalhada de estatisticas, fonte, formula e guard rails.', icon: 'mdi-chart-box-outline', status: 'Auditavel', statusColor: 'green', route: '/estatisticas' },
      { id: 'monitoramento', title: 'Runtime e CI', description: 'Cruzar a projecao com monitoramento operacional, readiness e analytics runtime.', icon: 'mdi-monitor-dashboard', status: 'Vivo', statusColor: 'blue', route: '/monitoramento-operacional' },
      { id: 'governanca', title: 'Governanca aplicada', description: 'Conectar o forecast aos gates, riscos e a consolidacao do padrao ouro.', icon: 'mdi-shield-check-outline', status: 'Enterprise', statusColor: 'amber', route: '/governanca' },
    ]
  }

  return [
    { id: 'requisitos', title: 'Requisitos', description: 'Consultar e acompanhar o catalogo de requisitos e demandas.', icon: 'mdi-file-document-edit-outline', status: 'MVP', statusColor: 'blue', route: '/requisitos' },
    { id: 'pendencias', title: 'Pendencias operacionais', description: 'Acessar a area de trabalho com filtros preparados para itens pendentes.', icon: 'mdi-clipboard-alert-outline', status: 'Inicial', statusColor: 'amber', route: '/workspace?status=pendente' },
    { id: 'governanca', title: 'Governanca', description: 'Visualizar gates, evidencias e trilhas de auditoria em alto nivel.', icon: 'mdi-shield-check-outline', status: 'Auditavel', statusColor: 'green', route: '/governanca' },
  ]
})

const uiStates = [
  { id: 'loading', label: 'Carregando', message: 'Exibir feedback não bloqueante enquanto dados operacionais são carregados.', icon: 'mdi-loading', color: 'blue' },
  { id: 'empty', label: 'Sem dados', message: 'Explicar o próximo passo quando não houver informações disponíveis.', icon: 'mdi-inbox-outline', color: 'grey' },
  { id: 'error', label: 'Erro operacional', message: 'Mostrar mensagem segura e caminho de recuperação sem expor detalhe sensível.', icon: 'mdi-alert-circle-outline', color: 'red' },
  { id: 'success', label: 'Disponível', message: 'Exibir conteúdo e ações primárias quando a área estiver pronta.', icon: 'mdi-check-circle-outline', color: 'green' },
  { id: 'unauthorized', label: 'Acesso restrito', message: 'Orientar login ou permissão necessária sem vazar regra interna.', icon: 'mdi-lock-outline', color: 'amber' },
]

const nextSteps = computed(() => {
  if (isAnalyticsRoute.value) {
    return [
      { title: 'Remediar gargalos de CI', subtitle: gargalosPrincipais[0], icon: 'mdi-source-branch-refresh' },
      { title: 'Sincronizar ambientes', subtitle: 'Reduzir o maior gap residual antes do hardening final.', icon: 'mdi-lan-connect' },
      { title: 'Automatizar evidencias', subtitle: listarAceleradoresPrioritariosText(), icon: 'mdi-file-document-check-outline' },
    ]
  }

  return [
    { title: 'Abrir workspace', subtitle: 'Entender pendencias e itens em andamento.', icon: 'mdi-view-dashboard-outline' },
    { title: 'Consultar requisitos', subtitle: 'Acompanhar demanda, status e rastreabilidade.', icon: 'mdi-file-search-outline' },
    { title: 'Ver governanca', subtitle: 'Conferir gates, evidencias e seguranca operacional.', icon: 'mdi-shield-search' },
  ]
})

const analyticsSummaryCards = computed(() => [
  {
    id: 'consolidacao-media',
    label: 'Consolidacao media',
    value: `${resumoProjecao.value.consolidacaoMedia}%`,
    helper: 'Media dos indicadores reais de conclusao'
  },
  {
    id: 'maturidade-ecossistema',
    label: 'Maturidade do ecossistema',
    value: `${resumoProjecao.value.maturidadeEcossistema}%`,
    helper: 'Media do estado atual consolidado'
  },
  {
    id: 'capacidade-mensurada',
    label: 'Capacidade semanal segura',
    value: `${resumoProjecao.value.capacidadeSemanalMerges} merges`,
    helper: `${resumoProjecao.value.capacidadeSemanalPrs} PRs em cadencia media`
  },
  {
    id: 'lead-time',
    label: 'Lead time medio',
    value: `${resumoProjecao.value.leadTimeMedioMinutos} min`,
    helper: `${resumoProjecao.value.estabilizacaoCi}% de estabilizacao de CI`
  }
])

function listarAceleradoresPrioritariosText() {
  return aceleradoresPriorizados.value[0] || 'Pipeline consolidado'
}

function riskColor(nivel) {
  if (nivel === 'Medio') return 'error'
  if (nivel === 'Medio/Baixo') return 'warning'
  return 'success'
}

function trendColor(tendencia) {
  if (tendencia === 'Forte') return 'success'
  if (tendencia === 'Moderada') return 'info'
  return 'amber'
}

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
.hero-actions, .shell-navigation { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.shell-navigation { align-items: center; justify-content: flex-start; padding: 10px; border-radius: 14px; }
.shell-nav-button { min-width: 132px; }
.environment-chip { font-weight: 800; }
.analytics-meta { display: flex; gap: 10px; flex-wrap: wrap; }
.metric-card { padding: 16px; height: 100%; border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.metric-card span, .metric-card small { display: block; color: rgba(0, 0, 0, 0.62); }
.metric-card strong { display: block; margin: 8px 0 4px; font-size: 30px; }
.analytics-panel { border: 1px solid rgba(148, 163, 184, 0.24); }
.analytics-stack { display: grid; gap: 12px; }
.dimension-row, .trend-row, .gap-row { display: grid; gap: 8px; }
.dimension-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dimension-value { font-weight: 800; color: var(--accent); }
.gap-value { color: #b45309; }
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
@media (max-width: 760px) {
  .user-final-page { padding: 12px; }
  .user-final-hero { flex-direction: column; padding: 18px; }
  .hero-actions, .shell-navigation { align-items: stretch; justify-content: flex-start; width: 100%; }
  .hero-actions :deep(.v-btn), .shell-nav-button { width: 100%; }
  .dimension-header { align-items: flex-start; flex-direction: column; }
}
</style>
