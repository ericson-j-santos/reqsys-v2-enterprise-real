<template>
  <section class="analytics-hub" data-testid="route-analytics" aria-labelledby="titulo-analytics">
    <div class="analytics-header">
      <div>
        <p class="eyebrow">Trilha C · UX Operacional</p>
        <h1 id="titulo-analytics">Analytics Navegável</h1>
        <p class="muted">
          Hub executivo com semáforo operacional, cards clicáveis e drill-down filtrado para monitoramento,
          estatísticas e runtime.
        </p>
      </div>
      <div class="header-actions">
        <SemaforoChip :value="semaforoGeralValor" size="large" />
        <v-btn color="amber" variant="flat" prepend-icon="mdi-refresh" :loading="carregando" @click="carregarTudo">
          Atualizar
        </v-btn>
      </div>
    </div>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <v-row dense class="mt-2">
      <v-col v-for="card in cardsResumo" :key="card.id" cols="12" sm="6" lg="3">
        <OperationalMetricCard
          :label="card.label"
          :value="card.value"
          :semaforo="card.semaforo"
          :icon="card.icon"
          :hint="card.hint"
          :test-id="`analytics-card-${card.id}`"
          @drilldown="irPara(card.rota)"
        />
      </v-col>
    </v-row>

    <v-card class="panel mt-4" elevation="0">
      <v-card-title>Runtime operacional</v-card-title>
      <v-card-subtitle>Cards schema-driven com drill-down para o analítico filtrado.</v-card-subtitle>
      <v-card-text>
        <v-row dense>
          <v-col v-for="card in runtimeCards" :key="card.id" cols="12" sm="6" md="4" xl="3">
            <OperationalMetricCard
              :label="card.title"
              :value="formatarValor(card)"
              :semaforo="semaforoCard(card)"
              icon="mdi-chart-timeline-variant"
              :hint="card.drilldown ? 'Drill-down conectado' : ''"
              :test-id="`analytics-runtime-${card.id}`"
              @drilldown="irPara(card.rotaSpa)"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-row class="mt-2" dense>
      <v-col cols="12" lg="7">
        <v-card class="panel" elevation="0">
          <v-card-title>Topologia operacional</v-card-title>
          <v-card-text>
            <v-timeline density="compact" side="end">
              <v-timeline-item
                v-for="item in workflowTopology"
                :key="item.step"
                :dot-color="corTimeline(item.status)"
              >
                <div class="timeline-row">
                  <div>
                    <strong>{{ item.label }}</strong>
                    <div class="muted">{{ item.status }}</div>
                  </div>
                  <div class="timeline-actions">
                    <SemaforoChip :value="item.status" size="x-small" />
                    <v-btn size="small" variant="tonal" color="amber" @click="abrirTopologia(item)">
                      Detalhar
                    </v-btn>
                  </div>
                </div>
              </v-timeline-item>
            </v-timeline>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card class="panel" elevation="0">
          <v-card-title>Destinos analíticos</v-card-title>
          <v-list density="comfortable">
            <v-list-item
              v-for="destino in destinosAnaliticos"
              :key="destino.path"
              :prepend-icon="destino.icon"
              :title="destino.title"
              :subtitle="destino.subtitle"
              role="button"
              tabindex="0"
              @click="irPara({ path: destino.path, query: destino.query })"
              @keyup.enter="irPara({ path: destino.path, query: destino.query })"
            />
          </v-list>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import SemaforoChip from '../components/SemaforoChip.vue'
import { useMonitoramentoOperacional } from '../composables/useMonitoramentoOperacional'
import { semaforoGeral } from '../utils/filtrosMonitoramento'
import { resolverDrilldownSpa } from '../utils/runtimeDrilldown'
import { carregarRuntimeDashboard, formatarValorRuntimeCard, semaforoRuntimeCard } from '../services/runtimeDashboard'

const router = useRouter()
const runtimeDashboard = ref(null)
const { carregarMonitoramento, resumoSemaforo, carregando, erro } = useMonitoramentoOperacional()

const runtimeCards = computed(() => runtimeDashboard.value?.cards || [])
const workflowTopology = computed(() => runtimeDashboard.value?.sections?.find((s) => s.id === 'workflow-topology')?.items || [])

