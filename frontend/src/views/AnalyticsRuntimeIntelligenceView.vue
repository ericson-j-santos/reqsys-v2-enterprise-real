<template>
  <main class="ari-page" aria-labelledby="titulo-ari">
    <section class="hero">
      <div>
        <p class="eyebrow">ReqSys/GovBI · Capability transversal</p>
        <h1 id="titulo-ari">Analytics Runtime Intelligence</h1>
        <p class="hero-text">
          Plataforma enterprise de inteligência operacional auditável com analytics confiável, IA governada,
          runtime observável, explainability, confiança mensurável e qualidade operacional contínua.
        </p>
      </div>
      <div class="hero-actions">
        <a class="btn secundario" href="/figma-github">Abrir Figma GitHub</a>
        <button type="button" class="btn primario" :disabled="carregando" @click="carregarSnapshot">
          {{ carregando ? 'Atualizando...' : 'Atualizar runtime' }}
        </button>
      </div>
    </section>

    <p v-if="erro" class="alerta erro" role="alert">{{ erro }}</p>
    <p v-if="snapshot?.figma?.status" class="alerta sucesso" role="status">
      Figma: {{ snapshot.figma.status }} · {{ snapshot.figma.artefato }}
    </p>

    <section class="score-grid" aria-label="Indicadores consolidados ARI">
      <article class="score-card destaque">
        <span>Health Score</span>
        <strong>{{ score('health_score') }}%</strong>
        <small>saúde operacional</small>
      </article>
      <article class="score-card">
        <span>Confidence</span>
        <strong>{{ score('confidence_score') }}%</strong>
        <small>confiança analítica</small>
      </article>
      <article class="score-card">
        <span>IA Governance</span>
        <strong>{{ score('ai_governance_score') }}%</strong>
        <small>IA auditável</small>
      </article>
      <article class="score-card">
        <span>Operational Quality</span>
        <strong>{{ score('operational_quality_score') }}%</strong>
        <small>qualidade contínua</small>
      </article>
    </section>

    <section class="capability-grid" aria-label="Capabilities da plataforma enterprise">
      <article v-for="capability in capabilities" :key="capability.nome" class="capability-card">
        <div class="capability-icon" aria-hidden="true">{{ capability.indice }}</div>
        <div>
          <h2>{{ capability.nome }}</h2>
          <p>{{ capability.descricao }}</p>
        </div>
      </article>
    </section>

    <section class="panel" aria-labelledby="titulo-validacoes">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Query Validation Intelligence</p>
          <h2 id="titulo-validacoes">10 conferências essenciais operacionalizadas</h2>
          <p>Checklist da imagem convertido em runtime de validação, governança e retorno visual em tela.</p>
        </div>
        <label class="filtro">
          Status
          <select v-model="filtroStatus">
            <option value="">Todos</option>
            <option value="ok">OK</option>
            <option value="warn">Warn</option>
            <option value="fail">Fail</option>
            <option value="block">Block</option>
          </select>
        </label>
      </div>

      <div class="validation-list">
        <article v-for="item in validacoesFiltradas" :key="item.codigo" class="validation-item">
          <header>
            <span :class="['status', item.status]">{{ item.status }}</span>
            <strong>{{ item.nome }}</strong>
            <em>{{ item.score }}%</em>
          </header>
          <p>{{ item.evidencia }}</p>
          <small>{{ item.categoria }} · Próxima ação: {{ item.acao_recomendada }}</small>
        </article>
        <p v-if="!validacoesFiltradas.length" class="vazio">Nenhuma validação encontrada para o filtro atual.</p>
      </div>
    </section>

    <section class="grid-2">
      <article class="panel">
        <p class="eyebrow">Guard rails</p>
        <h2>Gates operacionais</h2>
        <ul class="gate-list">
          <li v-for="gate in snapshot?.guard_rails || []" :key="`${gate.regra}-${gate.acao}`">
            <span>{{ gate.regra }}</span>
            <strong>{{ gate.acao }}</strong>
          </li>
        </ul>
      </article>

      <article class="panel">
        <p class="eyebrow">Figma + GitHub</p>
        <h2>Retorno em tela</h2>
        <dl class="figma-dl">
          <div><dt>Status</dt><dd>{{ snapshot?.figma?.status || '-' }}</dd></div>
          <div><dt>Artefato</dt><dd>{{ snapshot?.figma?.artefato || '-' }}</dd></div>
          <div><dt>Objetivo</dt><dd>{{ snapshot?.figma?.objetivo || '-' }}</dd></div>
        </dl>
      </article>
    </section>

    <section class="panel">
      <p class="eyebrow">Arquitetura viva</p>
      <h2>Fluxo end to end</h2>
      <div class="flow" aria-label="Fluxo ARI">
        <span>Dados</span>
        <b>→</b>
        <span>Validation Engine</span>
        <b>→</b>
        <span>Confidence Engine</span>
        <b>→</b>
        <span>AI Governance</span>
        <b>→</b>
        <span>Operations Center</span>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const API_BASE = '/v1/analytics-runtime-intelligence/snapshot'
