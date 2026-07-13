<template>
  <a class="req-skip-link" href="#reqsys-main-content" @click="prepareMainContent">
    Ir para o conteúdo principal
  </a>

  <p class="req-sr-only" aria-live="polite" aria-atomic="true" data-testid="route-announcement">
    {{ routeAnnouncement }}
  </p>

  <v-alert
    v-if="!online"
    class="req-connectivity-alert"
    type="warning"
    variant="tonal"
    border="start"
    density="compact"
    role="status"
    aria-live="assertive"
    data-testid="offline-alert"
  >
    <strong>Conexão indisponível.</strong>
    Algumas informações podem estar desatualizadas. O ReqSys retomará as consultas quando a conexão voltar.
  </v-alert>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine)

const routeAnnouncement = computed(() => {
  const title = route.meta?.title || route.name || 'Tela carregada'
  return `Navegação concluída: ${String(title)}.`
})

function resolveMainContent() {
  const main = document.querySelector('.req-main')
  if (!main) return null
  main.id = 'reqsys-main-content'
  main.setAttribute('tabindex', '-1')
  main.setAttribute('aria-label', 'Conteúdo principal')
  return main
}

function prepareMainContent() {
  resolveMainContent()
}

async function focusMainContent() {
  await nextTick()
  const main = resolveMainContent()
  main?.focus({ preventScroll: true })
}

function updateConnectivity() {
  online.value = navigator.onLine
}

onMounted(() => {
  resolveMainContent()
  window.addEventListener('online', updateConnectivity)
  window.addEventListener('offline', updateConnectivity)
})

onBeforeUnmount(() => {
  window.removeEventListener('online', updateConnectivity)
  window.removeEventListener('offline', updateConnectivity)
})

watch(() => route.fullPath, focusMainContent)
</script>

<style scoped>
.req-skip-link {
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 10000;
  transform: translateY(-160%);
  padding: 10px 14px;
  border-radius: 8px;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  font-weight: 700;
  text-decoration: none;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
  transition: transform 120ms ease-out;
}

.req-skip-link:focus {
  transform: translateY(0);
  outline: 3px solid rgb(var(--v-theme-warning));
  outline-offset: 2px;
}

.req-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.req-connectivity-alert {
  position: fixed;
  top: 12px;
  right: 12px;
  z-index: 9999;
  width: min(440px, calc(100vw - 24px));
}

@media (prefers-reduced-motion: reduce) {
  .req-skip-link { transition: none; }
}
</style>
