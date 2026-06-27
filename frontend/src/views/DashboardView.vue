<template>
  <section class="page" data-testid="route-dashboard">
    <div class="page-header">
      <div>
        <h1>Dashboard de Requisitos</h1>
        <p class="muted dashboard-subtitle">Visão consolidada de métricas, pipeline operacional e informações do sistema.</p>
      </div>
      <v-chip size="small" color="amber" variant="tonal" data-testid="ambiente-chip">
        {{ ambienteLabel }}
      </v-chip>
    </div>

    <v-row>
      <v-col
        v-for="card in cards"
        :key="card.titulo"
        cols="12"
        sm="6"
        lg="3"
      >
        <v-menu open-on-hover open-on-click location="bottom" :offset="8">
          <template #activator="{ props }">
            <v-card
              v-bind="props"
              class="metric metric-interactive"
              :data-testid="`metric-card-${card.id}`"
              role="button"
              tabindex="0"
              @keyup.enter="irPara(card.rota)"
              @keyup.space.prevent="irPara(card.rota)"
            >
              <div class="metric-head">
                <v-icon size="18" :icon="card.icone" class="metric-icon" />
                <div class="metric-title-wrap">
                  <div class="muted metric-title">{{ card.titulo }}</div>
                </div>
                <v-tooltip :text="card.tooltip" location="top">
                  <template #activator="{ props: tooltipProps }">
                    <v-btn
                      v-bind="tooltipProps"
                      icon="mdi-information-outline"
                      variant="text"
                      density="compact"
                      size="x-small"
                      :data-testid="`tooltip-${card.id}`"
                      aria-label="Informação da métrica"
                      @click.stop
                    />
                  </template>
                </v-tooltip>
              </div>

              <div class="metric-value-row">
                <div class="metric-value">{{ card.valor }}</div>
                <v-tooltip text="Abrir analítico filtrado" location="top">
                  <template #activator="{ props: actionProps }">
                    <v-btn
                      v-bind="actionProps"
                      icon="mdi-open-in-new"
                      variant="tonal"
                      size="small"
                      color="amber"
                      aria-label="Abrir analítico filtrado da métrica"
                      @click.stop="irPara(card.rota)"
                    />
                  </template>
                </v-tooltip>
              </div>
            </v-card>
          </template>

          <v-card class="metric-preview pa-3">
            <div class="preview-title">{{ card.titulo }}</div>
            <div class="muted preview-text">{{ card.resumo }}</div>
            <v-divider class="my-2" />
            <div class="preview-value">Valor atual: {{ card.valor }}</div>
            <v-btn class="mt-2" size="small" color="amber" variant="flat" @click="irPara(card.rota)">
              Ver analítico
            </v-btn>
          </v-card>
        </v-menu>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col cols="12" lg="7">
        <v-card class="mt-4">
          <v-card-title>Pipeline operacional</v-card-title>
          <v-card-text>
            <v-timeline density="compact" side="end" truncate-line="both">
              <v-timeline-item
                v-for="step in pipelineSteps"
                :key="step.titulo"
                :dot-color="step.cor"
              >
                <div class="step-row">
                  <strong>{{ step.titulo }}</strong>
                  <v-tooltip :text="step.tooltip" location="top">
                    <template #activator="{ props }">
                      <v-icon v-bind="props" icon="mdi-help-circle-outline" size="16" class="step-help" />
                    </template>
                  </v-tooltip>
                </div>
                <div class="muted">{{ step.descricao }}</div>
              </v-timeline-item>
            </v-timeline>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card class="mt-4" data-testid="dashboard-info-card">
          <v-card-title>Informações do sistema</v-card-title>
          <v-card-text>
            <div class="info-line">
              <span class="muted">Total de requisitos:</span>
              <strong>{{ totalRequisitosInfo }}</strong>
            </div>
            <div class="info-line">
              <span class="muted">Status:</span>
              <strong>{{ sistemaStatus }}</strong>
            </div>
            <div class="info-line">
              <span class="muted">Atualizado em:</span>
              <strong>{{ timestampLabel }}</strong>
            </div>

            <v-divider class="my-3" />

            <div class="muted mb-2">Endpoints críticos</div>
            <v-list density="compact" class="dashboard-list">
              <v-list-item
                v-for="ep in endpointsCriticos"
                :key="`${ep.metodo}-${ep.url}`"
                :title="ep.titulo"
                :subtitle="`${ep.metodo} ${ep.url}`"
              />
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRequisitosStore } from '../stores/requisitos'
import { api } from '../services/api'
import { contarIntegracoesPorStatus } from '../utils/filtrosIntegracao'
import { carregarHistoricoGovbi, contarConsultasGovbi } from '../utils/filtrosGovbi'
import { achatarHistoricoPipeline, carregarHistoricoPipeline, contarEtapasPipeline } from '../utils/filtrosPipeline'

