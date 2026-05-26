<!-- Dashboard de Relatórios SSRS — ReqSys Enterprise -->
<template>
  <section class="page">
    <!-- ─── Cabeçalho ────────────────────────────────────────────────── -->
    <div class="page-header">
      <div>
        <h1 class="page-title">Relatórios SSRS</h1>
        <div class="muted" style="font-size:13px;margin-top:2px">
          Monitoramento e acesso centralizado dos relatórios publicados
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <v-tooltip text="Verificar status de cada relatório no SSRS" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-radar"
              color="primary"
              :loading="verificando"
              @click="verificarStatus"
            >Verificar</v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Recarregar catálogo" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              icon="mdi-refresh"
              :loading="carregando"
              @click="carregar"
            />
          </template>
        </v-tooltip>
        <v-chip
          size="small"
          :color="healthColor"
          variant="tonal"
          :prepend-icon="healthIcon"
        >{{ healthText }}</v-chip>
      </div>
    </div>

    <!-- ─── Alerta SSRS desabilitado ─────────────────────────────────── -->
    <v-alert
      v-if="!enabled"
      type="warning"
      variant="tonal"
      class="mb-4"
      density="comfortable"
    >
      Integração SSRS desabilitada. Configure <code>SSRS_BASE_URL</code> no backend.
    </v-alert>

    <!-- ─── KPI Cards ─────────────────────────────────────────────────── -->
    <v-row class="mb-2">
      <v-col cols="6" sm="3">
        <v-card class="metric" variant="tonal">
          <div class="metric-head">
            <v-icon size="16" :color="healthColor">{{ healthIcon }}</v-icon>
            <span>SSRS Status</span>
          </div>
          <div class="metric-value-row">
            <span
              class="metric-value"
              :class="healthy ? 'text-green' : 'text-orange'"
            >{{ healthy ? 'Online' : (enabled ? 'Offline' : 'N/A') }}</span>
          </div>
        </v-card>
      </v-col>
      <v-col cols="6" sm="3">
        <v-card class="metric" variant="tonal">
          <div class="metric-head">
            <v-icon size="16" color="amber">mdi-file-chart-outline</v-icon>
            <v-icon size="16" color="primary">mdi-file-chart-outline</v-icon>
            <span>Total Relatórios</span>
          </div>
          <div class="metric-value-row">
            <span class="metric-value">{{ reports.length }}</span>
          </div>
        </v-card>
      </v-col>
      <v-col cols="6" sm="3">
        <v-card class="metric" variant="tonal">
          <div class="metric-head">
            <v-icon size="16" color="green">mdi-check-circle-outline</v-icon>
            <span>Acessíveis</span>
          </div>
          <div class="metric-value-row">
            <span class="metric-value text-green">{{ statusOnline }}</span>
            <span class="muted" style="font-size:11px;margin-left:4px">/ {{ statusReports.length }}</span>
          </div>
        </v-card>
      </v-col>
      <v-col cols="6" sm="3">
        <v-card class="metric" variant="tonal">
          <div class="metric-head">
            <v-icon size="16" color="grey">mdi-clock-outline</v-icon>
            <span>Última Verificação</span>
          </div>
          <div class="metric-value-row">
            <span class="metric-value" style="font-size:14px">{{ ultimaVerificacao }}</span>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- ─── Tabs principais ───────────────────────────────────────────── -->
    <v-tabs v-model="tab" color="primary" class="mb-3">
      <v-tab value="monitor" prepend-icon="mdi-monitor-dashboard">Monitor</v-tab>
      <v-tab value="visualizador" prepend-icon="mdi-eye-outline">Visualizador</v-tab>
      <v-tab value="downloads" prepend-icon="mdi-download-outline">Downloads PDF</v-tab>
    </v-tabs>

    <!-- ─── Tab: Monitor ─────────────────────────────────────────────── -->
    <v-window v-model="tab">
      <v-window-item value="monitor">
        <v-card class="table-card">
          <v-card-text class="pa-0">
            <v-table density="comfortable" hover>
              <thead>
                <tr>
                  <th style="width:44px"></th>
                  <th>Relatório</th>
                  <th class="text-center" style="width:120px">Status</th>
                  <th class="text-center" style="width:80px">HTTP</th>
                  <th class="text-right" style="width:200px">Ações</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!reports.length">
                  <td colspan="5" style="text-align:center;padding:24px;color:var(--muted)">
                    Nenhum relatório disponível
                  </td>
                </tr>
                <tr
                  v-for="row in mergedReports"
                  :key="row.name"
                >
                  <td>
                    <v-icon color="primary" size="18">mdi-file-chart-outline</v-icon>
                  </td>
                  <td>
                    <span style="font-weight:500">{{ row.name }}</span>
                  </td>
                  <td class="text-center">
                    <v-chip
                      v-if="statusChecked"
                      size="x-small"
                      :color="row.accessible ? 'green' : 'red'"
                      variant="tonal"
                    >
                      {{ row.accessible ? 'Online' : 'Offline' }}
                    </v-chip>
                    <v-chip v-else size="x-small" color="grey" variant="tonal">—</v-chip>
                  </td>
                  <td class="text-center">
                    <span style="font-size:12px;color:var(--muted)">
                      {{ row.status_code || '—' }}
                    </span>
                  </td>
                  <td class="text-right">
                    <div style="display:flex;justify-content:flex-end;gap:4px">
                      <v-tooltip text="Visualizar no painel" location="top">
                        <template #activator="{ props }">
                          <v-btn
                            v-bind="props"
                            size="x-small"
                            variant="tonal"
                            icon="mdi-eye-outline"
                            color="primary"
                            @click="abrirVisualizador(row)"
                          />
                        </template>
                      </v-tooltip>
                      <v-tooltip text="Abrir em nova guia" location="top">
                        <template #activator="{ props }">
                          <v-btn
                            v-bind="props"
                            size="x-small"
                            variant="tonal"
                            icon="mdi-open-in-new"
                            @click="abrirNovaGuia(row)"
                          />
                        </template>
                      </v-tooltip>
                      <v-tooltip text="Baixar PDF" location="top">
                        <template #activator="{ props }">
                          <v-btn
                            v-bind="props"
                            size="x-small"
                            variant="tonal"
                            icon="mdi-file-pdf-box"
                            color="red"
                            :loading="downloadingPdf === row.name"
                            @click="baixarPdf(row)"
                          />
                        </template>
                      </v-tooltip>
                    </div>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>

        <v-expand-transition>
          <div v-if="statusChecked && statusOffline > 0" class="mt-3">
            <v-alert type="warning" variant="tonal" density="comfortable">
              <strong>{{ statusOffline }}</strong> relatório(s) com problema de acesso.
              Verifique se o SSRS está disponível e as credenciais estão configuradas.
            </v-alert>
          </div>
        </v-expand-transition>

        <div v-if="statusChecked" class="muted mt-2" style="font-size:12px;text-align:right">
          Verificado em {{ ultimaVerificacao }}
          <v-btn size="x-small" variant="text" :loading="verificando" @click="verificarStatus">re-verificar</v-btn>
        </div>
      </v-window-item>

      <!-- ─── Tab: Visualizador ──────────────────────────────────────── -->
      <v-window-item value="visualizador">
        <v-row>
          <v-col cols="12" md="3">
            <v-card class="table-card">
              <v-card-title class="py-2 px-4" style="font-size:14px">Relatórios</v-card-title>
              <v-divider />
              <v-list density="compact" nav>
                <v-list-item
                  v-for="r in reports"
                  :key="r.name"
                  :title="r.name"
                  prepend-icon="mdi-file-chart-outline"
                  :active="selecionado && selecionado.name === r.name"
                  active-color="amber"
                  rounded="lg"
                  @click="selecionado = r"
                />
                <v-list-item v-if="!reports.length" title="Nenhum relatório" />
              </v-list>
            </v-card>
          </v-col>

          <v-col cols="12" md="9">
            <v-card class="table-card">
              <v-card-title
                class="py-3 px-4"
                style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap"
              >
                <span>{{ selecionado ? selecionado.name : 'Selecione um relatório' }}</span>
                <div v-if="selecionado" style="display:flex;gap:6px">
                  <v-btn
                    size="small"
                    variant="outlined"
                    prepend-icon="mdi-file-pdf-box"
                      color="secondary"
                    :loading="downloadingPdf === (selecionado && selecionado.name)"
                    @click="baixarPdf(selecionado)"
                  >Download PDF</v-btn>
                  <v-btn
                    size="small"
                      color="primary"
                    variant="flat"
                    prepend-icon="mdi-open-in-new"
                    @click="abrirNovaGuia(selecionado)"
                  >Nova guia</v-btn>
                </div>
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-2">
                <div
                  v-if="selecionado"
                  style="height:72vh;min-height:420px;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:#f8f8f8"
                >
                  <iframe
                    :src="selecionado.render_url"
                    :title="selecionado.name"
                    style="width:100%;height:100%;border:0"
                  />
                </div>
                <div v-else class="empty-state" style="padding:48px 0">
                  <v-icon size="48" color="grey">mdi-file-chart-outline</v-icon>
                  <div class="empty-sub mt-2">Selecione um relatório na lista à esquerda</div>
                </div>
                <v-alert
                  v-if="selecionado"
                  type="info"
                  variant="tonal"
                  density="compact"
                  class="mt-2"
                  style="font-size:12px"
                >
                  Se o preview não carregar (X-Frame-Options), use "Nova guia" ou "Download PDF".
                </v-alert>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <!-- ─── Tab: Downloads ────────────────────────────────────────── -->
      <v-window-item value="downloads">
        <v-card class="table-card">
          <v-card-title class="py-3 px-4" style="font-size:15px">
            <v-icon class="mr-2" color="secondary">mdi-file-pdf-box</v-icon>
            Download de Relatórios em PDF
          </v-card-title>
          <v-card-subtitle class="px-4 pb-2" style="font-size:12px">
            PDF gerado via SSRS pelo backend. Autenticação Windows gerenciada automaticamente.
          </v-card-subtitle>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col
                v-for="r in mergedReports"
                :key="r.name"
                cols="12"
                sm="6"
                md="4"
              >
                <v-card
                  class="pa-4 d-flex flex-column"
                  :class="{ 'pdf-card-offline': statusChecked && !r.accessible }"
                  variant="outlined"
                  style="border-radius:12px;gap:12px;min-height:130px"
                >
                  <div style="display:flex;align-items:center;gap:10px">
                    <v-icon color="secondary" size="28">mdi-file-pdf-box</v-icon>
                    <div>
                      <div style="font-weight:600;font-size:13px">{{ r.name }}</div>
                      <div v-if="statusChecked" style="font-size:11px;margin-top:2px">
                        <v-chip
                          size="x-small"
                          :color="r.accessible ? 'green' : 'red'"
                          variant="tonal"
                        >{{ r.accessible ? 'Acessível' : 'Inacessível' }}</v-chip>
                      </div>
                    </div>
                  </div>
                  <div style="display:flex;gap:8px;margin-top:auto">
                    <v-btn
                      size="small"
                      color="secondary"
                      variant="flat"
                      prepend-icon="mdi-download"
                      :loading="downloadingPdf === r.name"
                      :disabled="!enabled"
                      style="flex:1"
                      @click="baixarPdf(r)"
                    >PDF</v-btn>
                    <v-btn
                      size="small"
                      variant="outlined"
                      icon="mdi-open-in-new"
                      :disabled="!enabled"
                      @click="abrirNovaGuia(r)"
                    />
                  </div>
                </v-card>
              </v-col>
            </v-row>

            <v-alert
              v-if="erroDownload"
              type="error"
              variant="tonal"
              density="comfortable"
              class="mt-4"
              closable
              @click:close="erroDownload = null"
            >
              {{ erroDownload }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </section>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { relatoriosService } from '../services/relatorios'

// ─── Estado ──────────────────────────────────────────────────────────────────
const carregando = ref(false)
const verificando = ref(false)
const reports = ref([])
const statusReports = ref([])
const statusChecked = ref(false)
const checkedAt = ref(null)
const enabled = ref(false)
const healthy = ref(false)
const selecionado = ref(null)
const tab = ref('monitor')
const downloadingPdf = ref(null)
const erroDownload = ref(null)

// ─── Computed ─────────────────────────────────────────────────────────────────
const healthText = computed(() => {
  if (!enabled.value) return 'SSRS não configurado'
  return healthy.value ? 'SSRS online' : 'SSRS offline'
})

const healthColor = computed(() => {
  if (!enabled.value) return 'grey'
  return healthy.value ? 'green' : 'orange'
})

const healthIcon = computed(() => {
  if (!enabled.value) return 'mdi-cloud-off-outline'
  return healthy.value ? 'mdi-cloud-check-outline' : 'mdi-cloud-alert-outline'
})

const statusOnline = computed(() => statusReports.value.filter(r => r.accessible).length)
const statusOffline = computed(() => statusReports.value.filter(r => !r.accessible).length)

const ultimaVerificacao = computed(() => {
  if (!checkedAt.value) return '—'
  return new Date(checkedAt.value).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
})

const mergedReports = computed(() => {
  const statusMap = Object.fromEntries(statusReports.value.map(r => [r.name, r]))
  return reports.value.map(r => ({
    ...r,
    ...(statusMap[r.name] || {}),
  }))
})

// ─── Ações ────────────────────────────────────────────────────────────────────
function abrirNovaGuia(report) {
  const url = report && report.render_url
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

function abrirVisualizador(report) {
  selecionado.value = report
  tab.value = 'visualizador'
}

async function baixarPdf(report) {
  if (!report || !report.name) return
  erroDownload.value = null
  downloadingPdf.value = report.name
  try {
    await relatoriosService.downloadPdf(report.name)
  } catch (err) {
    const msg = (err && err.response && err.response.data && err.response.data.detail)
      || (err && err.message)
      || 'Erro ao baixar PDF'
    erroDownload.value = 'Erro ao baixar "' + report.name + '": ' + msg
  } finally {
    downloadingPdf.value = null
  }
}

async function verificarStatus() {
  if (!enabled.value) return
  verificando.value = true
  try {
    const resp = await relatoriosService.status()
    const data = (resp.data && resp.data.data) || {}
    statusReports.value = data.reports || []
    checkedAt.value = data.checked_at || new Date().toISOString()
    statusChecked.value = true
  } finally {
    verificando.value = false
  }
}

async function carregar() {
  carregando.value = true
  try {
    const [linksResp, healthResp] = await Promise.all([
      relatoriosService.listar(),
      relatoriosService.health(),
    ])
    const linksData = (linksResp.data && linksResp.data.data) || {}
    const healthData = (healthResp.data && healthResp.data.data) || {}

    enabled.value = Boolean(linksData.enabled)
    reports.value = linksData.reports || []
    healthy.value = Boolean(healthData.reachable)

    if (!selecionado.value && reports.value.length) {
      selecionado.value = reports.value[0]
    }
  } finally {
    carregando.value = false
  }
}

onMounted(() => {
  carregar().then(() => {
    if (enabled.value) verificarStatus()
  })
})
</script>

<style scoped>
.metric {
  padding: 14px 16px 12px;
  border-radius: 12px;
  background: var(--card-alt, #e8f1fa);
  min-height: 76px;
}

.metric-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted, #6b6b6b);
  margin-bottom: 6px;
}

.metric-value-row {
  display: flex;
  align-items: baseline;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}

.text-green { color: #2e7d32; }
.text-orange { color: #f57c00; }

.table-card {
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--border, #d0d0d0);
}

.pdf-card-offline {
  opacity: 0.72;
  background: #f8fbff;
}

@media (max-width: 600px) {
  .metric-value { font-size: 18px; }
}
</style>