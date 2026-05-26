<template>
  <div class="quality-page">
    <div class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Qualidade de IA</div>
        <div class="text-body-2 text-medium-emphasis">
          Score geral, métricas-chave, tendência histórica e exportação para análise operacional.
        </div>
      </div>

      <div class="page-actions">
        <v-btn-toggle v-model="periodDays" density="compact" variant="outlined" divided mandatory>
          <v-btn :value="7" size="small">7d</v-btn>
          <v-btn :value="30" size="small">30d</v-btn>
          <v-btn :value="90" size="small">90d</v-btn>
        </v-btn-toggle>
        <v-btn variant="outlined" prepend-icon="mdi-file-delimited" :loading="exportingCsv" @click="exportCsv">
          CSV
        </v-btn>
        <v-btn variant="outlined" prepend-icon="mdi-file-pdf-box" :loading="exportingPdf" @click="exportPdf">
          PDF
        </v-btn>
        <v-btn color="secondary" prepend-icon="mdi-camera" :loading="savingSnapshot" @click="createSnapshot">
          Snapshot
        </v-btn>
        <v-btn color="primary" prepend-icon="mdi-refresh" :loading="loading" @click="loadSummary">
          Atualizar
        </v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" closable @click:close="errorMessage = ''">
      {{ errorMessage }}
    </v-alert>

    <v-alert v-if="loading" type="info" variant="tonal" class="mb-2" icon="mdi-loading mdi-spin">
      Atualizando indicadores de qualidade...
    </v-alert>

    <v-row>
      <v-col cols="12" md="4">
        <v-card rounded="xl" elevation="1" class="panel-card h-100">
          <v-card-title>Score geral</v-card-title>
          <v-divider />
          <v-card-text class="score-card">
            <v-progress-circular :model-value="scoreGeral" :size="132" :width="12" :color="statusColor">
              <strong>{{ scoreGeral }}%</strong>
            </v-progress-circular>
            <div class="mt-4 text-body-2 text-medium-emphasis">Amostra analisada: {{ summary.contexto?.amostra_total ?? 0 }}</div>
            <div class="text-body-2 text-medium-emphasis">Incidentes críticos (7d): {{ summary.contexto?.incidentes_criticos_7d ?? 0 }}</div>
            <v-chip class="mt-4" :color="statusColor" variant="tonal">{{ statusLabel }}</v-chip>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="8">
        <v-card rounded="xl" elevation="1" class="panel-card h-100">
          <v-card-title>Métricas de qualidade</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col v-for="metric in metricsList" :key="metric.key" cols="12" sm="6">
                <div class="metric-head-row">
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.value }}%</strong>
                </div>
                <v-progress-linear :model-value="metric.value" :color="metric.color" rounded height="10" />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col cols="12" lg="8">
        <v-card rounded="xl" elevation="1" class="panel-card">
          <v-card-title class="d-flex align-center justify-space-between ga-2 flex-wrap">
            <span>Tendência histórica</span>
            <v-chip size="small" color="secondary" variant="tonal">{{ periodDays }}d</v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <v-sparkline
              v-if="trendValues.length"
              :model-value="trendValues"
              color="primary"
              line-width="2"
              auto-draw
              padding="8"
              smooth
              :fill="false"
            />
            <div v-else class="text-medium-emphasis">Ainda não existem snapshots para exibir tendência.</div>

            <v-table class="mt-3" density="comfortable">
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
                <tr v-for="item in trend" :key="item.id || item.timestamp">
                  <td>{{ formatDate(item.timestamp) }}</td>
                  <td><strong>{{ item.score_geral }}%</strong></td>
                  <td>{{ item.acuracia }}%</td>
                  <td>{{ item.seguranca }}%</td>
                  <td>{{ item.incidentes_criticos }}</td>
                </tr>
                <tr v-if="!trend.length">
                  <td colspan="5" class="empty-cell">Nenhum snapshot disponível.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card rounded="xl" elevation="1" class="panel-card">
          <v-card-title>Recomendações</v-card-title>
          <v-divider />
          <v-list density="comfortable">
            <v-list-item
              v-for="(recommendation, index) in recommendations"
              :key="`${index}-${recommendation}`"
              :title="recommendation"
              prepend-icon="mdi-lightbulb-on-outline"
            />
            <v-list-item v-if="!recommendations.length" title="Sem recomendações no momento." />
          </v-list>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../services/api'