const store = useRequisitosStore()
const router = useRouter()
const integracaoErros = ref(0)
const govbiDegradado = ref(0)
const pipelineErros = ref(0)

onMounted(async () => {
  await Promise.all([
    store.carregarMetricas(),
    store.carregarDashboardInfo(),
    store.carregarQualidadeIA(),
    carregarIntegracaoErros(),
    carregarMetricasAnaliticas(),
  ])
})

function carregarMetricasAnaliticas() {
  const consultasGovbi = carregarHistoricoGovbi()
  govbiDegradado.value = contarConsultasGovbi(consultasGovbi).erros
  const etapasPipeline = achatarHistoricoPipeline(carregarHistoricoPipeline())
  pipelineErros.value = contarEtapasPipeline(etapasPipeline).erros
}

async function carregarIntegracaoErros() {
  try {
    const resp = await api.get('/v1/hub-lowcode/integracoes/historico?limit=100')
    const eventos = resp.data?.data?.eventos || []
    integracaoErros.value = contarIntegracoesPorStatus(eventos).erros
  } catch (_) {
    integracaoErros.value = 0
  }
}

const cards = computed(() => [
  {
    id: 'requisitos',
    titulo: 'Requisitos',
    valor: store.metricas.total ?? 0,
    icone: 'mdi-file-document-outline',
    tooltip: 'Quantidade total de requisitos cadastrados.',
    resumo: 'Acompanhe a base completa de requisitos e entre no módulo para filtrar por área, urgência e status.',
    rota: { path: '/requisitos' },
  },
  {
    id: 'em-analise',
    titulo: 'Em análise',
    valor: store.metricas.em_analise ?? 0,
    icone: 'mdi-chart-timeline-variant',
    tooltip: 'Requisitos atualmente em avaliação técnica/funcional.',
    resumo: 'Abre o analítico de requisitos filtrado por status em análise.',
    rota: { path: '/requisitos', query: { status: 'em_analise' } },
  },
  {
    id: 'aprovados',
    titulo: 'Aprovados',
    valor: store.metricas.aprovados ?? 0,
    icone: 'mdi-check-decagram-outline',
    tooltip: 'Requisitos aprovados para execução.',
    resumo: 'Abre o analítico de requisitos aprovados para execução e rastreabilidade.',
    rota: { path: '/requisitos', query: { status: 'aprovado' } },
  },
  {
    id: 'qualidade-ia',
    titulo: 'Qualidade IA',
    valor: `${Math.round((store.qualidadeIAResumo.score_geral ?? 0))}%`,
    icone: 'mdi-brain',
    tooltip: 'Score geral de qualidade do módulo de IA monitorado no backend.',
    resumo: 'Monitore acurácia, consistência, segurança e tendência de qualidade dos resultados de IA.',
    rota: { path: '/qualidade-ia' },
  },
  {
    id: 'pendencias',
    titulo: 'Pendências',
    valor: store.metricas.pendentes ?? 0,
    icone: 'mdi-alert-circle-outline',
    tooltip: 'Itens que ainda demandam ajuste ou decisão.',
    resumo: 'Abre o analítico de requisitos recebidos, que normalmente ainda exigem triagem ou decisão.',
    rota: { path: '/requisitos', query: { status: 'recebido' } },
  },
  {
    id: 'integracao-erros',
    titulo: 'Erros integração',
    valor: integracaoErros.value,
    icone: 'mdi-connection',
    tooltip: 'Falhas recentes em envios Planner ou Teams.',
    resumo: 'Abre o painel de integrações filtrado por erros, com origem, data e correlation_id.',
    rota: { path: '/painel-integracao', query: { status: 'erro' } },
  },
  {
    id: 'govbi-degradado',
    titulo: 'GovBI degradado',
    valor: govbiDegradado.value,
    icone: 'mdi-robot-outline',
    tooltip: 'Consultas GovBI com erro ou modo degradado na sessão.',
    resumo: 'Abre o histórico analítico GovBI filtrado por status degradado.',
    rota: { path: '/govbi-ia', query: { status: 'MODO_DEGRADADO' } },
  },
  {
    id: 'pipeline-erros',
    titulo: 'Pipeline com erro',
    valor: pipelineErros.value,
    icone: 'mdi-pipe',
    tooltip: 'Etapas de pipeline com falha registradas na sessão.',
    resumo: 'Abre o analítico de execuções do pipeline filtrado por etapas com erro.',
    rota: { path: '/pipeline', query: { status: 'error' } },
  },
  {
    id: 'task-console',
    titulo: 'Task Console',
    valor: store.metricas.pendentes ?? 0,
    icone: 'mdi-console',
    tooltip: 'Tarefas pendentes de envio ao Planner.',
    resumo: 'Abre o Task Console com filtro de tarefas pendentes.',
    rota: { path: '/task-console', query: { status: 'pendente' } },
  },
])

