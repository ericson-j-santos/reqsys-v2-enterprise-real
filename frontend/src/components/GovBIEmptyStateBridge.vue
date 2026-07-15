<template>
  <v-dialog v-model="visible" max-width="720" persistent data-testid="govbi-empty-state-dialog">
    <v-card>
      <v-card-text class="pa-4 pa-sm-6">
        <GovBIEmptyState :reason="reason" @reformulate="reformulate" @retry="retry" />
      </v-card-text>
      <v-card-actions class="justify-end">
        <v-btn variant="text" aria-label="Fechar orientação de consulta sem resultados" @click="close">Fechar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import GovBIEmptyState from './GovBIEmptyState.vue'

export const GOVBI_EMPTY_EVENT = 'reqsys:govbi-empty-result'
const visible = ref(false)
const reason = ref('Não existem linhas compatíveis com a consulta atual.')
let retryCallback = null

function close() {
  visible.value = false
  retryCallback = null
}

function reformulate() {
  close()
  requestAnimationFrame(() => {
    const field = document.querySelector('[data-testid="route-govbi-ia"] textarea, textarea[aria-label*="pergunta" i]')
    field?.focus()
  })
}

function retry() {
  const callback = retryCallback
  close()
  callback?.()
}

function onEmptyResult(event) {
  const detail = event?.detail || {}
  reason.value = detail.reason || 'A consulta foi concluída, mas nenhum registro corresponde aos filtros informados.'
  retryCallback = typeof detail.retry === 'function' ? detail.retry : null
  visible.value = true
}

onMounted(() => window.addEventListener(GOVBI_EMPTY_EVENT, onEmptyResult))
onBeforeUnmount(() => window.removeEventListener(GOVBI_EMPTY_EVENT, onEmptyResult))
</script>