const semaforoGeralValor = computed(() => {
  const resumo = resumoSemaforo()
  return semaforoGeral({
    verde: resumo.verde || 0,
    amarelo: resumo.amarelo || 0,
    vermelho: resumo.vermelho || 0,
    bloqueado: resumo.bloqueado || 0,
  })
})

const resumoMonitoramento = computed(() => {
  const resumo = resumoSemaforo()
  return {
    verde: resumo.verde || 0,
    amarelo: resumo.amarelo || 0,
    vermelho: resumo.vermelho || 0,
    bloqueados: resumo.bloqueado || 0,
  }
})

const cardsResumo = computed(() => [
  {
    id: 'monitoramento',
    label: 'Monitoramento',
    value: resumoMonitoramento.value.verde + resumoMonitoramento.value.amarelo + resumoMonitoramento.value.vermelho,
    semaforo: semaforoGeralValor.value,
    icon: 'mdi-monitor-dashboard',
    hint: 'Itens operacionais monitorados',
    rota: { path: '/monitoramento-operacional' },
  },
  {
    id: 'estatisticas',
    label: 'Estatísticas',
    value: 'Analítico',
    semaforo: 'verde',
    icon: 'mdi-chart-box-outline',
    hint: 'Indicadores auditáveis com fonte e fórmula',
    rota: { path: '/estatisticas' },
  },
  {
    id: 'integracoes',
    label: 'Integrações',
    value: 'Drill-down',
    semaforo: 'amarelo',
    icon: 'mdi-connection',
    hint: 'Falhas recentes em Planner e Teams',
    rota: { path: '/painel-integracao', query: { status: 'erro' } },
  },
  {
    id: 'dashboard',
    label: 'Dashboard',
    value: 'Métricas',
    semaforo: 'verde',
    icon: 'mdi-view-dashboard',
    hint: 'Visão consolidada de requisitos e pipeline',
    rota: { path: '/' },
  },
])

const destinosAnaliticos = [
  { path: '/monitoramento-operacional', query: { estado: 'vermelho' }, icon: 'mdi-alert-circle-outline', title: 'Incidentes críticos', subtitle: 'Itens em vermelho ou bloqueados' },
  { path: '/monitoramento-operacional', query: { secao: 'conectores' }, icon: 'mdi-lan-connect', title: 'Connection Broker', subtitle: 'Health-check de conectores' },
  { path: '/estatisticas', query: { estado: 'critico' }, icon: 'mdi-chart-line', title: 'Indicadores críticos', subtitle: 'Estatísticas com estado crítico' },
  { path: '/painel-integracao', query: { status: 'erro' }, icon: 'mdi-connection', title: 'Erros de integração', subtitle: 'Eventos com falha e correlation_id' },
]

function formatarValor(card) {
  return formatarValorRuntimeCard(card)
}

function semaforoCard(card) {
  return semaforoRuntimeCard(card)
}

function corTimeline(status) {
  const map = { healthy: 'green', attention: 'amber', degraded: 'red', verde: 'green', amarelo: 'amber', vermelho: 'red' }
  return map[String(status).toLowerCase()] || 'grey'
}

function irPara(rota) {
  if (!rota?.path) return
  router.push(rota)
}

function abrirTopologia(item) {
  const rota = resolverDrilldownSpa(item.href || item.spa_drilldown?.path || '/monitoramento-operacional', item)
  irPara(rota)
}

async function carregarTudo() {
  carregando.value = true
  erro.value = ''
  try {
    const [dashboard] = await Promise.all([
      carregarRuntimeDashboard(),
      carregarMonitoramento(),
    ])
    runtimeDashboard.value = dashboard
  } catch (e) {
    erro.value = e?.message || 'Erro ao carregar analytics operacional'
  } finally {
    carregando.value = false
  }
}

onMounted(carregarTudo)
</script>

<style scoped>
.analytics-hub { display: flex; flex-direction: column; gap: 8px; padding: 4px; }
.analytics-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.erro { border: 1px solid #d1242f; border-radius: 8px; color: #d1242f; padding: 0.75rem; }
.timeline-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.timeline-actions { display: flex; align-items: center; gap: 8px; }
@media (max-width: 700px) {
  .analytics-header { flex-direction: column; }
  .header-actions { width: 100%; }
}
</style>