function irPara(rota) {
  if (!rota) return
  router.push(rota)
}

const pipelineSteps = [
  {
    titulo: 'Entrada',
    descricao: 'SharePoint, Forms e planilhas Excel',
    cor: 'blue',
    tooltip: 'Fontes de entrada da demanda de negócio.',
  },
  {
    titulo: 'Normalização e validação',
    descricao: 'Padronização e checagens de consistência',
    cor: 'green',
    tooltip: 'Aplicação de regras para garantir qualidade dos dados.',
  },
  {
    titulo: 'Estruturação do requisito',
    descricao: 'Requisito, histórias e backlog',
    cor: 'orange',
    tooltip: 'Transformação da demanda em artefatos rastreáveis.',
  },
  {
    titulo: 'Publicação e auditoria',
    descricao: 'Redmine, Planner e trilha de auditoria',
    cor: 'purple',
    tooltip: 'Distribuição para execução e registro de governança.',
  },
]

const dashboardInfo = computed(() => store.dashboardInfo || {})
const resumo = computed(() => dashboardInfo.value.resumo || {})

const totalRequisitosInfo = computed(() => resumo.value.total_requisitos ?? store.metricas.total ?? 0)
const sistemaStatus = computed(() => resumo.value.sistema_status || 'indisponível')
const ambienteLabel = computed(() => (resumo.value.ambiente || 'desconhecido').replace('_', ' '))
const endpointsCriticos = computed(() => dashboardInfo.value.endpoints_criticos || [])

const timestampLabel = computed(() => {
  const raw = dashboardInfo.value.timestamp
  if (!raw) return '—'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('pt-BR')
})
</script>

<style scoped>
.dashboard-subtitle {
  max-width: 58ch;
}

.metric {
  height: 100%;
  min-height: 132px;
  padding: 14px;
}

.metric-interactive {
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.metric-interactive:hover,
.metric-interactive:focus-visible {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--accent) 38%, var(--border));
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.22);
  outline: 2px solid color-mix(in srgb, var(--accent) 55%, transparent);
  outline-offset: 2px;
}

.metric-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-title-wrap {
  flex: 1;
}

.metric-title {
  font-size: 13px;
}

.metric-value-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.metric-preview {
  width: min(360px, calc(100vw - 32px));
  border-radius: 12px;
}

.preview-title {
  font-size: 15px;
  font-weight: 700;
}

.preview-text {
  margin-top: 6px;
  line-height: 1.45;
}

.preview-value {
  font-weight: 700;
}

.metric-icon {
  color: var(--accent);
}

.step-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.step-help {
  color: var(--muted);
  cursor: help;
}

.info-line {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.dashboard-list {
  background: transparent !important;
}

@media (max-width: 600px) {
  .metric-value {
    font-size: 28px;
  }

  .metric-preview {
    width: calc(100vw - 24px);
  }
}
</style>
