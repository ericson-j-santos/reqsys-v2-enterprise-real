<template>
  <div class="audit-page">
    <div class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Auditoria</div>
        <div class="text-body-2 text-medium-emphasis">
          Linha do tempo, filtros e eventos de configuração para rastreabilidade operacional.
        </div>
      </div>

      <div class="page-actions">
        <v-select
          v-model="selectedEntity"
          :items="entityOptions"
          label="Entidade"
          variant="outlined"
          density="compact"
          hide-details
          class="filter-select"
        />
        <v-btn variant="outlined" prepend-icon="mdi-refresh" :loading="loading" @click="loadAudit">
          Atualizar
        </v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" closable @click:close="errorMessage = ''">
      {{ errorMessage }}
    </v-alert>

    <v-alert v-if="loading" type="info" variant="tonal" class="mb-2" icon="mdi-loading mdi-spin">
      Atualizando eventos de auditoria...
    </v-alert>

    <v-row>
      <v-col cols="12" md="4">
        <v-card rounded="xl" elevation="1" class="panel-card h-100">
          <v-card-title>Resumo</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col cols="6" md="12" xl="6">
                <div class="summary-item">
                  <div class="summary-label">Total carregado</div>
                  <div class="summary-value">{{ events.length }}</div>
                </div>
              </v-col>
              <v-col cols="6" md="12" xl="6">
                <div class="summary-item">
                  <div class="summary-label">Infraestrutura</div>
                  <div class="summary-value">{{ infraEvents.length }}</div>
                </div>
              </v-col>
              <v-col cols="6" md="12" xl="6">
                <div class="summary-item">
                  <div class="summary-label">Entidade ativa</div>
                  <div class="summary-value summary-value-small">{{ selectedEntity || 'Todas' }}</div>
                </div>
              </v-col>
              <v-col cols="6" md="12" xl="6">
                <div class="summary-item">
                  <div class="summary-label">Último evento</div>
                  <div class="summary-value summary-value-small">{{ latestEventDate }}</div>
                </div>
              </v-col>
            </v-row>
            <v-alert type="info" variant="tonal" density="comfortable" class="mt-2">
              Os registros exibem correlation_id, entidade e payload mínimo para análise segura.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="8">
        <v-card rounded="xl" elevation="1" class="panel-card mb-4">
          <v-card-title>Eventos recentes</v-card-title>
          <v-divider />
          <v-card-text>
            <v-timeline density="compact" side="end">
              <v-timeline-item v-for="event in events" :key="event.id" dot-color="primary">
                <div class="event-row">
                  <strong>{{ event.acao }}</strong>
                  <v-chip size="x-small" variant="outlined">{{ event.entidade }}</v-chip>
                  <v-chip size="x-small" variant="outlined">{{ event.correlation_id || 'sem correlation' }}</v-chip>
                </div>
                <div class="text-body-2 text-medium-emphasis mt-1">
                  {{ formatDate(event.criado_em) }} · {{ event.usuario || 'sistema' }}
                </div>
                <div class="text-caption text-medium-emphasis mt-1">{{ summarizePayload(event.payload_minimo) }}</div>
              </v-timeline-item>
              <v-timeline-item v-if="!events.length" dot-color="grey">
                <div class="text-medium-emphasis">Nenhum evento disponível.</div>
              </v-timeline-item>
            </v-timeline>
          </v-card-text>
        </v-card>

        <v-card rounded="xl" elevation="1" class="panel-card">
          <v-card-title>Configuração de infraestrutura</v-card-title>
          <v-divider />
          <v-card-text class="pa-0">
            <v-table density="comfortable">
              <thead>
                <tr>
                  <th>Ação</th>
                  <th>Usuário</th>
                  <th>Correlation</th>
                  <th>Quando</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="event in infraEvents" :key="`infra-${event.id}`">
                  <td>{{ event.acao }}</td>
                  <td>{{ event.usuario || 'sistema' }}</td>
                  <td>{{ event.correlation_id || '—' }}</td>
                  <td>{{ formatDate(event.criado_em) }}</td>
                </tr>
                <tr v-if="!infraEvents.length">
                  <td colspan="4" class="empty-cell">Nenhum evento de infraestrutura encontrado.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
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
const events = ref([])
const infraEvents = ref([])
const selectedEntity = ref(null)

const entityOptions = ['infra', 'requisito', 'pipeline', 'auth', 'auditoria']

const latestEventDate = computed(() => {
  if (!events.value.length) return '—'
  return formatDate(events.value[0].criado_em)
})

function formatDate(raw) {
  if (!raw) return '—'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('pt-BR')
}

function summarizePayload(payload) {
  if (!payload) return 'Sem payload mínimo.'
  if (typeof payload === 'string') return payload
  const serialized = JSON.stringify(payload)
  return serialized.length > 180 ? `${serialized.slice(0, 180)}...` : serialized
}

async function loadAudit() {
  setLoading()
  try {
    const params = new URLSearchParams({ limit: '30', offset: '0' })
    if (selectedEntity.value) params.set('entidade', selectedEntity.value)

    const [eventsResponse, infraResponse] = await Promise.all([
      api.get(`/v1/auditoria/eventos?${params.toString()}`),
      api.get('/v1/auditoria/eventos/config-infra?limit=12'),
    ])

    events.value = eventsResponse?.data?.data?.dados || []
    infraEvents.value = infraResponse?.data?.data?.config_historico || []
  } catch (error) {
    setError(error?.response?.data?.detail || error?.message || 'Erro ao carregar eventos de auditoria.')
  } finally {
    setLoading(false)
  }
}

watch(selectedEntity, loadAudit)
onMounted(loadAudit)
</script>

<style scoped>
.audit-page {
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

.filter-select {
  min-width: 160px;
}

.panel-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
}

.summary-item {
  border: 1px solid rgba(208, 208, 208, 0.9);
  border-radius: 16px;
  padding: 14px;
  background: #f8fbff;
  height: 100%;
}

.summary-label {
  font-size: 12px;
  color: rgba(51, 51, 51, 0.72);
  margin-bottom: 6px;
}

.summary-value {
  font-size: 24px;
  font-weight: 800;
  color: rgb(var(--v-theme-primary));
}

.summary-value-small {
  font-size: 15px;
}

.event-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.empty-cell {
  text-align: center;
  color: rgba(51, 51, 51, 0.7);
  padding: 18px;
}

@media (max-width: 600px) {
  .summary-value {
    font-size: 20px;
  }

  .filter-select {
    min-width: 100%;
  }
}
</style>