const snapshot = ref(null)
const carregando = ref(false)
const erro = ref('')
const filtroStatus = ref('')

const capabilities = [
  { indice: '01', nome: 'Analytics confiável', descricao: 'Validação de volume, estatística, filtros, joins, agregações e reconciliação.' },
  { indice: '02', nome: 'IA governada', descricao: 'Grounding, fontes, lineage, score e bloqueio de respostas sem evidência.' },
  { indice: '03', nome: 'Runtime observável', descricao: 'Telemetria, eventos, métricas, correlation_id, incidentes e audit trail.' },
  { indice: '04', nome: 'Explainability', descricao: 'Origem, regra, query, transformação, evidência e rastreabilidade por decisão.' },
  { indice: '05', nome: 'Operação autônoma', descricao: 'Alertas, RCA, retry, rollback, invalidação de cache e self-healing governado.' },
  { indice: '06', nome: 'Arquitetura viva', descricao: 'Fluxos navegáveis integrados ao código, runtime, analytics, Figma e GitHub.' },
]

const validacoesFiltradas = computed(() => {
  const itens = snapshot.value?.validacoes || []
  return itens.filter((item) => !filtroStatus.value || item.status === filtroStatus.value)
})

function score(campo) {
  return snapshot.value?.[campo] ?? '-'
}

async function carregarSnapshot() {
  carregando.value = true
  erro.value = ''
  try {
    const resposta = await fetch(API_BASE, { headers: { Accept: 'application/json' } })
    const payload = await resposta.json().catch(() => ({}))
    if (!resposta.ok) throw new Error(payload.detail || 'Falha ao carregar Analytics Runtime Intelligence')
    snapshot.value = payload.data || payload
  } catch (e) {
    erro.value = e?.message || 'Erro inesperado ao carregar ARI'
    snapshot.value = fallbackSnapshot()
  } finally {
    carregando.value = false
  }
}

function fallbackSnapshot() {
  return {
    health_score: 91,
    confidence_score: 92,
    ai_governance_score: 89,
    operational_quality_score: 91,
    figma: {
      status: 'fallback_local_em_tela',
      artefato: 'Enterprise Operations Center / Analytics Runtime Intelligence',
      objetivo: 'Retorno visual resiliente quando API estiver indisponível',
    },
    validacoes: [
      { codigo: 'COUNT_BEFORE_AFTER', nome: 'Comparar totais antes/depois', categoria: 'Volume', status: 'ok', score: 96, evidencia: 'Checklist operacional carregado em fallback.', acao_recomendada: 'Validar API de snapshot.' },
      { codigo: 'JOIN_CARDINALITY', nome: 'Validar JOINs utilizados', categoria: 'Relacionamento', status: 'warn', score: 87, evidencia: 'Gate de explosão cartesiana mantido em tela.', acao_recomendada: 'Conectar baseline real.' },
      { codigo: 'AI_GROUNDING', nome: 'IA governada com fonte e lineage', categoria: 'IA Auditável', status: 'warn', score: 89, evidencia: 'Resposta sem fonte permanece bloqueável.', acao_recomendada: 'Ativar policy runtime.' },
    ],
    guard_rails: [
      { regra: 'JOIN explosion', acao: 'FAIL' },
      { regra: 'IA sem fonte ou grounding', acao: 'BLOCK' },
      { regra: 'PII/log sensível exposto', acao: 'FAIL' },
    ],
  }
}

onMounted(carregarSnapshot)
</script>

