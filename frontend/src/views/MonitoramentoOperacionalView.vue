<template>
  <main class="monitoramento-operacional" aria-labelledby="titulo-monitoramento">
    <section class="cabecalho">
      <div>
        <p class="eyebrow">ReqSys Operacional</p>
        <h1 id="titulo-monitoramento">Monitoramento Operacional</h1>
        <p>Visão mínima de estado, bloqueios, pendências, conectores e itens monitorados.</p>
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
const totalPorStatus = computed(() => conectores.value.reduce((acc, item) => {
  acc[item.status] = (acc[item.status] || 0) + 1
  return acc
}, { ready: 0, missing_permission: 0, expired: 0, blocked: 0 }))

function classeStatus(status) {
  if (status === 'ready') return 'badge-ok'
  if (['blocked', 'unavailable', 'misconfigured'].includes(status)) return 'badge-erro'
  return 'badge-alerta'
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
    await Promise.all([carregarMonitoramento(), carregarConectores()])
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
