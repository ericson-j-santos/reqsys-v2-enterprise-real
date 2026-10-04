<template>
  <section class="query-page" data-testid="route-query-intelligence">
    <div class="query-header">
      <div>
        <p class="eyebrow">Arquitetura Viva · análise SQL</p>
        <h1>Análise inteligente de consultas</h1>
        <p class="muted">Examine SQL sem executar comandos, veja intenção lógica, relações e alertas de risco.</p>
      </div>
      <v-chip :color="riskColor" variant="tonal" size="large" data-testid="query-risk-chip">
        Risco {{ analysis.riskScore }} · {{ riskLabel }}
      </v-chip>
    </div>

    <v-row class="mt-4" dense>
      <v-col cols="12" md="7">
        <v-card class="panel" elevation="0">
          <v-card-title>Consulta SQL</v-card-title>
          <v-card-text>
            <v-textarea
              v-model="sql"
              label="Consulta SQL"
              rows="14"
              auto-grow
              spellcheck="false"
              variant="outlined"
              class="sql-editor"
              data-testid="query-sql-input"
              @update:model-value="analisar"
            />
            <div class="actions">
              <v-btn color="primary" prepend-icon="mdi-database-search" @click="analisar">Analisar</v-btn>
              <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="carregarExemplo">Carregar exemplo</v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="5">
        <v-card class="panel fill" elevation="0">
          <v-card-title>Intenção lógica</v-card-title>
          <v-card-text>
            <p class="summary">{{ analysis.summary }}</p>
            <v-divider class="my-4" />
            <div class="metric-grid">
              <div class="metric"><span>Tabelas</span><strong>{{ analysis.tables.length }}</strong></div>
              <div class="metric"><span>Junções</span><strong>{{ analysis.joins.length }}</strong></div>
              <div class="metric"><span>CTEs</span><strong>{{ analysis.ctes.length }}</strong></div>
              <div class="metric"><span>Alertas</span><strong>{{ analysis.findings.length }}</strong></div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-2" dense>
      <v-col cols="12" lg="6">
        <v-card class="panel" elevation="0">
          <v-card-title>Relações lógicas</v-card-title>
          <v-card-text>
            <div class="graph" role="list" aria-label="Relações lógicas da consulta">
              <div v-for="node in analysis.graph.nodes" :key="node.id" class="graph-node" role="listitem">
                <strong>{{ node.label }}</strong>
                <span>{{ node.type }}</span>
                <small v-if="node.detail">{{ node.detail }}</small>
              </div>
              <p v-if="!analysis.graph.nodes.length" class="muted">Nenhum item identificado.</p>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="6">
        <v-card class="panel" elevation="0">
          <v-card-title>Alertas de governança</v-card-title>
          <v-card-text>
            <v-alert
              v-for="finding in analysis.findings"
              :key="`${finding.type}-${finding.message}`"
              :type="alertType(finding.severity)"
              variant="tonal"
              class="mb-2"
              data-testid="query-finding"
            >
              <strong>{{ finding.type }}</strong> — {{ finding.message }}
            </v-alert>
            <v-alert v-if="!analysis.findings.length" type="success" variant="tonal">
              Nenhum alerta relevante identificado na análise estática.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { analyzeSql } from '../services/queryIntelligence'

const exampleSql = `WITH vendas_mes AS (
  SELECT cliente_id, SUM(valor_total) AS total_mes
  FROM vendas
  WHERE situacao = 'CONCLUIDA'
  GROUP BY cliente_id
)
SELECT cliente_id, total_mes
FROM vendas_mes
ORDER BY total_mes DESC;`

const sql = ref('SELECT u.id, u.nome, p.total FROM usuarios u JOIN pedidos p ON p.usuario_id = u.id WHERE p.total > 100 ORDER BY p.total DESC;')
const analysis = ref(analyzeSql(sql.value))

function analisar() {
  analysis.value = analyzeSql(sql.value)
}

function carregarExemplo() {
  sql.value = exampleSql
  analisar()
}

const riskColor = computed(() => ({
  critical: 'red',
  high: 'deep-orange',
  medium: 'amber',
  low: 'green',
  none: 'grey',
}[analysis.value.riskLevel] || 'grey'))

const riskLabel = computed(() => ({
  critical: 'crítico',
  high: 'alto',
  medium: 'médio',
  low: 'baixo',
  none: 'sem dados',
}[analysis.value.riskLevel] || 'sem dados'))

function alertType(severity) {
  if (severity === 'critical' || severity === 'high') return 'error'
  if (severity === 'medium') return 'warning'
  return 'info'
}
</script>

<style scoped>
.query-page { display: flex; flex-direction: column; gap: var(--space-sm); }
.query-header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-lg); flex-wrap: wrap; }
.eyebrow { margin: 0 0 var(--space-xs); font-size: var(--font-size-xs); font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--muted); }
.panel { border: 1px solid var(--line); border-radius: 16px; }
.fill { height: 100%; }
.sql-editor :deep(textarea) { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; line-height: 1.45; }
.actions { display: flex; gap: var(--space-sm); flex-wrap: wrap; }
.summary { font-size: var(--font-size-md); line-height: 1.55; }
.metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-sm); }
.metric { padding: var(--space-md); border-radius: 12px; background: rgba(148, 163, 184, 0.12); }
.metric span { display: block; font-size: var(--font-size-xs); color: var(--muted); }
.metric strong { font-size: 24px; }
.graph { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-sm); }
.graph-node { min-height: 96px; padding: var(--space-md); border: 1px solid var(--line); border-radius: 14px; background: rgba(15, 23, 42, 0.03); }
.graph-node strong, .graph-node span, .graph-node small { display: block; }
.graph-node span { margin-top: var(--space-xs); font-size: var(--font-size-xs); text-transform: uppercase; color: var(--muted); }
.graph-node small { margin-top: var(--space-sm); word-break: break-word; }
@media (max-width: 600px) { .metric-grid { grid-template-columns: 1fr; } }
</style>
