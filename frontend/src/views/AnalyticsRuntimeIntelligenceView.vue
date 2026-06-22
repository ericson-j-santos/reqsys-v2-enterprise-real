<template>
  <main class="ari-page" aria-labelledby="titulo-ari">
    <section class="hero">
      <div>
        <p class="eyebrow">ReqSys/GovBI · Capability transversal</p>
        <h1 id="titulo-ari">Analytics Runtime Intelligence</h1>
        <p class="hero-text">
          Plataforma enterprise de inteligência operacional auditável com readiness visual, gaps explícitos,
          status colorido e evidências operacionais.
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
    <p v-if="snapshot?.draft_recomendado" class="alerta aviso" role="status">
      Draft recomendado: existem gaps operacionais que bloqueiam production readiness.
    </p>

    <section class="score-grid" aria-label="Indicadores consolidados ARI">
      <article v-for="card in scoreCards" :key="card.campo" :class="['score-card', scoreClass(score(card.campo))]">
        <span>{{ card.titulo }}</span>
        <strong>{{ score(card.campo) }}%</strong>
        <small>{{ card.descricao }}</small>
      </article>
    </section>

    <section class="panel readiness-panel" aria-labelledby="titulo-readiness">
      <div class="panel-header">
        <div>
          <p class="eyebrow">ARI Operational Readiness Layer</p>
          <h2 id="titulo-readiness">Operational Readiness Matrix</h2>
          <p>Status semafórico, evidência, gap e indicação objetiva do que ainda impede produção.</p>
        </div>
        <span :class="['readiness-badge', snapshot?.production_ready ? 'verde' : 'vermelho']">
          {{ snapshot?.production_ready ? 'PRODUCTION READY' : 'DRAFT MANTIDO' }}
        </span>
      </div>

      <div class="readiness-table" role="table" aria-label="Matriz de readiness operacional">
        <div class="readiness-row readiness-head" role="row">
          <span>Capability</span><span>Estado</span><span>Evidência</span><span>Gap</span>
        </div>
        <div v-for="item in snapshot?.readiness_matrix || []" :key="item.capability" class="readiness-row" role="row">
          <strong>{{ item.capability }}</strong>
          <span :class="['status-pill', item.cor]">{{ item.estado }}</span>
          <span>{{ item.evidencia }}</span>
          <span>{{ item.gap }}</span>
        </div>
      </div>
    </section>

    <section class="grid-2">
      <article class="panel">
        <p class="eyebrow">Production Readiness Gaps</p>
        <h2>O que falta para produção</h2>
        <ul class="gap-list">
          <li v-for="gap in snapshot?.production_gaps || []" :key="gap">{{ gap }}</li>
        </ul>
      </article>

      <article class="panel">
        <p class="eyebrow">Runtime Timeline</p>
        <h2>Linha do tempo operacional</h2>
        <ol class="timeline">
          <li v-for="evento in snapshot?.runtime_timeline || []" :key="evento.evento">
            <span :class="['dot', evento.cor]"></span>
            <div><strong>{{ evento.evento }}</strong><small>{{ evento.estado }} · {{ evento.detalhe }}</small></div>
          </li>
        </ol>
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
          <p>Checklist convertido em runtime de validação, governança e retorno visual.</p>
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
        <h2>Gates operacionais ativos</h2>
        <ul class="gate-list">
          <li v-for="gate in snapshot?.guard_rails || []" :key="`${gate.regra}-${gate.acao}`">
            <span>{{ gate.regra }}</span>
            <strong :class="['gate-action', gate.acao.toLowerCase()]">{{ gate.acao }}</strong>
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
        <span>Dados</span><b>→</b><span>Validation Engine</span><b>→</b><span>Confidence Engine</span><b>→</b><span>AI Governance</span><b>→</b><span>Operations Center</span>
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

const scoreCards = [
  { campo: 'health_score', titulo: 'Health Score', descricao: 'saúde operacional' },
  { campo: 'confidence_score', titulo: 'Confidence', descricao: 'confiança analítica' },
  { campo: 'ai_governance_score', titulo: 'IA Governance', descricao: 'IA auditável' },
  { campo: 'operational_quality_score', titulo: 'Operational Quality', descricao: 'qualidade contínua' },
]

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

