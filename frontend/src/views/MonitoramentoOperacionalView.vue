<template>
  <main class="monitoramento-operacional" aria-labelledby="titulo-monitoramento">
    <section class="cabecalho">
      <div>
        <p class="eyebrow">ReqSys Operacional</p>
        <h1 id="titulo-monitoramento">Monitoramento Operacional</h1>
        <p>Runtime navegável com health, readiness, métricas, topologia operacional e drill-downs conectados.</p>
      </div>
      <button type="button" :disabled="carregando" @click="carregarTudo">
        {{ carregando ? 'Atualizando...' : 'Atualizar' }}
      </button>
    </section>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <section class="cards" aria-label="Indicadores operacionais">
      <article class="card"><span>Estado geral</span><strong>{{ resumo.estado_geral || estadoGeralCalculado }}</strong></article>
      <article class="card"><span>Bloqueios</span><strong>{{ resumo.bloqueios ?? bloqueiosCalculados }}</strong></article>
      <article class="card"><span>Pendências</span><strong>{{ resumo.pendencias ?? pendenciasCalculadas }}</strong></article>
      <article class="card"><span>Itens</span><strong>{{ resumo.total_itens ?? itens.length }}</strong></article>
      <article class="card"><span>Conectores</span><strong>{{ conectores.length }}</strong></article>
      <article class="card"><span>Conectores críticos</span><strong>{{ conectoresCriticos.length }}</strong></article>
    </section>

    <section class="painel runtime" aria-labelledby="titulo-runtime">
      <div class="subcabecalho">
        <div>
          <h2 id="titulo-runtime">Runtime Operacional Navegável</h2>
          <p>Health map, readiness gate e topologia de workflow expostos pelo backend runtime.</p>
        </div>
        <span class="correlation">Runtime: {{ runtimeDashboard?.correlation_id || 'carregando' }}</span>
      </div>

      <div class="cards" aria-label="Cards do runtime">
        <article v-for="card in runtimeCards" :key="card.id" class="card">
          <span>{{ card.title }}</span>
          <strong>{{ formatarValorCard(card) }}</strong>
          <a v-if="card.drilldown" :href="card.drilldown">Abrir drill-down</a>
        </article>
      </div>

      <div class="cards" aria-label="Readiness de observabilidade">
        <article class="card"><span>Observabilidade</span><strong>{{ observabilityReadiness.observability_percent ?? 'n/a' }}%</strong></article>
        <article class="card"><span>Cobertura topologia</span><strong>{{ observabilityReadiness.topology_coverage ?? 'n/a' }}%</strong></article>
        <article class="card"><span>Profundidade correlação</span><strong>{{ observabilityReadiness.correlation_depth ?? 'n/a' }}</strong></article>
        <article class="card"><span>Traceabilidade</span><strong>{{ observabilityReadiness.operational_traceability ?? 'n/a' }}%</strong></article>
      </div>

      <ol class="timeline" aria-label="Topologia operacional">
        <li v-for="item in workflowTopology" :key="item.step">
          <span class="timeline-step">{{ item.label }}</span>
          <span :class="['badge', classeRuntime(item.status)]">{{ item.status }}</span>
          <a :href="item.href">Detalhar</a>
        </li>
      </ol>

      <div class="analitico" aria-label="Correlation analytics">
        <table>
          <thead><tr><th>Artefato</th><th>Correlation ID</th><th>Cadeia operacional</th><th>Incidentes correlacionados</th></tr></thead>
          <tbody>
            <tr>
              <td>{{ correlationAnalytics.artifact_name || 'runtime-correlation-report.json' }}</td>
              <td>{{ correlationAnalytics.correlation_id || runtimeDashboard?.correlation_id }}</td>
              <td>{{ traceChain }}</td>
              <td>{{ correlationAnalytics.incident_correlation?.total_related_events ?? 0 }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="analitico" aria-label="Environment dependency graph">
        <table>
          <thead><tr><th>Ambiente</th><th>Dependências</th><th>Status</th></tr></thead>
          <tbody>
            <tr v-for="env in environmentDependencies" :key="env.environment">
              <td>{{ env.environment }}</td>
              <td>{{ env.depends_on?.join(', ') }}</td>
              <td><span :class="['badge', classeRuntime(env.status)]">{{ env.status }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="filtros" aria-label="Filtros do analítico">
      <label>
        Estado
        <select v-model="filtroEstado">
          <option value="">Todos</option>
          <option value="verde">Verde</option>
          <option value="amarelo">Amarelo</option>
          <option value="vermelho">Vermelho</option>
          <option value="bloqueado">Bloqueado</option>
          <option value="desconhecido">Desconhecido</option>
        </select>
      </label>
    </section>

    <section class="painel" aria-labelledby="titulo-conectores">
      <div class="subcabecalho">
        <div>
          <h2 id="titulo-conectores">Connection Broker</h2>
          <p>Health-check operacional dos conectores e capabilities usados por agentes e automações.</p>
        </div>
        <span class="correlation">Correlação: {{ correlationId }}</span>
      </div>

      <div class="cards" aria-label="Indicadores de conectores">
        <article class="card status-ready"><span>Prontos</span><strong>{{ totalPorStatus.ready }}</strong></article>
        <article class="card status-alerta"><span>Pendentes</span><strong>{{ totalPorStatus.missing_permission }}</strong></article>
        <article class="card status-alerta"><span>Expirados</span><strong>{{ totalPorStatus.expired }}</strong></article>
        <article class="card status-bloqueado"><span>Bloqueados</span><strong>{{ totalPorStatus.blocked }}</strong></article>
      </div>

      <div class="analitico">
        <table>
          <thead>
            <tr><th>Ambiente</th><th>Conector</th><th>Capability</th><th>Status</th><th>Criticidade</th><th>Ação sugerida</th></tr>
          </thead>
          <tbody>
            <tr v-for="conector in conectores" :key="`${conector.ambiente}-${conector.conector}-${conector.capability}`">
              <td>{{ conector.ambiente }}</td>
              <td>{{ conector.conector }}</td>
              <td>{{ conector.capability }}</td>
              <td><span :class="['badge', classeStatus(conector.status)]">{{ conector.status }}</span></td>
              <td>{{ conector.criticidade }}</td>
              <td>{{ conector.acao_sugerida }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="analitico" aria-label="Itens monitorados">
      <table>
        <thead>
          <tr><th>Tipo</th><th>Referência</th><th>Título</th><th>Estado</th><th>Severidade</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in itensFiltrados" :key="`${item.tipo}-${item.referencia}`">
            <td>{{ item.tipo }}</td>
            <td>{{ item.referencia }}</td>
            <td>{{ item.titulo }}</td>
            <td>{{ item.estado }}</td>
            <td>{{ item.severidade }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const resumo = ref({})
const itens = ref([])
const conectores = ref([])
const runtimeDashboard = ref(null)
const correlationId = ref('local-fallback')
const filtroEstado = ref(route.query.estado || '')
const carregando = ref(false)
const erro = ref('')

const fallbackConectores = [
  { ambiente: 'dev', conector: 'repository_provider', capability: 'repository.read', status: 'ready', criticidade: 'high', acao_sugerida: 'Executar com auditoria.' },
  { ambiente: 'homolog', conector: 'repository_provider', capability: 'repository.write', status: 'missing_permission', criticidade: 'critical', acao_sugerida: 'Solicitar autorização contextual antes da escrita.' },
  { ambiente: 'prod', conector: 'document_provider', capability: 'document.read', status: 'ready', criticidade: 'medium', acao_sugerida: 'Manter health-check periódico.' },
  { ambiente: 'prod', conector: 'communication_provider', capability: 'message.compose', status: 'blocked', criticidade: 'high', acao_sugerida: 'Exigir confirmação humana antes do envio.' }
]

const itensFiltrados = computed(() => itens.value.filter((item) => !filtroEstado.value || item.estado === filtroEstado.value))
const conectoresCriticos = computed(() => conectores.value.filter((item) => ['critical', 'high'].includes(item.criticidade)))
const bloqueiosCalculados = computed(() => conectores.value.filter((item) => ['blocked', 'unavailable', 'misconfigured'].includes(item.status)).length)
const pendenciasCalculadas = computed(() => conectores.value.filter((item) => ['missing_permission', 'insufficient_permission', 'expired'].includes(item.status)).length)
const estadoGeralCalculado = computed(() => {
  if (bloqueiosCalculados.value > 0) return 'bloqueado'
  if (pendenciasCalculadas.value > 0) return 'amarelo'
  return 'verde'
})
const runtimeCards = computed(() => runtimeDashboard.value?.cards || [])
const workflowTopology = computed(() => runtimeDashboard.value?.sections?.find((section) => section.id === 'workflow-topology')?.items || [])
const correlationAnalytics = computed(() => runtimeDashboard.value?.correlation_analytics || {})
const observabilityReadiness = computed(() => runtimeDashboard.value?.observability_readiness || {})
const runtimeTopologyPreview = computed(() => runtimeDashboard.value?.runtime_topology || {})
const environmentDependencies = computed(() => runtimeTopologyPreview.value?.environment_dependencies || [])
const traceChain = computed(() => correlationAnalytics.value?.operational_trace_chains?.[0]?.chain?.join(' → ') || runtimeTopologyPreview.value?.trace_chain?.join(' → ') || 'n/a')

const totalPorStatus = computed(() => conectores.value.reduce((acc, item) => {
  acc[item.status] = (acc[item.status] || 0) + 1
  return acc
}, { ready: 0, missing_permission: 0, expired: 0, blocked: 0 }))

function classeStatus(status) {
  if (status === 'ready') return 'badge-ok'
  if (['blocked', 'unavailable', 'misconfigured'].includes(status)) return 'badge-erro'
  return 'badge-alerta'
}

function classeRuntime(status) {
  if (['healthy', 'available', 'verde', 'runtime_healthy'].includes(status)) return 'badge-ok'
  if (['degraded', 'runtime_degraded', 'bloqueado', 'vermelho'].includes(status)) return 'badge-erro'
  return 'badge-alerta'
}

function formatarValorCard(card) {
  if (card.unit === 'seconds') return `${Math.round(card.value)}s`
  if (card.unit) return `${card.value} ${card.unit}`
  return card.value
}

async function carregarRuntimeDashboard() {
  const resposta = await fetch('/api/runtime/dashboard', { headers: { Accept: 'application/json' } })
  if (!resposta.ok) throw new Error('Falha ao carregar runtime dashboard')
  const payload = await resposta.json()
  runtimeDashboard.value = payload.data || null
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
    await Promise.all([carregarMonitoramento(), carregarConectores(), carregarRuntimeDashboard()])
  } catch (e) {
    erro.value = e?.message || 'Erro inesperado ao carregar monitoramento operacional'
    await carregarConectores()
  } finally {
    carregando.value = false
  }
}

watch(filtroEstado, () => {
  router.replace({ query: { ...route.query, estado: filtroEstado.value || undefined } })
})

onMounted(carregarTudo)
</script>

<style scoped>
.monitoramento-operacional { display: grid; gap: 1rem; padding: 1rem; }
.cabecalho, .subcabecalho { display: grid; gap: 1rem; align-items: center; }
.eyebrow { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.cards { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
.card { border: 1px solid #d0d7de; border-radius: 12px; padding: 1rem; background: #fff; }
.card span, .card strong { display: block; }
.card strong { font-size: 1.5rem; margin-top: 0.5rem; }
.status-ready { border-color: #1a7f37; }
.status-alerta { border-color: #9a6700; }
.status-bloqueado { border-color: #d1242f; }
.filtros { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
.filtros label { display: grid; gap: 0.25rem; }
.erro { border: 1px solid #d1242f; border-radius: 8px; color: #d1242f; padding: 0.75rem; }
.painel { border: 1px solid #d0d7de; border-radius: 16px; display: grid; gap: 1rem; padding: 1rem; }
.runtime { background: linear-gradient(135deg, #f6f8fa, #ffffff); }
.card a, .timeline a { color: #0969da; display: inline-block; font-size: 0.85rem; margin-top: 0.5rem; }
.timeline { display: grid; gap: 0.75rem; list-style: none; margin: 0; padding: 0; }
.timeline li { align-items: center; border: 1px solid #d0d7de; border-radius: 12px; display: grid; gap: 0.5rem; grid-template-columns: minmax(140px, 1fr) auto auto; padding: 0.75rem; }
.timeline-step { font-weight: 700; }
.correlation { color: #57606a; font-size: 0.85rem; }
.analitico { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #d0d7de; padding: 0.75rem; text-align: left; }
.badge { border-radius: 999px; display: inline-block; font-size: 0.8rem; font-weight: 700; padding: 0.25rem 0.5rem; }
.badge-ok { background: #dafbe1; color: #116329; }
.badge-alerta { background: #fff8c5; color: #7d4e00; }
.badge-erro { background: #ffebe9; color: #a40e26; }
@media (min-width: 768px) { .cabecalho, .subcabecalho { grid-template-columns: 1fr auto; } }
</style>
