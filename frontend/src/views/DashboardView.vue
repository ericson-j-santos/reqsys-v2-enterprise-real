<template>
  <section class="dashboard-operacional" data-testid="route-dashboard" aria-labelledby="titulo-dashboard">
    <div class="dashboard-header">
      <div>
        <p class="eyebrow">ReqSys · Trilha C · Dashboard Operacional</p>
        <h1 id="titulo-dashboard">Dashboard de Requisitos</h1>
        <p class="muted dashboard-subtitle">
          Visão consolidada com semáforo operacional, cards clicáveis e drill-down filtrado para requisitos,
          pipeline, integrações e analytics.
        </p>
      </div>
      <div class="header-actions">
        <v-chip size="small" color="amber" variant="tonal" data-testid="ambiente-chip">
          {{ ambienteLabel }}
        </v-chip>
        <SemaforoChip :value="semaforoGeralValor" size="large" data-testid="dashboard-semaforo-geral" />
        <v-btn
          color="amber"
          variant="flat"
          prepend-icon="mdi-refresh"
          :loading="carregando"
          data-testid="dashboard-atualizar"
          @click="carregarTudo"
        >
          Atualizar
        </v-btn>
      </div>
    </div>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <v-row dense class="mt-2">
      <v-col v-for="card in cards" :key="card.id" cols="12" sm="6" lg="3">
        <OperationalMetricCard
          :label="card.label"
          :value="card.value"
          :semaforo="card.semaforo"
          :icon="card.icon"
          :hint="card.hint"
          :test-id="`metric-card-${card.id}`"
          @drilldown="irPara(card.rota)"
        />
      </v-col>
    </v-row>

    <v-row class="mt-2" dense>
      <v-col cols="12" lg="7">
        <v-card class="panel" elevation="0">
          <v-card-title>Pipeline operacional</v-card-title>
          <v-card-subtitle>Etapas clicáveis com drill-down para o analítico correspondente.</v-card-subtitle>
          <v-card-text>
            <v-timeline density="compact" side="end" truncate-line="both">
              <v-timeline-item
                v-for="step in pipelineSteps"
                :key="step.titulo"
                :dot-color="step.cor"
              >
                <div
                  class="step-row step-row--clickable"
                  role="button"
                  tabindex="0"
                  :data-testid="`pipeline-step-${step.id}`"
                  @click="irPara(step.rota)"
                  @keyup.enter="irPara(step.rota)"
                  @keyup.space.prevent="irPara(step.rota)"
                >
                  <div>
                    <strong>{{ step.titulo }}</strong>
                    <div class="muted">{{ step.descricao }}</div>
                  </div>
                  <div class="step-actions">
                    <v-tooltip :text="step.tooltip" location="top">
                      <template #activator="{ props }">
                        <v-icon v-bind="props" icon="mdi-help-circle-outline" size="16" class="step-help" @click.stop />
                      </template>
                    </v-tooltip>
                    <v-btn size="small" variant="tonal" color="amber" @click.stop="irPara(step.rota)">
                      Abrir analítico
                    </v-btn>
                  </div>
                </div>
              </v-timeline-item>
            </v-timeline>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card class="panel" elevation="0" data-testid="dashboard-info-card">
          <v-card-title>Informações do sistema</v-card-title>
          <v-card-text>
            <div class="info-line">
              <span class="muted">Total de requisitos:</span>
              <strong>{{ totalRequisitosInfo }}</strong>
            </div>
            <div class="info-line">
              <span class="muted">Status:</span>
              <SemaforoChip :value="statusSistemaSemaforo" size="x-small" />
              <strong>{{ sistemaStatus }}</strong>
            </div>
            <div class="info-line">
              <span class="muted">Atualizado em:</span>
              <strong>{{ timestampLabel }}</strong>
            </div>

            <v-divider class="my-3" />

            <div class="muted mb-2">Destinos analíticos</div>
            <v-list density="compact" class="dashboard-list">
              <v-list-item
                v-for="destino in destinosAnaliticos"
                :key="destino.path"
                :prepend-icon="destino.icon"
                :title="destino.title"
                :subtitle="destino.subtitle"
                role="button"
                tabindex="0"
                :data-testid="`destino-${destino.id}`"
                @click="irPara({ path: destino.path, query: destino.query })"
                @keyup.enter="irPara({ path: destino.path, query: destino.query })"
              />
            </v-list>

            <v-divider class="my-3" />

            <div class="muted mb-2">Endpoints críticos</div>
            <v-list density="compact" class="dashboard-list">
              <v-list-item
                v-for="ep in endpointsCriticos"
                :key="`${ep.metodo}-${ep.url}`"
                :title="ep.titulo"
                :subtitle="`${ep.metodo} ${ep.url}`"
                prepend-icon="mdi-api"
                role="button"
                tabindex="0"
                @click="irPara({ path: '/monitoramento-operacional', query: { secao: 'runtime' } })"
                @keyup.enter="irPara({ path: '/monitoramento-operacional', query: { secao: 'runtime' } })"
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
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import SemaforoChip from '../components/SemaforoChip.vue'
import { useRequisitosStore } from '../stores/requisitos'
import { api } from '../services/api'
import { semaforoGeral } from '../utils/filtrosMonitoramento'
import { contarIntegracoesPorStatus } from '../utils/filtrosIntegracao'
import { carregarHistoricoGovbi, contarConsultasGovbi } from '../utils/filtrosGovbi'
import { achatarHistoricoPipeline, carregarHistoricoPipeline, contarEtapasPipeline } from '../utils/filtrosPipeline'