function scoreClass(valor) {
  if (valor === '-') return 'score-neutro'
  if (valor >= 95) return 'score-verde'
  if (valor >= 80) return 'score-amarelo'
  if (valor >= 60) return 'score-laranja'
  return 'score-vermelho'
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
    production_ready: false,
    draft_recomendado: true,
    figma: { status: 'fallback_local_em_tela', artefato: 'Enterprise Operations Center / Analytics Runtime Intelligence', objetivo: 'Retorno visual resiliente quando API estiver indisponível' },
    readiness_matrix: [
      { capability: 'Backend ARI', estado: 'VALIDADO', evidencia: 'Fallback carregado.', gap: 'Validar API.', cor: 'verde' },
      { capability: 'Staging Evidence', estado: 'EVIDENCIA AUSENTE', evidencia: 'Sem ambiente validado.', gap: 'Executar staging.', cor: 'cinza', bloqueia_producao: true },
      { capability: 'Production Readiness', estado: 'BLOQUEIO', evidencia: 'Runtime real ausente.', gap: 'Manter draft.', cor: 'vermelho', bloqueia_producao: true },
    ],
    production_gaps: ['Validar staging', 'Capturar evidência visual', 'Conectar adapter real'],
    runtime_timeline: [
      { evento: 'Fallback local', estado: 'PARCIAL', detalhe: 'API indisponível.', cor: 'amarelo' },
    ],
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
.hero-text { max-width: 900px; color: #e6edf7; font-size: 1.02rem; }
.hero-actions { display: flex; flex-wrap: wrap; gap: .75rem; }
.btn { border: 1px solid transparent; border-radius: 999px; padding: .72rem 1rem; font-weight: 800; text-decoration: none; cursor: pointer; }
.primario { background: #f6c445; color: #101828; }
.secundario { border-color: rgba(255,255,255,.35); color: #fff; background: transparent; }
.alerta { border-radius: 12px; padding: .8rem 1rem; margin: 0; }
.erro { border: 1px solid #d1242f; color: #d1242f; background: #fff5f5; }
.aviso { border: 1px solid #f59e0b; color: #92400e; background: #fffbeb; }
.score-grid, .capability-grid, .grid-2 { display: grid; gap: 1rem; }
.score-grid { grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); }
.score-card { padding: 1rem; border-left-width: 6px; }
.score-card span, .score-card small { display: block; color: #667085; }
.score-card strong { display: block; margin: .35rem 0; font-size: 2rem; letter-spacing: -0.04em; }
.score-verde { border-left-color: #15803d; }
.score-amarelo { border-left-color: #d97706; }
.score-laranja { border-left-color: #ea580c; }
.score-vermelho { border-left-color: #b91c1c; }
.score-neutro { border-left-color: #64748b; }
.capability-grid { grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.capability-card { display: flex; gap: .9rem; padding: 1rem; }
.capability-icon { flex: 0 0 auto; display: grid; place-items: center; width: 2.5rem; height: 2.5rem; border-radius: 999px; background: #eef2ff; color: #4338ca; font-weight: 900; }
.panel { padding: 1rem; }
.panel-header { display: grid; gap: 1rem; align-items: start; }
.readiness-badge, .status-pill, .status { border-radius: 999px; padding: .25rem .65rem; font-size: .72rem; text-transform: uppercase; font-weight: 900; width: fit-content; }
.readiness-badge.verde, .status-pill.verde, .status.ok, .dot.verde { background: #ecfdf3; color: #027a48; }
.readiness-badge.vermelho, .status-pill.vermelho, .status.fail, .status.block, .dot.vermelho { background: #fef3f2; color: #b42318; }
.status-pill.amarelo, .status.warn, .dot.amarelo { background: #fffaeb; color: #b54708; }
.status-pill.azul, .dot.azul { background: #eff6ff; color: #1d4ed8; }
.status-pill.cinza, .dot.cinza { background: #f1f5f9; color: #475569; }
.readiness-table { display: grid; gap: .35rem; overflow-x: auto; }
.readiness-row { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(130px, .6fr) minmax(220px, 1.2fr) minmax(220px, 1.2fr); gap: .75rem; align-items: center; border: 1px solid #eaecf0; border-radius: 12px; padding: .75rem; min-width: 760px; }
.readiness-head { background: #f8fafc; color: #475569; font-weight: 900; }
.gap-list, .gate-list { display: grid; gap: .65rem; padding: 0; list-style: none; }
.gap-list li { border-left: 4px solid #d97706; padding: .55rem .75rem; background: #fffbeb; border-radius: 10px; }
.timeline { display: grid; gap: .75rem; padding: 0; list-style: none; }
.timeline li { display: flex; gap: .75rem; align-items: flex-start; }
.timeline small { display: block; color: #667085; }
.dot { width: .9rem; height: .9rem; border-radius: 999px; margin-top: .25rem; flex: 0 0 auto; }
.filtro { display: grid; gap: .3rem; font-weight: 700; }
select { border: 1px solid #d0d7de; border-radius: 10px; padding: .6rem; }
.validation-list { display: grid; gap: .75rem; }
.validation-item { border: 1px solid #eaecf0; border-radius: 14px; padding: .9rem; background: #fcfcfd; }
.validation-item header { display: flex; flex-wrap: wrap; gap: .55rem; align-items: center; }
.validation-item p { margin: .55rem 0 .35rem; color: #344054; }
.validation-item small { color: #667085; }
.validation-item em { margin-left: auto; font-style: normal; font-weight: 900; }
.gate-list li { display: flex; justify-content: space-between; gap: 1rem; border-bottom: 1px solid #eaecf0; padding-bottom: .55rem; }
.gate-action.fail, .gate-action.block { color: #b42318; }
.gate-action.warn { color: #b54708; }
.figma-dl { display: grid; gap: .75rem; }
.figma-dl div { border: 1px solid #eaecf0; border-radius: 12px; padding: .75rem; }
dt { font-weight: 800; }
dd { margin: .25rem 0 0; color: #344054; word-break: break-word; }
.flow { display: flex; flex-wrap: wrap; gap: .65rem; align-items: center; }
.flow span { border: 1px solid #d0d7de; border-radius: 999px; padding: .55rem .8rem; font-weight: 800; background: #f9fafb; }
.vazio { color: #667085; }
@media (min-width: 820px) { .hero, .panel-header, .grid-2 { grid-template-columns: 1fr auto; } .grid-2 { align-items: stretch; } }
</style>
