<template>
  <div class="reports-page">
    <div class="reports-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Relatórios SSRS</div>
        <div class="text-body-2 text-medium-emphasis">
          Catálogo, monitoramento, preview e download de relatórios em uma experiência responsiva.
        </div>
      </div>

      <div class="reports-actions">
        <v-btn
          variant="outlined"
          prepend-icon="mdi-radar"
          :loading="checkingStatus"
          :disabled="!enabled"
          @click="loadStatus"
        >
          Verificar
        </v-btn>
        <v-btn
          color="primary"
          prepend-icon="mdi-refresh"
          :loading="loading"
          @click="loadData"
        >
          Atualizar
        </v-btn>
        <v-chip :color="healthColor" variant="tonal" prepend-icon="mdi-cloud-check-outline">
          {{ healthLabel }}
        </v-chip>
      </div>
    </div>

    <v-alert
      v-if="errorMessage"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="errorMessage = ''"
    >
      {{ errorMessage }}
    </v-alert>

    <v-alert
      v-if="!enabled"
      type="warning"
      variant="tonal"
      class="mb-4"
    >
      Integração SSRS desabilitada. Configure SSRS_BASE_URL no backend para habilitar catálogo e preview.
    </v-alert>

    <v-row class="mb-2">
      <v-col cols="12" sm="6" xl="3">
        <v-card rounded="xl" elevation="1" class="summary-card">
          <v-card-text>
            <div class="summary-label">Status do SSRS</div>
            <div class="summary-value" :class="enabled && healthy ? 'is-good' : 'is-warning'">{{ healthLabel }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" xl="3">
        <v-card rounded="xl" elevation="1" class="summary-card">
          <v-card-text>
            <div class="summary-label">Relatórios no catálogo</div>
            <div class="summary-value">{{ reports.length }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" xl="3">
        <v-card rounded="xl" elevation="1" class="summary-card">
          <v-card-text>
            <div class="summary-label">Acessíveis</div>
            <div class="summary-value is-good">{{ onlineReports }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" xl="3">
        <v-card rounded="xl" elevation="1" class="summary-card">
          <v-card-text>
            <div class="summary-label">Última verificação</div>
            <div class="summary-value summary-value-small">{{ checkedAtLabel }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" lg="4" xl="3">
        <v-card rounded="xl" elevation="1" class="panel-card h-100">
          <v-card-title class="d-flex align-center justify-space-between ga-2 flex-wrap">
            <span>Catálogo</span>
            <v-chip size="small" color="secondary" variant="tonal">{{ reports.length }}</v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-0">
            <v-list density="comfortable" nav>
              <v-list-item
                v-for="report in mergedReports"
                :key="report.name"
                :active="selectedReport?.name === report.name"
                rounded="lg"
                class="mx-2 my-1"
                @click="selectReport(report)"
              >
                <template #prepend>
                  <v-icon :color="report.accessible === false ? 'error' : 'primary'">mdi-file-chart-outline</v-icon>
                </template>
                <v-list-item-title>{{ report.name }}</v-list-item-title>
                <v-list-item-subtitle>
                  {{ reportStatusLabel(report) }}
                </v-list-item-subtitle>
                <template #append>
                  <v-chip size="x-small" :color="report.accessible === false ? 'error' : 'success'" variant="tonal">
                    {{ report.status_code || '—' }}
                  </v-chip>
                </template>
              </v-list-item>
              <v-list-item v-if="!reports.length" title="Nenhum relatório disponível" subtitle="Verifique a configuração do backend." />
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="8" xl="9">
        <v-card rounded="xl" elevation="1" class="panel-card mb-4">
          <v-card-title class="d-flex align-center justify-space-between ga-2 flex-wrap">
            <div>
              <div class="text-h6">{{ selectedReport?.name || 'Selecione um relatório' }}</div>
              <div class="text-body-2 text-medium-emphasis">
                {{ selectedReport ? 'Preview e ações rápidas do relatório selecionado.' : 'Escolha um item do catálogo para visualizar.' }}
              </div>
            </div>
            <div class="reports-actions" v-if="selectedReport">
              <v-btn variant="outlined" prepend-icon="mdi-open-in-new" @click="openNewTab(selectedReport)">
                Nova guia
              </v-btn>
              <v-btn color="secondary" prepend-icon="mdi-file-pdf-box" :loading="downloadingReport === selectedReport.name" @click="downloadPdf(selectedReport)">
                PDF
              </v-btn>
            </div>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <div v-if="selectedReport" class="preview-shell">
              <iframe :src="selectedReport.render_url" :title="selectedReport.name" class="preview-frame" />
            </div>
            <div v-else class="empty-state">
              <v-icon size="52" color="primary">mdi-monitor-dashboard</v-icon>
              <div class="text-h6 mt-3">Preview de relatórios</div>
              <div class="text-body-2 text-medium-emphasis mt-1">Selecione um item no catálogo para abrir o preview ou baixar o PDF.</div>
            </div>
            <v-alert v-if="selectedReport" type="info" variant="tonal" density="compact" class="mt-3">
              Se o preview for bloqueado pelo servidor, use Nova guia ou PDF.
            </v-alert>
          </v-card-text>
        </v-card>

        <v-card rounded="xl" elevation="1" class="panel-card">
          <v-card-title>Downloads rápidos</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col v-for="report in mergedReports" :key="report.name + '-download'" cols="12" md="6" xl="4">
                <v-card variant="outlined" rounded="lg" class="download-card">
                  <div class="download-card__header">
                    <div>
                      <div class="font-weight-medium">{{ report.name }}</div>
                      <div class="text-caption text-medium-emphasis">{{ reportStatusLabel(report) }}</div>
                    </div>
                    <v-icon color="secondary">mdi-file-pdf-box</v-icon>
                  </div>
                  <div class="download-card__actions">
                    <v-btn block color="secondary" prepend-icon="mdi-download" :loading="downloadingReport === report.name" @click="downloadPdf(report)">
                      Baixar PDF
                    </v-btn>
                  </div>
                </v-card>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useStatusBanner } from '../composables/useStatusBanner'

const { loading, errorMessage, setLoading, setError } = useStatusBanner()
const checkingStatus = ref(false)
const reports = ref([])
const statusReports = ref([])
const enabled = ref(false)
const healthy = ref(false)
const selectedReport = ref(null)
const checkedAt = ref('')
const downloadingReport = ref('')

const healthLabel = computed(() => {
  if (!enabled.value) return 'Não configurado'
  return healthy.value ? 'Online' : 'Offline'
})

const healthColor = computed(() => {
  if (!enabled.value) return 'warning'
  return healthy.value ? 'success' : 'warning'
})

const mergedReports = computed(() => {
  const statusMap = Object.fromEntries(statusReports.value.map((item) => [item.name, item]))
  return reports.value.map((report) => ({
    ...report,
    ...(statusMap[report.name] || {}),
  }))
})

const onlineReports = computed(() => mergedReports.value.filter((item) => item.accessible).length)

const checkedAtLabel = computed(() => {
  if (!checkedAt.value) return '—'
  return new Date(checkedAt.value).toLocaleString('pt-BR')
})

function unwrap(response) {
  return response?.data?.data || {}
}

function selectReport(report) {
  selectedReport.value = report
}

function reportStatusLabel(report) {
  if (report.accessible === true) return 'Acessível agora'
  if (report.accessible === false) return 'Falha de acesso'
  return 'Status não verificado'
}

function openNewTab(report) {
  if (!report?.render_url) return
  window.open(report.render_url, '_blank', 'noopener,noreferrer')
}

async function downloadPdf(report) {
  if (!report?.name) return
  downloadingReport.value = report.name
  errorMessage.value = ''
  try {
    const response = await api.get(`/v1/relatorios/ssrs/${encodeURIComponent(report.name)}/pdf`, {
      responseType: 'blob',
    })
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${report.name}.pdf`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || `Erro ao baixar ${report.name}.`
  } finally {
    downloadingReport.value = ''
  }
}

async function loadStatus() {
  if (!enabled.value) return
  checkingStatus.value = true
  errorMessage.value = ''
  try {
    const response = await api.get('/v1/relatorios/ssrs/status')
    const data = unwrap(response)
    statusReports.value = data.reports || []
    checkedAt.value = data.checked_at || ''
    if (selectedReport.value) {
      selectedReport.value = mergedReports.value.find((item) => item.name === selectedReport.value.name) || selectedReport.value
    }
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Erro ao verificar relatórios.'
  } finally {
    checkingStatus.value = false
  }
}

async function loadData() {
  setLoading()
  try {
    const [linksResponse, healthResponse] = await Promise.all([
      api.get('/v1/relatorios/ssrs'),
      api.get('/v1/relatorios/ssrs/health'),
    ])

    const linksData = unwrap(linksResponse)
    const healthData = unwrap(healthResponse)

    enabled.value = Boolean(linksData.enabled)
    healthy.value = Boolean(healthData.reachable)
    reports.value = linksData.reports || []

    if (!selectedReport.value && reports.value.length) {
      selectedReport.value = reports.value[0]
    }

    if (enabled.value) {
      await loadStatus()
    } else {
      statusReports.value = []
      checkedAt.value = ''
      selectedReport.value = null
    }
  } catch (error) {
    setError(error?.response?.data?.detail || error?.message || 'Erro ao carregar catálogo de relatórios.')
  } finally {
    setLoading(false)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.reports-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.reports-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.reports-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.summary-card {
  height: 100%;
  border: 1px solid rgba(208, 208, 208, 0.9);
}

.summary-label {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface));
  opacity: 0.72;
  margin-bottom: 6px;
}

.summary-value {
  font-size: 28px;
  font-weight: 800;
  color: rgb(var(--v-theme-primary));
  line-height: 1.1;
}

.summary-value-small {
  font-size: 15px;
}

.is-good {
  color: rgb(var(--v-theme-success));
}

.is-warning {
  color: rgb(var(--v-theme-warning));
}

.panel-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
}

.preview-shell {
  min-height: 460px;
  height: 68vh;
  border: 1px solid rgba(208, 208, 208, 0.9);
  border-radius: 16px;
  overflow: hidden;
  background: #f8fbff;
}

.preview-frame {
  width: 100%;
  height: 100%;
  border: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 320px;
  padding: 24px;
}

.download-card {
  height: 100%;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-color: rgba(208, 208, 208, 0.9);
}

.download-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.download-card__actions {
  margin-top: auto;
}

@media (max-width: 960px) {
  .preview-shell {
    height: 56vh;
    min-height: 360px;
  }
}

@media (max-width: 600px) {
  .summary-value {
    font-size: 22px;
  }

  .preview-shell {
    height: 52vh;
    min-height: 300px;
  }

  .reports-actions {
    width: 100%;
  }
}
</style>
