<template>
  <section class="page arquitetura-viva-page">
    <div class="page-header arquitetura-viva-header">
      <div>
        <h1>Arquitetura Viva</h1>
        <p class="muted">
          Diagramas navegáveis com rastreabilidade entre requisitos, código, runtime e analytics.
        </p>
      </div>
      <div class="d-flex flex-wrap gap-2">
        <v-chip size="small" color="success" variant="tonal">UI operacional</v-chip>
        <v-chip size="small" color="info" variant="tonal">Ambiente: {{ diagrama.environment }}</v-chip>
        <v-chip size="small" color="warning" variant="tonal">Confiança: {{ diagrama.audit.confidence }}</v-chip>
      </div>
    </div>

    <v-row class="mb-4">
      <v-col cols="12" md="3" v-for="kpi in kpis" :key="kpi.titulo">
        <v-card class="living-kpi" elevation="0">
          <v-card-text class="pa-4">
            <div class="kpi-label">{{ kpi.titulo }}</div>
            <div class="kpi-value">{{ kpi.valor }}</div>
            <div class="kpi-desc">{{ kpi.descricao }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="living-shell" elevation="0">
      <v-card-title class="d-flex align-center flex-wrap gap-2 pa-4">
        <v-icon color="primary">mdi-graph-outline</v-icon>
        <span class="living-title">Fluxo navegável · {{ diagrama.title }}</span>
        <v-spacer />
        <v-text-field
          v-model="filtro"
          density="compact"
          hide-details
          clearable
          prepend-inner-icon="mdi-magnify"
          label="Filtrar nós"
          class="living-search"
          data-testid="architecture-live-filter"
        />
      </v-card-title>

      <v-card-text class="pa-4 pt-0">
        <v-row>
          <v-col cols="12" lg="8">
            <div class="living-canvas" data-testid="architecture-live-canvas">
              <div class="lane" v-for="lane in lanesFiltradas" :key="lane.id">
                <div class="lane-title">{{ lane.titulo }}</div>
                <button
                  v-for="node in lane.nodes"
                  :key="node.id"
                  type="button"
                  class="living-node"
                  :class="[`living-node--${node.type}`, { 'living-node--active': node.id === noSelecionado.id }]"
                  :data-testid="`architecture-node-${node.id}`"
                  @click="selecionarNo(node.id)"
                >
                  <span class="node-icon">{{ node.icon }}</span>
                  <span class="node-label">{{ node.label }}</span>
                  <span class="node-meta">{{ node.environment }} · {{ node.owner }}</span>
                </button>
              </div>
            </div>

            <div class="flow-legend mt-3">
              <span v-for="edge in edgesDoNo" :key="edge.id" class="edge-chip">
                {{ nomeNo(edge.from) }} → {{ nomeNo(edge.to) }}
                <small>{{ edge.label }}</small>
              </span>
            </div>
          </v-col>

          <v-col cols="12" lg="4">
            <v-card class="inspector-card" elevation="0" data-testid="architecture-live-inspector">
              <v-card-title class="pa-4 pb-2">
                <div>
                  <div class="inspector-eyebrow">Inspector</div>
                  <div class="inspector-title">{{ noSelecionado.label }}</div>
                </div>
              </v-card-title>
              <v-card-text class="pa-4 pt-2">
                <p class="inspector-desc">{{ noSelecionado.description }}</p>

                <div class="inspector-grid">
                  <div>
                    <span>Tipo</span>
                    <strong>{{ noSelecionado.type }}</strong>
                  </div>
                  <div>
                    <span>Owner</span>
                    <strong>{{ noSelecionado.owner }}</strong>
                  </div>
                  <div>
                    <span>Ambiente</span>
                    <strong>{{ noSelecionado.environment }}</strong>
                  </div>
                  <div>
                    <span>Fonte</span>
                    <strong>{{ noSelecionado.source }}</strong>
                  </div>
                </div>

                <v-divider class="my-4" />

                <div class="subsection-title mb-2">
                  <v-icon size="15">mdi-source-branch</v-icon>
                  Dependências diretas
                </div>
                <div class="dependency-list">
                  <button
                    v-for="dep in dependenciasSelecionadas"
                    :key="dep.id"
                    type="button"
                    class="dependency-item"
                    @click="selecionarNo(dep.id)"
                  >
                    <v-icon size="14">mdi-arrow-right</v-icon>
                    <span>{{ dep.label }}</span>
                  </button>
                  <div v-if="!dependenciasSelecionadas.length" class="muted small-text">Sem dependências diretas mapeadas.</div>
                </div>

                <v-divider class="my-4" />

                <div class="subsection-title mb-2">
                  <v-icon size="15">mdi-robot-outline</v-icon>
                  Explicação IA governada
                </div>
                <div class="ai-explanation">
                  {{ explicacaoSelecionada }}
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card class="comp-card" elevation="0">
          <v-card-title class="pa-4 pb-2">Metadados auditáveis</v-card-title>
          <v-card-text class="pa-4 pt-0">
            <v-table density="compact" class="env-table">
              <tbody>
                <tr><td>ID</td><td><code>{{ diagrama.id }}</code></td></tr>
                <tr><td>Versão</td><td><code>{{ diagrama.version }}</code></td></tr>
                <tr><td>Gerado por</td><td><code>{{ diagrama.audit.generatedBy }}</code></td></tr>
                <tr><td>Gerado em</td><td><code>{{ diagrama.audit.generatedAt }}</code></td></tr>
                <tr><td>Hash</td><td><code>{{ diagrama.audit.hash }}</code></td></tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card class="comp-card" elevation="0">
          <v-card-title class="pa-4 pb-2">Gates de publicação</v-card-title>
          <v-card-text class="pa-4 pt-0">
            <div class="gate-list">
              <div v-for="gate in gates" :key="gate.nome" class="gate-item">
                <v-icon :color="gate.ok ? 'success' : 'warning'" size="16">
                  {{ gate.ok ? 'mdi-check-circle' : 'mdi-alert-circle-outline' }}
                </v-icon>
                <span>{{ gate.nome }}</span>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const filtro = ref('')
const noSelecionadoId = ref('req')

const diagrama = {
  id: 'diag-reqsys-living-architecture-001',
  title: 'Ciclo ReqSys de requisito até monitoramento',
  version: '1.0.0',
  environment: 'dev',
  audit: {
    generatedAt: '2026-06-20T00:00:00-03:00',
    generatedBy: 'architecture-visualization-engine',
    hash: 'sha256:pending-runtime-source',
    confidence: 'media',
  },
}

const nodes = [
  { id: 'req', lane: 'negocio', icon: '📄', label: 'Requisito', type: 'business', owner: 'Squad/Negócio', environment: 'dev', source: 'ReqSys', description: 'Demanda funcional ou técnica capturada no ReqSys com rastreabilidade de origem.' },
  { id: 'ia', lane: 'negocio', icon: '🤖', label: 'Análise IA', type: 'ai', owner: 'IA Governada', environment: 'dev', source: 'Qualidade IA', description: 'Análise assistida para critérios, ambiguidades, riscos e recomendações com score de confiança.' },
  { id: 'backlog', lane: 'delivery', icon: '📋', label: 'Backlog', type: 'delivery', owner: 'PO/Tech Lead', environment: 'dev', source: 'ReqSys/Pipeline', description: 'Priorização, refinamento e preparação da entrega com vínculo ao requisito original.' },
  { id: 'branch', lane: 'delivery', icon: '🌿', label: 'Branch', type: 'code', owner: 'Dev', environment: 'dev', source: 'GitHub', description: 'Branch de implementação criada a partir da linha base governada.' },
  { id: 'pr', lane: 'delivery', icon: '🔀', label: 'Pull Request', type: 'code', owner: 'Dev/Reviewer', environment: 'dev', source: 'GitHub PR', description: 'PR em draft ou review com checklist, evidências, CI e discussão técnica.' },
  { id: 'ci', lane: 'runtime', icon: '✅', label: 'CI/CD', type: 'runtime', owner: 'DevOps', environment: 'dev', source: 'GitHub Actions', description: 'Validação automatizada de build, testes, segurança e responsividade.' },
  { id: 'deploy', lane: 'runtime', icon: '🚀', label: 'Deploy', type: 'runtime', owner: 'DevOps', environment: 'homologacao', source: 'Pipeline', description: 'Publicação controlada para ambiente alvo após gates técnicos aprovados.' },
  { id: 'obs', lane: 'operacao', icon: '📡', label: 'Observabilidade', type: 'runtime', owner: 'SRE/Suporte', environment: 'producao', source: 'Logs/Traces', description: 'Monitoramento por logs, métricas, correlation_id, incidentes e saúde operacional.' },
  { id: 'analytics', lane: 'operacao', icon: '📊', label: 'Analytics', type: 'analytics', owner: 'BI/Gestão', environment: 'producao', source: 'Dashboard', description: 'Indicadores, linhagem, drill-down e análise de impacto a partir dos dados operacionais.' },
]

const edges = [
  { id: 'e1', from: 'req', to: 'ia', label: 'refinar' },
  { id: 'e2', from: 'ia', to: 'backlog', label: 'priorizar' },
  { id: 'e3', from: 'backlog', to: 'branch', label: 'implementar' },
  { id: 'e4', from: 'branch', to: 'pr', label: 'submeter' },
  { id: 'e5', from: 'pr', to: 'ci', label: 'validar' },
  { id: 'e6', from: 'ci', to: 'deploy', label: 'promover' },
  { id: 'e7', from: 'deploy', to: 'obs', label: 'monitorar' },
  { id: 'e8', from: 'obs', to: 'analytics', label: 'medir' },
  { id: 'e9', from: 'analytics', to: 'req', label: 'retroalimentar' },
]

const lanes = [
  { id: 'negocio', titulo: 'Negócio e IA' },
  { id: 'delivery', titulo: 'Delivery e Código' },
  { id: 'runtime', titulo: 'Runtime e Deploy' },
  { id: 'operacao', titulo: 'Operação e Analytics' },
]

const gates = [
  { nome: 'Fonte rastreável declarada', ok: true },
  { nome: 'Ambiente identificado', ok: true },
  { nome: 'Metadados auditáveis exibidos', ok: true },
  { nome: 'Sem secrets ou PII no grafo', ok: true },
  { nome: 'Drill-down por nó disponível', ok: true },
  { nome: 'Runtime real integrado', ok: false },
]

const kpis = computed(() => [
  { titulo: 'Nós', valor: nodes.length, descricao: 'Componentes navegáveis' },
  { titulo: 'Conexões', valor: edges.length, descricao: 'Dependências mapeadas' },
  { titulo: 'Gates OK', valor: gates.filter((gate) => gate.ok).length, descricao: 'Validações locais da UI' },
  { titulo: 'Confiança', valor: diagrama.audit.confidence, descricao: 'Sem runtime real ainda' },
])

const termoFiltro = computed(() => (filtro.value || '').trim().toLowerCase())

const noSelecionado = computed(() => nodes.find((node) => node.id === noSelecionadoId.value) || nodes[0])

const lanesFiltradas = computed(() => {
  return lanes
    .map((lane) => ({
      ...lane,
      nodes: nodes.filter((node) => {
        const pertenceLane = node.lane === lane.id
        const correspondeFiltro = !termoFiltro.value || [node.label, node.type, node.owner, node.source]
          .join(' ')
          .toLowerCase()
          .includes(termoFiltro.value)
        return pertenceLane && correspondeFiltro
      }),
    }))
    .filter((lane) => lane.nodes.length)
})

const edgesDoNo = computed(() => edges.filter((edge) => edge.from === noSelecionado.value.id || edge.to === noSelecionado.value.id))

const dependenciasSelecionadas = computed(() => {
  const ids = edges
    .filter((edge) => edge.from === noSelecionado.value.id)
    .map((edge) => edge.to)
  return nodes.filter((node) => ids.includes(node.id))
})

const explicacaoSelecionada = computed(() => {
  return `O nó ${noSelecionado.value.label} participa do fluxo vivo com fonte ${noSelecionado.value.source}, ambiente ${noSelecionado.value.environment} e owner ${noSelecionado.value.owner}. A explicação é limitada aos metadados versionados nesta UI; runtime real e OpenTelemetry ainda não estão integrados neste incremento.`
})

function selecionarNo(id) {
  noSelecionadoId.value = id
}

function nomeNo(id) {
  return nodes.find((node) => node.id === id)?.label || id
}
</script>

<style scoped>
.arquitetura-viva-header {
  gap: 16px;
}
.living-kpi,
.living-shell,
.inspector-card,
.comp-card {
  background: var(--card) !important;
  border: 1px solid var(--border);
  border-radius: 12px;
}
.kpi-label {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.kpi-value {
  color: var(--text);
  font-size: 26px;
  font-weight: 800;
  margin-top: 4px;
}
.kpi-desc,
.small-text {
  color: var(--muted);
  font-size: 11px;
}
.living-title {
  font-size: 15px;
  font-weight: 800;
}
.living-search {
  max-width: 260px;
}
.living-canvas {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 12px;
  min-height: 420px;
  padding: 16px;
  overflow-x: auto;
  background: var(--card-alt);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.lane {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 150px;
}
.lane-title {
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
  padding: 0 4px 4px;
  border-bottom: 1px solid var(--border);
}
.living-node {
  width: 100%;
  min-height: 92px;
  padding: 12px;
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--card);
  color: var(--text);
  cursor: pointer;
  transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease;
}
.living-node:hover,
.living-node:focus-visible {
  transform: translateY(-1px);
  border-color: var(--accent);
  outline: none;
}
.living-node--active {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(0, 92, 169, .18);
}
.node-icon {
  display: block;
  font-size: 20px;
  margin-bottom: 6px;
}
.node-label {
  display: block;
  font-size: 13px;
  font-weight: 800;
}
.node-meta {
  display: block;
  color: var(--muted);
  font-size: 10px;
  margin-top: 4px;
}
.living-node--business { background: rgba(99, 102, 241, .10); }
.living-node--ai { background: rgba(168, 85, 247, .10); }
.living-node--delivery { background: rgba(0, 92, 169, .10); }
.living-node--code { background: rgba(2, 132, 199, .10); }
.living-node--runtime { background: rgba(243, 146, 0, .10); }
.living-node--analytics { background: rgba(0, 179, 173, .10); }
.flow-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.edge-chip {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text);
  background: var(--card);
  font-size: 11px;
}
.edge-chip small {
  color: var(--muted);
}
.inspector-eyebrow {
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .06em;
}
.inspector-title {
  font-size: 18px;
  font-weight: 800;
}
.inspector-desc {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}
.inspector-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.inspector-grid div {
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card-alt);
}
.inspector-grid span {
  display: block;
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
}
.inspector-grid strong {
  display: block;
  font-size: 12px;
  margin-top: 2px;
}
.dependency-list,
.gate-list {
  display: grid;
  gap: 6px;
}
.dependency-item,
.gate-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card-alt);
  color: var(--text);
  font-size: 12px;
}
.dependency-item {
  cursor: pointer;
  text-align: left;
}
.ai-explanation {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card-alt);
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
}
.subsection-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.env-table {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
@media (max-width: 960px) {
  .living-canvas {
    grid-template-columns: repeat(2, minmax(160px, 1fr));
    min-height: auto;
  }
}
@media (max-width: 600px) {
  .living-search {
    max-width: 100%;
    width: 100%;
  }
  .living-canvas {
    grid-template-columns: 1fr;
    overflow-x: hidden;
  }
  .inspector-grid {
    grid-template-columns: 1fr;
  }
}
</style>
