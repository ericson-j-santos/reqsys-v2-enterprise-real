<template>
  <section class="page">
    <PageHeader
      title="Monitoramento de Qualidade de IA"
      subtitle="Acompanhe score geral, métricas-chave, tendência histórica e recomendações para melhoria contínua."
      :chip="statusLabel"
      :chip-color="statusColor"
      chip-tooltip="Status operacional atual da qualidade de IA"
    >
      <template #actions>
        <v-tooltip text="Executa um novo snapshot do monitoramento de qualidade" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              color="amber"
              variant="tonal"
              prepend-icon="mdi-camera"
              :loading="salvandoSnapshot"
              @click="gerarSnapshot"
            >
              Gerar snapshot
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Recarrega dados do monitoramento de qualidade" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-refresh"
              :loading="carregando"
              @click="carregar"
            >
              Atualizar
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Período do histórico para exportação/tendência" location="top">
          <template #activator="{ props }">
            <v-btn-toggle
              v-bind="props"
              v-model="periodoFiltro"
              density="compact"
              variant="outlined"
              divided
              mandatory
            >
              <v-btn :value="7" size="small">7d</v-btn>
              <v-btn :value="30" size="small">30d</v-btn>
              <v-btn :value="90" size="small">90d</v-btn>
              <v-btn :value="null" size="small">Todos</v-btn>
            </v-btn-toggle>
          </template>
        </v-tooltip>
        <v-tooltip text="Exporta tendência histórica em CSV" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-file-delimited"
              :loading="exportandoCsv"
              @click="exportarCsv"
            >
              CSV
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Exporta tendência histórica em PDF" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-file-pdf-box"
              :loading="exportandoPdf"
              @click="exportarPdf"
            >
              PDF
            </v-btn>
          </template>
        </v-tooltip>
      </template>
    </PageHeader>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4">
      {{ erro }}
    </v-alert>

    <v-row>
      <v-col cols="12" md="4">
        <v-card class="table-card h-100">
          <v-card-title>Score geral</v-card-title>
          <v-divider />
          <v-card-text>
            <div class="score-wrap">
              <v-progress-circular
                :model-value="scoreGeral"
                :size="132"
                :width="14"
                :color="statusColor"
              >
                <strong>{{ scoreGeral }}%</strong>
              </v-progress-circular>
              <div class="mt-3 muted">Amostra analisada: {{ resumo.contexto?.amostra_total ?? 0 }}</div>
              <div class="muted">Incidentes críticos (7d): {{ resumo.contexto?.incidentes_criticos_7d ?? 0 }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="8">
        <v-card class="table-card h-100">
          <v-card-title>Métricas de qualidade</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col v-for="item in metricasList" :key="item.key" cols="12" sm="6">
                <div class="metric-head-row">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}%</strong>
                </div>
                <v-progress-linear
                  :model-value="item.value"
                  :color="item.color"
                  rounded
                  height="10"
                />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col cols="12" lg="8">
        <v-card class="table-card">
          <v-card-title>
            Tendência histórica
            <v-chip v-if="periodoFiltro" size="x-small" class="ml-2" color="amber" variant="tonal">
              {{ periodoFiltro }}d
            </v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <v-sparkline
              v-if="tendenciaValues.length"
              :model-value="tendenciaValues"
              color="amber"
              line-width="2"
              auto-draw
              padding="8"
              smooth
              :fill="false"
            />
            <div v-else class="muted">Ainda não existem snapshots para exibir tendência.</div>

            <v-table class="mt-3" density="compact">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Score</th>
                  <th>Acurácia</th>
                  <th>Segurança</th>
                  <th>Incidentes</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in tendencia" :key="item.id">
                  <td>{{ formatDate(item.timestamp) }}</td>
                  <td><strong>{{ item.score_geral }}%</strong></td>
                  <td>{{ item.acuracia }}%</td>
                  <td>{{ item.seguranca }}%</td>
                  <td>{{ item.incidentes_criticos }}</td>
                </tr>
                <tr v-if="!tendencia.length">
                  <td colspan="5" class="empty-cell">Nenhum snapshot disponível.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card class="table-card">
          <v-card-title>Recomendações</v-card-title>
          <v-divider />
          <v-list density="compact">
            <v-list-item
              v-for="(item, idx) in recomendacoes"
              :key="`${idx}-${item}`"
              :title="item"
              prepend-icon="mdi-lightbulb-on-outline"
            />
            <v-list-item v-if="!recomendacoes.length" title="Sem recomendações no momento." />
          </v-list>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../services/api'