const store = useRequisitosStore()
const router = useRouter()
const integracaoErros = ref(0)
const govbiDegradado = ref(0)
const pipelineErros = ref(0)
const carregando = ref(false)
const erro = ref('')

onMounted(carregarTudo)

async function carregarTudo() {
  carregando.value = true
  erro.value = ''
  try {
    await Promise.all([
      store.carregarMetricas(),
      store.carregarDashboardInfo(),
      store.carregarQualidadeIA(),
      carregarIntegracaoErros(),
      carregarMetricasAnaliticas(),
    ])
  } catch (e) {
    erro.value = e?.message || 'Erro ao carregar dashboard operacional'
  } finally {
    carregando.value = false
  }
}

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

function semaforoQualidadeIA(score) {
  const valor = Number(score ?? 0)
  if (valor < 70) return 'vermelho'
  if (valor < 90) return 'amarelo'
  return 'verde'
}

function semaforoContagem(valor, limiarAtencao = 0) {
  return Number(valor) > limiarAtencao ? 'amarelo' : 'verde'
}

function semaforoErro(valor) {
  return Number(valor) > 0 ? 'vermelho' : 'verde'
}

const cards = computed(() => {
  const scoreIA = Math.round(store.qualidadeIAResumo.score_geral ?? 0)
  const pendentes = store.metricas.pendentes ?? 0
  const emAnalise = store.metricas.em_analise ?? 0

  return [
    {
      id: 'requisitos',
      label: 'Requisitos',
      value: store.metricas.total ?? 0,
      semaforo: 'verde',
      icon: 'mdi-file-document-outline',
      hint: 'Base completa de requisitos cadastrados',
      rota: { path: '/requisitos' },
    },
    {
      id: 'em-analise',
      label: 'Em análise',
      value: emAnalise,
      semaforo: semaforoContagem(emAnalise),
      icon: 'mdi-chart-timeline-variant',
      hint: 'Requisitos em avaliação técnica/funcional',
      rota: { path: '/requisitos', query: { status: 'em_analise' } },
    },
    {
      id: 'aprovados',
      label: 'Aprovados',
      value: store.metricas.aprovados ?? 0,
      semaforo: 'verde',
      icon: 'mdi-check-decagram-outline',
      hint: 'Requisitos aprovados para execução',
      rota: { path: '/requisitos', query: { status: 'aprovado' } },
    },
    {
      id: 'qualidade-ia',
      label: 'Qualidade IA',
      value: `${scoreIA}%`,
      semaforo: semaforoQualidadeIA(scoreIA),
      icon: 'mdi-brain',
      hint: 'Score geral de qualidade do módulo de IA',
      rota: { path: '/qualidade-ia' },
    },
    {
      id: 'pendencias',
      label: 'Pendências',
      value: pendentes,
      semaforo: semaforoContagem(pendentes),
      icon: 'mdi-alert-circle-outline',
      hint: 'Itens que demandam triagem ou decisão',
      rota: { path: '/requisitos', query: { status: 'recebido' } },
    },
    {
      id: 'integracao-erros',
      label: 'Erros integração',
      value: integracaoErros.value,
      semaforo: semaforoErro(integracaoErros.value),
      icon: 'mdi-connection',
      hint: 'Falhas recentes em Planner ou Teams',
      rota: { path: '/painel-integracao', query: { status: 'erro' } },
    },
    {
      id: 'govbi-degradado',
      label: 'GovBI degradado',
      value: govbiDegradado.value,
      semaforo: semaforoErro(govbiDegradado.value),
      icon: 'mdi-robot-outline',
      hint: 'Consultas GovBI com erro ou modo degradado',
      rota: { path: '/govbi-ia', query: { status: 'MODO_DEGRADADO' } },
    },
    {
      id: 'pipeline-erros',
      label: 'Pipeline com erro',
      value: pipelineErros.value,
      semaforo: semaforoErro(pipelineErros.value),
      icon: 'mdi-pipe',
      hint: 'Etapas de pipeline com falha registradas',
      rota: { path: '/pipeline', query: { status: 'error' } },
    },
    {
      id: 'task-console',
      label: 'Task Console',
      value: pendentes,
      semaforo: semaforoContagem(pendentes),
      icon: 'mdi-console',
      hint: 'Tarefas pendentes de envio ao Planner',
      rota: { path: '/task-console', query: { status: 'pendente' } },
    },
  ]
})

