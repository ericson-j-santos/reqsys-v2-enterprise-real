<template>
  <section class="query-page">
    <div class="query-header">
      <div>
        <p class="eyebrow">Arquitetura Viva · SQL Intelligence</p>
        <h1>Query Intelligence Platform</h1>
        <p class="muted">Analise SQL sem execução, extraia intenção lógica, riscos, lineage inicial e grafo navegável.</p>
      </div>
      <v-chip :color="riskColor" variant="tonal" size="large">Risco {{ analysis.riskScore }} · {{ analysis.riskLevel }}</v-chip>
    </div>

    <v-row class="mt-4" dense>
      <v-col cols="12" md="7">
        <v-card class="panel" elevation="0">
          <v-card-title>Editor SQL</v-card-title>
          <v-card-text>
            <v-textarea v-model="sql" label="Consulta SQL" rows="16" auto-grow spellcheck="false" variant="outlined" class="sql-editor" @update:model-value="analisar" />
            <div class="actions">
              <v-btn color="primary" prepend-icon="mdi-database-search" @click="analisar">Analisar</v-btn>
              <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="carregarExemplo">Exemplo avançado</v-btn>
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
              <div class="metric"><span>Joins</span><strong>{{ analysis.joins.length }}</strong></div>
              <div class="metric"><span>CTEs</span><strong>{{ analysis.ctes.length }}</strong></div>
              <div class="metric"><span>Achados</span><strong>{{ analysis.findings.length }}</strong></div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-2" dense>
      <v-col cols="12" lg="6">
        <v-card class="panel" elevation="0">
          <v-card-title>Grafo lógico navegável</v-card-title>
          <v-card-text>
            <div class="graph" role="list" aria-label="Grafo lógico da consulta">
              <div v-for="node in analysis.graph.nodes" :key="node.id" class="graph-node" :class="`node-${node.type}`" role="listitem">
                <strong>{{ node.label }}</strong>
                <span>{{ node.type }}</span>
                <small v-if="node.detail">{{ node.detail }}</small>
              </div>
              <p v-if="!analysis.graph.nodes.length" class="muted">Nenhum nó identificado.</p>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" lg="6">
        <v-card class="panel" elevation="0">
          <v-card-title>Achados de governança</v-card-title>
          <v-card-text>
            <v-alert v-for="finding in analysis.findings" :key="`${finding.type}-${finding.message}`" :type="alertType(finding.severity)" variant="tonal" class="mb-2">
              <strong>{{ finding.type }}</strong> — {{ finding.message }}
            </v-alert>
            <v-alert v-if="!analysis.findings.length" type="success" variant="tonal">Nenhum achado crítico identificado na análise estática inicial.</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="panel mt-4" elevation="0">
      <v-card-title>Analítico extraído</v-card-title>
      <v-card-text>
        <v-table density="compact">
          <thead><tr><th>Dimensão</th><th>Valor</th></tr></thead>
          <tbody>
            <tr><td>Colunas</td><td>{{ analysis.columns.join(', ') || 'Não detectado' }}</td></tr>
            <tr><td>Tabelas</td><td>{{ tableLabels || 'Não detectado' }}</td></tr>
            <tr><td>Filtros</td><td>{{ analysis.filters || 'Não detectado' }}</td></tr>
            <tr><td>Agrupamento</td><td>{{ analysis.groupBy || 'Não detectado' }}</td></tr>
            <tr><td>Ordenação</td><td>{{ analysis.orderBy || 'Não detectado' }}</td></tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { analyzeSql } from '../services/queryIntelligence'

const exemploAvancado = `WITH vendas_mes AS (
    SELECT cliente_id, date_trunc('month', data_venda) AS mes, SUM(valor_total) AS total_mes
    FROM vendas
    WHERE status = 'CONCLUIDA'
    GROUP BY cliente_id, date_trunc('month', data_venda)
), ranking AS (
    SELECT cliente_id, mes, total_mes, RANK() OVER (PARTITION BY mes ORDER BY total_mes DESC) AS posicao
    FROM vendas_mes
)
SELECT cliente_id, mes, total_mes, posicao
FROM ranking
WHERE posicao <= 10
ORDER BY mes DESC, posicao;`

const sql = ref(`SELECT
    u.id,
    u.name,
    o.total
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE o.total > 100
ORDER BY o.total DESC;`)

const analysis = ref(analyzeSql(sql.value))

function analisar() { analysis.value = analyzeSql(sql.value) }
function carregarExemplo() { sql.value = exemploAvancado; analisar() }

const tableLabels = computed(() => analysis.value.tables.map((item) => (item.alias ? `${item.table} (${item.alias})` : item.table)).join(', '))
const riskColor = computed(() => ({ critical: 'red', high: 'deep-orange', medium: 'amber', low: 'green', none: 'grey' }[analysis.value.riskLevel] || 'grey'))

function alertType(severity) {
  if (severity === 'critical' || severity === 'high') return 'error'
  if (severity === 'medium') return 'warning'
  return 'info'
}
</script>

<style scoped>
.query-page { display: flex; flex-direction: column; gap: 8px; }
.query-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.fill { height: 100%; }
.sql-editor :deep(textarea) { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace; line-height: 1.45; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.summary { font-size: 16px; line-height: 1.55; }
.metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.metric { padding: 12px; border-radius: 12px; background: rgba(148, 163, 184, 0.12); }
.metric span { display: block; font-size: 12px; color: var(--text-muted, #6b7280); }
.metric strong { font-size: 24px; }
.graph { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.graph-node { min-height: 96px; padding: 12px; border: 1px solid rgba(148, 163, 184, 0.32); border-radius: 14px; background: rgba(15, 23, 42, 0.03); }
.graph-node strong, .graph-node span, .graph-node small { display: block; }
.graph-node span { margin-top: 4px; font-size: 12px; text-transform: uppercase; color: var(--text-muted, #6b7280); }
.graph-node small { margin-top: 8px; word-break: break-word; }
@media (max-width: 600px) { .query-header { align-items: stretch; } .metric-grid { grid-template-columns: 1fr; } }
</style>
