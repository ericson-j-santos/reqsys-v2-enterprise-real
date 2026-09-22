<template>
  <div class="journey-feedback" aria-live="polite" aria-atomic="true">
    <GovBIEmptyStateBridge />

    <v-progress-linear
      v-if="state.type === 'loading'"
      indeterminate
      color="primary"
      height="4"
      data-testid="journey-loading"
    />

    <v-snackbar
      v-model="visible"
      :timeout="state.persistent ? -1 : 5000"
      location="bottom right"
      :color="snackbarColor"
      role="status"
      data-testid="journey-feedback"
    >
      <div class="d-flex align-center gap-2">
        <v-icon :icon="icon" aria-hidden="true" />
        <span>{{ state.message }}</span>
      </div>

      <template #actions>
        <v-btn
          v-if="state.type === 'error' && typeof state.retry === 'function'"
          variant="text"
          data-testid="journey-retry"
          @click="retry"
        >
          Tentar novamente
        </v-btn>
        <v-btn variant="text" aria-label="Fechar mensagem" @click="clear">Fechar</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { EVENT_NAME } from '../services/userJourneyFeedback'
import GovBIEmptyStateBridge from './GovBIEmptyStateBridge.vue'

const visible = ref(false)
const state = reactive({ type: 'clear', message: '', persistent: false, retry: null })

const snackbarColor = computed(() => ({ success: 'success', error: 'error', loading: 'info' }[state.type] || 'info'))
const icon = computed(() => ({ success: 'mdi-check-circle-outline', error: 'mdi-alert-circle-outline', loading: 'mdi-progress-clock' }[state.type] || 'mdi-information-outline'))

function clear() {
  visible.value = false
  Object.assign(state, { type: 'clear', message: '', persistent: false, retry: null })
}

function retry() {
  const callback = state.retry
  clear()
  callback?.()
}

function onFeedback(event) {
  const detail = event?.detail || {}
  if (detail.type === 'clear') {
    clear()
    return
  }
  Object.assign(state, {
    type: detail.type || 'info',
    message: detail.message || 'Atualização concluída.',
    persistent: Boolean(detail.persistent),
    retry: typeof detail.retry === 'function' ? detail.retry : null,
  })
  visible.value = true
}

onMounted(() => window.addEventListener(EVENT_NAME, onFeedback))
onBeforeUnmount(() => window.removeEventListener(EVENT_NAME, onFeedback))
</script>

<style scoped>
.journey-feedback :deep(.v-snackbar__wrapper) {
  max-width: min(520px, calc(100vw - 24px));
}

@media (prefers-reduced-motion: reduce) {
  .journey-feedback :deep(*) { scroll-behavior: auto !important; }
}
</style>
