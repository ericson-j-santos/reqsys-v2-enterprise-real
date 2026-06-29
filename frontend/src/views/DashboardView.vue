<template>
  <section class="dashboard-operacional" data-testid="route-dashboard" aria-labelledby="titulo-dashboard">
    <div class="dashboard-header">
      <div>
        <p class="figma-eyebrow">ReqSys · Trilha C · Dashboard Operacional</p>
        <h1 id="titulo-dashboard">Dashboard de Requisitos</h1>
        <p class="muted dashboard-subtitle">
          Visão consolidada com semáforo operacional, cards clicáveis e drill-down filtrado.
        </p>
      </div>
      <div class="header-actions">
        <span class="figma-pill" data-testid="ambiente-chip">Ambiente: {{ ambienteLabel }}</span>
        <div
          class="figma-semaforo-geral"
          :class="`figma-semaforo-geral--${semaforoGeralValor}`"
          data-testid="dashboard-semaforo-geral"
        >
          <span class="figma-semaforo-dot" :class="`figma-semaforo-dot--${semaforoGeralValor}`" />
          Geral: {{ semaforoGeralLabel }}
        </div>
        <v-btn
          color="primary"
          variant="flat"
          class="figma-btn-atualizar"
          :loading="carregando"
          data-testid="dashboard-atualizar"
          @click="carregarTudo"
        >
          Atualizar
        </v-btn>
      </div>
    </div>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <div class="metrics-grid">
      <OperationalMetricCard
        v-for="card in cards"
        :key="card.id"
        :label="card.label"
        :value="card.value"
        :semaforo="card.semaforo"
        :icon="card.icon"
        :hint="card.hint"
        :test-id="`metric-card-${card.id}`"
        @drilldown="irPara(card.rota)"
      />
    </div>

    <div class="lower-panels">
      <section class="figma-panel pipeline-panel">
        <h2>Pipeline operacional</h2>
        <p class="panel-lead">Etapas clicáveis com drill-down para o analítico correspondente.</p>
        <div class="timeline-steps">
          <div
            v-for="step in pipelineSteps"
            :key="step.id"
            class="timeline-step"
            role="button"
            tabindex="0"
            :data-testid="`pipeline-step-${step.id}`"
            @click="irPara(step.rota)"
            @keyup.enter="irPara(step.rota)"
            @keyup.space.prevent="irPara(step.rota)"
          >
            <div>
              <strong>{{ step.titulo }}</strong>
              <span>{{ step.descricao }}</span>
            </div>
            <span class="step-btn">Abrir analítico</span>
          </div>
        </div>
      </section>

      <section class="figma-panel info-panel" data-testid="dashboard-info-card">
        <h2>Informações do sistema</h2>
        <p class="panel-lead">Destinos analíticos e endpoints críticos.</p>
        <div class="figma-list">
          <div
            v-for="item in painelDireito"
            :key="item.id"
            class="figma-list-item"
            role="button"
            tabindex="0"
            :data-testid="item.testId"
            @click="irPara(item.rota)"
            @keyup.enter="irPara(item.rota)"
            @keyup.space.prevent="irPara(item.rota)"
          >
            <strong>{{ item.title }}</strong>
            <small>{{ item.subtitle }}</small>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import { useRequisitosStore } from '../stores/requisitos'
import { api } from '../services/api'
import { semaforoGeral, normalizarSemaforo } from '../utils/filtrosMonitoramento'
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
const semaforoGeralLabel = computed(() => normalizarSemaforo(semaforoGeralValor.value).label)

const pipelineSteps = [
  {
    id: 'entrada',
    titulo: 'Entrada',
    descricao: 'SharePoint, Forms e planilhas Excel',
    rota: { path: '/hub-lowcode' },
  },
  {
    id: 'normalizacao',
    titulo: 'Normalização e validação',
    descricao: 'Padronização e checagens de consistência',
    rota: { path: '/pipeline' },
  },
  {
    id: 'estruturacao',
    titulo: 'Estruturação do requisito',
    descricao: 'Requisito, histórias e backlog',
    rota: { path: '/requisitos' },
  },
  {
    id: 'publicacao',
    titulo: 'Publicação e auditoria',
    descricao: 'Redmine, Planner e trilha de auditoria',
    rota: { path: '/painel-integracao' },
  },
]

const painelDireito = computed(() => {
  const endpoint = (dashboardInfo.value.endpoints_criticos || []).find(
    (ep) => String(ep.url || '').includes('/dashboard/requisitos'),
  ) || (dashboardInfo.value.endpoints_criticos || [])[0]

  const items = [
    {
      id: 'analytics',
      title: 'Analytics navegável',
      subtitle: 'Hub executivo com runtime',
      rota: { path: '/analytics' },
      testId: 'destino-analytics',
    },
    {
      id: 'monitoramento',
      title: 'Incidentes críticos',
      subtitle: 'Itens em vermelho ou bloqueados',
      rota: { path: '/monitoramento-operacional', query: { estado: 'vermelho' } },
      testId: 'destino-monitoramento',
    },
    {
      id: 'estatisticas',
      title: 'Estatísticas auditáveis',
      subtitle: 'Indicadores com fonte e fórmula',
      rota: { path: '/estatisticas' },
      testId: 'destino-estatisticas',
    },
  ]

  if (endpoint) {
    items.push({
      id: 'endpoint-critico',
      title: `${endpoint.metodo} ${endpoint.url}`,
      subtitle: endpoint.titulo || 'Endpoint crítico de métricas',
      rota: { path: '/monitoramento-operacional', query: { secao: 'runtime' } },
      testId: 'destino-endpoint-critico',
    })
  } else {
    items.push({
      id: 'endpoint-critico',
      title: 'GET /v1/dashboard/requisitos',
      subtitle: 'Endpoint crítico de métricas',
      rota: { path: '/monitoramento-operacional', query: { secao: 'runtime' } },
      testId: 'destino-endpoint-critico',
    })
  }

  return items
})

function irPara(rota) {
  if (!rota?.path) return
  router.push(rota)
}

const dashboardInfo = computed(() => store.dashboardInfo || {})
const resumo = computed(() => dashboardInfo.value.resumo || {})
const ambienteLabel = computed(() => (resumo.value.ambiente || 'desenvolvimento').replace(/_/g, ' '))
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
  gap: 20px;
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.dashboard-subtitle {
  max-width: 62ch;
  margin-top: 8px;
  font-size: 14px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-top: 24px;
}

.lower-panels {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 16px;
  margin-top: 18px;
}

.pipeline-panel h2,
.info-panel h2 {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 700;
}

.panel-lead {
  margin: 0 0 14px;
  color: var(--muted);
  font-size: 13px;
}

.timeline-steps {
  display: grid;
  gap: 12px;
}

.timeline-step {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
}

.timeline-step:hover,
.timeline-step:focus-visible {
  background: rgba(243, 146, 0, 0.08);
  outline: none;
}

.timeline-step strong {
  display: block;
}

.timeline-step span {
  color: var(--muted);
  font-size: 13px;
}

.step-btn {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.figma-list {
  display: grid;
  gap: 8px;
}

.figma-btn-atualizar {
  border-radius: 999px !important;
  font-weight: 700 !important;
  padding-inline: 14px !important;
}

.erro {
  border: 1px solid var(--red);
  border-radius: 8px;
  color: var(--red);
  padding: 0.75rem;
}

@media (max-width: 1100px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .lower-panels {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .dashboard-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .figma-pill,
  .figma-btn-atualizar {
    width: 100%;
    text-align: center;
  }
}
</style>