<style scoped>
.ari-page { display: grid; gap: 1rem; padding: 1rem; color: #172033; }
.hero, .panel, .score-card, .capability-card { border: 1px solid #d0d7de; border-radius: 18px; background: #fff; }
.hero { display: grid; gap: 1rem; align-items: start; padding: 1.25rem; background: linear-gradient(135deg, #101828, #1d2a48); color: #fff; }
.eyebrow { margin: 0 0 .35rem; font-size: .76rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: #667085; }
.hero .eyebrow { color: #f6c445; }
h1, h2, p { margin-top: 0; }
h1 { font-size: clamp(1.85rem, 4vw, 3.2rem); letter-spacing: -0.04em; margin-bottom: .55rem; }
h2 { margin-bottom: .5rem; }
.hero-text { max-width: 880px; color: #e6edf7; font-size: 1.02rem; }
.hero-actions { display: flex; flex-wrap: wrap; gap: .75rem; }
.btn { border: 1px solid transparent; border-radius: 999px; padding: .72rem 1rem; font-weight: 800; text-decoration: none; cursor: pointer; }
.primario { background: #f6c445; color: #101828; }
.secundario { border-color: rgba(255,255,255,.35); color: #fff; background: transparent; }
.alerta { border-radius: 12px; padding: .8rem 1rem; margin: 0; }
.erro { border: 1px solid #d1242f; color: #d1242f; background: #fff5f5; }
.sucesso { border: 1px solid #1a7f37; color: #14532d; background: #f0fff4; }
.score-grid, .capability-grid, .grid-2 { display: grid; gap: 1rem; }
.score-grid { grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); }
.score-card { padding: 1rem; }
.score-card span, .score-card small { display: block; color: #667085; }
.score-card strong { display: block; margin: .35rem 0; font-size: 2rem; letter-spacing: -0.04em; }
.score-card.destaque { border-color: #7c3aed; box-shadow: 0 10px 30px rgba(124,58,237,.12); }
.capability-grid { grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.capability-card { display: flex; gap: .9rem; padding: 1rem; }
.capability-icon { flex: 0 0 auto; display: grid; place-items: center; width: 2.5rem; height: 2.5rem; border-radius: 999px; background: #eef2ff; color: #4338ca; font-weight: 900; }
.panel { padding: 1rem; }
.panel-header { display: grid; gap: 1rem; align-items: start; }
.filtro { display: grid; gap: .3rem; font-weight: 700; }
select { border: 1px solid #d0d7de; border-radius: 10px; padding: .6rem; }
.validation-list { display: grid; gap: .75rem; }
.validation-item { border: 1px solid #eaecf0; border-radius: 14px; padding: .9rem; background: #fcfcfd; }
.validation-item header { display: flex; flex-wrap: wrap; gap: .55rem; align-items: center; }
.validation-item p { margin: .55rem 0 .35rem; color: #344054; }
.validation-item small { color: #667085; }
.status { border-radius: 999px; padding: .18rem .55rem; font-size: .72rem; text-transform: uppercase; font-weight: 900; }
.status.ok { background: #ecfdf3; color: #027a48; }
.status.warn { background: #fffaeb; color: #b54708; }
.status.fail, .status.block { background: #fef3f2; color: #b42318; }
.validation-item em { margin-left: auto; font-style: normal; font-weight: 900; }
.gate-list { display: grid; gap: .65rem; padding: 0; list-style: none; }
.gate-list li { display: flex; justify-content: space-between; gap: 1rem; border-bottom: 1px solid #eaecf0; padding-bottom: .55rem; }
.figma-dl { display: grid; gap: .75rem; }
.figma-dl div { border: 1px solid #eaecf0; border-radius: 12px; padding: .75rem; }
dt { font-weight: 800; }
dd { margin: .25rem 0 0; color: #344054; word-break: break-word; }
.flow { display: flex; flex-wrap: wrap; gap: .65rem; align-items: center; }
.flow span { border: 1px solid #d0d7de; border-radius: 999px; padding: .55rem .8rem; font-weight: 800; background: #f9fafb; }
.vazio { color: #667085; }
@media (min-width: 820px) { .hero, .panel-header, .grid-2 { grid-template-columns: 1fr auto; } .grid-2 { align-items: stretch; } }
</style>
