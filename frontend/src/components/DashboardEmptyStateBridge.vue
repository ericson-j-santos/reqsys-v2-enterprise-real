<template>
  <v-dialog v-model="visible" max-width="720" persistent data-testid="dashboard-empty-state-dialog">
    <v-card>
      <v-card-text class="pa-4 pa-sm-6">
        <OperationalDashboardEmptyState
          :context="context"
          :reason="reason"
          @refresh="refresh"
          @clear-filters="clearFilters"
        />
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn variant="text" aria-label="Fechar orientação de dashboard sem dados" @click="close">Fechar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import OperationalDashboardEmptyState from './OperationalDashboardEmptyState.vue'
import { DASHBOARD_EMPTY_EVENT } from '../services/dashboardEmptyStateIntegration'

const visible = ref(false)
const context = ref('operational-dashboard')
const reason = ref('Nenhum registro atende aos filtros selecionados.')
let retryCallback = null

function close() {
  visible.value = false
  retryCallback = null
}
function refresh() {
  const callback = retryCallback
  close()
  callback?.()
}
function clearFilters() {
  close()
  window.dispatchEvent(new CustomEvent('reqsys:dashboard-clear-filters', { detail: { context: context.value } }))
}
function onEmpty(event) {
  const detail = event?.detail || {}
  context.value = detail.context || 'operational-dashboard'
  reason.value = detail.reason || 'Nenhum registro atende ao período ou aos filtros atuais.'
  retryCallback = typeof detail.retry === 'function' ? detail.retry : null
  visible.value = true
}

onMounted(() => window.addEventListener(DASHBOARD_EMPTY_EVENT, onEmpty))
onBeforeUnmount(() => window.removeEventListener(DASHBOARD_EMPTY_EVENT, onEmpty))
</script>
