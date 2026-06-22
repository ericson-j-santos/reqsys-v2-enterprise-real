<template>
  <main class="runtime-center" aria-labelledby="titulo-runtime-center">
    <section class="hero">
      <div>
        <p class="eyebrow">Consolidação Operacional</p>
        <h1 id="titulo-runtime-center">Runtime Operational Center</h1>
        <p>Health, ambiente, timeline, analytics e base governada para self-healing.</p>
      </div>
      <div class="acoes">
        <label>
          Ambiente
          <select v-model="ambienteSelecionado">
            <option value="dev">DEV</option>
            <option value="homolog">HOMOLOG</option>
            <option value="prod">PROD</option>
          </select>
        </label>
        <button type="button" :disabled="carregando" @click="carregarTudo">
          {{ carregando ? 'Atualizando...' : 'Atualizar' }}
        </button>
      </div>
    </section>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <section class="cards" aria-label="Indicadores executivos">
      <article class="card"><span>Estado</span><strong>{{ estadoRuntime }}</strong></article>
      <article class="card"><span>Score</span><strong>{{ scoreOperacional }}</strong></article>
      <article class="card"><span>Bloqueios</span><strong>{{ bloqueios }}</strong></article>
      <article class="card"><span>Pendências</span><strong>{{ pendencias }}</strong></article>
      <article class="card"><span>Ambiente</span><strong>{{ ambienteSelecionado }}</strong></article>
      <article class="card"><span>Correlação</span><small>{{ correlationId }}</small></article>
    </section>

    <section class="painel">
      <h2>Runtime Health</h2>
      <div class="health-grid">
        <article v-for="servico in servicos" :key="servico.nome" :class="['health-card', classeEstado(servico.estado)]">
          <span>{{ servico.nome }}</span>
          <strong>{{ servico.estado }}</strong>
          <small>{{ servico.detalhe }}</small>
        </article>
      </div>
    </section>

    <section class="duas-colunas">
      <article class="painel">
        <h2>Timeline Operacional</h2>
        <ol class="timeline">
          <li v-for="evento in timeline" :key="evento.titulo">
            <strong>{{ evento.titulo }}</strong>
            <small>{{ evento.detalhe }}</small>
          </li>
        </ol>
      </article>

      <article class="painel">
        <h2>Self-Healing Runtime</h2>
        <p>Status: {{ selfHealingStatus }}</p>
        <p class="texto-suporte">Base preparada para execução governada após Runtime Center P0 estável.</p>
      </article>
    </section>

    <section class="painel analitico">
      <h2>Analítico Operacional</h2>
      <table>
        <thead>
          <tr><th>Tipo</th><th>Referência</th><th>Título</th><th>Estado</th><th>Severidade</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in itens" :key="`${item.tipo}-${item.referencia}`">
            <td>{{ item.tipo }}</td>
            <td>{{ item.referencia }}</td>
            <td>{{ item.titulo }}</td>
            <td><span :class="['badge', classeEstado(item.estado)]">{{ item.estado }}</span></td>
            <td>{{ item.severidade }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const ambienteSelecionado = ref(localStorage.getItem('reqsys.runtime.environment') || 'dev')
const carregando = ref(false)
const erro = ref('')
const resumo = ref({})
const itens = ref([])
const runtimeHealth = ref({})
const diagnostico = ref(null)
const acaoRecomendada = ref(null)
const correlationId = ref('runtime-center-local')

const sinaisBase = [
  { nome: 'ci_cd', sucesso: true, latencia_ms: 0, retries: 0, falhas_consecutivas: 0, criticidade: 'alta' },
  { nome: 'api', sucesso: true, latencia_ms: 130, retries: 0, falhas_consecutivas: 0, criticidade: 'alta' },
  { nome: 'auth', sucesso: true, latencia_ms: 260, retries: 0, falhas_consecutivas: 0, criticidade: 'alta' },
  { nome: 'self_healing', sucesso: false, latencia_ms: 0, retries: 0, falhas_consecutivas: 1, criticidade: 'media' }
]

const servicos = computed(() => [
  { nome: 'CI/CD', estado: resumo.value.estado_geral === 'bloqueado' ? 'bloqueado' : 'saudavel', detalhe: 'Gate operacional.' },
  { nome: 'API', estado: runtimeHealth.value.status || 'saudavel', detalhe: 'FastAPI runtime.' },
  { nome: 'Auth', estado: 'atencao', detalhe: 'Item observado.' },
  { nome: 'Observabilidade', estado: 'saudavel', detalhe: 'correlation_id ativo.' },
  { nome: 'Self-Healing', estado: acaoRecomendada.value?.exige_aprovacao ? 'atencao' : 'saudavel', detalhe: 'Executor governado.' }
])

const bloqueios = computed(() => resumo.value.bloqueios ?? 0)
const pendencias = computed(() => resumo.value.pendencias ?? 0)
const scoreOperacional = computed(() => diagnostico.value?.score ?? Math.max(0, 100 - pendencias.value * 10 - bloqueios.value * 25))
const estadoRuntime = computed(() => diagnostico.value?.status || runtimeHealth.value.status || resumo.value.estado_geral || 'DESCONHECIDO')
const selfHealingStatus = computed(() => acaoRecomendada.value?.acao || 'AGUARDANDO_P0_ESTAVEL')
const timeline = computed(() => [
  { titulo: 'Runtime Center carregado', detalhe: `Ambiente ${ambienteSelecionado.value}` },
  { titulo: 'Health consultado', detalhe: runtimeHealth.value.status || 'pendente' },
  { titulo: 'Diagnóstico executado', detalhe: estadoRuntime.value }
])

function classeEstado(estado) {
  const valor = String(estado || '').toLowerCase()
  if (['verde', 'saudavel', 'healthy'].includes(valor)) return 'estado-ok'
  if (['bloqueado', 'vermelho', 'degradado', 'blocked'].includes(valor)) return 'estado-erro'
  return 'estado-alerta'
}

async function carregarMonitoramento() {
  const resposta = await fetch('/api/monitoramento-operacional', { headers: { Accept: 'application/json' } })
  if (!resposta.ok) throw new Error('Falha ao carregar monitoramento')
  const payload = await resposta.json()
  resumo.value = payload.data?.resumo || {}
  itens.value = payload.data?.itens || []
  correlationId.value = payload.meta?.correlation_id || payload.data?.correlation_id || correlationId.value
}

async function carregarHealth() {
  const resposta = await fetch('/api/monitoramento-operacional/runtime/health', {
    headers: { Accept: 'application/json', 'X-Correlation-Id': correlationId.value }
  })
  if (!resposta.ok) throw new Error('Falha ao carregar runtime health')
  runtimeHealth.value = await resposta.json()
  correlationId.value = runtimeHealth.value.correlation_id || correlationId.value
}

async function diagnosticarRuntime() {
  const resposta = await fetch('/api/monitoramento-operacional/runtime/diagnostico', {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Correlation-Id': correlationId.value },
    body: JSON.stringify(sinaisBase)
  })
  if (!resposta.ok) throw new Error('Falha ao diagnosticar runtime')
  const payload = await resposta.json()
  diagnostico.value = payload.diagnostico || null
  acaoRecomendada.value = payload.acao_recomendada || null
  correlationId.value = payload.correlation_id || correlationId.value
}

async function carregarTudo() {
  carregando.value = true
  erro.value = ''
  try {
    await carregarMonitoramento()
    await carregarHealth()
    await diagnosticarRuntime()
  } catch (e) {
    erro.value = e?.message || 'Erro inesperado ao carregar Runtime Center'
  } finally {
    carregando.value = false
  }
}

watch(ambienteSelecionado, (valor) => localStorage.setItem('reqsys.runtime.environment', valor))
onMounted(carregarTudo)
</script>

<style scoped>
.runtime-center { display: grid; gap: 1rem; padding: 1rem; }
.hero, .acoes { display: grid; gap: 1rem; align-items: center; }
.eyebrow { font-size: .78rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.cards, .health-grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }
.card, .health-card, .painel { background: #fff; border: 1px solid #d0d7de; border-radius: 16px; padding: 1rem; }
.card span, .card strong, .health-card span, .health-card strong { display: block; }
.card strong, .health-card strong { font-size: 1.25rem; margin-top: .35rem; text-transform: uppercase; }
.duas-colunas { display: grid; gap: 1rem; }
.timeline { display: grid; gap: .75rem; padding-left: 1.25rem; }
.texto-suporte, small { color: #57606a; }
.estado-ok { border-color: #1a7f37; color: #116329; }
.estado-alerta { border-color: #9a6700; color: #7d4e00; }
.estado-erro { border-color: #d1242f; color: #a40e26; }
.badge { border-radius: 999px; display: inline-block; font-weight: 700; padding: .25rem .5rem; }
.erro { border: 1px solid #d1242f; border-radius: 8px; color: #d1242f; padding: .75rem; }
.analitico { overflow-x: auto; }
table { border-collapse: collapse; min-width: 720px; width: 100%; }
th, td { border-bottom: 1px solid #d0d7de; padding: .75rem; text-align: left; }
button, select { border: 1px solid #d0d7de; border-radius: 10px; padding: .55rem .75rem; }
label { display: grid; gap: .25rem; }
@media (min-width: 768px) { .hero { grid-template-columns: 1fr auto; } .acoes { grid-template-columns: auto auto; } .duas-colunas { grid-template-columns: 1fr 1fr; } }
</style>