import { qualidadeIAService } from '../services/qualidadeIA'
import PageHeader from '../components/PageHeader.vue'
import { useAsyncLoader } from '../composables/useAsyncLoader'

const { carregando, erro, run } = useAsyncLoader()

const resumo = ref({})
const salvandoSnapshot = ref(false)
const exportandoCsv = ref(false)
const exportandoPdf = ref(false)
const periodoFiltro = ref(30)

const scoreGeral = computed(() => Math.round(resumo.value?.score_geral || 0))
const tendencia = computed(() => resumo.value?.tendencia || [])
const recomendacoes = computed(() => resumo.value?.recomendacoes || [])

const tendenciaValues = computed(() => tendencia.value.map((i) => Number(i.score_geral || 0)))

const metricasList = computed(() => {
  const m = resumo.value?.metricas || {}
  return [
    { key: 'acuracia', label: 'Acurácia', value: Number(m.acuracia || 0), color: 'blue' },
    { key: 'relevancia', label: 'Relevância', value: Number(m.relevancia || 0), color: 'purple' },
    { key: 'consistencia', label: 'Consistência', value: Number(m.consistencia || 0), color: 'teal' },
    { key: 'seguranca', label: 'Segurança', value: Number(m.seguranca || 0), color: 'green' },
    { key: 'cobertura_dados', label: 'Cobertura de dados', value: Number(m.cobertura_dados || 0), color: 'amber' },
  ]
})

const statusLabel = computed(() => {
  const value = resumo.value?.status || 'desconhecido'
  return value.charAt(0).toUpperCase() + value.slice(1)
})

const statusColor = computed(() => {
  const value = resumo.value?.status
  if (value === 'excelente') return 'green'
  if (value === 'estavel') return 'blue'
  if (value === 'atencao') return 'amber'
  if (value === 'critico') return 'red'
  return 'grey'
})

function formatDate(raw) {
  if (!raw) return '—'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('pt-BR')
}

async function carregar() {
  await run(async () => {
    const params = periodoFiltro.value != null ? `?dias=${periodoFiltro.value}` : ''
    const { data } = await api.get(`/v1/qualidade-ia/resumo${params}`)
    resumo.value = data?.data || {}
  })
}

watch(periodoFiltro, carregar)

async function gerarSnapshot() {
  salvandoSnapshot.value = true
  try {
    await api.post('/v1/qualidade-ia/snapshot')
    await carregar()
  } catch {
    // Erro já tratado por carregar() na atualização posterior.
  } finally {
    salvandoSnapshot.value = false
  }
}

async function exportarCsv() {
  exportandoCsv.value = true
  try {
    await qualidadeIAService.baixarTendenciaCsv(200, periodoFiltro.value)
  } finally {
    exportandoCsv.value = false
  }
}

async function exportarPdf() {
  exportandoPdf.value = true
  try {
    await qualidadeIAService.baixarTendenciaPdf(200, periodoFiltro.value)
  } finally {
    exportandoPdf.value = false
  }
}

onMounted(carregar)
</script>

<style scoped>
.score-wrap {
  display: grid;
  place-items: center;
  text-align: center;
}

.metric-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 0.92rem;
}

.empty-cell {
  text-align: center;
  color: var(--muted);
  padding: 18px;
}
</style>
