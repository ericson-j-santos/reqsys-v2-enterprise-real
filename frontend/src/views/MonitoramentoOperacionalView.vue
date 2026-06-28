<template>
  <section class="monitoramento-operacional" data-testid="route-monitoramento-operacional" aria-labelledby="titulo-monitoramento">
    <div class="cabecalho">
      <div>
        <p class="eyebrow">ReqSys Operacional · Trilha C</p>
        <h1 id="titulo-monitoramento">Monitoramento Operacional</h1>
        <p>Runtime navegável com semáforo operacional, cards clicáveis, drill-down filtrado e layouts responsivos.</p>
      </div>
      <div class="cabecalho-acoes">
        <SemaforoChip :value="estadoGeralExibido" size="large" />
        <v-btn color="amber" variant="flat" :loading="carregando" @click="carregarTudo">
          {{ carregando ? 'Atualizando...' : 'Atualizar' }}
        </v-btn>
      </div>
    </div>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <v-row dense>
      <v-col v-for="card in cardsResumo" :key="card.id" cols="12" sm="6" md="4" lg="2">
        <OperationalMetricCard
          :label="card.label"
          :value="card.value"
          :semaforo="card.semaforo"
          :icon="card.icon"
          :test-id="`monitoramento-card-${card.id}`"
          @drilldown="aplicarDrilldown(card.filtros)"
        />
      </v-col>
    </v-row>

    <v-card class="painel runtime mt-4" elevation="0" :data-section="secaoAtiva === 'runtime' ? 'active' : undefined">
      <v-card-title id="titulo-runtime">Runtime Operacional Navegável</v-card-title>
      <v-card-subtitle>Health map, readiness gate e topologia de workflow expostos pelo backend runtime.</v-card-subtitle>
      <v-card-text>
        <div class="subcabecalho mb-3">
          <span class="correlation">Runtime: {{ runtimeDashboard?.correlation_id || 'carregando' }}</span>
        </div>

        <v-row dense>
          <v-col v-for="card in runtimeCards" :key="card.id" cols="12" sm="6" md="4" lg="3">
            <OperationalMetricCard
              :label="card.title"
              :value="formatarValorCard(card)"
              :semaforo="semaforoCard(card)"
              icon="mdi-chart-timeline-variant"
              :test-id="`runtime-card-${card.id}`"
              @drilldown="irPara(card.rotaSpa)"
            />
          </v-col>
        </v-row>

        <v-row dense class="mt-2">
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Observabilidade" :value="`${observabilityReadiness.observability_percent ?? 'n/a'}%`" semaforo="verde" :clickable="false" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Cobertura topologia" :value="`${observabilityReadiness.topology_coverage ?? 'n/a'}%`" semaforo="amarelo" :clickable="false" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Profundidade correlação" :value="observabilityReadiness.correlation_depth ?? 'n/a'" semaforo="verde" :clickable="false" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Traceabilidade" :value="`${observabilityReadiness.operational_traceability ?? 'n/a'}%`" semaforo="verde" :clickable="false" />
          </v-col>
        </v-row>

        <v-list class="timeline mt-4" aria-label="Topologia operacional">
          <v-list-item
            v-for="item in workflowTopology"
            :key="item.step"
            class="timeline-item"
            @click="abrirTopologia(item)"
          >
            <template #prepend>
              <SemaforoChip :value="item.status" size="x-small" />
            </template>
            <v-list-item-title>{{ item.label }}</v-list-item-title>
            <v-list-item-subtitle>{{ item.status }}</v-list-item-subtitle>
            <template #append>
              <v-btn size="small" variant="text" color="amber">Detalhar</v-btn>
            </template>
          </v-list-item>
        </v-list>

        <div class="analitico mt-4" aria-label="Correlation analytics">
          <v-table density="compact">
            <thead><tr><th>Artefato</th><th>Correlation ID</th><th>Cadeia operacional</th><th>Incidentes correlacionados</th></tr></thead>
            <tbody>
              <tr>
                <td>{{ correlationAnalytics.artifact_name || 'runtime-correlation-report.json' }}</td>
                <td>{{ correlationAnalytics.correlation_id || runtimeDashboard?.correlation_id }}</td>
                <td>{{ traceChain }}</td>
                <td>{{ correlationAnalytics.incident_correlation?.total_related_events ?? 0 }}</td>
              </tr>
            </tbody>
          </v-table>
        </div>
      </v-card-text>
    </v-card>

    <v-card class="painel governanca mt-4" elevation="0" :data-section="secaoAtiva === 'governanca' ? 'active' : undefined">
      <v-card-title id="titulo-governanca">Governança e Evidências</v-card-title>
      <v-card-subtitle>Cards de capacidades governadas consumindo governance-evidence-index.json.</v-card-subtitle>
      <v-card-text>
        <v-row dense>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Score de governança" :value="governanceResumo.score" semaforo="verde" :clickable="false" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Status geral" :value="governanceResumo.status" :semaforo="governanceResumo.status" :clickable="false" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Capacidades prontas" :value="governanceResumo.dashboardReady" semaforo="verde" :clickable="false" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Próximo incremento" :value="governanceResumo.nextIncrement" semaforo="amarelo" :clickable="false" />
          </v-col>
        </v-row>

        <div class="analitico mt-4">
          <v-table density="compact">
            <thead>
              <tr><th>Capacidade</th><th>Status</th><th>Dashboard</th><th>Workflow / Artifact</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in governanceEvidenceFiltrada" :key="item.id">
                <td>{{ item.title || item.id }}</td>
                <td><SemaforoChip :value="statusGovernancaParaSemaforo(item.status)" size="x-small" /></td>
                <td>{{ item.dashboard_ready ? 'ready' : 'pending' }}</td>
                <td>
                  <div>{{ item.workflow || '-' }}</div>
                  <div class="small text-medium-emphasis">{{ item.artifact || item.json_path || '-' }}</div>
                </td>
              </tr>
            </tbody>
          </v-table>
        </div>
      </v-card-text>
    </v-card>

    <v-card class="filtros mt-4" elevation="0">
      <v-card-title>Filtros do analítico</v-card-title>
      <v-card-text>
        <div class="filtros-grid">
          <v-select v-model="filtroEstado" :items="opcoesEstado" label="Estado (semáforo)" clearable variant="outlined" density="comfortable" />
          <v-select v-model="filtroSecao" :items="opcoesSecao" label="Seção" clearable variant="outlined" density="comfortable" />
          <v-text-field v-model="filtroBusca" label="Busca" clearable variant="outlined" density="comfortable" />
        </div>
      </v-card-text>
    </v-card>

    <v-card class="painel mt-4" elevation="0" :data-section="secaoAtiva === 'conectores' ? 'active' : undefined">
      <v-card-title id="titulo-conectores">Connection Broker</v-card-title>
      <v-card-subtitle>Health-check operacional dos conectores e capabilities usados por agentes e automações.</v-card-subtitle>
      <v-card-text>
        <div class="subcabecalho mb-3">
          <span class="correlation">Correlação: {{ correlationId }}</span>
        </div>

        <v-row dense>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Prontos" :value="totalPorStatus.ready" semaforo="verde" @drilldown="aplicarDrilldown({ secao: 'conectores' })" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Pendentes" :value="totalPorStatus.missing_permission" semaforo="amarelo" @drilldown="aplicarDrilldown({ secao: 'conectores', estado: 'amarelo' })" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Expirados" :value="totalPorStatus.expired" semaforo="amarelo" @drilldown="aplicarDrilldown({ secao: 'conectores', estado: 'amarelo' })" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <OperationalMetricCard label="Bloqueados" :value="totalPorStatus.blocked" semaforo="vermelho" @drilldown="aplicarDrilldown({ secao: 'conectores', estado: 'vermelho' })" />
          </v-col>
        </v-row>

        <div class="analitico mt-4">
          <v-table density="compact">
            <thead>
              <tr><th>Ambiente</th><th>Conector</th><th>Capability</th><th>Status</th><th>Criticidade</th><th>Ação sugerida</th></tr>
            </thead>
            <tbody>
              <tr v-for="conector in conectores" :key="`${conector.ambiente}-${conector.conector}-${conector.capability}`">
                <td>{{ conector.ambiente }}</td>
                <td>{{ conector.conector }}</td>
                <td>{{ conector.capability }}</td>
                <td><SemaforoChip :value="statusParaSemaforo(conector.status)" size="x-small" /></td>
                <td>{{ conector.criticidade }}</td>
                <td>{{ conector.acao_sugerida }}</td>
              </tr>
            </tbody>
          </v-table>
        </div>
      </v-card-text>
    </v-card>

    <v-card class="analitico mt-4" elevation="0" :data-section="secaoAtiva === 'itens' ? 'active' : undefined" aria-label="Itens monitorados">
      <v-card-title>Itens monitorados</v-card-title>
      <v-card-text>
        <v-table density="compact">
          <thead>
            <tr><th>Tipo</th><th>Referência</th><th>Título</th><th>Estado</th><th>Severidade</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in itensFiltrados" :key="`${item.tipo}-${item.referencia}`">
              <td>{{ item.tipo }}</td>
              <td>{{ item.referencia }}</td>
              <td>{{ item.titulo }}</td>
              <td><SemaforoChip :value="item.estado" size="x-small" /></td>
              <td>{{ item.severidade }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import SemaforoChip from '../components/SemaforoChip.vue'
import {
  criarQueryFiltrosMonitoramento,
  filtrarItensMonitoramento,
  normalizarFiltrosMonitoramento,
} from '../utils/filtrosMonitoramento'
import { resolverDrilldownSpa } from '../utils/runtimeDrilldown'
import { carregarRuntimeDashboard, formatarValorRuntimeCard, semaforoRuntimeCard } from '../services/runtimeDashboard'

const route = useRoute()
const router = useRouter()
const resumo = ref({})
const itens = ref([])
const conectores = ref([])
const runtimeDashboard = ref(null)
const correlationId = ref('local-fallback')
const filtroEstado = ref(route.query.estado || '')
const filtroSecao = ref(route.query.secao || '')
const filtroBusca = ref(route.query.busca || '')
const carregando = ref(false)
const erro = ref('')

const opcoesEstado = [
  { title: 'Verde', value: 'verde' },
  { title: 'Amarelo', value: 'amarelo' },
  { title: 'Vermelho', value: 'vermelho' },
  { title: 'Bloqueado', value: 'bloqueado' },
  { title: 'Desconhecido', value: 'desconhecido' },
]

const opcoesSecao = [
  { title: 'Itens monitorados', value: 'itens' },
  { title: 'Conectores', value: 'conectores' },
  { title: 'Runtime', value: 'runtime' },
  { title: 'Métricas', value: 'metrics' },
  { title: 'Timeline', value: 'timeline' },
  { title: 'Governança', value: 'governanca' },
]

const fallbackConectores = [
  { ambiente: 'dev', conector: 'repository_provider', capability: 'repository.read', status: 'ready', criticidade: 'high', acao_sugerida: 'Executar com auditoria.' },
  { ambiente: 'homolog', conector: 'repository_provider', capability: 'repository.write', status: 'missing_permission', criticidade: 'critical', acao_sugerida: 'Solicitar autorização contextual antes da escrita.' },
  { ambiente: 'prod', conector: 'document_provider', capability: 'document.read', status: 'ready', criticidade: 'medium', acao_sugerida: 'Manter health-check periódico.' },
  { ambiente: 'prod', conector: 'communication_provider', capability: 'message.compose', status: 'blocked', criticidade: 'high', acao_sugerida: 'Exigir confirmação humana antes do envio.' },
]

const filtrosAtivos = computed(() => normalizarFiltrosMonitoramento({
  estado: filtroEstado.value,
  secao: filtroSecao.value,
  busca: filtroBusca.value,
}))

const secaoAtiva = computed(() => filtrosAtivos.value.secao)
const itensFiltrados = computed(() => filtrarItensMonitoramento(itens.value, filtrosAtivos.value))
const conectoresCriticos = computed(() => conectores.value.filter((item) => ['critical', 'high'].includes(item.criticidade)))
const bloqueiosCalculados = computed(() => conectores.value.filter((item) => ['blocked', 'unavailable', 'misconfigured'].includes(item.status)).length)
const pendenciasCalculadas = computed(() => conectores.value.filter((item) => ['missing_permission', 'insufficient_permission', 'expired'].includes(item.status)).length)
const estadoGeralCalculado = computed(() => {
  if (bloqueiosCalculados.value > 0) return 'bloqueado'
  if (pendenciasCalculadas.value > 0) return 'amarelo'
  return 'verde'
})
const estadoGeralExibido = computed(() => resumo.value.estado_geral || estadoGeralCalculado.value)
const runtimeCards = computed(() => runtimeDashboard.value?.cards || [])
const workflowTopology = computed(() => runtimeDashboard.value?.sections?.find((section) => section.id === 'workflow-topology')?.items || [])
const correlationAnalytics = computed(() => runtimeDashboard.value?.correlation_analytics || {})
const observabilityReadiness = computed(() => runtimeDashboard.value?.observability_readiness || {})
const runtimeTopologyPreview = computed(() => runtimeDashboard.value?.runtime_topology || {})
const governanceEvidence = computed(() => runtimeDashboard.value?.governance_evidence || {})
const governanceSection = computed(() => runtimeDashboard.value?.sections?.find((section) => section.id === 'governance-evidence') || null)
const governanceItems = computed(() => governanceSection.value?.items?.evidence || governanceEvidence.value?.evidence || [])
const governanceResumo = computed(() => {
  const summary = governanceSection.value?.items?.summary || governanceEvidence.value?.summary || {}
  return {
    score: governanceSection.value?.items?.governance_evidence_score ?? governanceEvidence.value?.governance_evidence_score ?? 'n/a',
    status: governanceSection.value?.items?.overall_status ?? governanceEvidence.value?.overall_status ?? 'desconhecido',
    dashboardReady: `${summary.dashboard_ready_capabilities ?? 0}/${summary.implemented_capabilities ?? 0}`,
    nextIncrement: summary.next_increment || 'n/a',
  }
})
const governanceEvidenceFiltrada = computed(() => {
  const capability = route.query.capability
  if (!capability) return governanceItems.value
  return governanceItems.value.filter((item) => item.id === capability)
})
const traceChain = computed(() => correlationAnalytics.value?.operational_trace_chains?.[0]?.chain?.join(' → ') || runtimeTopologyPreview.value?.trace_chain?.join(' → ') || 'n/a')

const totalPorStatus = computed(() => conectores.value.reduce((acc, item) => {
  acc[item.status] = (acc[item.status] || 0) + 1
  return acc
}, { ready: 0, missing_permission: 0, expired: 0, blocked: 0 }))

const cardsResumo = computed(() => [
  { id: 'estado', label: 'Estado geral', value: estadoGeralExibido.value, semaforo: estadoGeralExibido.value, icon: 'mdi-traffic-light', filtros: {} },
  { id: 'bloqueios', label: 'Bloqueios', value: resumo.value.bloqueios ?? bloqueiosCalculados.value, semaforo: bloqueiosCalculados.value > 0 ? 'vermelho' : 'verde', icon: 'mdi-cancel', filtros: { estado: 'bloqueado', secao: 'itens' } },
  { id: 'pendencias', label: 'Pendências', value: resumo.value.pendencias ?? pendenciasCalculadas.value, semaforo: pendenciasCalculadas.value > 0 ? 'amarelo' : 'verde', icon: 'mdi-clock-alert-outline', filtros: { estado: 'amarelo', secao: 'itens' } },
  { id: 'itens', label: 'Itens', value: resumo.value.total_itens ?? itens.value.length, semaforo: 'verde', icon: 'mdi-format-list-bulleted', filtros: { secao: 'itens' } },
  { id: 'conectores', label: 'Conectores', value: conectores.value.length, semaforo: 'verde', icon: 'mdi-lan-connect', filtros: { secao: 'conectores' } },
  { id: 'criticos', label: 'Conectores críticos', value: conectoresCriticos.value.length, semaforo: conectoresCriticos.value.length > 0 ? 'amarelo' : 'verde', icon: 'mdi-alert-decagram-outline', filtros: { secao: 'conectores' } },
])

function statusGovernancaParaSemaforo(status) {
  if (status === 'implemented') return 'verde'
  if (status === 'dry_run') return 'amarelo'
  return 'desconhecido'
}

function statusParaSemaforo(status) {
  if (status === 'ready') return 'verde'
  if (['blocked', 'unavailable', 'misconfigured'].includes(status)) return 'vermelho'
  return 'amarelo'
}

function formatarValorCard(card) {
  return formatarValorRuntimeCard(card)
}

function semaforoCard(card) {
  return semaforoRuntimeCard(card)
}

function irPara(rota) {
  if (!rota?.path) return
  router.push(rota)
}

function aplicarDrilldown(filtros = {}) {
  const query = criarQueryFiltrosMonitoramento({
    estado: filtros.estado ?? filtroEstado.value,
    secao: filtros.secao ?? filtroSecao.value,
    busca: filtros.busca ?? filtroBusca.value,
  })
  router.replace({ path: '/monitoramento-operacional', query })
}

function abrirTopologia(item) {
  irPara(resolverDrilldownSpa(item.spa_drilldown?.path || item.href, item))
}

function sincronizarFiltrosDaUrl() {
  const filtros = normalizarFiltrosMonitoramento(route.query)
  filtroEstado.value = filtros.estado
  filtroSecao.value = filtros.secao
  filtroBusca.value = filtros.busca
}

function sincronizarUrlDosFiltros() {
  const query = criarQueryFiltrosMonitoramento({
    estado: filtroEstado.value,
    secao: filtroSecao.value,
    busca: filtroBusca.value,
  })
  router.replace({ path: '/monitoramento-operacional', query })
}

async function carregarMonitoramento() {
  const resposta = await fetch('/api/monitoramento-operacional', { headers: { Accept: 'application/json' } })
  if (!resposta.ok) throw new Error('Falha ao carregar monitoramento operacional')
  const payload = await resposta.json()
  resumo.value = payload.data?.resumo || {}
  itens.value = payload.data?.itens || []
}

async function carregarConectores() {
  try {
    const resposta = await fetch('/api/connectors/health', { headers: { Accept: 'application/json' } })
    if (!resposta.ok) throw new Error('Health-check de conectores indisponível')
    const payload = await resposta.json()
    conectores.value = payload.data?.conectores || fallbackConectores
    correlationId.value = payload.correlation_id || payload.data?.correlation_id || 'sem-correlacao'
  } catch {
    conectores.value = fallbackConectores
    correlationId.value = 'fallback-sem-backend'
  }
}

async function carregarTudo() {
  carregando.value = true
  erro.value = ''
  try {
    const [dashboard] = await Promise.all([
      carregarRuntimeDashboard(),
      carregarMonitoramento(),
      carregarConectores(),
    ])
    runtimeDashboard.value = dashboard
  } catch (e) {
    erro.value = e?.message || 'Erro inesperado ao carregar monitoramento operacional'
    await carregarConectores()
  } finally {
    carregando.value = false
  }
}

watch([filtroEstado, filtroSecao, filtroBusca], sincronizarUrlDosFiltros)
watch(() => route.query, sincronizarFiltrosDaUrl, { deep: true })

watch(secaoAtiva, async (secao) => {
  if (!secao) return
  await nextTick()
  const alvo = document.querySelector(`[data-section="${secao}"]`)
  alvo?.scrollIntoView({ behavior: 'smooth', block: 'start' })
})

onMounted(async () => {
  sincronizarFiltrosDaUrl()
  await carregarTudo()
})
</script>

<style scoped>
.monitoramento-operacional { display: grid; gap: 1rem; padding: 0.25rem; }
.cabecalho { display: grid; gap: 1rem; align-items: center; }
.cabecalho-acoes { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.eyebrow { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
.erro { border: 1px solid #d1242f; border-radius: 8px; color: #d1242f; padding: 0.75rem; }
.painel, .filtros { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.runtime { background: linear-gradient(135deg, #f6f8fa, #ffffff); }
.subcabecalho { display: flex; justify-content: flex-end; }
.correlation { color: #57606a; font-size: 0.85rem; }
.filtros-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
.timeline { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; }
.timeline-item { cursor: pointer; }
.analitico { overflow-x: auto; }
@media (min-width: 768px) { .cabecalho { grid-template-columns: 1fr auto; } }
@media (max-width: 600px) {
  .filtros-grid { grid-template-columns: 1fr; }
}
</style>
