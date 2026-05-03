<template>
  <section class="page">
    <div class="page-header">
      <h1 class="page-title">Relatórios SSRS</h1>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <v-tooltip text="Recarrega catálogo e status do SSRS" location="top">
          <template #activator="{ props }">
            <v-btn v-bind="props" size="small" variant="outlined" prepend-icon="mdi-refresh" :loading="carregando" @click="carregar">Atualizar</v-btn>
          </template>
        </v-tooltip>
        <v-chip size="small" :color="healthColor" variant="tonal">{{ healthText }}</v-chip>
      </div>
    </div>

    <v-alert v-if="!enabled" type="warning" variant="tonal" class="mb-4">
      Integração SSRS desabilitada. Configure SSRS_BASE_URL no backend.
    </v-alert>

    <v-row>
      <v-col cols="12" md="5">
        <v-card class="table-card">
          <v-card-title class="py-3 px-4">Catálogo de Relatórios</v-card-title>
          <v-divider />
          <v-list>
            <v-list-item
              v-for="report in reports"
              :key="report.name"
              :title="report.name"
              prepend-icon="mdi-file-chart-outline"
              @click="selecionar(report)"
            >
              <template #append>
                <v-tooltip text="Abrir relatório em nova guia" location="top">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      size="x-small"
                      variant="text"
                      icon="mdi-open-in-new"
                      @click.stop="abrirRelatorio(report)"
                    />
                  </template>
                </v-tooltip>
              </template>
            </v-list-item>
            <v-list-item v-if="!reports.length" title="Nenhum relatório disponível" />
          </v-list>
        </v-card>
      </v-col>

      <v-col cols="12" md="7">
        <v-card class="table-card">
          <v-card-title class="py-3 px-4" style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
            <span>{{ selecionado?.name || 'Visualizador SSRS' }}</span>
            <v-btn v-if="selecionado" size="small" color="amber" variant="flat" @click="abrirRelatorio(selecionado)">Abrir em nova guia</v-btn>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <div v-if="selecionado" style="height:70vh;min-height:420px;border:1px solid var(--border);border-radius:10px;overflow:hidden">
              <iframe :src="selecionado.render_url" title="SSRS" style="width:100%;height:100%;border:0" />
            </div>
            <v-alert v-if="selecionado" type="info" variant="tonal" density="comfortable" class="mt-3">
              Se o preview não carregar por política do navegador/SSRS, use "Abrir em nova guia".
            </v-alert>
            <div v-else class="empty-state" style="padding:32px 0">
              <v-icon size="40" color="grey">mdi-file-chart-outline</v-icon>
              <div class="empty-sub">Selecione um relatório para visualizar</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { api } from '../services/api'

const carregando = ref(false)
const reports = ref([])
const selecionado = ref(null)
const enabled = ref(false)
const healthy = ref(false)

const healthText = computed(() => {
  if (!enabled.value) return 'SSRS não configurado'
  return healthy.value ? 'SSRS online' : 'SSRS sem resposta'
})

const healthColor = computed(() => {
  if (!enabled.value) return 'grey'
  return healthy.value ? 'green' : 'orange'
})

function selecionar(report) {
  selecionado.value = report
}

function abrirRelatorio(report) {
  const url = report?.render_url
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function carregar() {
  carregando.value = true
  try {
    const [linksResp, healthResp] = await Promise.all([
      api.get('/v1/relatorios/ssrs'),
      api.get('/v1/relatorios/ssrs/health'),
    ])
    const linksData = linksResp.data?.data || {}
    const healthData = healthResp.data?.data || {}

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

onMounted(carregar)
</script>
