<template>
  <section class="ari-page" data-testid="route-analytics-runtime-intelligence" aria-labelledby="titulo-ari">
    <div class="cabecalho">
      <div>
        <p class="eyebrow">Analytics · runtime · evidência</p>
        <h1 id="titulo-ari">Analytics Runtime Intelligence</h1>
        <p class="muted">
          Consolida validações analíticas e prontidão operacional sem promover amostras locais a evidência de produção.
        </p>
      </div>
      <div class="acoes">
        <a class="link-acao" href="/figma-github">Figma e GitHub</a>
        <v-btn color="primary" :loading="carregando" @click="carregarSnapshot">Atualizar</v-btn>
      </div>
    </div>

    <v-alert v-if="erro" type="error" variant="tonal" role="alert">{{ erro }}</v-alert>
    <v-alert v-if="snapshot && !snapshot.production_ready" type="warning" variant="tonal" role="status">
      <strong>Evidência externa pendente.</strong>
      O contrato está implementado, mas produção continua bloqueada até staging, telemetria e lineage reais serem comprovados.
    </v-alert>

    <v-row dense>
      <v-col v-for="card in scoreCards" :key="card.campo" cols="12" sm="6" md="3">
        <v-card class="painel" elevation="0">
          <v-card-text>
            <span class="muted">{{ card.titulo }}</span>
            <strong class="score">{{ formatarScore(card.campo) }}</strong>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="painel" elevation="0">
      <v-card-title>Prontidão operacional</v-card-title>
      <v-card-subtitle>
        Fonte: {{ snapshot?.evidence_scope || 'não carregada' }} · Execução: {{ snapshot?.correlation_id || '-' }}
      </v-card-subtitle>
      <v-card-text>
        <div class="readiness-list">
          <article v-for="item in snapshot?.readiness_matrix || []" :key="item.capability" class="readiness-item">
            <div>
              <strong>{{ item.capability }}</strong>
              <span class="muted">{{ item.estado }}</span>
            </div>
            <p>{{ item.evidencia }}</p>
            <small class="muted">Próximo passo: {{ item.gap }}</small>
          </article>
        </div>
      </v-card-text>
    </v-card>

    <v-row dense>
      <v-col cols="12" md="6">
        <v-card class="painel fill" elevation="0">
          <v-card-title>Validações analíticas</v-card-title>
          <v-card-text>
            <article v-for="item in snapshot?.validacoes || []" :key="item.codigo" class="validacao">
              <div class="linha">
                <strong>{{ item.nome }}</strong>
                <span>{{ item.score }}% · {{ item.status }}</span>
              </div>
              <p>{{ item.evidencia }}</p>
              <small class="muted">{{ item.acao_recomendada }}</small>
            </article>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card class="painel fill" elevation="0">
          <v-card-title>Bloqueios para produção</v-card-title>
          <v-card-text>
            <ul class="gap-list">
              <li v-for="gap in snapshot?.production_gaps || []" :key="gap">{{ gap }}</li>
            </ul>
            <p v-if="!snapshot?.production_gaps?.length" class="muted">Nenhum gap informado.</p>
            <v-divider class="my-4" />
            <strong>Figma</strong>
            <p>{{ snapshot?.figma?.evidence || 'Sem evidência carregada.' }}</p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const API_BASE = '/api/analytics-runtime-intelligence/snapshot'
const snapshot = ref(null)
const carregando = ref(false)
const erro = ref('')

const scoreCards = [
  { campo: 'health_score', titulo: 'Health Score' },
  { campo: 'production_ready', titulo: 'Produção' },
  { campo: 'runtime_sql_validation', titulo: 'SQL estático' },
  { campo: 'staging_validation', titulo: 'Staging' },
]

function formatarScore(campo) {
  if (!snapshot.value) return '-'
  if (campo === 'health_score') return `${snapshot.value.health_score ?? '-'}%`
  if (campo === 'production_ready') return snapshot.value.production_ready ? 'Pronto' : 'Bloqueado'
  if (campo === 'runtime_sql_validation') return snapshot.value.runtime_sql_validation?.runtime_sql_ready ? 'Contrato OK' : 'Bloqueado'
  if (campo === 'staging_validation') return snapshot.value.staging_validation?.staging_ready ? 'Validado' : 'Sem evidência'
  return '-'
}

function fallbackSnapshot() {
  return {
    evidence_scope: 'frontend_fallback',
    correlation_id: 'não disponível',
    health_score: null,
    production_ready: false,
    draft_recomendado: true,
    runtime_sql_validation: { runtime_sql_ready: false, production_evidence: false },
    staging_validation: { staging_ready: false },
    readiness_matrix: [
      {
        capability: 'API ARI',
        estado: 'EVIDENCIA_AUSENTE',
        evidencia: 'A API não respondeu; o frontend não promove fallback a estado saudável.',
        gap: 'Restabelecer API e repetir a coleta.',
        bloqueia_producao: true,
      },
    ],
    validacoes: [],
    production_gaps: ['API ARI indisponível; manter fail-closed.'],
    figma: { status: 'evidence_pending', ready: false, evidence: 'Sem readback Figma atual.' },
  }
}

async function carregarSnapshot() {
  carregando.value = true
  erro.value = ''
  try {
    const resposta = await fetch(API_BASE, { headers: { Accept: 'application/json' } })
    const payload = await resposta.json().catch(() => ({}))
    if (!resposta.ok) throw new Error('Falha ao carregar Analytics Runtime Intelligence')
    snapshot.value = payload.data || payload
  } catch {
    erro.value = 'Não foi possível carregar o ARI; o estado permanece bloqueado.'
    snapshot.value = fallbackSnapshot()
  } finally {
    carregando.value = false
  }
}

onMounted(carregarSnapshot)
</script>

<style scoped>
.ari-page { display: grid; gap: var(--space-md); }
.cabecalho { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-lg); flex-wrap: wrap; }
.acoes { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
.eyebrow { margin: 0 0 var(--space-xs); font-size: var(--font-size-xs); font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
.muted { color: var(--muted); }
.link-acao { font-weight: 700; }
.painel { border: 1px solid var(--line); }
.fill { height: 100%; }
.score { display: block; margin-top: var(--space-xs); font-size: var(--font-size-2xl); }
.readiness-list { display: grid; gap: var(--space-sm); }
.readiness-item, .validacao { border-bottom: 1px solid var(--line); padding: var(--space-sm) 0; }
.readiness-item:last-child, .validacao:last-child { border-bottom: 0; }
.readiness-item div, .linha { display: flex; justify-content: space-between; gap: var(--space-sm); flex-wrap: wrap; }
.readiness-item p, .validacao p { margin: var(--space-xs) 0; }
.gap-list { display: grid; gap: var(--space-xs); padding-left: var(--space-lg); }
</style>