import { useStatusBanner } from '../composables/useStatusBanner'

const { loading, errorMessage, setLoading, setError } = useStatusBanner()
const savingSnapshot = ref(false)
const exportingCsv = ref(false)
const exportingPdf = ref(false)
const periodDays = ref(30)
const summary = ref({})

const scoreGeral = computed(() => Math.round(summary.value?.score_geral || 0))
const trend = computed(() => summary.value?.tendencia || [])
const recommendations = computed(() => summary.value?.recomendacoes || [])
const trendValues = computed(() => trend.value.map((item) => Number(item.score_geral || 0)))

const metricsList = computed(() => {
  const metrics = summary.value?.metricas || {}
  return [
    { key: 'acuracia', label: 'Acurácia', value: Number(metrics.acuracia || 0), color: 'primary' },
    { key: 'relevancia', label: 'Relevância', value: Number(metrics.relevancia || 0), color: 'secondary' },
    { key: 'consistencia', label: 'Consistência', value: Number(metrics.consistencia || 0), color: 'success' },
    { key: 'seguranca', label: 'Segurança', value: Number(metrics.seguranca || 0), color: 'info' },
    { key: 'cobertura_dados', label: 'Cobertura de dados', value: Number(metrics.cobertura_dados || 0), color: 'warning' },
  ]
})

const statusLabel = computed(() => {
  const status = summary.value?.status || 'desconhecido'
  return status.charAt(0).toUpperCase() + status.slice(1)
})

const statusColor = computed(() => {
  const status = summary.value?.status
  if (status === 'excelente') return 'success'
  if (status === 'estavel') return 'primary'
  if (status === 'atencao') return 'warning'
  if (status === 'critico') return 'error'
  return 'grey'
})

function buildTrendUrl(extension) {
  const params = new URLSearchParams({ limit: '200', dias: String(periodDays.value) })
  return `/v1/qualidade-ia/tendencia.${extension}?${params.toString()}`
}

function downloadBlob(data, type, filename) {
  const blob = new Blob([data], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function formatDate(raw) {
  if (!raw) return '—'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('pt-BR')
}

async function loadSummary() {
  setLoading()
  try {
    const response = await api.get(`/v1/qualidade-ia/resumo?dias=${periodDays.value}`)
    summary.value = response?.data?.data || {}
  } catch (error) {
    setError(error?.response?.data?.detail || error?.message || 'Erro ao carregar monitoramento de qualidade de IA.')
  } finally {
    setLoading(false)
  }
}

async function createSnapshot() {
  savingSnapshot.value = true
  try {
    await api.post('/v1/qualidade-ia/snapshot')
    await loadSummary()
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Erro ao gerar snapshot.'
  } finally {
    savingSnapshot.value = false
  }
}

async function exportCsv() {
  exportingCsv.value = true
  try {
    const response = await api.get(buildTrendUrl('csv'), { responseType: 'blob' })
    downloadBlob(response.data, 'text/csv;charset=utf-8', `qualidade-ia-tendencia-${periodDays.value}d.csv`)
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Erro ao exportar CSV de tendência.'
  } finally {
    exportingCsv.value = false
  }
}

async function exportPdf() {
  exportingPdf.value = true
  try {
    const response = await api.get(buildTrendUrl('pdf'), { responseType: 'blob' })
    downloadBlob(response.data, 'application/pdf', `qualidade-ia-tendencia-${periodDays.value}d.pdf`)
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Erro ao exportar PDF de tendência.'
  } finally {
    exportingPdf.value = false
  }
}

watch(periodDays, loadSummary)
onMounted(loadSummary)
</script>

<style scoped>
.quality-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.page-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.panel-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
}

.score-card {
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
  color: rgba(51, 51, 51, 0.7);
  padding: 18px;
}

@media (max-width: 600px) {
  .page-actions {
    width: 100%;
  }
}
</style>