const resumoSemaforo = computed(() => {
  return cards.value.reduce((acc, card) => {
    const chave = card.semaforo || 'desconhecido'
    acc[chave] = (acc[chave] || 0) + 1
    return acc
  }, { verde: 0, amarelo: 0, vermelho: 0, bloqueado: 0 })
})

const semaforoGeralValor = computed(() => semaforoGeral(resumoSemaforo.value))

const pipelineSteps = [
  {
    id: 'entrada',
    titulo: 'Entrada',
    descricao: 'SharePoint, Forms e planilhas Excel',
    cor: 'blue',
    tooltip: 'Fontes de entrada da demanda de negócio.',
    rota: { path: '/hub-lowcode' },
  },
  {
    id: 'normalizacao',
    titulo: 'Normalização e validação',
    descricao: 'Padronização e checagens de consistência',
    cor: 'green',
    tooltip: 'Aplicação de regras para garantir qualidade dos dados.',
    rota: { path: '/pipeline' },
  },
  {
    id: 'estruturacao',
    titulo: 'Estruturação do requisito',
    descricao: 'Requisito, histórias e backlog',
    cor: 'orange',
    tooltip: 'Transformação da demanda em artefatos rastreáveis.',
    rota: { path: '/requisitos' },
  },
  {
    id: 'publicacao',
    titulo: 'Publicação e auditoria',
    descricao: 'Redmine, Planner e trilha de auditoria',
    cor: 'purple',
    tooltip: 'Distribuição para execução e registro de governança.',
    rota: { path: '/painel-integracao' },
  },
]

const destinosAnaliticos = [
  { id: 'analytics', path: '/analytics', icon: 'mdi-chart-box-outline', title: 'Analytics navegável', subtitle: 'Hub executivo com runtime e drill-down' },
  { id: 'monitoramento', path: '/monitoramento-operacional', query: { estado: 'vermelho' }, icon: 'mdi-alert-circle-outline', title: 'Incidentes críticos', subtitle: 'Itens em vermelho ou bloqueados' },
  { id: 'estatisticas', path: '/estatisticas', icon: 'mdi-chart-line', title: 'Estatísticas auditáveis', subtitle: 'Indicadores com fonte e fórmula' },
  { id: 'integracoes', path: '/painel-integracao', query: { status: 'erro' }, icon: 'mdi-connection', title: 'Erros de integração', subtitle: 'Eventos com falha e correlation_id' },
]

function irPara(rota) {
  if (!rota?.path) return
  router.push(rota)
}

const dashboardInfo = computed(() => store.dashboardInfo || {})
const resumo = computed(() => dashboardInfo.value.resumo || {})

const totalRequisitosInfo = computed(() => resumo.value.total_requisitos ?? store.metricas.total ?? 0)
const sistemaStatus = computed(() => resumo.value.sistema_status || 'indisponível')
const statusSistemaSemaforo = computed(() => {
  const status = String(sistemaStatus.value).toLowerCase()
  if (status.includes('ok') || status.includes('healthy') || status.includes('dispon') || status.includes('operacional')) return 'verde'
  if (status.includes('degrad') || status.includes('aten')) return 'amarelo'
  if (status.includes('indispon') || status.includes('erro') || status.includes('crit')) return 'vermelho'
  return 'desconhecido'
})
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
.dashboard-operacional {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px;
}

.dashboard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.eyebrow {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
}

h1 {
  margin: 0;
  font-size: clamp(24px, 4vw, 38px);
  line-height: 1.05;
}

.dashboard-subtitle {
  max-width: 62ch;
}

.muted {
  color: var(--text-muted, #6b7280);
}

.panel {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 16px;
}

.erro {
  border: 1px solid #d1242f;
  border-radius: 8px;
  color: #d1242f;
  padding: 0.75rem;
}

.step-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.step-row--clickable {
  cursor: pointer;
  border-radius: 10px;
  padding: 4px 6px;
  margin: -4px -6px;
  transition: background 0.16s ease;
}

.step-row--clickable:hover,
.step-row--clickable:focus-visible {
  background: color-mix(in srgb, var(--accent) 8%, transparent);
  outline: 2px solid color-mix(in srgb, var(--accent) 45%, transparent);
  outline-offset: 2px;
}

.step-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-help {
  color: var(--muted);
  cursor: help;
}

.info-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.dashboard-list {
  background: transparent !important;
}

@media (max-width: 700px) {
  .dashboard-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
  }
}
</style>
